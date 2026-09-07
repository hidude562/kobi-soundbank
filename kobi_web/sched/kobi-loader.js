/**
 * kobi-loader — fetch a bank one note at a time, in the order a song needs them.
 *
 * A *slice* is one note of one program: a byte range of the program's packed Ogg (from
 * slices.json) that decodes on its own (kobi-ogg.js).  The loader keeps three things per slice —
 * the compressed bytes, a decoded AudioBuffer, and the times a song will use it — and moves slices
 * through fetch -> decode -> ready in priority order:
 *
 *   priority = seconds until the slice is next needed
 *              - FIRST     if its (pitched) program has nothing loaded yet: one sample per instrument
 *                          first, so every later note at least has something to transpose from
 *              - NEIGHBOUR if nothing loaded sits within a fifth of its key
 *              + LAYER     if its key already has another velocity layer loaded (that layer can stand in)
 *
 * Compressed bytes are cheap and kept; decoded PCM is the expensive part (float32 at the context
 * rate: ~0.4 MB per second stereo), so slices are decoded only when due within `decodeAhead`
 * seconds and the decoded set is capped at `maxDecodedBytes`, evicting what is needed furthest
 * away.  Byte ranges go through a sparse per-file cache, so neighbouring notes that share a page
 * do not fetch it twice, and a server that ignores Range (python -m http.server) simply yields the
 * whole file once, which the cache then slices locally.
 */
import { parseSfz, regionParams, dbToGain } from '../kobi-player.js';
import { spliceOgg, lastGranule } from './kobi-ogg.js';

export const PRIORITY = { FIRST: 60, NEIGHBOUR: 10, LAYER: 20, NEIGHBOUR_SEMITONES: 7 };

export class SliceLoader {
  /**
   * @param {string} bankUrl folder holding GM/manifest.json
   * @param {AudioContext|OfflineAudioContext} ctx
   * @param {{parallel?: number, decodeAhead?: number, maxDecodedBytes?: number, rng?: () => number}} [opts]
   */
  constructor(bankUrl, ctx, opts = {}) {
    this.url = new URL(bankUrl.endsWith('/') ? bankUrl : bankUrl + '/', typeof location !== 'undefined' ? location.href : 'file:///');
    this.ctx = ctx;
    this.parallel = opts.parallel ?? 4;
    this.decodeAhead = opts.decodeAhead ?? 8;
    this.maxDecodedBytes = opts.maxDecodedBytes ?? 48e6;
    this.rng = opts.rng || Math.random;
    this.time = 0;                       // playback position the priorities are measured from
    this.programs = new Map();           // id -> Promise<Program>
    this.loaded = new Map();             // id -> Program
    this.files = new Map();              // url -> { header: Uint8Array|null, ranges: [{a, b, u8}], whole: boolean }
    this.slices = new Set();             // slices with registered uses
    this.fetching = 0;
    this.decoding = 0;
    this.pendingBytes = 0;               // estimated size of decodes in flight
    this.rangeSupported = null;          // learned from the first 206 / 200
    this.stats = { fetched: 0, bytes: 0, decoded: 0, decodedBytes: 0, evicted: 0, requests: 0 };
    this._manifest = null;
    this.onchange = null;                // () => void, after any state change (for a UI)
  }

  async manifest() {
    if (!this._manifest) {
      const r = await fetch(new URL('GM/manifest.json', this.url));
      if (!r.ok) throw new Error(`manifest: ${r.status}`);
      this._manifest = await r.json();
    }
    return this._manifest;
  }

  static id(program) { return program === 'drums' ? 'drums' : String(program); }

  /** SFZ + slice index of a program (a few KB); no audio.  Cached. */
  program(program) {
    const id = SliceLoader.id(program);
    if (!this.programs.has(id)) {
      const p = this._program(id).then((prog) => { this.loaded.set(id, prog); return prog; });
      p.catch(() => this.programs.delete(id));
      this.programs.set(id, p);
    }
    return this.programs.get(id);
  }

  async _program(id) {
    const man = await this.manifest();
    const entry = id === 'drums' ? man.drums : man.programs[id];
    if (!entry) throw new Error(`no program ${id} in the bank`);
    const sfzUrl = new URL('GM/' + encodeURIComponent(entry.file), this.url);
    const text = await (await fetch(sfzUrl)).text();
    const { control, global, regions } = parseSfz(text);
    const base = new URL((control.default_path || './').replace(/\\/g, '/'), sfzUrl);
    const index = await (await fetch(new URL('slices.json', base))).json();
    const params = regions.map((ops) => regionParams(ops, control)).filter((p) => p.sample && p.end !== null);
    const slices = new Map();
    for (const p of params) {
      const key = p.sample + '@' + p.offset;
      let s = slices.get(key);
      if (!s) {
        const file = index[p.sample];
        const note = file && file.notes[String(p.offset)];
        if (!note) continue;                                       // not indexed: unplayable here
        s = { key, program: id, url: new URL(encodeURIComponent(p.sample), base).href, header: file.header,
              rate: file.rate, channels: file.channels, b0: note[0], b1: note[1], granule: note[2], granuleStart: note[3] ?? null,
              offset: p.offset, end: p.end, keycenter: p.keycenter, lovel: p.lovel, hivel: p.hivel,
              keytrack: p.keytrack, regions: [], uses: [], u8: null, buffer: null, firstAbs: 0,
              state: 'idle', active: 0, lastUse: -Infinity };
        slices.set(key, s);
      }
      p.slice = s;
      s.regions.push(p);
    }
    const pitched = id !== 'drums' && params.some((p) => p.keytrack > 0 && p.lokey !== 0 && p.hikey !== 127);
    return { id, name: entry.name, globalDb: Number(global.volume || 0), regions: params, slices, pitched,
             hd72: Number(control.set_hdcc72 || 0), _seq: 0 };
  }

  /** Regions a key / velocity would trigger, round robins resolved (seeded when `rng` is given). */
  regionsFor(prog, key, vel) {
    const r = this.rng();
    const hits = prog.regions.filter((p) => p.slice && key >= p.lokey && key <= p.hikey && vel >= p.lovel && vel <= p.hivel &&
      r >= p.lorand && (r < p.hirand || p.hirand >= 1));
    if (hits.some((p) => p.seqLength > 1)) {
      prog._seq = (prog._seq % Math.max(...hits.map((p) => p.seqLength))) + 1;
      return hits.filter((p) => p.seqLength === 1 || p.seqPosition === prog._seq);
    }
    return hits;
  }

  /** Tell the loader a slice is needed at `t` (song seconds).  Registering is what puts it in the queue. */
  want(slice, t) {
    slice.uses.push(t);
    slice._sorted = false;
    this.slices.add(slice);
  }

  /** Forget every registered use (a new song). */
  clearUses() {
    for (const s of this.slices) { s.uses = []; }
    this.slices.clear();
  }

  nextUse(slice, now = this.time) {
    if (!slice._sorted) { slice.uses.sort((a, b) => a - b); slice._sorted = true; }
    const u = slice.uses;
    let lo = 0, hi = u.length;                                       // first use >= now - 0.05
    while (lo < hi) { const mid = (lo + hi) >> 1; if (u[mid] < now - 0.05) lo = mid + 1; else hi = mid; }
    return lo < u.length ? u[lo] : Infinity;
  }

  priority(slice, now = this.time) {
    const dt = this.nextUse(slice, now) - now;
    if (dt === Infinity) return Infinity;
    const prog = this.loaded.get(slice.program);
    let p = dt;
    if (prog && prog.pitched) {
      let any = false, near = false, layer = false;
      for (const s of prog.slices.values()) {
        if (s === slice || (s.state !== 'fetched' && s.state !== 'ready' && s.state !== 'decoding')) continue;
        any = true;
        if (Math.abs(s.keycenter - slice.keycenter) <= PRIORITY.NEIGHBOUR_SEMITONES) near = true;
        if (s.keycenter === slice.keycenter) layer = true;
      }
      if (!any) p -= PRIORITY.FIRST;
      else if (!near) p -= PRIORITY.NEIGHBOUR;
      if (layer) p += PRIORITY.LAYER;
    }
    return p;
  }

  /** Playback moved: re-rank and keep the pipes full. */
  setTime(t) {
    this.time = t;
    this.pump();
  }

  pump() {
    while (this.fetching < this.parallel) {
      let best = null, bp = Infinity;
      for (const s of this.slices) {
        if (s.state !== 'idle') continue;
        const p = this.priority(s);
        if (p < bp) { bp = p; best = s; }
      }
      if (!best) break;
      this._fetch(best);
    }
    this._decodePump();
  }

  async _fetch(slice) {
    slice.state = 'fetching';
    this.fetching++;
    try {
      const f = this._file(slice.url);
      if (!f.header) f.header = await this._bytes(slice.url, 0, slice.header);
      slice.u8 = await this._bytes(slice.url, slice.b0, slice.b1);
      slice.state = 'fetched';
      this.stats.fetched++;
    } catch (e) {
      slice.state = 'failed';
      slice.error = e;
    } finally {
      this.fetching--;
      this.onchange?.();
      this.pump();
    }
  }

  _file(url) {
    let f = this.files.get(url);
    if (!f) { f = { header: null, ranges: [], whole: false }; this.files.set(url, f); }
    return f;
  }

  /** Bytes [a, b) of a file, from the sparse cache or the network. */
  async _bytes(url, a, b) {
    const f = this._file(url);
    const hit = f.ranges.find((r) => r.a <= a && r.b >= b);
    if (hit) return hit.u8.subarray(a - hit.a, b - hit.a);
    this.stats.requests++;
    const res = await fetch(url, this.rangeSupported === false ? {} : { headers: { Range: `bytes=${a}-${b - 1}` } });
    if (!res.ok) throw new Error(`${url}: ${res.status}`);
    const u8 = new Uint8Array(await res.arrayBuffer());
    this.stats.bytes += u8.length;
    if (res.status === 206) {
      this.rangeSupported = true;
      f.ranges.push({ a, b: a + u8.length, u8 });
      return u8.subarray(0, b - a);
    }
    this.rangeSupported = false;                                    // whole file came back: keep it all
    f.ranges = [{ a: 0, b: u8.length, u8 }];
    f.whole = true;
    return u8.subarray(a, b);
  }

  /** Decoded size a slice will take, before it is decoded (for the budget). */
  estimateDecoded(slice) {
    const ctxRate = this.ctx.sampleRate || slice.rate;
    const samples = slice.granuleStart !== null ? slice.granule - slice.granuleStart              // exact: the run's span
      : (slice.end - slice.offset + 1) + 1.2 * slice.rate;                                        // older index: note + a 1 s page
    return samples * (ctxRate / slice.rate) * slice.channels * 4;
  }

  /** Slices due within `imminent` seconds are never evicted and may exceed the budget: the budget
   *  bounds what is decoded ahead of time, not what has to sound in the next moment. */
  get imminent() { return Math.max(0.75, this.decodeAhead / 8); }

  /** Decoded bytes plus decodes in flight, which is what the budget is checked against. */
  get committedBytes() { return this.stats.decodedBytes + this.pendingBytes; }

  _decodePump() {
    const due = [];
    for (const s of this.slices) {
      if (s.state === 'fetched' && this.nextUse(s) - this.time <= this.decodeAhead) due.push(s);
    }
    due.sort((x, y) => this.nextUse(x) - this.nextUse(y));
    for (const s of due) {
      if (this.decoding >= 2) break;
      const need = this.estimateDecoded(s);
      if (this.committedBytes + need > this.maxDecodedBytes) {
        // make room only from slices outside the window, so the window's contents are decoded once,
        // in order of need, until the budget is full — never traded back and forth.  A slice about
        // to sound may also displace anything that is not itself imminent.
        const imminent = this.nextUse(s) - this.time <= this.imminent;
        this._evict(need, imminent ? this.imminent : this.decodeAhead);
        if (this.committedBytes + need > this.maxDecodedBytes) { if (imminent) this._decode(s, need); break; }
      }
      this._decode(s, need);
    }
    this._evict(0, this.decodeAhead);
  }

  async _decode(slice, estimate = 0) {
    slice.state = 'decoding';
    this.decoding++;
    this.pendingBytes += estimate;
    try {
      const f = this._file(slice.url);
      const ogg = spliceOgg(f.header, slice.u8);
      const buffer = await this.ctx.decodeAudioData(ogg.buffer.slice(ogg.byteOffset, ogg.byteOffset + ogg.byteLength));
      const nFile = Math.round(buffer.length * slice.rate / buffer.sampleRate);
      slice.firstAbs = slice.b0 === slice.header ? 0 : lastGranule(slice.u8) - nFile;
      slice.buffer = buffer;
      slice.state = 'ready';
      this.stats.decoded++;
      this.stats.decodedBytes += buffer.length * buffer.numberOfChannels * 4;
    } catch (e) {
      slice.state = 'failed';
      slice.error = e;
    } finally {
      this.decoding--;
      this.pendingBytes -= estimate;
      this.onchange?.();
      this._decodePump();
    }
  }

  /** Free decoded audio not due within `protect` seconds, furthest need first, until `need` more
   *  bytes fit under the budget. */
  _evict(need, protect) {
    if (this.committedBytes + need <= this.maxDecodedBytes) return;
    const ready = [...this.slices].filter((s) => s.state === 'ready' && s.active === 0);
    ready.sort((x, y) => this.nextUse(y) - this.nextUse(x));
    for (const s of ready) {
      if (this.committedBytes + need <= this.maxDecodedBytes * 0.9) break;
      if (this.nextUse(s) - this.time <= protect) break;
      this.stats.decodedBytes -= s.buffer.length * s.buffer.numberOfChannels * 4;
      s.buffer = null;
      s.state = 'fetched';
      this.stats.evicted++;
    }
  }

  /** Best decoded stand-in for `slice` at `key`: another velocity layer of the same key, else the
   *  nearest key within an octave (pitched programs only).  null when nothing usable is ready. */
  fallbackFor(slice, key) {
    const prog = this.loaded.get(slice.program);
    if (!prog) return null;
    let best = null, bd = Infinity;
    for (const s of prog.slices.values()) {
      if (s.state !== 'ready' || s === slice) continue;
      const d = Math.abs(s.keycenter - slice.keycenter);
      if (d === 0) { if (bd > 0) { best = s; bd = 0; } }
      else if (prog.pitched && d <= 12 && d < bd) { best = s; bd = d; }
    }
    return best;
  }

  /** Fraction of the slices needed in [t0, t1] that are decoded, and how many that is. */
  readiness(t0, t1) {
    let need = 0, ready = 0;
    for (const s of this.slices) {
      if (!s._sorted) this.nextUse(s);
      if (s.uses.some((t) => t >= t0 && t <= t1)) { need++; if (s.state === 'ready') ready++; }
    }
    return { need, ready, fraction: need ? ready / need : 1 };
  }

  /** Resolve when every slice due in [t0, t1] is decoded, or after `timeoutMs`. */
  whenReady(t0, t1, timeoutMs = 4000) {
    return new Promise((resolve) => {
      const started = performance.now();
      const check = () => {
        const r = this.readiness(t0, t1);
        if (r.fraction >= 1 || performance.now() - started > timeoutMs) resolve(r);
        else setTimeout(check, 50);
      };
      check();
    });
  }

  get summary() {
    let idle = 0, fetching = 0, fetched = 0, ready = 0, failed = 0, pinnedBytes = 0;
    for (const s of this.slices) {
      if (s.state === 'idle') idle++; else if (s.state === 'fetching') fetching++;
      else if (s.state === 'fetched' || s.state === 'decoding') fetched++; else if (s.state === 'ready') ready++; else failed++;
      if (s.state === 'ready' && s.active > 0) pinnedBytes += s.buffer.length * s.buffer.numberOfChannels * 4;
    }
    // pinnedBytes: decoded audio that voices are playing right now — the graph holds it whatever the
    // budget says; the budget governs decodedBytes - pinnedBytes, what is decoded ahead of time
    return { slices: this.slices.size, idle, fetching, fetched, ready, failed, ...this.stats, pinnedBytes, rangeSupported: this.rangeSupported };
  }
}

export { dbToGain };
