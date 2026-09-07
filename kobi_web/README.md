# kobi web player

A dependency-free ES-module player for the kobi SFZ banks in the browser.  Programs load on
demand: the first request for a program fetches its SFZ and the dozen Ogg files it references,
later requests reuse them.  Nothing else is downloaded, so a page that uses three instruments
costs three instruments.

```
kobi_web/
  kobi-player.js     KobiBank: manifest, lazy program loading, voices, envelopes
  kobi-midi.js       parseMidi + MidiPlayer: Standard MIDI File playback through a KobiBank
  index.html         demo: program list, on-screen keys, Web MIDI input, MIDI file playback
  test/              node parser tests, Playwright browser smoke test
  sched/             a second engine for songs: schedule-only playback that fetches each note's sample by
                     byte range as the song needs it, with a decoded-RAM budget — see sched/README.md
```

## Serve

The player fetches the bank over HTTP from a folder that holds `GM/manifest.json`
(`kobi_slim/` or `kobi_ogg/` here).  Serve the repository root so both are reachable:

```
cd /home/nathan/kobi_soundbank
python3 -m http.server 8080
# http://localhost:8080/kobi_web/            -> slim bank (24 MB)
# http://localhost:8080/kobi_web/?bank=../kobi_ogg/   -> compressed bank (130 MB)
```

## Use

```js
import { KobiBank } from './kobi-player.js';
import { MidiPlayer } from './kobi-midi.js';

const bank = new KobiBank('../kobi_slim/');       // creates an AudioContext (or pass {context})
await bank.load(56);                              // trumpet: one SFZ + its samples, once
const h = bank.noteOn(56, 67, 100);               // program, key, velocity -> handle
bank.noteOff(h);                                  // or bank.noteOff(56, 67)
bank.noteOn('drums', 38, 110);                    // General MIDI drum keys 35..81
bank.stats;                                       // { programs, bytes, voices }

const player = new MidiPlayer(bank);
await player.load(await file.arrayBuffer());      // parses, loads only the programs the file uses
player.onprogress = (t, duration) => {};
player.play();  player.stop();
```

The master sits at -12 dB, sfizz's own output scale in which the bank was levelled, followed by a
fast compressor as a safety limiter; `new KobiBank(url, { gain, limiter: false })` changes that, and
`bank.master.gain` is the volume control.  `noteOn` accepts `{ when, destination, gain }` for scheduling ahead on the AudioContext clock and
routing a channel through its own gain node.  Browsers need a user gesture before audio starts;
call `bank.ctx.resume()` from a click handler.

## What the player implements

The SFZ subset the kobi build emits: `default_path`, global and region `volume`, `key` /
`lokey` / `hikey` / `pitch_keycenter`, `pitch_keytrack`, `lovel` / `hivel`, `tune`,
`loop_mode` with `loop_start` / `loop_end` (inclusive, in the file's own samples — the Ogg
header's rate is read because `decodeAudioData` resamples), `ampeg_hold` / `decay` / `sustain` /
`release` with sfizz's exp(−9t/T) convention, `ampeg_release_oncc72` scaled by `set_hdcc72`
(the piano damper), `lorand` / `hirand` and `seq_*` round robins.  Velocity maps to gain as
(vel / 127)².  Not implemented: pitch bend, filters, other controllers, keyswitches.

MIDI files: formats 0 and 1, tempo changes, notes, program changes, channel 10 drums, CC 7, 11,
64 (sustain), 120, 123.

## Tests

```
node --test kobi_web/test/*.mjs                    # parsers, envelope maths
python3 kobi_web/test/smoke_browser.py             # headless Chromium: serve, load, play (needs playwright)
python3 kobi_web/test/peaks_browser.py             # headroom: chord + drums + brass stay below full scale
```

## Format notes

Ogg Vorbis decodes natively in Chrome, Firefox and Edge; Safari gained Vorbis-in-Ogg support in
recent versions but older Safari will fail `decodeAudioData` on these files.  A CAF or AAC
variant of the bank would be the fallback there.
