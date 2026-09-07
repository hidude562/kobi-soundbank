/**
 * kobi-song — compile a parsed MIDI file into what the scheduler plays.
 *
 * Everything is resolved up front: which program each channel is on at each note, when each note
 * releases (the sustain pedal included), and — once the programs' SFZs are in — which regions and
 * therefore which slice each note triggers.  Registering those slices with the loader, each with
 * the time it is needed, is what drives the download order.
 *
 * Output: time-sorted `events` of kinds
 *   note   {t, t1, channel, program, key, vel, parts: [{region, slice}]}
 *   volume {t, channel, gain}      CC7 x CC11
 *   pan    {t, channel, pan}       CC10, -1..1
 *   bend   {t, channel, cents}     pitch bend through the channel's RPN 0 range (default 2 semitones)
 * plus `bendsByChannel` for voices to follow, `duration`, and the program ids used.
 */
export async function compileSong(parsed, loader) {
  const { events } = parsed;
  // held: per key, the notes not yet released, oldest first.  A key re-struck before its note-off
  // (common in scored MIDI: repeated notes written to overlap) keeps both sounding, and each
  // note-off releases the oldest — matching one held note per key would release the new note
  // early and leave the last one of a phrase hanging until the song ends
  const ch = Array.from({ length: 16 }, () => ({ program: 0, bank: 0, volume: 100, expression: 127, pan: 64, pedal: false,
                                                  bendRange: 2, rpn: null, held: new Map(), sustained: [] }));
  const push = (c, key, n) => { if (!c.held.has(key)) c.held.set(key, []); c.held.get(key).push(n); };
  const shift = (c, key) => { const l = c.held.get(key); if (!l || !l.length) return null; const n = l.shift(); if (!l.length) c.held.delete(key); return n; };
  const out = [];
  const bendsByChannel = Array.from({ length: 16 }, () => []);
  const progOf = (c, i) => (i === 9 || c.bank === 127 ? 'drums' : String(c.program));
  const release = (n, t) => { n.t1 = t; };
  for (const e of events) {
    const c = ch[e.channel ?? 0];
    switch (e.type) {
      case 'program': c.program = e.program; break;
      case 'on': {
        const n = { kind: 'note', t: e.time, t1: null, channel: e.channel, program: progOf(c, e.channel), key: e.key, vel: e.vel };
        push(c, e.key, n);
        out.push(n);
        break;
      }
      case 'off': {
        const n = shift(c, e.key);
        if (n) { if (c.pedal) c.sustained.push(n); else release(n, e.time); }
        break;
      }
      case 'cc':
        if (e.cc === 0) c.bank = e.value;
        else if (e.cc === 7 || e.cc === 11) {
          if (e.cc === 7) c.volume = e.value; else c.expression = e.value;
          out.push({ kind: 'volume', t: e.time, channel: e.channel, gain: (c.volume / 127) * (c.expression / 127) });
        } else if (e.cc === 10) {
          c.pan = e.value;
          out.push({ kind: 'pan', t: e.time, channel: e.channel, pan: Math.max(-1, Math.min(1, (e.value - 64) / 63)) });
        } else if (e.cc === 64) {
          c.pedal = e.value >= 64;
          if (!c.pedal) { for (const n of c.sustained) release(n, e.time); c.sustained = []; }
        } else if (e.cc === 101 || e.cc === 100) {
          c.rpn = c.rpn || [0, 0]; c.rpn[e.cc === 101 ? 0 : 1] = e.value;
        } else if (e.cc === 6 && c.rpn && c.rpn[0] === 0 && c.rpn[1] === 0) {
          c.bendRange = e.value;
        } else if (e.cc === 120 || e.cc === 123) {
          for (const l of c.held.values()) for (const n of l) release(n, e.time);
          for (const n of c.sustained) release(n, e.time);
          c.held.clear(); c.sustained = [];
        }
        break;
      case 'bend': {
        const cents = (e.value / 8192) * c.bendRange * 100;
        out.push({ kind: 'bend', t: e.time, channel: e.channel, cents });
        bendsByChannel[e.channel].push({ t: e.time, cents });
        break;
      }
      default: break;
    }
  }
  const end = parsed.duration;
  for (const c of ch) { for (const l of c.held.values()) for (const n of l) release(n, end); for (const n of c.sustained) release(n, end); }
  out.sort((a, b) => a.t - b.t);
  // programs, then regions and slices
  const notes = out.filter((e) => e.kind === 'note');
  const programs = [...new Set(notes.map((n) => n.program))];
  const progs = new Map(await Promise.all(programs.map(async (p) => [p, await loader.program(p === 'drums' ? 'drums' : Number(p))])));
  loader.clearUses();
  let unmapped = 0;
  for (const n of notes) {
    const prog = progs.get(n.program);
    n.parts = [];
    if (!prog) continue;
    const bySlice = new Map();
    for (const r of loader.regionsFor(prog, n.key, n.vel)) {
      if (!bySlice.has(r.slice)) bySlice.set(r.slice, []);
      bySlice.get(r.slice).push(r);
    }
    for (const [slice, regions] of bySlice) { n.parts.push({ slice, regions }); loader.want(slice, n.t); }
    if (!n.parts.length) unmapped++;
  }
  const slices = new Set(notes.flatMap((n) => n.parts.map((p) => p.slice)));
  const bytes = [...slices].reduce((a, s) => a + (s.b1 - s.b0), 0);
  return { events: out, bendsByChannel, duration: end, programs, notes: notes.length, unmapped, slices: slices.size, bytes };
}
