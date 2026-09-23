# kobi_soundbank — uncompressed sources

Pulled 2026-09-04 into `uncompressed/` (original archives kept in
`archives/`).  Priority for covering a GM program: VCSL, then
FreePats, then Karoryfer, then VSCO 2 (added for the orchestra none of the first three has).  Everything below may be redistributed in a derived, compressed library;
CC BY items need attribution, the one GPL item must be left out of a CC BY release.  What the banks are built from
now (the swipe picks included), with every author and licence, is in [ATTRIBUTION.md](ATTRIBUTION.md).

| source | size | samples | license | notes |
|---|---|---|---|---|
| VCSL (Versilian Community Sample Library) | 5.8G | 4231 wav | CC0 1.0 (`VCSL/LICENSE`) | git working tree of sgossner/VCSL; no SFZ files, folder-per-instrument WAV |
| FreePats | 2.2G | 3682 flac, 474 wav, 114 sfz | CC0 1.0 for every bank except the three below | 72 banks from 36 pages; SFZ+FLAC variant where offered |
| Karoryfer free sets | 12G | 22538 wav, 13474 flac, 1972 sfz | CC0 1.0 (LICENSE in 25 sets; the other 5 confirmed CC0-1.0 from their sfzinstruments repositories: Bear Sax, HorsePulse, Squidpipes, Sneakybass, The Hat With The Phat) | 30 sets |
| VSCO 2 Community Edition | 3.0G | 3168 wav | CC0 1.0 (`VSCO2/LICENSE`) | git working tree of sgossner/VSCO-2-CE, pulled 2026-09-04 as the fourth source for the orchestra: solo violin, violin/viola/cello sections, solo contrabass, trumpet, tenor trombone, F horn, tuba, flute, piccolo, oboe, clarinet, bassoon, harp, timpani, glock, marimba, xylophone; recorded by Sam Gossner and Simon Dalzell |
| University of Iowa MIS | 750M | 997 aif | "may be used for any projects, without restrictions" (`Iowa/LICENSE.txt`) | 2014 stereo re-recordings, ff only, one note per file: Bb trumpet (vib / novib), tenor and bass trombone, horn, tuba; violin, viola, cello, double bass (arco and pizzicato, every note on every string). Pulled 2026-09-05 as the fifth source, first for solo brass and solo strings |

## FreePats exceptions (everything else on freepats.zenvoid.org states "Creative Commons CC0 1.0 public domain dedication")

| bank | license | action |
|---|---|---|
| Piano/SalamanderGrandPiano (Alexander Holm) | CC BY 3.0 | attribute; only the SFZ+FLAC V3+20200602 variant kept |
| Percussion/MuldjordKit | CC BY 4.0 | attribute |
| Guitar/FSS-SteelStringGuitar, -small | GNU GPL | exclude from a CC BY release (use SpanishClassicalGuitar CC0 / Karoryfer guitars instead) |
| SoundSets/FreePatsGM, FreePatsGM-Percussion | CC0 + GPL bundle | do not use as a set; the individual CC0 banks are already here |
| ElectricGuitar/FingerBassYR, PickedBassYR (Yamaha RBX, Andrea Biasior) | Creative Commons CC0 1 | |

## Octave conventions (see PITCH_AUDIT.md, produced by `python3 -m kobi.pitch_audit`)

File names and even SFZ maps disagree about which octave a note name means, so every candidate in
`kobi/gm_map.py` carries an `octave` correction verified by pitch detection: most VCSL instruments
name notes one octave low (Steinway B, the TX81Z FM piano, the pipe organ and the concert harp do
not; the Clavisynth is two octaves low); VSCO 2 sections and brass are one octave low, its solo
violin is not; Karoryfer's Pastabass, Sneakybass, Growlybass and Black-and-Blue maps are written an
octave up and its Bigcat cello an octave down.

## What each source is good for in a GM bank

* VCSL: pianos (Steinway B, Kawai), uprights, five harpsichords, concert and folk harp, harmonicas,
  recorders, ocarinas, saxello and tenor sax, pipe and renaissance organ, kalimba/mbira/balafon,
  glockenspiel/marimba/vibraphone/xylophone/tubular bells, timpani, congas/bongos/darbuka, drums;
  TX81Z FM piano and clavisynth.
* FreePats: nylon and (GPL) steel guitars, ukulele, clean/distorted electric guitars, electric
  basses, accordion, organ emulations, clarinet, tenor sax, bagpipe, kalimba, jaw harp, hang,
  the whole GM synth block (leads, pads, brass, strings, bass, effects), synthesizer percussion,
  world percussion, Salamander and Upright KW pianos.
* Karoryfer: bass guitars (Black and Blue, Growly, Meat, Pasta, Swag, Fashion, Big Little, Ergo
  electric upright, Sneakybass double bass), electric guitars (Emily, Shiny, Black and Green),
  saxes (Bear Sax, Weresax), War Tuba, cello, choir-ish (272 Merry Orks), synths (Caveman
  Cosmonaut, Cowsynth, String Cyborgs), drum kits (Big Rusty, Swirly, Unruly, Frankensnare).

## Not pulled, and why

FluidR3 (MIT, complete GM) — you preferred the sources above; still installed at
/usr/share/sounds/sf2/FluidR3_GM.sf2 as a fallback for any program left uncovered.
GeneralUser GS, Arachno, Roland SC-55 soundfonts, Philharmonia: not redistributable.
The SSO-derived dctjoin library: Westlund's SSO is CC Sampling Plus 1.0 with Philharmonia and
unknown-provenance sources inside; keep it as a separate pack or replace with VSCO 2 CE (CC0).

## Pulled on demand by the swipe app (`python3 -m kobi.swipe`)

Alternatives for disliked programs, fetched piece by piece into `uncompressed/Extra/<id>/` (Iowa instruments
into `uncompressed/Iowa/<name>/`): a preview pulls only the SFZ text and the samples its phrase plays; a pick
pulls the rest of that one instrument.  The list lives in `kobi/swipe/libraries.py`.

| id | library | licence | where |
|---|---|---|---|
| Discord-GM | Discord SFZ GM Bank | CC0 / CC BY, per instrument (stated in each SFZ) | github sfzinstruments/Discord-SFZ-GM-Bank |
| SplendidGrandPiano | Splendid Grand Piano (Akai) | Public Domain | github sfzinstruments/SplendidGrandPiano |
| HeadroomPiano | Headroom Piano (Bengt Nilsson) | CC BY 4.0 | github sfzinstruments/BengtNilsson.HeadroomPiano |
| OsirisPiano | Osiris Piano (Versilian + Karoryfer) | CC0 1.0 | github sfzinstruments/Osiris_Piano |
| GregSullivan-EPianos | CP80, Pianet T, Wurlitzer (Greg Sullivan) | CC BY 3.0 | github sfzinstruments/GregSullivan.E-Pianos |
| Smolken-DoubleBass | D. Smolken's double bass | CC0 1.0 | github sfzinstruments/dsmolken.double-bass |
| Erhu, CitharaBarbarica, HungarianZither, Ganjo | erhu, medieval lyre, zither, guitar banjo | CC0 1.0 | github sfzinstruments |
| Kay5StringBanjo | Kay 5-string banjo (Flame Studios) | GPL 3.0 or later | github sfzinstruments/FlameStudios.Kay5StringBanjo |
| EtherealwindsHarp | Etherealwinds Harp II CE (Versilian) | CC0 1.0 | versilian-studios.com zip |
| MTG-SoloSax | soprano, alto, tenor, baritone sax (MTG) | CC BY 4.0 | github sfzinstruments/MTG.SoloSax |
| IxoxFlute | Ixox flute | CC BY 4.0 | github sfzinstruments/Ixox.Flute |
| JLearman-SteelDrum | tenor steel drum (Jeff Learman) | Unlicense | github sfzinstruments/jlearman.SteelDrum |
| MSLP-Vibes | MSLP vibes | CC BY 3.0 | bandshed.net zip |
| BodyPercussion, LegatoVocal | body percussion, a sung legato voice | CC0 1.0 | github sfzinstruments |
| GTownChurch | G-Town Church Sampling Project | CC Sampling Plus 1.0 | github sfzinstruments/GTownChurchSamplingProject |
| EthanWiner | Ethan Winer collection | Public Domain | github sfzinstruments/EthanWiner.Soundfonts |
| VirtuosityDrums, DRSKit, MuldjordKit-sfz, NakedDrums, SamsSonor, SMDrums | drum kits | CC0 / CC BY 4.0 / CC BY-SA 4.0 / PD | github sfzinstruments |
| Iowa-* | flute, alto and bass flute, oboe, E♭ / B♭ / bass clarinet, bassoon, soprano and alto sax, marimba, vibraphone, xylophone, bells, crotales (2014 stereo) | unrestricted | theremin.music.uiowa.edu zips |
| ClassicalAcousticGuitar | "Classical Acoustic Guitar" SFZ + WAV (2018 zip, no author, readme or licence) | unknown: check before shipping | copied from a local download (2026-09-22) into `uncompressed/Extra/ClassicalAcousticGuitar`; the nylon guitar (24) by request |

Left out: NC-licensed sets (jRhodes3c/3d, Rickenbacker 4001, MF Tin Whistle), the sfzinstruments repositories
that state no licence (Clavecin, OrgueEglise, OvationGuitar, Terkelsen, Kastendieck steel drum, Krumhorn,
DamiensFunkyGuitar, PickedLapharp, TicTokMen), Maestro Concert Grand (copyright, free to pass on only) and
anything behind Google Drive or a torrent.

## General MIDI soundfonts (added for the second look, 2026-09-22)

Copied into `uncompressed/SF2/`; the swipe app extracts a preset to SFZ + WAV in `uncompressed/Extra/<id>/`
(`kobi/swipe/sf2.py`) the first time a card needs it.  Every program gets its GM counterpart, and the GS
variation banks give further versions — the only open source here for the synth leads, pads and effects.

| id | soundfont | licence | notes |
|---|---|---|---|
| FluidR3-GM | FluidR3_GM.sf2 (Frank Wen), 189 presets | MIT | from the Ubuntu fluid-soundfont-gm package |
| MS-Basic | MS_Basic.sf2 (MuseScore), 309 presets incl. variation banks | MIT | MuseScore's successor to MuseScore_General |
| TimGM6mb | TimGM6mb.sf2 (Tim Brechbill), 136 presets | GPL 2.0 | small; copyleft, ranked after the MIT ones |
| A320U | A320U.sf2, "Airfont 320 update" (Milton Paredes, 2005), 325 presets | GPL 2.0 or later (stated in the file's INFO) | added 2026-09-23 for Voice Oohs, asked for by name; bank 127 is an MT-32 map, so its presets land on the wrong GM programs |

Left out: the other soundfonts on this machine (game rips, SC-55 rips, Arachno, GeneralUser GS) are not
redistributable; drolez's CC0 Minifreak / Wavestate pads sit behind a Patreon login.

## Made here (`uncompressed/Extra/Derived/`)

Versions asked for in notes, built from the libraries above and licensed as their sources: the Iowa viola
with its samples starting 40 / 90 ms past the bow's onset (12 ms fade-in), and layered stacks (recorder +
overblown flute; Fake Glass Harmonica + FreePats Glass with a 300 ms echo; A320U Solo Vox 70% right + Voice
Oohs 70% left).  A picked stack goes into gm_map.LAYERS; its echo is previewed with the SFZ `delay` opcode but
not built into the bank.  kobi.compress marks each layer's regions (`// layer:`) and kobi.balance evens notes
within a layer, so the layers keep the balance they were stacked (and previewed) at.

Soundfont presets are resampled before stacking: a GM soundfont's samples are a few hundred ms on a tiny loop,
shaped by a filter the bank's players do not have, and too short for kobi.compress to loop (they fall back to
a plain transcode — Pad 1's FluidR3 Fantasia has 14 ms notes for that reason).  `make='resample'` plays the
preset through sfizz every 3 keys (24–96), 4 s at velocity 127, pan removed, and keeps each note as a WAV.
The soundfont picks that had compressed to blips (Synth Brass 1 = FluidR3 Synth Brass 3, Lead 2 = FluidR3 Saw Wave,
Lead 4 = MS Basic Chiffer Lead, Pad 1 = FluidR3 Fantasia, FX 1 = FluidR3 Ice Rain) are resampled the same way but in
stereo (their own pan kept) and with 1.5 s after the note-off, so their release is measured too.

