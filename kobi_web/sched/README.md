# kobi scheduler

A second playback engine for the kobi banks, built for songs rather than live playing: a MIDI file
is compiled to a timeline, and every note's sample is fetched by **byte range** from the bank in the
order the song needs it.  RAM is bounded, and a note whose sample has not arrived plays the closest
loaded stand-in instead of nothing.

```
kobi_web/sched/
  kobi-ogg.js       Ogg page parsing, CRC, splice: header pages + a note's pages -> a valid small Ogg
  kobi-loader.js    SliceLoader: per-note fetch queue by priority, decode window, decoded-RAM budget, fallbacks
  kobi-song.js      compileSong: MIDI events -> notes with their regions / slices, channel volume, pan, bend
  kobi-engine.js    KobiEngine: load / play / pause / seek / stop, tick scheduler, voices, offline render
  index.html        demo with a readiness strip and live loader statistics
kobi_web/test/
  sched.test.mjs    node: CRC and splice against a real file, priority rules, fallback choice, compilation, retries
  splice_browser.py Chromium: a Range-fetched slice decodes bit-identically to the whole file
  sched_browser.py  Chromium: a demo MIDI in real time (bytes, RAM, fallbacks) and offline against sfizz
  songs_browser.py  Chromium: a run of songs through one engine, each reaching full readiness
  dropout_browser.py Chromium: the network drops mid-fetch and comes back; every note still arrives
  rangeserver.py    a static server that honours Range requests (python -m http.server does not)
```

## How a note is fetched

A packed program is one Ogg Vorbis file whose notes the SFZ addresses with `offset` / `end`.
`kobi.slices` (Python, build time) writes `slices.json` next to each file: for every note, the byte
range of the Ogg pages that hold it plus one page of decoder warm-up, and the granule positions
that say which absolute samples that run decodes to.  The client prepends the file's header pages
(fetched once, ~3.5 KB), renumbers the page sequence, flags end-of-stream, recomputes the CRCs and
hands the result to `decodeAudioData`.  Vorbis decoding is deterministic, so the decoded slice is
**bit-identical** to the same span of the whole file (`splice_browser.py` checks this).

Pages are written 0.1 s long (`packing.PAGE_S`) so a note fetch is about 1.3x the note's own bytes
rather than 3x with ffmpeg's default 1 s pages; that costs 2.4 % of the bank.  If the server ignores
`Range` the first response comes back whole (HTTP 200); the loader keeps it and slices locally, so
everything still works — it just downloads programs instead of notes.

The connection can drop mid-song.  A request that fails for want of a network (or stalls past
`RETRY.stallMs`, or gets a 5xx / 429) puts its note back in the queue and pauses new requests — 1 s,
doubling to 15 s while they keep failing — rather than running the whole queue into failures; the
browser's `online` event (or `loader.resume()`) ends the pause at once, and `summary.paused` says a
pause is on.  Only a 4xx other than 408 / 429 gives a note up: that file is not in the bank.  The
manifest, SFZs and slice indexes are retried a few times too.  A loader whose AudioContext has been
closed stops, so a player a page threw away does not wake up on `online`.

## Priority

Every registered slice has the times the song uses it.  Lower is fetched first:

```
priority = seconds until next use
         - 60  if its pitched program has nothing loaded yet   (one sample per instrument first,
                                                               so later notes have something to transpose)
         - 10  if nothing loaded is within a fifth of its key
         + 20  if its key already has another velocity layer loaded (that layer can stand in)
```

Four fetches run in parallel and the queue is re-ranked every tick as playback moves.  Compressed
bytes are kept (they are small); decoding happens only within `decodeAhead` seconds of use, and the
decoded set is capped at `maxDecodedBytes` (48 MB by default), evicting what is needed furthest
away.  Slices due within the next ~second are always decoded and never evicted, and a buffer a
voice is playing is held by the audio graph regardless, so the budget bounds *pre-decoded* audio;
`status.pinnedBytes` reports the rest.

A page lasts a sitting rather than a file, so the loader keeps every decoded slice in `decoded`, not
just the current song's: when a new song is compiled the previous one's slices leave `slices` but
keep their buffers, and eviction — furthest need first, which puts them first since they are no
longer due — reclaims them under pressure.  A song returned to soon is therefore still in memory,
and its compressed bytes are kept either way, so replaying costs no network.

## Fallback

At note time, if the slice is not decoded: another velocity layer of the same key, else (pitched
programs) the nearest decoded key within an octave, transposed.  Counted in `status.fallbacks`; a
note with nothing to stand in is `missed` (a key the bank has no region for at all is `unmapped`).

## Use

```js
import { KobiEngine } from './kobi-engine.js';
const engine = new KobiEngine('../../kobi_slim/', { maxDecodedBytes: 32e6, polyphony: 64 });
const info = await engine.load(await file.arrayBuffer());   // { duration, programs, notes, slices, bytes }
await engine.play();          // waits up to prerollTimeout for the first `preroll` seconds to be decoded
engine.pause(); engine.resume(); engine.seek(60); engine.stop();
engine.status                 // fetched, ready, bytes, decodedBytes, pinnedBytes, voices, fallbacks, missed …
const { buffer } = await KobiEngine.renderOffline('../../kobi_slim/', bytes, { seconds: 30 });
```

Compared with `kobi-player.js`: no live `noteOn`; channel pan (CC10), pitch bend with RPN range, and
smooth CC7 / CC11 are honoured; stacked decay regions share one source; voices that decayed to
silence are stopped; polyphony is capped by stealing the voice that was about to end anyway.

## Serve

```
python3 kobi_web/test/rangeserver.py 8080        # from the repository root (or: make serve)
# http://localhost:8080/kobi_web/sched/
```
