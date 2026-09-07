import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseSfz, regionParams, oggSampleRate } from '../kobi-player.js';
import { parseMidi, MidiPlayer } from '../kobi-midi.js';

test('parseSfz merges hierarchy and reads values with spaces', () => {
  const { control, global, regions } = parseSfz(`// comment
<control> default_path=../000 Piano/ set_hdcc72=0.35
<global> volume=11.0
<group> ampeg_release=0.3
<region> sample=a b.ogg pitch_keycenter=60 lokey=58 hikey=61 lovel=1 hivel=84 tune=19 loop_start=22050 loop_end=46541 volume=-3.20 ampeg_hold=0.351 ampeg_decay=5.9 ampeg_sustain=0 ampeg_release_oncc72=2 loop_mode=loop_continuous
<region> sample=hit.ogg key=38 pitch_keytrack=0 loop_mode=one_shot lovel=65 hivel=106 volume=18.59 pan=-40`);
  assert.equal(control.default_path, '../000 Piano/');
  assert.equal(global.volume, '11.0');
  assert.equal(regions.length, 2);
  assert.equal(regions[0].sample, 'a b.ogg');
  assert.equal(regions[0].ampeg_release, '0.3');
  const p = regionParams(regions[0], control);
  assert.deepEqual([p.keycenter, p.lokey, p.hikey, p.lovel, p.hivel, p.tune, p.volumeDb], [60, 58, 61, 1, 84, 19, -3.2]);
  assert.deepEqual(p.loop, { start: 22050, end: 46541 });
  assert.equal(p.decay, 5.9);
  assert.equal(p.sustain, 0);
  assert.ok(Math.abs(p.release - (0.3 + 2 * 0.35)) < 1e-9);     // base + oncc72 * hdcc72
  const d = regionParams(regions[1], control);
  assert.deepEqual([d.lokey, d.hikey, d.keycenter, d.keytrack, d.oneShot, d.loop], [38, 38, 38, 0, true, null]);
  assert.ok(Math.abs(d.pan + 0.4) < 1e-9 && p.pan === 0);
});

test('regionParams reads a packed region (offset / end)', () => {
  const { regions } = parseSfz('<region> sample=pack.ogg pitch_keycenter=60 lokey=60 hikey=60 lovel=1 hivel=127 ' +
    'loop_mode=loop_continuous loop_start=124100 loop_end=146000 ampeg_release=0.4 offset=102050 end=168000');
  const p = regionParams(regions[0], {});
  assert.equal(p.offset, 102050);
  assert.equal(p.end, 168000);
  assert.deepEqual(p.loop, { start: 124100, end: 146000 });
  const plain = regionParams(parseSfz('<region> sample=a.ogg key=60').regions[0], {});
  assert.equal(plain.offset, 0);
  assert.equal(plain.end, null);
});

test('oggSampleRate finds the vorbis identification header', () => {
  const bytes = new Uint8Array(64);
  bytes.set([0x4f, 0x67, 0x67, 0x53], 0);                                        // OggS
  bytes.set([0x01, 0x76, 0x6f, 0x72, 0x62, 0x69, 0x73], 28);                     // \x01vorbis
  new DataView(bytes.buffer).setUint32(28 + 12, 48000, true);
  assert.equal(oggSampleRate(bytes.buffer), 48000);
  assert.equal(oggSampleRate(new Uint8Array(32).buffer), null);
});

function buildMidi() {
  // format 0, 480 ticks per beat; tempo 120 -> 500000 us/beat; program change, two notes, a CC, running status
  const trk = [
    0x00, 0xff, 0x51, 0x03, 0x07, 0xa1, 0x20,       // tempo 500000
    0x00, 0xf0, 0x05, 0x7e, 0x7f, 0x09, 0x01, 0xf7, // SysEx (GM reset), 5 bytes: must not shift the cursor
    0x00, 0xc0, 0x38,                               // program 56 on channel 1
    0x00, 0xb0, 0x07, 0x64,                         // CC7 = 100
    0x00, 0x90, 0x3c, 0x64,                         // note on 60 vel 100 at tick 0
    0x83, 0x60, 0x3c, 0x00,                         // running status: note on vel 0 (= off) at +480 ticks (1 beat)
    0x00, 0x99, 0x26, 0x7f,                         // drums: snare
    0x60, 0x89, 0x26, 0x40,                         // note off at +96 ticks
    0x00, 0xff, 0x2f, 0x00,                         // end of track
  ];
  const head = [0x4d, 0x54, 0x68, 0x64, 0, 0, 0, 6, 0, 0, 0, 1, 0x01, 0xe0];
  const th = [0x4d, 0x54, 0x72, 0x6b, 0, 0, 0, trk.length];
  return new Uint8Array([...head, ...th, ...trk]).buffer;
}

test('parseMidi times events through the tempo map and resolves running status', () => {
  const { division, events, duration } = parseMidi(buildMidi());
  assert.equal(division, 480);
  const types = events.map((e) => e.type);
  assert.deepEqual(types, ['tempo', 'program', 'cc', 'on', 'off', 'on', 'off']);
  const off = events[4];
  assert.ok(Math.abs(off.time - 0.5) < 1e-9);                     // one beat at 120 bpm
  assert.equal(events[1].program, 56);
  assert.equal(events[5].channel, 9);
  assert.ok(Math.abs(duration - 0.6) < 1e-9);                     // + 96 ticks = 0.1 s
  assert.deepEqual(MidiPlayer.programsUsed(events).sort(), ['56', 'drums']);
});
