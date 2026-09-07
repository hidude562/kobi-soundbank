import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { oggCrc, parsePages, spliceOgg, lastGranule } from '../sched/kobi-ogg.js';
import { SliceLoader, PRIORITY } from '../sched/kobi-loader.js';
import { compileSong } from '../sched/kobi-song.js';
import { parseMidi } from '../kobi-midi.js';

const PACK = new URL('../../kobi_ogg/056_Trumpet/pack.ogg', import.meta.url).pathname;   // a built bank, if present

test('oggCrc reproduces the CRC stored in real pages; spliceOgg renumbers and flags EOS', { skip: !existsSync(PACK) }, () => {
  const u8 = new Uint8Array(readFileSync(PACK));
  const pages = parsePages(u8);
  assert.ok(pages.length > 3);
  for (const p of pages.slice(0, 20)) {
    const stored = new DataView(u8.buffer, p.pos + 22, 4).getUint32(0, true);
    assert.equal(oggCrc(u8.subarray(p.pos, p.pos + p.size)), stored);
  }
  const nHeader = pages.findIndex((p) => p.granule > 0);                 // identification, comment + setup pages
  const header = u8.subarray(0, pages[nHeader].pos);
  const b0 = pages[nHeader + 5].pos, b1 = pages[nHeader + 8].pos + pages[nHeader + 8].size, g = pages[nHeader + 8].granule;
  const out = spliceOgg(header, u8.subarray(b0, b1));
  const op = parsePages(out);
  assert.equal(op.length, parsePages(header).length + parsePages(u8.subarray(b0, b1)).length);
  for (let i = 1; i < op.length; i++) assert.equal(op[i].seq, op[i - 1].seq + 1);        // contiguous
  assert.ok(op[op.length - 1].flags & 0x04);                                              // EOS
  assert.equal(op[op.length - 1].granule, g);
  assert.equal(lastGranule(u8.subarray(b0, b1)), g);
  for (const p of op) {
    const stored = new DataView(out.buffer, out.byteOffset + p.pos + 22, 4).getUint32(0, true);
    assert.equal(oggCrc(out.subarray(p.pos, p.pos + p.size)), stored);                  // every CRC valid
  }
});

function fakeLoader() {
  const l = new SliceLoader('file:///bank/', {}, { rng: () => 0.5 });
  const mk = (program, keycenter, lovel, hivel, state = 'idle') => ({ program, keycenter, lovel, hivel, state, uses: [], b0: 0, b1: 1000, regions: [] });
  const prog = { id: '0', pitched: true, slices: new Map(), regions: [], _seq: 0 };
  const add = (s, k) => { prog.slices.set(k, s); return s; };
  l.loaded.set('0', prog);
  return { l, prog, mk, add };
}

test('priority: sooner first, a program with nothing loaded jumps the queue, a second velocity layer waits', () => {
  const { l, mk, add } = fakeLoader();
  const a = add(mk('0', 60, 1, 64), 'a'), b = add(mk('0', 60, 65, 127), 'b'), c = add(mk('0', 72, 1, 127), 'c');
  l.want(a, 5); l.want(b, 2); l.want(c, 20);
  l.time = 0;
  // nothing loaded: every slice of the program gets the FIRST boost, so plain order by time
  assert.ok(l.priority(b) < l.priority(a) && l.priority(a) < l.priority(c));
  assert.equal(l.priority(b), 2 - PRIORITY.FIRST);
  a.state = 'ready';                                  // key 60 soft layer arrived
  assert.equal(l.priority(b), 2 + PRIORITY.LAYER);    // its loud layer can wait: the soft one stands in
  assert.equal(l.priority(c), 20 - PRIORITY.NEIGHBOUR); // key 72 has nothing within a fifth
  const d = add(mk('0', 65, 1, 127), 'd'); l.want(d, 30);
  assert.equal(l.priority(d), 30);                    // a fifth away from key 60: no boost
  assert.equal(l.priority(mk('0', 40, 1, 127)), Infinity);   // never used
});

test('nextUse follows playback and fallbackFor prefers the same key, then the nearest within an octave', () => {
  const { l, mk, add } = fakeLoader();
  const s = add(mk('0', 60, 1, 127), 's'); l.want(s, 1); l.want(s, 9); l.want(s, 4);
  assert.equal(l.nextUse(s, 0), 1); assert.equal(l.nextUse(s, 2), 4); assert.equal(l.nextUse(s, 10), Infinity);
  const soft = add(mk('0', 60, 1, 64, 'ready'), 'soft'), far = add(mk('0', 67, 1, 127, 'ready'), 'far'), near = add(mk('0', 62, 1, 127, 'ready'), 'near');
  assert.equal(l.fallbackFor(s, 60), soft);
  soft.state = 'fetched';
  assert.equal(l.fallbackFor(s, 60), near);
  near.state = 'idle'; far.keycenter = 80;
  assert.equal(l.fallbackFor(s, 60), null);           // 20 semitones: too far to transpose
});

function buildMidi() {
  const trk = [
    0x00, 0xff, 0x51, 0x03, 0x07, 0xa1, 0x20,       // 120 bpm
    0x00, 0xc0, 0x38,                               // program 56
    0x00, 0xb0, 0x0a, 0x00,                         // pan hard left
    0x00, 0xe0, 0x00, 0x60,                         // bend +50% (value 4096)
    0x00, 0x90, 0x3c, 0x64,                         // note 60 on
    0x00, 0xb0, 0x40, 0x7f,                         // pedal down
    0x83, 0x60, 0x90, 0x3c, 0x00,                   // note 60 off at 1 beat (explicit status: the last one was a CC), held by pedal
    0x83, 0x60, 0xb0, 0x40, 0x00,                   // pedal up at 2 beats -> release
    0x00, 0x99, 0x26, 0x7f,                         // drums snare
    0x60, 0x89, 0x26, 0x40,
    0x00, 0xff, 0x2f, 0x00,
  ];
  const head = [0x4d, 0x54, 0x68, 0x64, 0, 0, 0, 6, 0, 0, 0, 1, 0x01, 0xe0];
  const th = [0x4d, 0x54, 0x72, 0x6b, 0, 0, 0, trk.length];
  return new Uint8Array([...head, ...th, ...trk]).buffer;
}

test('compileSong resolves programs, pedal-held releases, pan and bend, and registers slice uses', async () => {
  const parsed = parseMidi(buildMidi());
  assert.ok(parsed.events.some((e) => e.type === 'bend' && e.value === 4096));
  const wants = [];
  const slice = { program: '56', keycenter: 60, state: 'idle', uses: [], b0: 100, b1: 900, regions: [] };
  const region = { slice, lokey: 0, hikey: 127, lovel: 0, hivel: 127, lorand: 0, hirand: 1, seqLength: 1 };
  slice.regions.push(region);
  const loader = {
    program: async (id) => ({ id: String(id), regions: id === 'drums' ? [] : [region], slices: new Map([['x', slice]]), pitched: true, _seq: 0 }),
    regionsFor: (prog, key, vel) => prog.regions.filter((r) => key >= r.lokey && key <= r.hikey),
    clearUses: () => {}, want: (s, t) => wants.push([s, t]),
  };
  const song = await compileSong(parsed, loader);
  assert.deepEqual(song.programs.sort(), ['56', 'drums']);
  const note = song.events.find((e) => e.kind === 'note' && e.program === '56');
  assert.ok(Math.abs(note.t1 - 1.0) < 1e-9, 'released when the pedal lifts, not at note-off');
  assert.deepEqual(wants, [[slice, 0]]);
  assert.equal(song.events.find((e) => e.kind === 'pan').pan, -1);
  assert.ok(Math.abs(song.events.find((e) => e.kind === 'bend').cents - 100) < 1e-9);    // half of the default 2-semitone range
  assert.equal(song.unmapped, 1);                                                          // the drum hit had no regions in this fake bank
  assert.equal(song.bytes, 800);
});
