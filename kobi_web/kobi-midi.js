/**
 * kobi-midi — a small Standard MIDI File parser and a player that drives a KobiBank.
 *
 *   import { MidiPlayer } from './kobi-midi.js';
 *   const player = new MidiPlayer(bank);
 *   await player.load(arrayBuffer);        // parses, then loads only the programs the file uses
 *   player.play(); player.stop();
 *   player.onprogress = (seconds, duration) => ...;
 *
 * Handled: formats 0 and 1, tempo changes, note on / off, program change, bank-agnostic channel 10
 * drums, CC 7 volume, CC 11 expression, CC 64 sustain pedal, CC 120 / 123 all sound / notes off.
 * Parsed but ignored by this player: pitch bend (the scheduler in sched/ uses it), other controllers.
 */

/** Parse a Standard MIDI File into a merged, time-sorted event list in seconds. */
export function parseMidi(arrayBuffer) {
  const d = new DataView(arrayBuffer);
  let pos = 0;
  const str = (n) => { let s = ''; for (let i = 0; i < n; i++) s += String.fromCharCode(d.getUint8(pos++)); return s; };
  const u32 = () => { const v = d.getUint32(pos); pos += 4; return v; };
  const u16 = () => { const v = d.getUint16(pos); pos += 2; return v; };
  const vlq = () => { let v = 0, b; do { b = d.getUint8(pos++); v = (v << 7) | (b & 0x7f); } while (b & 0x80); return v; };
  if (str(4) !== 'MThd') throw new Error('not a MIDI file');
  const hlen = u32();
  const format = u16(), ntracks = u16(), division = u16();
  pos += hlen - 6;
  if (division & 0x8000) throw new Error('SMPTE time division is not supported');
  const events = [];   // {tick, type, channel, a, b}
  for (let t = 0; t < ntracks; t++) {
    if (str(4) !== 'MTrk') throw new Error('bad track header');
    const len = u32(), end = pos + len;
    let tick = 0, status = 0;
    while (pos < end) {
      tick += vlq();
      let b = d.getUint8(pos);
      if (b & 0x80) { status = b; pos++; } else b = status;   // running status
      const hi = status & 0xf0, ch = status & 0x0f;
      if (status === 0xff) {
        const type = d.getUint8(pos++), l = vlq();
        if (type === 0x51) events.push({ tick, type: 'tempo', usPerBeat: (d.getUint8(pos) << 16) | (d.getUint8(pos + 1) << 8) | d.getUint8(pos + 2) });
        pos += l;
      } else if (status === 0xf0 || status === 0xf7) {
        const l = vlq();                   // not `pos += vlq()`: that reads pos before vlq() advances it
        pos += l;
      } else if (hi === 0xc0 || hi === 0xd0) {
        const a = d.getUint8(pos++);
        if (hi === 0xc0) events.push({ tick, type: 'program', channel: ch, program: a });
      } else {
        const a = d.getUint8(pos++), v = d.getUint8(pos++);
        if (hi === 0x90 && v > 0) events.push({ tick, type: 'on', channel: ch, key: a, vel: v });
        else if (hi === 0x80 || hi === 0x90) events.push({ tick, type: 'off', channel: ch, key: a });
        else if (hi === 0xb0) events.push({ tick, type: 'cc', channel: ch, cc: a, value: v });
        else if (hi === 0xe0) events.push({ tick, type: 'bend', channel: ch, value: ((v << 7) | a) - 8192 });   // -8192..8191
      }
    }
    pos = end;
  }
  events.sort((x, y) => x.tick - y.tick || (x.type === 'tempo' ? -1 : 0) - (y.type === 'tempo' ? -1 : 0));
  // ticks -> seconds through the tempo map
  let usPerBeat = 500000, lastTick = 0, time = 0;
  for (const e of events) {
    time += ((e.tick - lastTick) / division) * (usPerBeat / 1e6);
    lastTick = e.tick;
    e.time = time;
    if (e.type === 'tempo') usPerBeat = e.usPerBeat;
  }
  return { format, division, events, duration: time };
}

export class MidiPlayer {
  constructor(bank) {
    this.bank = bank;
    this.ctx = bank.ctx;
    this.events = [];
    this.duration = 0;
    this.onprogress = null;
    this.onend = null;
    this._timer = null;
    this._channels = [];
  }

  /** Programs a parsed file needs (channel 10 -> 'drums'; channels without a program change use 0). */
  static programsUsed(events) {
    const used = new Set();
    const current = new Array(16).fill(0);
    const noted = new Set();
    for (const e of events) {
      if (e.type === 'program') current[e.channel] = e.program;
      if (e.type === 'on') { used.add(e.channel === 9 ? 'drums' : String(current[e.channel])); noted.add(e.channel); }
    }
    return [...used];
  }

  /** Parse and load every program the file uses. */
  async load(arrayBuffer) {
    const parsed = parseMidi(arrayBuffer);
    this.events = parsed.events;
    this.duration = parsed.duration;
    this.programs = MidiPlayer.programsUsed(this.events);
    await Promise.all(this.programs.map((p) => this.bank.load(p === 'drums' ? 'drums' : Number(p))));
    return { duration: this.duration, programs: this.programs, events: this.events.length };
  }

  play() {
    this.stop();
    this.ctx.resume();
    this._channels = Array.from({ length: 16 }, () => {
      const gain = this.ctx.createGain();
      gain.connect(this.bank.master);
      return { program: 0, volume: 100, expression: 127, gain, held: new Map(), pedal: false, sustained: [] };
    });
    this._channels.forEach((c) => this._applyVolume(c, this.ctx.currentTime));
    this._start = this.ctx.currentTime + 0.15;
    this._index = 0;
    this._loadingPrograms = new Set();
    const lookahead = 0.35;
    const tick = () => {
      const now = this.ctx.currentTime - this._start;
      while (this._index < this.events.length && this.events[this._index].time <= now + lookahead) {
        this._dispatch(this.events[this._index], this._start + this.events[this._index].time);
        this._index++;
      }
      this.onprogress?.(Math.max(0, Math.min(now, this.duration)), this.duration);
      if (this._index >= this.events.length && now > this.duration + 1) {
        this.stop();
        this.onend?.();
        return;
      }
      this._timer = setTimeout(tick, 60);
    };
    tick();
  }

  get playing() { return this._timer !== null; }

  stop() {
    if (this._timer) { clearTimeout(this._timer); this._timer = null; }
    this.bank.allNotesOff();
    for (const c of this._channels) c.gain.disconnect();
    this._channels = [];
  }

  _applyVolume(c, when) {
    c.gain.gain.setValueAtTime((c.volume / 127) * (c.expression / 127), when);
  }

  _dispatch(e, when) {
    const c = this._channels[e.channel ?? 0];
    if (!c) return;
    switch (e.type) {
      case 'program':
        c.program = e.program;
        if (!this.bank.isLoaded(e.program) && !this._loadingPrograms.has(e.program)) {
          this._loadingPrograms.add(e.program);
          this.bank.load(e.program).catch(() => {});      // notes before it arrives are dropped
        }
        break;
      case 'on': {
        const prog = e.channel === 9 ? 'drums' : c.program;
        const h = this.bank.noteOn(prog, e.key, e.vel, { when, destination: c.gain });
        if (h) {                                          // a re-struck key keeps both notes; note-offs release oldest first
          if (!c.held.has(e.key)) c.held.set(e.key, []);
          c.held.get(e.key).push(h);
        }
        break;
      }
      case 'off': {
        const l = c.held.get(e.key);
        const h = l && l.shift();
        if (l && !l.length) c.held.delete(e.key);
        if (h) { if (c.pedal) c.sustained.push(h); else this.bank.noteOff(h, e.key, when); }
        break;
      }
      case 'cc':
        if (e.cc === 7) { c.volume = e.value; this._applyVolume(c, when); }
        else if (e.cc === 11) { c.expression = e.value; this._applyVolume(c, when); }
        else if (e.cc === 64) {
          c.pedal = e.value >= 64;
          if (!c.pedal) { for (const h of c.sustained) this.bank.noteOff(h, h.key, when); c.sustained = []; }
        } else if (e.cc === 120 || e.cc === 123) {
          for (const l of c.held.values()) for (const h of l) this.bank.noteOff(h, h.key, when);
          c.held.clear();
        }
        break;
      default:
        break;
    }
  }
}
