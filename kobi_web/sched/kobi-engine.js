/**
 * kobi-engine — schedule-only playback of a kobi bank, loading each note's sample as it is needed.
 *
 *   import { KobiEngine } from './kobi-engine.js';
 *   const engine = new KobiEngine('../kobi_slim/');
 *   const info = await engine.load(midiArrayBuffer);   // parse, compile, start downloading by priority
 *   await engine.play();                                // waits (briefly) for the first seconds to be ready
 *   engine.pause(); engine.resume(); engine.seek(42); engine.stop();
 *
 * There is no live noteOn: a song is compiled to a timeline (kobi-song.js) and a 50 ms tick starts
 * the voices that fall within the next `lookahead` seconds, sample-accurately, with whatever the
 * loader has ready.  A note whose slice has not arrived plays the best loaded stand-in of its
 * program — another velocity layer of the same key, or the nearest key transposed — and is counted
 * in `stats.fallbacks`; a note with nothing to stand in is counted in `stats.missed`.
 *
 * Decoded audio is bounded (`maxDecodedBytes`, 48 MB by default) and voices are bounded
 * (`polyphony`), so long songs on small devices stay flat in memory and CPU.
 */
import { parseMidi } from '../kobi-midi.js';
import { SliceLoader, dbToGain } from './kobi-loader.js';
import { softClipper } from '../kobi-player.js';
import { compileSong } from './kobi-song.js';

const SFZ_EXP = 9;                        // sfizz decay / release: exp(-9 t / T)
const SILENT = Math.log(1e4) / SFZ_EXP;   // a sustain=0 decay is 80 dB down at hold + decay * SILENT

export class KobiEngine {
  /**
   * @param {string} bankUrl
   * @param {{context?: BaseAudioContext, sampleRate?: number, latencyHint?: string, destination?: AudioNode, gain?: number, limiter?: boolean, parallel?: number,
   *          decodeAhead?: number, maxDecodedBytes?: number, lookahead?: number, tick?: number, polyphony?: number,
   *          preroll?: number, prerollTimeout?: number, rng?: () => number}} [opts]
   */
  constructor(bankUrl, opts = {}) {
    // at the bank's rate (manifest `rate`, via KobiEngine.open) a decoded slice is a copy, not a resample
    // 'playback' asks the browser for larger output buffers: a file player schedules ahead anyway, and
    // the extra ~50 ms of latency buys immunity to dropouts when the machine is busy
    this.ctx = opts.context || new (window.AudioContext || window.webkitAudioContext)({ latencyHint: opts.latencyHint ?? 'playback',
      ...(opts.sampleRate ? { sampleRate: opts.sampleRate } : {}) });
    this.loader = new SliceLoader(bankUrl, this.ctx, opts);
    this.lookahead = opts.lookahead ?? 0.4;
    this.tickMs = opts.tick ?? 50;
    this.polyphony = opts.polyphony ?? 96;
    this.preroll = opts.preroll ?? 3;
    this.prerollTimeout = opts.prerollTimeout ?? 4000;
    // -12 dB leaves a full mix ~4 dB of headroom; the soft clipper only catches the rare peak
    this.master = this.ctx.createGain();
    this.master.gain.value = opts.gain ?? dbToGain(-12);
    const dest = opts.destination || this.ctx.destination;
    if (opts.limiter === false) this.master.connect(dest);
    else {
      this.limiter = softClipper(this.ctx);               // peak safety without gain riding (see kobi-player.js)
      this.master.connect(this.limiter).connect(dest);
    }
    this.channels = Array.from({ length: 16 }, () => {
      const gain = this.ctx.createGain();
      const pan = this.ctx.createStereoPanner ? this.ctx.createStereoPanner() : null;
      if (pan) gain.connect(pan).connect(this.master); else gain.connect(this.master);
      gain.gain.value = (100 / 127);
      return { gain, pan, bend: 0 };
    });
    this.song = null;
    this.voices = new Set();
    this.live = 0;                      // voices not yet stolen or released to silence
    this.stats = { started: 0, fallbacks: 0, missed: 0, unmapped: 0, stolen: 0, late: 0 };   // unmapped: no region for the key; late: dispatched after its time
    this.missedLog = [];               // the last 50 notes that could not sound: {t, program, key, states}
    this._timer = null;
    this._start = null;                 // ctx time that corresponds to song time 0 while playing
    this._position = 0;                 // song time while stopped / paused
    this._index = 0;
    this.onprogress = null;
    this.onend = null;
    this.onchange = null;
    this.loader.onchange = () => this.onchange?.();
  }

  /** Create an engine whose context runs at the bank's own sample rate. */
  static async open(bankUrl, opts = {}) {
    const url = new URL(bankUrl.endsWith('/') ? bankUrl : bankUrl + '/', typeof location !== 'undefined' ? location.href : 'file:///');
    const man = await (await fetch(new URL('GM/manifest.json', url))).json();
    const engine = new KobiEngine(bankUrl, { ...opts, sampleRate: opts.sampleRate ?? man.rate });
    engine.loader._manifest = man;
    return engine;
  }

  /** Parse and compile a Standard MIDI File; the loader starts fetching at once. */
  async load(arrayBuffer) {
    this.stop();
    const parsed = parseMidi(arrayBuffer);
    this.song = await compileSong(parsed, this.loader);
    this._position = 0;
    this.loader.setTime(0);
    return { duration: this.song.duration, programs: this.song.programs, notes: this.song.notes, slices: this.song.slices,
             bytes: this.song.bytes, unmapped: this.song.unmapped };
  }

  get position() {
    return this._start === null ? this._position : Math.max(0, this.ctx.currentTime - this._start);
  }

  get playing() { return this._timer !== null; }

  /** Start from the current position; resolves once playback has begun. */
  async play() {
    if (!this.song || this.playing) return;
    if (this.ctx.resume) await this.ctx.resume();
    await this.loader.whenReady(this._position, this._position + this.preroll, this.prerollTimeout);
    this._start = this.ctx.currentTime + 0.1 - this._position;
    this._index = this._firstEventAt(this._position);
    this._applyStateAt(this._position, this.ctx.currentTime);
    const tick = () => {
      const now = this.position;
      const ahead = (typeof document !== 'undefined' && document.hidden) ? 1.5 : this.lookahead;
      const ev = this.song.events;
      while (this._index < ev.length && ev[this._index].t <= now + ahead) {
        this._dispatch(ev[this._index], this._start + ev[this._index].t);
        this._index++;
      }
      this.loader.setTime(now);
      this.onprogress?.(Math.min(now, this.song.duration), this.song.duration);
      if (this._index >= ev.length && now > this.song.duration + 1) {
        this.stop();
        this._position = 0;
        this.onend?.();
        return;
      }
      this._timer = setTimeout(tick, this.tickMs);
    };
    tick();
  }

  pause() {
    if (!this.playing) return;
    this._position = this.position;
    this._silence(this.ctx.currentTime, 0.03);
    clearTimeout(this._timer); this._timer = null; this._start = null;
  }

  resume() { return this.play(); }

  /** Jump to `t` seconds; keeps playing if it was.  Notes already sounding at `t` are not restarted. */
  seek(t) {
    const was = this.playing;
    if (was) this.pause();
    this._position = Math.max(0, Math.min(t, this.song ? this.song.duration : 0));
    this.loader.setTime(this._position);
    if (was) return this.play();
    this.onprogress?.(this._position, this.song ? this.song.duration : 0);
  }

  stop() {
    if (this._timer) { clearTimeout(this._timer); this._timer = null; }
    this._silence(this.ctx.currentTime, 0.02);
    this._start = null;
    this._position = 0;
  }

  _firstEventAt(t) {
    const ev = this.song.events;
    let lo = 0, hi = ev.length;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (ev[mid].t < t) lo = mid + 1; else hi = mid; }
    return lo;
  }

  /** Channel volume / pan / bend as they stand at song time `t`, applied at ctx time `when`. */
  _applyStateAt(t, when) {
    const state = this.channels.map(() => ({ gain: 100 / 127, pan: 0, cents: 0 }));
    for (const e of this.song.events) {
      if (e.t >= t) break;
      if (e.kind === 'volume') state[e.channel].gain = e.gain;
      else if (e.kind === 'pan') state[e.channel].pan = e.pan;
      else if (e.kind === 'bend') state[e.channel].cents = e.cents;
    }
    state.forEach((s, i) => {
      const c = this.channels[i];
      c.gain.gain.cancelScheduledValues(when); c.gain.gain.setValueAtTime(s.gain, when);
      if (c.pan) { c.pan.pan.cancelScheduledValues(when); c.pan.pan.setValueAtTime(s.pan, when); }
      c.bend = s.cents;
    });
  }

  _dispatch(e, when) {
    const c = this.channels[e.channel ?? 0];
    switch (e.kind) {
      case 'note': this._startNote(e, when); break;
      case 'volume': c.gain.gain.setTargetAtTime(e.gain, when, 0.01); break;
      case 'pan': if (c.pan) c.pan.pan.setTargetAtTime(e.pan, when, 0.01); break;
      case 'bend': c.bend = e.cents; break;               // live voices follow through their own detune schedule
      default: break;
    }
  }

  _miss(n, why) {
    this.stats.missed++;
    if (this.missedLog.length < 50) this.missedLog.push({ t: +n.t.toFixed(2), program: n.program, key: n.key, why });
  }

  _startNote(n, when) {
    if (!n.parts.length) { this.stats.unmapped++; return; }         // a bank gap, not a loading failure
    if (when < this.ctx.currentTime) this.stats.late++;
    const c = this.channels[n.channel];
    const t1 = this._start + n.t1;
    const velGain = Math.pow(Math.max(n.vel, 1) / 127, 2);
    let fell = false, played = 0;
    for (const part of n.parts) {
      let slice = part.slice, regions = part.regions;
      if (slice.state !== 'ready') {
        const fb = this.loader.fallbackFor(slice, n.key);
        if (!fb) continue;
        slice = fb; regions = fb.regions.filter((r) => n.vel >= r.lovel && n.vel <= r.hivel);
        if (!regions.length) regions = fb.regions.slice(0, 1);
        fell = true;
      }
      this._voice(n, slice, regions, when, t1, velGain, c);
      played++;
    }
    if (!played) this._miss(n, n.parts.map((p) => `${p.slice.key}:${p.slice.state}`).join(' '));
    else { this.stats.started++; if (fell) this.stats.fallbacks++; }
  }

  _voice(n, slice, regions, when, t1, velGain, c) {
    if (this.live >= this.polyphony) this._steal(when);
    const r0 = regions[0];
    const src = this.ctx.createBufferSource();
    src.buffer = slice.buffer;
    const semis = r0.keytrack * (n.key - r0.keycenter) + r0.tune / 100;
    src.playbackRate.value = Math.pow(2, semis / 12);
    // pitch bend: the channel's value now, then every change while the note sounds
    src.detune.setValueAtTime(c.bend, when);
    const bends = this.song.bendsByChannel[n.channel];
    if (bends.length) {
      let i = this._bendIndex(bends, n.t);
      for (; i < bends.length && bends[i].t <= n.t1 + 0.5; i++) src.detune.setValueAtTime(bends[i].cents, this._start + bends[i].t);
    }
    const rate = slice.rate;
    const startSec = (r0.offset - slice.firstAbs) / rate;
    const noteSec = (r0.end - r0.offset + 1) / rate;
    if (r0.loop) {
      src.loop = true;
      src.loopStart = (r0.loop.start - slice.firstAbs) / rate;
      src.loopEnd = (r0.loop.end + 1 - slice.firstAbs) / rate;
    }
    // one source feeds every envelope of the stack, so it may stop only when the *slowest* of them is
    // silent (stopping at the fastest cut a piano's long envelope mid-decay: a click on every held note)
    let silentAt = -Infinity, releaseEnd = -Infinity, decays = false;
    const voice = { src, envs: [], when, slice, note: n };
    // the release can never come before the attack ramp has finished
    const tRel = Math.max(t1, when + 0.003);
    for (const r of regions) {
      // one gain per envelope: the region's level scales the envelope instead of a second node
      const g = velGain * dbToGain(r.volumeDb);
      const env = this.ctx.createGain();
      env.gain.setValueAtTime(0.0001 * g, when);
      env.gain.exponentialRampToValueAtTime(g, when + 0.002);
      // hold and decay are scheduled only if the note outlives the hold: for a shorter note (a staccato
      // piano note under 150 ms) an event at hold's end would land *after* the release and snap the gain
      // back to full — a pop and a ghost note, 150 ms after every short note
      // (a one-shot ignores its note-off, so its envelope runs whatever the note length)
      if (r.decay !== null && (r.oneShot || when + r.hold < tRel)) {
        env.gain.setValueAtTime(g, when + r.hold);
        env.gain.setTargetAtTime(Math.max(r.sustain, 0) * g, when + r.hold, r.decay / SFZ_EXP);
        if (r.sustain === 0) { decays = true; silentAt = Math.max(silentAt, when + r.hold + r.decay * SILENT); }
      }
      let tail = src.connect(env);
      if (r.pan && this.ctx.createStereoPanner) { const pan = this.ctx.createStereoPanner(); pan.pan.value = r.pan; tail = tail.connect(pan); }
      tail.connect(c.gain);
      voice.envs.push(env);
      if (!r.oneShot) {                                             // release at the note's end
        env.gain.setTargetAtTime(0, tRel, r.release / SFZ_EXP);
        releaseEnd = Math.max(releaseEnd, tRel + r.release * 1.3 + 0.05);
      }
    }
    let stopAt = Infinity;
    if (releaseEnd > -Infinity) stopAt = releaseEnd;
    if (decays && regions.every((r) => r.sustain === 0)) stopAt = Math.min(stopAt, silentAt);
    if (r0.loop) src.start(when, startSec);
    else {
      src.start(when, startSec, noteSec);
      stopAt = Math.min(stopAt, when + noteSec / src.playbackRate.value + 0.01);
    }
    if (r0.oneShot && stopAt === Infinity) stopAt = when + noteSec / src.playbackRate.value + 0.01;
    if (stopAt !== Infinity) src.stop(stopAt);
    slice.active++;
    this.live++;
    voice.stopAt = stopAt;
    src.onended = () => {
      this.voices.delete(voice); slice.active--; if (!voice.stolen) this.live--;
      src.disconnect(); voice.envs.forEach((g) => g.disconnect());
    };
    this.voices.add(voice);
  }

  _bendIndex(bends, t) {
    let lo = 0, hi = bends.length;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (bends[mid].t < t) lo = mid + 1; else hi = mid; }
    return lo;
  }

  /** Over the polyphony budget: fade out the voice that was going to end soonest anyway (a tail in
   *  release or a decayed note), over 20 ms. */
  _steal(when) {
    let pick = null;
    for (const v of this.voices) if (!v.stolen && (!pick || v.stopAt < pick.stopAt)) pick = v;
    if (!pick) return;
    pick.stolen = true;
    this.live--;
    for (const g of pick.envs) { g.gain.cancelScheduledValues(when); g.gain.setTargetAtTime(0, when, 0.015); }   // ~50 ms fade
    try { pick.src.stop(when + 0.08); } catch (e) { /* already scheduled to stop earlier */ }
    this.stats.stolen++;
  }

  _silence(when, fade) {
    for (const v of this.voices) {
      for (const g of v.envs) { g.gain.cancelScheduledValues(when); g.gain.setTargetAtTime(0, when, fade / 3); }
      try { v.src.stop(when + fade + 0.01); } catch (e) { /* already stopped */ }
    }
  }

  /** Loader + voice statistics for a status line. */
  get status() {
    return { ...this.loader.summary, voices: this.live, ...this.stats, position: this.position,
             duration: this.song ? this.song.duration : 0 };
  }

  /**
   * Render the loaded song in an OfflineAudioContext: every slice is fetched and decoded first, then
   * all notes are scheduled at once.  Deterministic, so it is what the tests compare against sfizz.
   */
  static async renderOffline(bankUrl, arrayBuffer, opts = {}) {
    const parsed = parseMidi(arrayBuffer);
    const rate = opts.sampleRate ?? 44100;
    const probe = new OfflineAudioContext(2, 1, rate);
    const loader = new SliceLoader(bankUrl, probe, { parallel: 6, decodeAhead: Infinity, maxDecodedBytes: Infinity, rng: opts.rng });
    const song = await compileSong(parsed, loader);
    const seconds = Math.min(opts.seconds ?? song.duration + 2, song.duration + 2);
    const ctx = new OfflineAudioContext(2, Math.ceil(seconds * rate), rate);
    loader.ctx = ctx;
    loader.setTime(0);
    await loader.whenReady(0, seconds, opts.timeoutMs ?? 120000);
    // everything is scheduled before a sample is rendered, so voices never end from the engine's point
    // of view while scheduling: no polyphony stealing here (the graph handles thousands of nodes offline)
    const engine = new KobiEngine(bankUrl, { ...opts, context: ctx, polyphony: Infinity });
    engine.loader = loader;
    engine.song = song;
    engine._start = 0.05;
    engine._applyStateAt(0, 0);
    for (const e of song.events) { if (e.t > seconds) break; engine._dispatch(e, engine._start + e.t); }
    const buffer = await ctx.startRendering();
    return { buffer, stats: engine.stats, loader: loader.summary, song: { notes: song.notes, slices: song.slices, bytes: song.bytes } };
  }
}
