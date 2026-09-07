/**
 * kobi-player — play a kobi SFZ bank in the browser with Web Audio, loading programs on demand.
 *
 *   import { KobiBank } from './kobi-player.js';
 *   const bank = new KobiBank('../kobi_slim/');          // folder holding GM/manifest.json
 *   await bank.load(0);                                    // fetches "000 Acoustic Grand Piano.sfz" + its samples
 *   const voice = bank.noteOn(0, 60, 100);                 // program, MIDI key, velocity
 *   bank.noteOff(0, 60);                                   // release; one-shots ignore this
 *   bank.noteOn('drums', 38, 110);                         // General MIDI drum key
 *
 * The bank's SFZ subset: <control> default_path / set_hdcc72, <global> volume, <region> sample, key,
 * lokey / hikey / pitch_keycenter, pitch_keytrack, lovel / hivel, tune, volume, offset / end,
 * loop_mode with loop_start / loop_end (inclusive, in the file's own samples), ampeg_hold / decay /
 * sustain / release, ampeg_release_oncc72 (scaled by set_hdcc72), lorand / hirand, seq_length /
 * seq_position.  Everything else is parsed and ignored.  No dependencies.
 *
 * A packed bank puts every note of a program in one Ogg (see kobi/packing.py) and addresses them
 * with offset / end, so one fetch serves a whole instrument.
 */

const SFZ_EXP = 9; // sfizz decay / release: exp(-9 t / T), so the time constant is T / 9

export function dbToGain(db) {
  return Math.pow(10, db / 20);
}

/**
 * A transparent peak safety: linear up to `knee` (0.7 = -3 dBFS), then a soft saturation that never
 * reaches full scale.  Unlike a DynamicsCompressor it has no gain riding — a compressor on a bank
 * mix was measured swinging 3-14 dB within 100 ms every time one instrument stopped and another
 * carried on, and adding make-up gain on top — so nothing here pumps or breathes.
 */
export function softClipper(ctx, knee = 0.7, ceiling = 0.98) {
  const n = 8193, curve = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const x = (i / (n - 1)) * 2 - 1, a = Math.abs(x);
    const y = a <= knee ? a : knee + (1 - knee) * Math.tanh((a - knee) / (1 - knee));
    curve[i] = Math.sign(x) * y * ceiling;
  }
  const shaper = ctx.createWaveShaper();
  shaper.curve = curve;
  shaper.oversample = 'none';                    // no latency; the curve is linear for everything but the rare over
  return shaper;
}


/** Parse SFZ text into { control, global, regions } with inherited opcodes merged into each region. */
export function parseSfz(text) {
  const control = {};
  let global = {}, master = {}, group = {};
  const regions = [];
  const body = text.replace(/\/\/[^\n]*/g, '');
  const parts = body.split(/<(\w+)>/);
  for (let i = 1; i < parts.length; i += 2) {
    const header = parts[i];
    const ops = {};
    const re = /(?<![\w$])([\w$]+)=/g;
    const chunk = parts[i + 1].replace(/\n/g, ' ');
    let m, last = null;
    const found = [];
    while ((m = re.exec(chunk)) !== null) found.push(m);
    for (let k = 0; k < found.length; k++) {
      const end = k + 1 < found.length ? found[k + 1].index : chunk.length;
      ops[found[k][1]] = chunk.slice(found[k].index + found[k][0].length, end).trim();
    }
    if (header === 'control') Object.assign(control, ops);
    else if (header === 'global') { global = ops; master = {}; group = {}; }
    else if (header === 'master') { master = ops; group = {}; }
    else if (header === 'group') group = ops;
    else if (header === 'region') regions.push({ ...global, ...master, ...group, ...ops });
  }
  return { control, global, regions };
}

const num = (v, d = 0) => (v === undefined ? d : Number(v));

/** Turn merged region opcodes into the numbers a voice needs. */
export function regionParams(ops, control) {
  const key = ops.key !== undefined ? num(ops.key) : undefined;
  const lokey = ops.lokey !== undefined ? num(ops.lokey) : (key ?? 0);
  const hikey = ops.hikey !== undefined ? num(ops.hikey) : (key ?? 127);
  const keycenter = ops.pitch_keycenter !== undefined ? num(ops.pitch_keycenter) : (key ?? 60);
  const loopMode = ops.loop_mode || (ops.loop_end !== undefined ? 'loop_continuous' : 'no_loop');
  const hd72 = num(control.set_hdcc72, 0);
  const release = num(ops.ampeg_release, 0) + num(ops.ampeg_release_oncc72, 0) * hd72;
  return {
    sample: ops.sample,
    lokey, hikey, keycenter,
    keytrack: num(ops.pitch_keytrack, 100) / 100,
    lovel: num(ops.lovel, 0), hivel: num(ops.hivel, 127),
    tune: num(ops.tune, 0) + 100 * num(ops.transpose, 0),
    volumeDb: num(ops.volume, 0),
    pan: Math.max(-1, Math.min(1, num(ops.pan, 0) / 100)),
    loop: loopMode === 'loop_continuous' || loopMode === 'loop_sustain'
      ? { start: num(ops.loop_start, 0), end: num(ops.loop_end, 0) } : null,
    oneShot: loopMode === 'one_shot',
    offset: num(ops.offset, 0),
    end: ops.end !== undefined ? num(ops.end) : null,
    hold: num(ops.ampeg_hold, 0),
    decay: ops.ampeg_decay !== undefined ? num(ops.ampeg_decay) : null,
    sustain: num(ops.ampeg_sustain, 100) / 100,
    release: Math.max(release, 0.005),
    lorand: num(ops.lorand, 0), hirand: num(ops.hirand, 1),
    seqLength: num(ops.seq_length, 1), seqPosition: num(ops.seq_position, 1),
  };
}

/** Sample rate written in an Ogg Vorbis identification header (decodeAudioData resamples, so the
 *  loop points, which are in the file's own samples, need the original rate). */
export function oggSampleRate(bytes) {
  const u8 = new Uint8Array(bytes);
  const limit = Math.min(u8.length - 16, 4096);
  for (let i = 0; i < limit; i++) {
    if (u8[i] === 1 && u8[i + 1] === 0x76 && u8[i + 2] === 0x6f && u8[i + 3] === 0x72 && u8[i + 4] === 0x62 &&
        u8[i + 5] === 0x69 && u8[i + 6] === 0x73) {
      return new DataView(u8.buffer, u8.byteOffset + i + 12, 4).getUint32(0, true);
    }
  }
  return null;
}

export class KobiBank {
  /**
   * @param {string} bankUrl folder that holds GM/manifest.json (e.g. '../kobi_slim/')
   * @param {{context?: AudioContext, sampleRate?: number, latencyHint?: string, destination?: AudioNode, gain?: number, limiter?: boolean}} [opts]
   */
  constructor(bankUrl, opts = {}) {
    this.url = new URL(bankUrl.endsWith('/') ? bankUrl : bankUrl + '/', typeof location !== 'undefined' ? location.href : 'file:///');
    // a context at the bank's own rate (see GM/manifest.json `rate`): decodeAudioData then copies samples
    // instead of resampling them, so loop points stay exact in every browser; the output is resampled
    // to the device by the browser, which is harmless
    this.ctx = opts.context || new (window.AudioContext || window.webkitAudioContext)({ latencyHint: opts.latencyHint ?? 'playback',   // see sched/kobi-engine.js
      ...(opts.sampleRate ? { sampleRate: opts.sampleRate } : {}) });
    // -12 dB leaves a full mix ~4 dB of headroom (a single voice sits about 3.5 dB below sfizz's level);
    // the soft clipper is a safety net for the rare peak, not a stage the mix leans on
    this.master = this.ctx.createGain();
    this.master.gain.value = opts.gain ?? dbToGain(-12);
    this.limiter = softClipper(this.ctx);
    this.master.connect(opts.limiter === false ? (opts.destination || this.ctx.destination) : this.limiter);
    if (opts.limiter !== false) this.limiter.connect(opts.destination || this.ctx.destination);
    this._manifest = null;
    this._programs = new Map();      // id -> Promise<Program>
    this._loaded = new Map();        // id -> Program
    this.voices = new Set();
    this.bytes = 0;                  // audio + sfz bytes fetched so far
    this.onload = null;              // (id, program) => void
  }

  async manifest() {
    if (!this._manifest) {
      const r = await fetch(new URL('GM/manifest.json', this.url));
      if (!r.ok) throw new Error(`manifest: ${r.status}`);
      this._manifest = await r.json();
    }
    return this._manifest;
  }

  /** Program ids: 0..127 and 'drums'. */
  static id(program) {
    return program === 'drums' ? 'drums' : String(program);
  }

  isLoaded(program) {
    return this._loaded.has(KobiBank.id(program));
  }

  /** Open a bank: read the manifest and create the player with a context at the bank's rate. */
  static async open(bankUrl, opts = {}) {
    const url = new URL(bankUrl.endsWith('/') ? bankUrl : bankUrl + '/', typeof location !== 'undefined' ? location.href : 'file:///');
    const r = await fetch(new URL('GM/manifest.json', url));
    if (!r.ok) throw new Error(`manifest: ${r.status}`);
    const man = await r.json();
    const bank = new KobiBank(bankUrl, { ...opts, sampleRate: opts.sampleRate ?? man.rate });
    bank._manifest = man;
    return bank;
  }

  /** Fetch and decode a program once; concurrent calls share the same promise. */
  load(program) {
    const id = KobiBank.id(program);
    if (!this._programs.has(id)) {
      const p = this._load(id).then((prog) => { this._loaded.set(id, prog); this.onload?.(id, prog); return prog; });
      p.catch(() => this._programs.delete(id));
      this._programs.set(id, p);
    }
    return this._programs.get(id);
  }

  async _load(id) {
    const man = await this.manifest();
    const entry = id === 'drums' ? man.drums : man.programs[id];
    if (!entry) throw new Error(`no program ${id} in the bank`);
    const sfzUrl = new URL('GM/' + encodeURIComponent(entry.file), this.url);
    const r = await fetch(sfzUrl);
    if (!r.ok) throw new Error(`${entry.file}: ${r.status}`);
    const text = await r.text();
    this.bytes += text.length;
    const { control, global, regions } = parseSfz(text);
    const base = new URL((control.default_path || './').replace(/\\/g, '/'), sfzUrl);
    const params = regions.map((ops) => regionParams(ops, control)).filter((p) => p.sample);
    const files = [...new Set(params.map((p) => p.sample))];
    const buffers = new Map();
    await Promise.all(files.map(async (f) => {
      const res = await fetch(new URL(encodeURIComponent(f), base));
      if (!res.ok) throw new Error(`${f}: ${res.status}`);
      const bytes = await res.arrayBuffer();
      this.bytes += bytes.byteLength;
      const rate = oggSampleRate(bytes);
      const buffer = await this.ctx.decodeAudioData(bytes.slice(0));
      buffers.set(f, { buffer, rate: rate || buffer.sampleRate });
    }));
    for (const p of params) Object.assign(p, buffers.get(p.sample));
    return { id, name: entry.name, globalDb: num(global.volume, 0), regions: params, files: files.length };
  }

  /** Regions that key / velocity would trigger (random and sequence round robins resolved). */
  regionsFor(prog, key, vel) {
    const r = Math.random();
    const hits = prog.regions.filter((p) => key >= p.lokey && key <= p.hikey && vel >= p.lovel && vel <= p.hivel &&
      r >= p.lorand && (r < p.hirand || p.hirand >= 1));
    if (hits.some((p) => p.seqLength > 1)) {
      prog._seq = ((prog._seq || 0) % Math.max(...hits.map((p) => p.seqLength))) + 1;
      return hits.filter((p) => p.seqLength === 1 || p.seqPosition === prog._seq);
    }
    return hits;
  }

  /**
   * Start a note.  Returns a handle for noteOff.  The program must be loaded (use load()).
   * @param {number|string} program 0..127 or 'drums'
   * @param {{when?: number, destination?: AudioNode, gain?: number}} [opts]
   */
  noteOn(program, key, vel, opts = {}) {
    const prog = this._loaded.get(KobiBank.id(program));
    if (!prog) return null;
    const when = opts.when ?? this.ctx.currentTime;
    const out = opts.destination || this.master;
    const velGain = Math.pow(Math.max(vel, 1) / 127, 2);
    const handle = { program: prog.id, key, voices: [], released: false };
    for (const p of this.regionsFor(prog, key, vel)) {
      const src = this.ctx.createBufferSource();
      src.buffer = p.buffer;
      const semis = p.keytrack * (key - p.keycenter) + p.tune / 100;
      src.playbackRate.value = Math.pow(2, semis / 12);
      if (p.loop) {
        src.loop = true;
        src.loopStart = p.loop.start / p.rate;
        src.loopEnd = (p.loop.end + 1) / p.rate;
      }
      const startSec = p.offset / p.rate;                 // sample positions are in the file's own rate
      const noteSec = p.end !== null ? (p.end - p.offset + 1) / p.rate : null;
      const env = this.ctx.createGain();
      env.gain.setValueAtTime(0.0001, when);
      env.gain.exponentialRampToValueAtTime(1, when + 0.002);
      if (p.decay !== null) {
        env.gain.setValueAtTime(1, when + p.hold);
        env.gain.setTargetAtTime(Math.max(p.sustain, 0), when + p.hold, p.decay / SFZ_EXP);
      }
      const amp = this.ctx.createGain();
      amp.gain.value = velGain * dbToGain(p.volumeDb) * (opts.gain ?? 1);   // volume already inherits <global>
      let tail = src.connect(env).connect(amp);
      if (p.pan && this.ctx.createStereoPanner) { const pan = this.ctx.createStereoPanner(); pan.pan.value = p.pan; tail = tail.connect(pan); }
      tail.connect(out);
      if (p.loop) src.start(when, startSec);              // the loop bounds keep it inside the note
      else if (noteSec !== null) src.start(when, startSec, noteSec);
      else src.start(when, startSec);
      const voice = { src, env, p, when, program: prog.id, key };
      src.onended = () => { this.voices.delete(voice); src.disconnect(); env.disconnect(); amp.disconnect(); };
      this.voices.add(voice);
      handle.voices.push(voice);
      if (p.oneShot && !p.loop) {                         // a packed buffer holds the whole program: use the note's own length
        const len = noteSec !== null ? noteSec : p.buffer.duration - startSec;
        src.stop(when + len / src.playbackRate.value + 0.01);
      }
    }
    return handle;
  }

  /** Release a note started with noteOn (handle) or by program + key. */
  noteOff(programOrHandle, key, when) {
    const t = when ?? this.ctx.currentTime;
    const handles = typeof programOrHandle === 'object' && programOrHandle
      ? [programOrHandle]
      : null;
    const voices = handles ? handles.flatMap((h) => h.voices)
      : [...this.voices].filter((v) => v.program === KobiBank.id(programOrHandle) && v.key === key);
    for (const v of voices) this._release(v, t);
    if (handles) handles.forEach((h) => { h.released = true; });
  }

  _release(v, t) {
    if (v.p.oneShot || v.releasing) return;
    v.releasing = true;
    const g = v.env.gain;
    if (g.cancelAndHoldAtTime) g.cancelAndHoldAtTime(t);
    else { g.cancelScheduledValues(t); g.setValueAtTime(g.value, t); }
    g.setTargetAtTime(0, t, v.p.release / SFZ_EXP);
    v.src.stop(t + v.p.release * 1.3 + 0.05);
  }

  allNotesOff(when) {
    const t = when ?? this.ctx.currentTime;
    for (const v of this.voices) this._release(v, t);
  }

  /** Loaded programs and bytes fetched, for a status line. */
  get stats() {
    return { programs: this._loaded.size, bytes: this.bytes, voices: this.voices.size };
  }
}
