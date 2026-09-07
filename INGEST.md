# Ingest report

First ingestible candidate per program (see MAPPING.md).  playable = regions a plain note-on reaches (default keyswitch, attack trigger, CC gates at their defaults); rel = release-trigger regions; notes = distinct key centres; vel = most velocity layers on one note; rr = longest round robin; looped = playable regions with loop points; ks = keyswitches in the file.

| # | program | candidate | kind | regions | playable | rel | notes | range | vel | rr | looped | ks | files | MB | format |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | Acoustic Grand Piano | VCSL:Chordophones/Zithers/Grand Piano, Steinway B [NoSus] | decay | 126 | 126 | 0 | 42 | A#0..G#7 | 3 | 1 | 0 | 0 | 126 | 540 | 44.1k 24 2ch wav |
| 1 | Bright Acoustic Piano | VCSL:Chordophones/Zithers/Grand Piano, Kawai [Sustains] | decay | 144 | 144 | 0 | 37 +3 keyless | C1..C8 | 4 | 1 | 0 | 0 | 144 | 444 | 44.1k 16 2ch wav |
| 2 | Electric Grand Piano | VCSL:Electrophones/TX81Z/Piano 1 | decay | 66 | 66 | 0 | 22 | C1..C8 | 3 | 1 | 0 | 0 | 66 | 36 | 44.1k 24 1ch wav |
| 3 | Honky-tonk Piano | VCSL:Chordophones/Zithers/Upright Piano, Knight | decay | 143 | 98 | 45 | 43 +12 keyless | C#1..C8 | 2 | 4 | 0 | 0 | 98 | 373 | 44.1k 24 2ch wav |
| 4 | Electric Piano 1 | VCSL:Electrophones/TX81Z/FM Piano | decay | 66 | 66 | 0 | 22 | C0..C7 | 3 | 1 | 0 | 0 | 66 | 68 | 44.1k 24 1ch wav |
| 5 | Electric Piano 2 | FreePats:ElectricPiano/FM-Piano2 [*.sfz] | decay | 12 | 12 | 0 | 12 | F#1..C7 | 1 | 1 | 0 | 0 | 12 | 9 | 44.1k 24 1ch flac |
| 6 | Harpsichord | VCSL:Chordophones/Zithers/Harpsichord, Flemish | decay | 108 | 54 | 54 | 38 | F#1..C7 | 1 | 1 | 0 | 0 | 54 | 111 | 44.1k 24 2ch wav |
| 7 | Clavinet | VCSL:Electrophones/TX81Z/Clavisynth | decay | 57 | 57 | 0 | 19 | C2..C8 | 3 | 1 | 0 | 0 | 57 | 31 | 44.1k 24 1ch wav |
| 8 | Celesta | SSO:Celeste | decay | 25 | 25 | 0 | 12 +1 keyless | C4..G#7 | 1 | 1 | 0 | 0 | 25 | 5 | 44.1k 16 2ch flac |
| 9 | Glockenspiel | VCSL:Idiophones/Struck Idiophones/Glockenspiel | decay | 18 | 18 | 0 | 7 | G5..C8 | 1 | 1 | 0 | 0 | 18 | 17 | 44.1k 16 2ch wav |
| 10 | Music Box | VCSL:Idiophones/Plucked Idiophones/Kalimba, Kenya | decay | 15 | 15 | 0 | 11 | B3..B5 | 1 | 2 | 0 | 0 | 15 | 22 | 48k 24 2ch wav |
| 11 | Vibraphone | VCSL:Idiophones/Struck Idiophones/Vibraphone | decay | 50 | 50 | 0 | 11 | F3..E6 | 1 | 1 | 0 | 0 | 50 | 99 | 44.1k 16 2ch wav |
| 12 | Marimba | VCSL:Idiophones/Struck Idiophones/Marimba | decay | 30 | 30 | 0 | 10 | F2..C7 | 1 | 1 | 0 | 0 | 30 | 32 | 44.1k 24 2ch wav |
| 13 | Xylophone | VCSL:Idiophones/Struck Idiophones/Xylophone | decay | 48 | 48 | 0 | 8 | G4..C8 | 2 | 1 | 0 | 0 | 48 | 27 | 44.1k 24 2ch wav |
| 14 | Tubular Bells | VCSL:Idiophones/Struck Idiophones/Tubular Bells 1 | decay | 18 | 18 | 0 | 9 | C4..E5 | 2 | 1 | 0 | 0 | 18 | 65 | 44.1k 24 2ch wav |
| 15 | Dulcimer | VCSL:Chordophones/Zithers/Dan Tranh | decay | 115 | 115 | 0 | 16 +19 keyless | B2..B5 | 6 | 5 | 0 | 0 | 115 | 101 | 44.1k 24 1ch wav |
| 16 | Drawbar Organ | FreePats:Organ/DrawbarOrganEmulation [*.sfz] | sustain | 16 | 16 | 0 | 16 | C2..C7 | 1 | 1 | 16 | 0 | 16 | 7 | 44.1k 16 1ch wav |
| 17 | Percussive Organ | FreePats:Organ/PercussiveOrganEmulation [*.sfz] | sustain | 32 | 32 | 0 | 16 | C2..C7 | 1 | 1 | 32 | 0 | 32 | 15 | 44.1k 16 1ch wav |
| 18 | Rock Organ | FreePats:Organ/RockOrganEmulation [*.sfz] | sustain | 32 | 32 | 0 | 16 | C2..C7 | 1 | 1 | 32 | 0 | 32 | 14 | 44.1k 16 1ch wav |
| 19 | Church Organ | VCSL:Aerophones/Edge-blown Aerophones/Pipe Organ [Loud] | sustain | 21 | 21 | 0 | 21 | C1..C6 | 1 | 1 | 0 | 0 | 21 | 45 | 44.1k 16 2ch wav |
| 20 | Reed Organ | VCSL:Aerophones/Edge-blown Aerophones/Renaissance Organ [8'] | sustain | 27 | 27 | 0 | 27 | C2..E6 | 1 | 1 | 0 | 0 | 27 | 57 | 44.1k 24 2ch wav |
| 21 | Accordion | FreePats:Organ/ButtonAccordionHN [PRESET*tuned.sfz] | sustain | 34 | 17 | 17 | 17 | B2..G5 | 1 | 1 | 17 | 0 | 17 | 4 | 44.1k 16 2ch flac |
| 22 | Harmonica | VCSL:Aerophones/Free Aerophones/Harmonica-Hohner-Special20-C [Sustains] | sustain | 9 | 9 | 0 | 9 | C4..C7 | 1 | 1 | 0 | 0 | 9 | 6 | 44.1k 24 1ch wav |
| 23 | Tango Accordion | FreePats:Organ/ButtonAccordionHN [PRESET*tuned.sfz] | sustain | 34 | 17 | 17 | 17 | B2..G5 | 1 | 1 | 17 | 0 | 17 | 4 | 44.1k 16 2ch flac |
| 24 | Acoustic Guitar (nylon) | FreePats:Guitar/SpanishClassicalGuitar [*.sfz] | decay | 48 | 48 | 0 | 48 | G1..C6 | 1 | 1 | 0 | 0 | 48 | 5 | 44.1k 16 1ch flac |
| 25 | Acoustic Guitar (steel) | Karoryfer:Karoryfer.Shinyguitar.v1.002 [acoustic_five.sfz] | decay | 912 | 912 | 0 | 17 | C#2..C6 | 4 | 1 | 0 | 0 | 272 | 223 | 44.1k 24 1ch wav |
| 26 | Electric Guitar (jazz) | FreePats:ElectricGuitar/EGuitarFSBS-jazz [*jazz bridge 2*.sfz] | decay | 120 | 120 | 0 | 19 | C2..C#6 | 2 | 1 | 0 | 0 | 120 | 67 | 48k 24 2ch flac |
| 27 | Electric Guitar (clean) | FreePats:ElectricGuitar/EGuitarFSBS-clean [*clean bridge 2*.sfz] | decay | 120 | 120 | 0 | 19 | C2..C#6 | 2 | 1 | 0 | 0 | 120 | 128 | 48k 24 2ch flac |
| 28 | Electric Guitar (muted) | Karoryfer:Karoryfer_Black_And_Green_Guitars_1000 [05-green_staccato.sfz] | decay | 1128 | 564 | 0 | 47 | E2..D6 | 1 | 4 | 0 | 0 | 188 | 15 | 44.1k 24 1ch wav |
| 29 | Overdriven Guitar | FreePats:ElectricGuitar/EGuitarFSBS-dist1 [*dist1 bridge*.sfz] | decay | 120 | 120 | 0 | 19 | C2..C#6 | 2 | 1 | 0 | 0 | 120 | 313 | 48k 24 2ch flac |
| 30 | Distortion Guitar | FreePats:ElectricGuitar/EGuitarFSBS-dist2 [*dist2 bridge*.sfz] | decay | 120 | 120 | 0 | 19 | C2..C#6 | 2 | 1 | 0 | 0 | 120 | 136 | 48k 24 2ch flac |
| 31 | Guitar Harmonics | FreePats:ElectricGuitar/EGuitarFSBS-clean [*clean bridge 2*.sfz] | decay | 120 | 120 | 0 | 19 | C2..C#6 | 2 | 1 | 0 | 0 | 120 | 128 | 48k 24 2ch flac |
| 32 | Acoustic Bass | Karoryfer:Sneakybass_v1.000 [02-sneakybass_pluck.sfz] | decay | 1040 | 480 | 80 | 37 | C1..C4 | 1 | 4 | 0 | 0 | 296 | 244 | 44.1k 24 2ch wav |
| 33 | Electric Bass (finger) | FreePats:ElectricGuitar/FingerBassYR [*.sfz] | decay | 12 | 12 | 0 | 12 | E1..D#2 | 1 | 1 | 0 | 0 | 12 | 3 | 44.1k 24 1ch flac |
| 34 | Electric Bass (pick) | FreePats:ElectricGuitar/PickedBassYR [*.sfz] | decay | 13 | 13 | 0 | 13 | E1..E2 | 1 | 1 | 0 | 0 | 13 | 3 | 44.1k 24 1ch flac |
| 35 | Fretless Bass | Karoryfer:Karoryfer.Pastabass.v1.101 [fetuccine.sfz] | decay | 256 | 256 | 0 | 16 | E1..C#5 | 4 | 1 | 0 | 0 | 256 | 137 | 44.1k 16 1ch wav |
| 36 | Slap Bass 1 | Karoryfer:Karoryfer.Growlybass.v1.002 [growlybass_angry.sfz] | decay | 388 | 318 | 70 | 19 | C#1..C5 | 5 | 1 | 0 | 0 | 310 | 188 | 44.1k 24 1ch wav |
| 37 | Slap Bass 2 | Karoryfer:Karoryfer.Swagbass.v1.001 [swagbass.sfz] | decay | 305 | 254 | 51 | 27 | A0..C6 | 3 | 5 | 0 | 0 | 254 | 146 | 44.1k 24 1ch wav |
| 38 | Synth Bass 1 | FreePats:Synthesizer/SynthBass1 [*.sfz] | sustain | 15 | 15 | 0 | 15 | E1..C6 | 1 | 1 | 15 | 0 | 15 | 1 | 44.1k 16 1ch flac |
| 39 | Synth Bass 2 | FreePats:Synthesizer/SynthBass2 [*.sfz] | sustain | 9 | 9 | 0 | 9 | C2..C6 | 1 | 1 | 0 | 0 | 9 | 3 | 44.1k 24 1ch flac |
| 40 | Violin | VSCO2:Strings/Solo Violin [Arco Vib] | sustain | 30 | 30 | 0 | 15 | G3..C7 | 2 | 1 | 0 | 0 | 30 | 74 | 44.1k 16 2ch wav |
| 41 | Viola | VSCO2:Strings/Viola Section [susvib] | sustain | 26 | 26 | 0 | 13 | C3..D6 | 2 | 1 | 0 | 0 | 26 | 72 | 44.1k 24 2ch wav |
| 42 | Cello | Karoryfer:Karoryfer_Bigcat_cello.v1.001 [01- Bowed*.sfz] | sustain | 2446 | 140 | 0 | 21 | C2..A8 | 4 | 2 | 0 | 0 | 140 | 94 | 44.1k 24 1ch wav |
| 43 | Contrabass | Karoryfer:Karoryfer.Meatbass.v1.001 [02_arco_3vel.sfz] | sustain | 2304 | 102 | 0 | 17 | A0..A4 | 3 | 2 | 0 | 0 | 102 | 63 | 44.1k 24 1ch wav |
| 44 | Tremolo Strings | VSCO2:Strings/Violin Section [Trem] | sustain | 21 | 21 | 0 | 11 | G3..D6 | 2 | 1 | 0 | 0 | 21 | 35 | 44.1k 16 2ch wav |
| 45 | Pizzicato Strings | VSCO2:Strings/Violin Section [Pizz] | decay | 44 | 44 | 0 | 11 | G3..D6 | 2 | 2 | 0 | 0 | 44 | 9 | 44.1k 16 2ch wav |
| 46 | Orchestral Harp | VCSL:Chordophones/Composite Chordophones/Concert Harp | decay | 45 | 45 | 0 | 23 | E1..F7 | 2 | 1 | 0 | 0 | 45 | 77 | 44.1k 16 2ch wav |
| 47 | Timpani | FreePats:Percussion/Timpani [*.sfz] | decay | 24 | 24 | 0 | 11 | D2..A3 | 1 | 2 | 0 | 0 | 21 | 10 | 44.1k 24 2ch flac |
| 48 | String Ensemble 1 | VSCO2:Strings/Violin Section [susVib] | sustain | 22 | 22 | 0 | 11 | G3..D6 | 2 | 1 | 0 | 0 | 22 | 46 | 44.1k 16 2ch wav |
| 49 | String Ensemble 2 | VSCO2:Strings/Viola Section [susvib] | sustain | 26 | 26 | 0 | 13 | C3..D6 | 2 | 1 | 0 | 0 | 26 | 72 | 44.1k 24 2ch wav |
| 50 | Synth Strings 1 | FreePats:Synthesizer/SynthStrings1 [*.sfz] | sustain | 12 | 12 | 0 | 12 | F#1..C7 | 1 | 1 | 12 | 0 | 12 | 4 | 44.1k 16 1ch flac |
| 51 | Synth Strings 2 | FreePats:Synthesizer/SynthStrings2 [*.sfz] | sustain | 18 | 18 | 0 | 18 | E1..C7 | 1 | 1 | 18 | 0 | 18 | 6 | 44.1k 16 1ch flac |
| 52 | Choir Aahs | FreePats:Synthesizer/SynthPadChoir [*.sfz] | sustain | 12 | 12 | 0 | 12 | C2..F#7 | 1 | 1 | 12 | 0 | 12 | 7 | 44.1k 16 2ch flac |
| 53 | Voice Oohs | FreePats:Synthesizer/SynthPadChoir [*.sfz] | sustain | 12 | 12 | 0 | 12 | C2..F#7 | 1 | 1 | 12 | 0 | 12 | 7 | 44.1k 16 2ch flac |
| 54 | Synth Voice | FreePats:Synthesizer/SynthPadChoir [*.sfz] | sustain | 12 | 12 | 0 | 12 | C2..F#7 | 1 | 1 | 12 | 0 | 12 | 7 | 44.1k 16 2ch flac |
| 55 | Orchestra Hit | FreePats:Synthesizer/SynthBrass1 [*.sfz] | sustain | 12 | 12 | 0 | 12 | F#1..C7 | 1 | 1 | 12 | 0 | 12 | 3 | 44.1k 16 1ch flac |
| 56 | Trumpet | VSCO2:Brass/Trumpet [sus] | sustain | 20 | 20 | 0 | 10 | F3..C6 | 2 | 1 | 0 | 0 | 20 | 41 | 44.1k 16 2ch wav |
| 57 | Trombone | VSCO2:Brass/Tenor Trombone [sus] | sustain | 31 | 31 | 0 | 11 | A#1..F4 | 3 | 1 | 0 | 0 | 31 | 60 | 44.1k 16 2ch wav |
| 58 | Tuba | Karoryfer:Karoryfer_War_Tuba_v1002 [2-solo-poly.sfz] | sustain | 1416 | 714 | 0 | 31 | F1..E4 | 5 | 1 | 0 | 3 | 714 | 80 | 44.1k 16 1ch wav |
| 59 | Muted Trumpet | VSCO2:Brass/Trumpet [straightM-sus] | sustain | 16 | 16 | 0 | 8 | A#3..A5 | 2 | 1 | 0 | 0 | 16 | 24 | 44.1k 16 2ch wav |
| 60 | French Horn | VSCO2:Brass/F Horn [sus] | sustain | 29 | 29 | 0 | 11 | A1..F5 | 4 | 1 | 0 | 0 | 29 | 51 | 44.1k 16 2ch wav |
| 61 | Brass Section | VSCO2:Brass/Trumpet [sus] | sustain | 20 | 20 | 0 | 10 | F3..C6 | 2 | 1 | 0 | 0 | 20 | 41 | 44.1k 16 2ch wav |
| 62 | Synth Brass 1 | FreePats:Synthesizer/SynthBrass1 [*.sfz] | sustain | 12 | 12 | 0 | 12 | F#1..C7 | 1 | 1 | 12 | 0 | 12 | 3 | 44.1k 16 1ch flac |
| 63 | Synth Brass 2 | FreePats:Synthesizer/SynthBrass2 [*.sfz] | sustain | 10 | 10 | 0 | 10 | F#2..C7 | 1 | 1 | 10 | 0 | 10 | 2 | 44.1k 16 2ch flac |
| 64 | Soprano Sax | VCSL:Aerophones/Reed Aerophones/Saxello [Non-Vibrato] | sustain | 16 | 16 | 0 | 8 | A#3..E6 | 2 | 1 | 0 | 0 | 16 | 24 | 48k 24 2ch wav |
| 65 | Alto Sax | Karoryfer:Karoryfer.Weresax.v.1.003 [alto_map_forte_condenser.sfz] | sustain | 64 | 64 | 0 | 32 | C#3..G#5 | 1 | 2 | 0 | 0 | 64 | 51 | 44.1k 24 1ch wav |
| 66 | Tenor Sax | VCSL:Aerophones/Reed Aerophones/Tenor Saxophone [Vibrato] | sustain | 19 | 19 | 0 | 19 | A#2..D6 | 1 | 1 | 0 | 0 | 19 | 34 | 48k 24 2ch wav |
| 67 | Baritone Sax | Karoryfer:Karoryfer.Bear_Sax.v1.004 [2-solo-poly.sfz] | sustain | 1433 | 191 | 124 | 33 | C2..G#4 | 1 | 1 | 0 | 5 | 141 | 65 | 44.1k float 1ch wav |
| 68 | Oboe | VSCO2:Woodwinds/Oboe [Sus] | sustain | 18 | 18 | 0 | 9 | A#3..F6 | 2 | 1 | 0 | 0 | 18 | 35 | 44.1k 16 2ch wav |
| 69 | English Horn | VSCO2:Woodwinds/Oboe [Sus] | sustain | 18 | 18 | 0 | 9 | A#3..F6 | 2 | 1 | 0 | 0 | 18 | 35 | 44.1k 16 2ch wav |
| 70 | Bassoon | VSCO2:Woodwinds/Bassoon [sus] | sustain | 25 | 25 | 0 | 13 | A#1..D#5 | 2 | 1 | 0 | 0 | 25 | 35 | 44.1k 16 2ch wav |
| 71 | Clarinet | FreePats:Reed/Clarinet [*.sfz] | sustain | 9 | 9 | 0 | 9 | D3..A#5 | 1 | 1 | 9 | 0 | 9 | 7 | 44.1k 16 1ch wav |
| 72 | Piccolo | VSCO2:Woodwinds/Piccolo [Sus] | sustain | 5 | 5 | 0 | 5 | G5..G7 | 1 | 1 | 0 | 0 | 5 | 12 | 44.1k 24 2ch wav |
| 73 | Flute | VSCO2:Woodwinds/Flute [susvib] | sustain | 13 | 13 | 0 | 10 | C4..C7 | 1 | 2 | 0 | 0 | 13 | 25 | 44.1k 24 2ch wav |
| 74 | Recorder | VCSL:Aerophones/Edge-blown Aerophones/Baroque Alto Recorder [Sustain] | sustain | 12 | 12 | 0 | 12 | F4..E6 | 1 | 1 | 0 | 0 | 12 | 29 | 48k 16 2ch wav |
| 75 | Pan Flute | VCSL:Aerophones/Edge-blown Aerophones/Ocarina, Typical [Sustains] | sustain | 21 | 21 | 0 | 13 | A4..C#6 | 1 | 1 | 0 | 0 | 21 | 40 | 44.1k 24 2ch wav |
| 76 | Blown Bottle | VCSL:Aerophones/Edge-blown Aerophones/Ocarina, Small | sustain | 23 | 23 | 0 | 15 | A5..C7 | 1 | 1 | 0 | 0 | 23 | 44 | 44.1k 24 2ch wav |
| 77 | Shakuhachi | VCSL:Aerophones/Edge-blown Aerophones/Baroque Tenor Recorder [Sustain] | sustain | 13 | 13 | 0 | 13 | C4..C6 | 1 | 1 | 0 | 0 | 13 | 21 | 48k 16 2ch wav |
| 78 | Whistle | VCSL:Aerophones/Edge-blown Aerophones/Ball Whistle | oneshot | 2 | 2 | 0 | 0 +2 keyless | -..- | 0 | 1 | 0 | 0 | 2 | 1 | 44.1k 16 2ch wav |
| 79 | Ocarina | VCSL:Aerophones/Edge-blown Aerophones/Ocarina, Typical [Sustains] | sustain | 21 | 21 | 0 | 13 | A4..C#6 | 1 | 1 | 0 | 0 | 21 | 40 | 44.1k 24 2ch wav |
| 80 | Lead 1 (square) | FreePats:Synthesizer/SynthSquare [*.sfz] | sustain | 19 | 19 | 0 | 19 | E1..E7 | 1 | 1 | 19 | 0 | 19 | 7 | 44.1k 16 1ch flac |
| 81 | Lead 2 (sawtooth) | Karoryfer:Karoryfer.Caveman_Cosmonaut.v1.001 [main.sfz] | sustain | 11973 | 586 | 0 | 49 | C2..C6 | 1 | 1 | 0 | 0 | 145 | 44 | 44.1k 16 1ch wav |
| 82 | Lead 3 (calliope) | FreePats:Synthesizer/SynthCalliope [*.sfz] | sustain | 16 | 16 | 0 | 16 | C2..C7 | 1 | 1 | 16 | 0 | 16 | 4 | 44.1k 16 1ch flac |
| 83 | Lead 4 (chiff) | FreePats:Synthesizer/SynthCalliope [*.sfz] | sustain | 16 | 16 | 0 | 16 | C2..C7 | 1 | 1 | 16 | 0 | 16 | 4 | 44.1k 16 1ch flac |
| 84 | Lead 5 (charang) | FreePats:Synthesizer/SynthBassLead [*.sfz] | sustain | 18 | 18 | 0 | 18 | F1..G#7 | 1 | 1 | 18 | 0 | 18 | 4 | 44.1k 16 2ch flac |
| 85 | Lead 6 (voice) | FreePats:Synthesizer/SynthPadChoir [*.sfz] | sustain | 12 | 12 | 0 | 12 | C2..F#7 | 1 | 1 | 12 | 0 | 12 | 7 | 44.1k 16 2ch flac |
| 86 | Lead 7 (fifths) | FreePats:Synthesizer/SynthFifths [*.sfz] | sustain | 15 | 15 | 0 | 15 | E2..C7 | 1 | 1 | 15 | 0 | 15 | 8 | 44.1k 16 2ch flac |
| 87 | Lead 8 (bass + lead) | FreePats:Synthesizer/SynthBassLead [*.sfz] | sustain | 18 | 18 | 0 | 18 | F1..G#7 | 1 | 1 | 18 | 0 | 18 | 4 | 44.1k 16 2ch flac |
| 88 | Pad 1 (new age) | FreePats:Synthesizer/NewAge [*.sfz] | sustain | 16 | 16 | 0 | 16 | C2..C7 | 1 | 1 | 16 | 0 | 16 | 5 | 44.1k 16 1ch flac |
| 89 | Pad 2 (warm) | Karoryfer:Karoryfer.Cowsynth.v1.001 [cowsynth_asthmatic_pad.sfz] | sustain | 32 | 16 | 0 | 16 | G2..E7 | 1 | 1 | 0 | 0 | 16 | 7 | 44.1k 16 1ch wav |
| 90 | Pad 3 (polysynth) | Karoryfer:Karoryfer.String_Cyborgs.v1.001 [blackheart_Master.sfz] | sustain | 246 | 64 | 0 | 17 | C2..C6 | 1 | 1 | 0 | 0 | 20 | 6 | 44.1k 16 1ch wav |
| 91 | Pad 4 (choir) | FreePats:Synthesizer/SynthPadChoir [*.sfz] | sustain | 12 | 12 | 0 | 12 | C2..F#7 | 1 | 1 | 12 | 0 | 12 | 7 | 44.1k 16 2ch flac |
| 92 | Pad 5 (bowed) | FreePats:Synthesizer/SynthPadBowed [*.sfz] | sustain | 32 | 32 | 0 | 16 | C2..C7 | 1 | 1 | 32 | 0 | 32 | 12 | 44.1k 16 1ch flac |
| 93 | Pad 6 (metallic) | FreePats:Synthesizer/SynthCrystal [*.sfz] | sustain | 11 | 11 | 0 | 11 | C2..C7 | 1 | 1 | 11 | 0 | 11 | 3 | 44.1k 16 1ch flac |
| 94 | Pad 7 (halo) | FreePats:Synthesizer/SynthPadChoir [*.sfz] | sustain | 12 | 12 | 0 | 12 | C2..F#7 | 1 | 1 | 12 | 0 | 12 | 7 | 44.1k 16 2ch flac |
| 95 | Pad 8 (sweep) | FreePats:Synthesizer/SweepPad [*.sfz] | sustain | 13 | 13 | 0 | 13 | C2..C6 | 1 | 1 | 13 | 0 | 13 | 3 | 44.1k 16 1ch flac |
| 96 | FX 1 (rain) | FreePats:Synthesizer/SynthCrystal [*.sfz] | sustain | 11 | 11 | 0 | 11 | C2..C7 | 1 | 1 | 11 | 0 | 11 | 3 | 44.1k 16 1ch flac |
| 97 | FX 2 (soundtrack) | FreePats:Synthesizer/SynthSoundtrack [*.sfz] | sustain | 15 | 15 | 0 | 15 | C2..G#6 | 1 | 1 | 15 | 0 | 15 | 10 | 44.1k 16 2ch flac |
| 98 | FX 3 (crystal) | FreePats:Synthesizer/SynthCrystal [*.sfz] | sustain | 11 | 11 | 0 | 11 | C2..C7 | 1 | 1 | 11 | 0 | 11 | 3 | 44.1k 16 1ch flac |
| 99 | FX 4 (atmosphere) | FreePats:Synthesizer/NewAge [*.sfz] | sustain | 16 | 16 | 0 | 16 | C2..C7 | 1 | 1 | 16 | 0 | 16 | 5 | 44.1k 16 1ch flac |
| 100 | FX 5 (brightness) | FreePats:Synthesizer/SynthCalliope [*.sfz] | sustain | 16 | 16 | 0 | 16 | C2..C7 | 1 | 1 | 16 | 0 | 16 | 4 | 44.1k 16 1ch flac |
| 101 | FX 6 (goblins) | FreePats:Synthesizer/SynthGoblins [*.sfz] | sustain | 18 | 18 | 0 | 18 | C2..G#7 | 1 | 1 | 18 | 0 | 18 | 11 | 44.1k 16 2ch flac |
| 102 | FX 7 (echoes) | FreePats:Synthesizer/SynthCrystal [*.sfz] | sustain | 11 | 11 | 0 | 11 | C2..C7 | 1 | 1 | 11 | 0 | 11 | 3 | 44.1k 16 1ch flac |
| 103 | FX 8 (sci-fi) | FreePats:Synthesizer/SynthSciFi [*.sfz] | sustain | 21 | 21 | 0 | 21 | C2..C7 | 1 | 1 | 21 | 0 | 21 | 14 | 44.1k 16 2ch flac |
| 104 | Sitar | VCSL:Chordophones/Zithers/Dan Tranh | decay | 115 | 115 | 0 | 16 +19 keyless | B2..B5 | 6 | 5 | 0 | 0 | 115 | 101 | 44.1k 24 1ch wav |
| 105 | Banjo | VCSL:Chordophones/Composite Chordophones/Strumstick | decay | 57 | 57 | 0 | 19 | D3..A5 | 3 | 1 | 0 | 0 | 57 | 90 | 44.1k 24 2ch wav |
| 106 | Shamisen | VCSL:Chordophones/Zithers/Dan Tranh | decay | 115 | 115 | 0 | 16 +19 keyless | B2..B5 | 6 | 5 | 0 | 0 | 115 | 101 | 44.1k 24 1ch wav |
| 107 | Koto | VCSL:Chordophones/Zithers/Dan Tranh | decay | 115 | 115 | 0 | 16 +19 keyless | B2..B5 | 6 | 5 | 0 | 0 | 115 | 101 | 44.1k 24 1ch wav |
| 108 | Kalimba | VCSL:Idiophones/Plucked Idiophones/Kalimba, Kenya | decay | 15 | 15 | 0 | 11 | B3..B5 | 1 | 2 | 0 | 0 | 15 | 22 | 48k 24 2ch wav |
| 109 | Bag pipe | FreePats:Ethnic/Bagpipe [Bagpipe 2*.sfz] | sustain | 26 | 26 | 0 | 15 | G2..G5 | 1 | 2 | 26 | 0 | 26 | 16 | 44.1k 24 1ch flac |
| 110 | Fiddle | VSCO2:Strings/Solo Violin [Arco Vib] | sustain | 30 | 30 | 0 | 15 | G3..C7 | 2 | 1 | 0 | 0 | 30 | 74 | 44.1k 16 2ch wav |
| 111 | Shanai | FreePats:Ethnic/Bagpipe [Bagpipe 2*.sfz] | sustain | 26 | 26 | 0 | 15 | G2..G5 | 1 | 2 | 26 | 0 | 26 | 16 | 44.1k 24 1ch flac |
| 112 | Tinkle Bell | VCSL:Idiophones/Struck Idiophones/Hand Bells, Nepalese | decay | 3 | 3 | 0 | 0 +3 keyless | -..- | 0 | 3 | 0 | 0 | 3 | 2 | 44.1k 24 2ch wav |
| 113 | Agogo | VCSL:Idiophones/Struck Idiophones/Agogo Bells | oneshot | 15 | 15 | 0 | 0 +15 keyless | -..- | 0 | 3 | 0 | 0 | 15 | 5 | 44.1k 16 2ch wav |
| 114 | Steel Drums | FreePats:ChromaticPercussion/Hang-D-minor [*.sfz] | decay | 51 | 51 | 0 | 9 | A3..D5 | 1 | 1 | 0 | 0 | 51 | 14 | 44.1k 24 2ch flac |
| 115 | Woodblock | VCSL:Idiophones/Struck Idiophones/Woodblock | oneshot | 10 | 10 | 0 | 0 +10 keyless | -..- | 0 | 3 | 0 | 0 | 10 | 2 | 44.1k 24 2ch wav |
| 116 | Taiko Drum | VCSL:Membranophones/Struck Membranophones/Bass Drum 1 | oneshot | 8 | 8 | 0 | 0 +8 keyless | -..- | 0 | 2 | 0 | 0 | 8 | 5 | 44.1k 16 2ch wav |
| 117 | Melodic Tom | VCSL:Membranophones/Struck Membranophones/Tom 1 | oneshot | 22 | 22 | 0 | 0 +22 keyless | -..- | 0 | 2 | 0 | 0 | 22 | 14 | 44.1k 16 2ch wav |
| 118 | Synth Drum | FreePats:Percussion/SynthesizerPercussion [*.sfz] | oneshot | 21 | 21 | 0 | 19 | C3..F#4 | 1 | 1 | 0 | 0 | 21 | 2 | 48k 24 1ch wav |
| 119 | Reverse Cymbal | VCSL:Idiophones/Struck Idiophones/Suspended Cymbal 1 | oneshot | 25 | 22 | 3 | 0 +22 keyless | -..- | 0 | 4 | 0 | 0 | 22 | 50 | 44.1k 16 2ch wav |
| 120 | Guitar Fret Noise | Karoryfer:Karoryfer.Shinyguitar.v1.002 [acoustic_noises.sfz] | oneshot | 66 | 66 | 0 | 14 | C0..D#1 | 1 | 1 | 0 | 0 | 66 | 4 | 44.1k 24 1ch wav |
| 121 | Breath Noise | VCSL:Aerophones/Edge-blown Aerophones/Ocarina, Small | oneshot | 23 | 23 | 0 | 15 | A5..C7 | 1 | 1 | 0 | 0 | 23 | 44 | 44.1k 24 2ch wav |
| 122 | Seashore | VCSL:Membranophones/Other Membranophones/Ocean Drum | oneshot | 3 | 3 | 0 | 0 +3 keyless | -..- | 0 | 3 | 0 | 0 | 3 | 15 | 44.1k 16 2ch wav |
| 123 | Bird Tweet | VCSL:Aerophones/Edge-blown Aerophones/Ball Whistle | oneshot | 2 | 2 | 0 | 0 +2 keyless | -..- | 0 | 1 | 0 | 0 | 2 | 1 | 44.1k 16 2ch wav |
| 124 | Telephone Ring | VCSL:Idiophones/Struck Idiophones/Hand Bells, Nepalese | oneshot | 3 | 3 | 0 | 0 +3 keyless | -..- | 0 | 3 | 0 | 0 | 3 | 2 | 44.1k 24 2ch wav |
| 125 | Helicopter | VCSL:Idiophones/Struck Idiophones/Ratchet | oneshot | 8 | 8 | 0 | 0 +8 keyless | -..- | 0 | 2 | 0 | 0 | 8 | 7 | 44.1k 16 2ch wav |
| 126 | Applause | VCSL:Idiophones/Struck Idiophones/Claps | oneshot | 10 | 10 | 0 | 0 +10 keyless | -..- | 0 | 6 | 0 | 0 | 10 | 1 | 48k 16 2ch wav |
| 127 | Gunshot | VCSL:Idiophones/Struck Idiophones/Slapstick | oneshot | 5 | 5 | 0 | 0 +5 keyless | -..- | 0 | 3 | 0 | 0 | 5 | 1 | 44.1k 24 2ch wav |
| drums | Drum kit | FreePats:Percussion/MuldjordKit | kit | 777 | 777 | 0 | 19 | C3..F#4 | 14 | 1 | 0 | 0 | 240 | 139 | 44.1k 24 2ch flac |
| drums | Drum kit | Karoryfer:Unruly_Drums_1100 | kit | 10339 | 5383 | 0 | 54 | C#1..B5 | 9 | 4 | 0 | 0 | 3279 | 356 | 44.1k 16 1ch flac |
| drums | Drum kit | Karoryfer:Swirly.Drums_1104 | kit | 5168 | 2884 | 0 | 32 | B1..F#5 | 33 | 4 | 0 | 0 | 2836 | 907 | 44.1k 16 1ch wav |

Source audio reached by the playable regions: 7532 MB in 12849 files.
