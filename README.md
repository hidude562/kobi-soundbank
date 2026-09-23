# kobi soundbank

A General MIDI soundbank — 128 programs and a drum kit — built from CC0 sample libraries
(VCSL, FreePats, Karoryfer, VSCO 2 CE, University of Iowa MIS; see [SOURCES.md](SOURCES.md)), compressed
with [dctloop / dctjoin](vendor/sfz_compressor) loop resynthesis into SFZ + Ogg Vorbis banks from 92 MB
down to 2.8 MB, and playable in a browser by two dependency-free Web Audio players.

## Banks

| `kobi_ogg` | 92.3 MB | 44.1 kHz | the full bank: 0.5 s loops, Vorbis q1, 44.1 kHz stereo |
| `kobi_slim` | 25.4 MB | 44.1 kHz | the full bank fitted to 25 MB by dropping round robins, velocity layers and keys |
| `kobi_ogg_lite` | 76.1 MB | 44.1 kHz | 0.2 s loops, 0.25 s sustain attacks (decays keep the long cross-fade) |
| `kobi_slim_lite` | 25.1 MB | 44.1 kHz | lite fitted to 25 MB |
| `kobi_ogg_lite25` | 56.5 MB | 44.1 kHz | 0.2 s loops, 0.25 s attacks everywhere |
| `kobi_slim_lite25` | 22.9 MB | 44.1 kHz | lite25 fitted to 25 MB — the most notes of any 25 MB bank |
| `kobi_ultra` | 6.0 MB | 11.025 kHz | lite25 fitted to 5 MB: 11 kHz mono |
| `kobi_ultra_hifi` | 5.2 MB | 22.05 kHz | 5 MB at 22 kHz mono with a single velocity layer |
| `kobi_ultra_hifi_pf` | 2.8 MB | 22.05 kHz | ultra hifi post-filtered: keys every fourth, un-looped strays dropped, cymbals looped, one sample per effect |

Every bank has the same layout: `GM/<nnn> <name>.sfz` and `GM/Drums.sfz`, one packed Ogg per program
addressed with `offset` / `end`, `GM/manifest.json` for the players, and `slices.json` next to each Ogg
so a note can be fetched by HTTP byte range.  `SIZES.md`, `LEVELS.md` and `BALANCE.md` in each bank
report what was kept and how it was levelled.

## Reproduce

```
git clone --recursive https://github.com/hidude562/kobi-soundbank.git && cd kobi-soundbank
python3 -m pip install -r requirements.txt          # plus ffmpeg on the system
# pull the sample libraries into uncompressed/ as described in SOURCES.md
make test                                            # 23 python tests, 8 node tests
make banks finish derive index                       # ~4 h; or `make all`
make demos web-test                                  # optional: sfizz renders of midi/nena, browser tests
```

Paths are resolved by [`kobi/paths.py`](kobi/paths.py) relative to the repository; `KOBI_SOURCES`,
`KOBI_SSO`, `KOBI_DCTJOIN` and `KOBI_MIDIS` override them.

## How a bank is built

1. **Mapping** — `kobi/gm_map.py` names, for every GM program, the candidate instruments in priority
   order with their octave corrections (verified by `kobi.pitch_audit`, see [PITCH_AUDIT.md](PITCH_AUDIT.md));
   `python3 -m kobi.gm_map` writes [MAPPING.md](MAPPING.md).  `kobi/ingest.py` reads a candidate's SFZ or
   folder into a playable view ([INGEST.md](INGEST.md)); `kobi/drums.py` assembles the GM kit.
2. **Compression** — `kobi.compress` runs every note through dctjoin: sustains keep a short attack and a
   harmonic bridge into an untouched loop, decaying notes are flattened, looped and given back their
   decay as stacked SFZ envelopes.  Notes are packed one Ogg per program (`kobi/packing.py`, 100 ms
   pages).  At the end of a build: `release` caps sustain releases at 0.5 s (doubled for the held
   sounds: string ensembles, synth strings, choirs, synth voice, pads), `kit` gives the kit one
   take per hit and the Latin percussion a decay and re-levels each piece to the level `kobi.drums`
   chose for it, `dedupe` makes one note per key and velocity, `extend` gives every pitched program the
   full keyboard (copies of at most 4 keys, so each copy's transposition loudness fits).
   **Pitch:** a library's key map is not trusted blindly.  `kobi/pitchcheck.py` reads a note with two
   detectors (pYIN and subharmonic summation) that must agree; a source note they put more than 30
   cents from its map is compressed from the pitch it really has (the Discord GM pizzicato's top files
   sound ~4 semitones above their names), and a replication whose own pitch refinement they put more
   than 20 cents off is corrected (a steel pan's upper modes pull it).  Retuned notes are listed in
   SIZES.md.  Bells, timpani, the orchestra hit, the fifths lead, percussion and effects are exempt.
3. **Levels** (`make finish`) — `balance` brings every note of a program to the program's loudness,
   `levels` brings every program to −23 LUFS, `extend` re-fills the map.
4. **Derivation** — `slim` fits a bank to a size target by dropping round robins, velocity layers and
   keys and, if needed, lowering codec quality, channels and rate; `postfilter` applies stronger musical
   rules for the smallest bank.  `slices` and `manifest` write what the players need.  A stacked
   program keeps every layer through `balance`, `extend` and `slim` (`// layer:` lines), and thinned
   velocity layers always keep the one velocity 100 plays.
5. **Audit** — `python3 -m kobi.audit kobi_slim` renders every key of every pitched program and every
   kit piece at velocity 100 (sfizz, freewheeling) and writes AUDIT.md: pitch per note (off past 35
   cents), loudness per note and per program.

## Web players

`kobi_web/` holds two players (see [kobi_web/README.md](kobi_web/README.md)):

* **kobi-player.js** — an instrument: programs load on demand, live `noteOn` / `noteOff`, a MIDI file
  player, Web MIDI input.
* **sched/** — a song engine: a MIDI file is compiled to a timeline and each note's sample is fetched
  by byte range in the order the song needs it, within a decoded-RAM budget, with fallbacks
  ([kobi_web/sched/README.md](kobi_web/sched/README.md)).

`make serve` then http://localhost:8080/kobi_web/ or http://localhost:8080/kobi_web/sched/.  Any
static server works, but one that honours `Range` (nginx, GitHub Pages, S3 — not `python -m http.server`)
lets the song engine fetch notes instead of programs.

## Swipe app: judging the sounds

`python3 -m kobi.swipe` (or `make swipe`) serves a card deck at http://localhost:8791/: one card per GM program
and the kit.  A card starts on the program's sound as the slim bank plays it (the microscopic bank and the
uncompressed source a tap away); **space** (or a tap on the card) cycles through the same instrument from
other banks and libraries: gm_map's own fallbacks, every other instrument in the pulled libraries whose name
says it can play the program, and free SFZ libraries online (the sfzinstruments repositories, the Discord GM
bank, more Iowa MIS instruments, Versilian's harp, MSLP vibes; see [SOURCES.md](SOURCES.md)).  **→** (swipe
right) takes the version playing, **←** none of them, **↓** decides later, **↑** goes back to the previous
instrument, Enter replays, holding C plays the bank's version at the same place.

Remote instruments arrive a few samples at a time: the SFZ text first, then only the samples the preview
phrase plays (a GitHub file, or one member of a zip read over HTTP `Range`), one stream at a time and capped
at `--max-rate` MB/s, so a card costs 1–7 MB rather than a whole library.  The whole instrument (not the
library) is fetched only once it is picked.  Downloads land in `uncompressed/Extra/<library>/` and
`uncompressed/Iowa/`, the app's state and rendered previews in `uncompressed/_swipe/`.  Every preview is
levelled to the same loudness, so the louder of two cards does not win by being louder; folder instruments
get their octave checked by pitch detection the way `kobi.audition` does.

Picks are written to `SWIPE_PICKS.json` / `SWIPE_PICKS.md`.  Once a pick's samples are all on disk,
`kobi.gm_map` puts it first for its program, so the next `make banks` builds with it
(`KOBI_SWIPE_PICKS=0` reads the map as written).  `--host 0.0.0.0` makes the deck reachable from a phone.

## Licence

The code in `kobi/` and `kobi_web/` is MIT, see [LICENSE](LICENSE).  The banks are collections of independently
licensed instruments: [ATTRIBUTION.md](ATTRIBUTION.md), written by `python3 -m kobi.attribution` (part of `make index`,
which also puts a copy in every built bank), lists each program's library, author and licence, and the credits and
notices the CC BY, CC BY-SA, CC Sampling Plus, MIT and GPL ones ask for.  Most programs come from CC0 or
unrestricted libraries (VCSL, VSCO 2 CE, FreePats, Karoryfer, the University of Iowa samples).

As mapped from the current swipe picks, a public release of a bank needs, first: the nylon guitar replaced or its
licence found (it came with none); the Sonatina Symphonic Orchestra programs checked (CC Sampling Plus 1.0, with
Philharmonia and unknown-provenance recordings inside the set); the FreePats steel-string guitar and the A320U voices
distributed under the GPL; and the Sam's Sonor kit shared alike (CC BY-SA 4.0).  See [SOURCES.md](SOURCES.md) for
where every library came from.
