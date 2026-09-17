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
   pages).  At the end of a build: `release` caps sustain releases at 0.5 s, `kit` gives the kit one
   take per hit and the Latin percussion a decay, `dedupe` makes one note per key and velocity,
   `extend` gives every pitched program the full keyboard.
3. **Levels** (`make finish`) — `balance` brings every note of a program to the program's loudness,
   `levels` brings every program to −23 LUFS, `extend` re-fills the map.
4. **Derivation** — `slim` fits a bank to a size target by dropping round robins, velocity layers and
   keys and, if needed, lowering codec quality, channels and rate; `postfilter` applies stronger musical
   rules for the smallest bank.  `slices` and `manifest` write what the players need.

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

## Licence

The bank is a derived work of CC0 libraries and may be redistributed; two items need attribution —
the Salamander Grand Piano (CC BY 3.0, Alexander Holm) if the FreePats piano candidate is used, and the
Muldjord kit (CC BY 4.0) — see [SOURCES.md](SOURCES.md).  The code in `kobi/` and `kobi_web/` is MIT, see [LICENSE](LICENSE).
