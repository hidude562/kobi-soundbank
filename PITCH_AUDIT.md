# Pitch audit

Detected pitch minus claimed key (semitones) for samples spread over each candidate's range, after the candidate's octave correction.  Folder sources with a consistent whole-octave offset need `octave=` in gm_map; SFZ sources are authoritative.

| # | program | source | instrument | sub | octave | agree | offsets | verdict |
|---|---|---|---|---|---|---|---|---|
| 0 | Acoustic Grand Piano | VCSL | Chordophones/Zithers/Grand Piano, Steinway B | NoSus | 0 | 0.86 | +0.1 +0.0 +0.0 +0.0 +0.0 +0.0 -83.8 | ok |
| 1 | Bright Acoustic Piano | VCSL | Chordophones/Zithers/Grand Piano, Kawai | Sustains | 1 | 0.86 | -0.1 -0.1 +0.0 -0.1 +0.0 +0.0 -12.1 | ok |
| 2 | Electric Grand Piano | VCSL | Electrophones/TX81Z/Piano 1 |  | 1 | 0.71 | +60.0 +0.0 +0.0 +0.0 +0.0 +0.0 -19.1 | ok |
| 3 | Honky-tonk Piano | VCSL | Chordophones/Zithers/Upright Piano, Knight |  | 1 | 0.86 | +0.1 -0.1 +0.0 +0.0 +0.0 +0.2 -86.5 | ok |
| 4 | Electric Piano 1 | VCSL | Electrophones/TX81Z/FM Piano |  | 0 | 0.71 | +7.3 +0.0 +0.0 +0.0 +0.0 +0.0 -12.0 | ok |
| 5 | Electric Piano 2 | FreePats | ElectricPiano/FM-Piano2 | *.sfz | 0 | 1.00 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 | ok |
| 6 | Harpsichord | VCSL | Chordophones/Zithers/Harpsichord, Flemish |  | 1 | 1.00 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 -0.1 | ok |
| 7 | Clavinet | VCSL | Electrophones/TX81Z/Clavisynth |  | 2 | 0.71 | +0.0 +0.0 +0.0 +0.0 +0.0 -12.0 -24.0 | ok |
| 8 | Celesta | SSO | Celeste |  | 0 | 1.00 | +0.0 -0.1 +0.0 +0.0 +0.0 +0.3 +0.7 | ok |
| 9 | Glockenspiel | VCSL | Idiophones/Struck Idiophones/Glockenspiel |  | 1 | 0.86 | +0.0 +0.1 +0.1 +0.1 +0.1 +0.1 -27.7 | ok |
| 10 | Music Box | VCSL | Idiophones/Plucked Idiophones/Kalimba, Kenya |  | 1 | 0.86 | +0.0 +0.0 +0.2 +0.4 +0.1 +0.3 -48.1 | ok |
| 11 | Vibraphone | VCSL | Idiophones/Struck Idiophones/Vibraphone |  | 1 | 0.86 | +10.4 +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 | ok |
| 12 | Marimba | VCSL | Idiophones/Struck Idiophones/Marimba |  | 1 | 0.86 | +0.0 +0.0 +0.0 +0.0 -0.1 +0.0 -75.3 | ok |
| 13 | Xylophone | VCSL | Idiophones/Struck Idiophones/Xylophone |  | 1 | 0.86 | +0.1 +0.1 +0.1 +0.1 +0.1 +0.3 -22.2 | ok |
| 14 | Tubular Bells | VCSL | Idiophones/Struck Idiophones/Tubular Bells 1 |  | 1 | 0.57 | +5.3 +0.0 -29.4 -0.3 +0.1 -0.2 -8.1 | inconsistent: listen |
| 15 | Dulcimer | VCSL | Chordophones/Zithers/Dan Tranh |  | 1 | 1.00 | -0.1 +0.3 -0.1 -0.1 -0.1 -0.1 -0.3 | ok |
| 16 | Drawbar Organ | FreePats | Organ/DrawbarOrganEmulation | *.sfz | 0 | 1.00 | -12.1 -12.1 -12.1 -12.1 -12.1 -12.0 -12.0 | detector reads -1 oct vs map (sub-oscillator?) |
| 17 | Percussive Organ | FreePats | Organ/PercussiveOrganEmulation | *.sfz | 0 | 1.00 | -12.1 -12.1 -12.1 -12.1 -12.0 -12.1 -12.0 | detector reads -1 oct vs map (sub-oscillator?) |
| 18 | Rock Organ | FreePats | Organ/RockOrganEmulation | *.sfz | 0 | 0.71 | -0.2 +0.0 -12.1 -12.1 -11.9 -12.0 -12.0 | detector reads -1 oct vs map (sub-oscillator?) |
| 19 | Church Organ | VCSL | Aerophones/Edge-blown Aerophones/Pipe Organ | Loud | 0 | 0.86 | +0.0 +0.0 -0.1 -0.1 -0.1 +11.9 -0.1 | ok |
| 20 | Reed Organ | VCSL | Aerophones/Edge-blown Aerophones/Renaissance Organ | 8' | 1 | 1.00 | -0.1 +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 | ok |
| 21 | Accordion | FreePats | Organ/ButtonAccordionHN | PRESET*tuned.sfz | 0 | 1.00 | +0.6 +0.5 +0.3 +0.4 +0.3 +0.5 +0.1 | ok |
| 22 | Harmonica | VCSL | Aerophones/Free Aerophones/Harmonica-Hohner-Special20-C | Sustains | 1 | 0.86 | +0.0 -0.1 -12.1 +0.0 +0.0 +0.0 +0.0 | ok |
| 23 | Tango Accordion | FreePats | Organ/ButtonAccordionHN | PRESET*tuned.sfz | 0 | 1.00 | +0.6 +0.5 +0.3 +0.4 +0.3 +0.5 +0.1 | ok |
| 24 | Acoustic Guitar (nylon) | FreePats | Guitar/SpanishClassicalGuitar | *.sfz | 0 | 1.00 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 | ok |
| 25 | Acoustic Guitar (steel) | Karoryfer | Karoryfer.Shinyguitar.v1.002 | acoustic_five.sfz | 0 | 1.00 | -0.1 -0.1 +0.0 +0.0 +0.0 -0.1 -0.1 | ok |
| 26 | Electric Guitar (jazz) | FreePats | ElectricGuitar/EGuitarFSBS-jazz | *jazz bridge 2*.sfz | 0 | 0.86 | +0.0 -0.1 -0.1 +0.0 +0.0 +0.0 +12.1 | ok |
| 27 | Electric Guitar (clean) | FreePats | ElectricGuitar/EGuitarFSBS-clean | *clean bridge 2*.sfz | 0 | 0.86 | +12.0 +0.0 -0.1 -0.1 +0.0 +0.0 +0.0 | ok |
| 28 | Electric Guitar (muted) | Karoryfer | Karoryfer_Black_And_Green_Guitars_1000 | 05-green_staccato.sfz | 0 | 1.00 | +0.1 +0.0 +0.1 +0.0 -0.1 -0.1 +0.1 | ok |
| 29 | Overdriven Guitar | FreePats | ElectricGuitar/EGuitarFSBS-dist1 | *dist1 bridge*.sfz | 0 | 1.00 | +0.0 +0.0 -0.1 -0.1 +0.0 +0.0 +0.0 | ok |
| 30 | Distortion Guitar | FreePats | ElectricGuitar/EGuitarFSBS-dist2 | *dist2 bridge*.sfz | 0 | 1.00 | +0.0 +0.0 -0.1 -0.1 +0.0 +0.0 +0.0 | ok |
| 31 | Guitar Harmonics | FreePats | ElectricGuitar/EGuitarFSBS-clean | *clean bridge 2*.sfz | 0 | 0.86 | +12.0 +0.0 -0.1 -0.1 +0.0 +0.0 +0.0 | ok |
| 32 | Acoustic Bass | Karoryfer | Sneakybass_v1.000 | 02-sneakybass_pluck.sfz | -1 | 0.43 | -0.5 +10.9 +0.0 -0.1 -28.7 -34.0 -36.5 | inconsistent: listen |
| 33 | Electric Bass (finger) | FreePats | ElectricGuitar/FingerBassYR | *.sfz | 0 | 1.00 | +0.0 +0.1 +0.0 +0.0 +0.0 -0.1 -0.1 | ok |
| 34 | Electric Bass (pick) | FreePats | ElectricGuitar/PickedBassYR | *.sfz | 0 | 1.00 | +0.0 +0.1 +0.0 +0.0 +0.0 +0.0 -0.1 | ok |
| 35 | Fretless Bass | Karoryfer | Karoryfer.Pastabass.v1.101 | fetuccine.sfz | -1 | 1.00 | -0.1 -0.0 +0.1 +0.1 -0.1 +0.0 +0.0 | ok |
| 36 | Slap Bass 1 | Karoryfer | Karoryfer.Growlybass.v1.002 | growlybass_angry.sfz | -1 | 0.71 | +7.1 +0.0 +0.1 -0.1 +0.0 +0.0 +22.8 | ok |
| 37 | Slap Bass 2 | Karoryfer | Karoryfer.Swagbass.v1.001 | swagbass.sfz | 0 | 0.71 | +0.3 -0.1 -0.1 +0.0 +0.0 -42.4 -58.6 | ok |
| 38 | Synth Bass 1 | FreePats | Synthesizer/SynthBass1 | *.sfz | 0 | 1.00 | -0.1 -0.1 -0.1 -0.1 -0.1 -0.1 +0.0 | ok |
| 39 | Synth Bass 2 | FreePats | Synthesizer/SynthBass2 | *.sfz | 0 | 1.00 | -12.0 -12.0 -12.0 -12.0 -12.0 -12.0 -12.0 | detector reads -1 oct vs map (sub-oscillator?) |
| 40 | Violin | VSCO2 | Strings/Solo Violin | Arco Vib | 0 | 0.86 | -0.1 +0.2 +0.1 +0.1 +0.0 +0.0 -12.0 | ok |
| 41 | Viola | VSCO2 | Strings/Viola Section | susvib | 1 | 1.00 | +0.0 +0.0 +0.0 -0.1 -0.1 +0.0 +0.0 | ok |
| 42 | Cello | Karoryfer | Karoryfer_Bigcat_cello.v1.001 | 01- Bowed*.sfz | 1 | 0.86 | +0.0 -0.2 +0.0 +0.0 +0.0 +0.0 -60.0 | ok |
| 43 | Contrabass | Karoryfer | Karoryfer.Meatbass.v1.001 | 02_arco_3vel.sfz | 0 | 1.00 | -0.1 -0.3 +0.1 +0.1 -0.1 +0.0 -0.1 | ok |
| 44 | Tremolo Strings | VSCO2 | Strings/Violin Section | Trem | 1 | 1.00 | -0.1 -0.1 +0.0 +0.0 +0.0 +0.0 -0.1 | ok |
| 45 | Pizzicato Strings | VSCO2 | Strings/Violin Section | Pizz | 1 | 1.00 | -0.1 -0.1 +0.0 -0.1 -0.1 -0.1 +0.0 | ok |
| 46 | Orchestral Harp | VCSL | Chordophones/Composite Chordophones/Concert Harp |  | 0 | 1.00 | -0.3 -0.1 -0.1 +0.0 -0.1 -0.2 +0.0 | ok |
| 47 | Timpani | FreePats | Percussion/Timpani | *.sfz | 0 | 0.29 | +7.0 -12.2 -20.8 -9.4 -22.8 +6.0 -12.4 | inconsistent: listen |
| 48 | String Ensemble 1 | VSCO2 | Strings/Violin Section | susVib | 1 | 1.00 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 -0.1 | ok |
| 49 | String Ensemble 2 | VSCO2 | Strings/Viola Section | susvib | 1 | 1.00 | +0.0 +0.0 +0.0 -0.1 -0.1 +0.0 +0.0 | ok |
| 50 | Synth Strings 1 | FreePats | Synthesizer/SynthStrings1 | *.sfz | 0 | 1.00 | -0.1 -0.1 -0.1 -0.1 +0.0 +0.0 -0.1 | ok |
| 51 | Synth Strings 2 | FreePats | Synthesizer/SynthStrings2 | *.sfz | 0 | 1.00 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 | ok |
| 52 | Choir Aahs | FreePats | Synthesizer/SynthPadChoir | *.sfz | 0 | 0.86 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 -12.0 | ok |
| 53 | Voice Oohs | FreePats | Synthesizer/SynthPadChoir | *.sfz | 0 | 0.86 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 -12.0 | ok |
| 54 | Synth Voice | FreePats | Synthesizer/SynthPadChoir | *.sfz | 0 | 0.86 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 -12.0 | ok |
| 55 | Orchestra Hit | FreePats | Synthesizer/SynthBrass1 | *.sfz | 0 | 1.00 | -0.1 +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 | ok |
| 56 | Trumpet | VSCO2 | Brass/Trumpet | sus | 1 | 1.00 | +0.0 -0.1 +0.0 -0.1 +0.0 +0.0 -0.1 | ok |
| 57 | Trombone | VSCO2 | Brass/Tenor Trombone | sus | 1 | 1.00 | +0.0 +0.0 +0.0 -0.1 +0.0 +0.0 +0.0 | ok |
| 58 | Tuba | Karoryfer | Karoryfer_War_Tuba_v1002 | 2-solo-poly.sfz | 0 | 0.86 | -0.3 +0.5 +0.1 +0.0 -0.3 +0.0 +14.6 | ok |
| 59 | Muted Trumpet | VSCO2 | Brass/Trumpet | straightM-sus | 1 | 1.00 | -0.1 +0.0 -0.1 +0.0 -0.1 -0.1 +0.0 | ok |
| 60 | French Horn | VSCO2 | Brass/F Horn | sus | 1 | 1.00 | -0.2 -0.1 +0.0 -0.1 -0.1 +0.0 +0.0 | ok |
| 61 | Brass Section | VSCO2 | Brass/Trumpet | sus | 1 | 1.00 | +0.0 -0.1 +0.0 -0.1 +0.0 +0.0 -0.1 | ok |
| 62 | Synth Brass 1 | FreePats | Synthesizer/SynthBrass1 | *.sfz | 0 | 1.00 | -0.1 +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 | ok |
| 63 | Synth Brass 2 | FreePats | Synthesizer/SynthBrass2 | *.sfz | 0 | 0.86 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 -12.0 | ok |
| 64 | Soprano Sax | VCSL | Aerophones/Reed Aerophones/Saxello | Non-Vibrato | 1 | 1.00 | +0.0 -0.1 -0.1 +0.0 +0.0 +0.0 +0.0 | ok |
| 65 | Alto Sax | Karoryfer | Karoryfer.Weresax.v.1.003 | alto_map_forte_condenser.sfz | 0 | 1.00 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 | ok |
| 66 | Tenor Sax | VCSL | Aerophones/Reed Aerophones/Tenor Saxophone | Vibrato | 1 | 1.00 | -0.1 +0.0 -0.1 -0.1 +0.0 +0.0 +0.0 | ok |
| 67 | Baritone Sax | Karoryfer | Karoryfer.Bear_Sax.v1.004 | 2-solo-poly.sfz | 0 | 0.00 | +5.2 -20.9 +4.0 +23.6 n/a n/a -28.2 | inconsistent: listen |
| 68 | Oboe | VSCO2 | Woodwinds/Oboe | Sus | 1 | 0.86 | +0.0 +0.0 +0.0 -0.1 +12.0 +0.0 +0.0 | ok |
| 69 | English Horn | VSCO2 | Woodwinds/Oboe | Sus | 1 | 0.86 | +0.0 +0.0 +0.0 -0.1 +12.0 +0.0 +0.0 | ok |
| 70 | Bassoon | VSCO2 | Woodwinds/Bassoon | sus | 1 | 1.00 | -0.1 -0.1 +0.0 +0.0 +0.0 +0.0 +0.0 | ok |
| 71 | Clarinet | FreePats | Reed/Clarinet | *.sfz | 0 | 1.00 | +0.0 +0.1 +0.1 +0.0 +0.1 -0.1 +0.1 | ok |
| 72 | Piccolo | VSCO2 | Woodwinds/Piccolo | Sus | 1 | 1.00 | +0.0 -0.1 +0.1 +0.1 +0.1 | ok |
| 73 | Flute | VSCO2 | Woodwinds/Flute | susvib | 1 | 1.00 | -0.1 -0.1 +0.0 -0.1 -0.1 +0.0 +0.0 | ok |
| 74 | Recorder | VCSL | Aerophones/Edge-blown Aerophones/Baroque Alto Recorder | Sustain | 1 | 1.00 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 | ok |
| 75 | Pan Flute | VCSL | Aerophones/Edge-blown Aerophones/Ocarina, Typical | Sustains | 1 | 1.00 | +0.0 +0.1 +0.0 +0.0 +0.1 +0.2 +0.1 | ok |
| 76 | Blown Bottle | VCSL | Aerophones/Edge-blown Aerophones/Ocarina, Small |  | 1 | 1.00 | +0.0 -0.1 +0.0 +0.0 +0.2 +0.0 -0.1 | ok |
| 77 | Shakuhachi | VCSL | Aerophones/Edge-blown Aerophones/Baroque Tenor Recorder | Sustain | 1 | 1.00 | +0.0 -0.1 +0.0 +0.0 +0.0 +0.0 -0.1 | ok |
| 78 | Whistle | VCSL | Aerophones/Edge-blown Aerophones/Ball Whistle |  | 0 | 0.00 |  | unpitched |
| 79 | Ocarina | VCSL | Aerophones/Edge-blown Aerophones/Ocarina, Typical | Sustains | 1 | 1.00 | +0.0 +0.1 +0.0 +0.0 +0.1 +0.2 +0.1 | ok |
| 80 | Lead 1 (square) | FreePats | Synthesizer/SynthSquare | *.sfz | 0 | 1.00 | -0.1 -0.1 +0.0 -0.1 -0.1 -0.1 +0.1 | ok |
| 81 | Lead 2 (sawtooth) | Karoryfer | Karoryfer.Caveman_Cosmonaut.v1.001 | main.sfz | 0 | 0.71 | -12.0 +12.0 +11.9 +11.9 +0.0 +11.9 +12.0 | detector reads +1 oct vs map (sub-oscillator?) |
| 82 | Lead 3 (calliope) | FreePats | Synthesizer/SynthCalliope | *.sfz | 0 | 1.00 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 | ok |
| 83 | Lead 4 (chiff) | FreePats | Synthesizer/SynthCalliope | *.sfz | 0 | 1.00 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 | ok |
| 84 | Lead 5 (charang) | FreePats | Synthesizer/SynthBassLead | *.sfz | 0 | 1.00 | +0.0 -0.1 -0.1 -0.1 +0.0 +0.0 +0.0 | ok |
| 85 | Lead 6 (voice) | FreePats | Synthesizer/SynthPadChoir | *.sfz | 0 | 0.86 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 -12.0 | ok |
| 86 | Lead 7 (fifths) | FreePats | Synthesizer/SynthFifths | *.sfz | 0 | 0.86 | -5.0 -24.1 -24.1 -24.1 -24.1 -24.1 -24.1 | detector reads -2 oct vs map (sub-oscillator?) |
| 87 | Lead 8 (bass + lead) | FreePats | Synthesizer/SynthBassLead | *.sfz | 0 | 1.00 | +0.0 -0.1 -0.1 -0.1 +0.0 +0.0 +0.0 | ok |
| 88 | Pad 1 (new age) | FreePats | Synthesizer/NewAge | *.sfz | 0 | 1.00 | +0.0 -0.1 +0.0 +0.0 -0.1 +0.0 +0.0 | ok |
| 89 | Pad 2 (warm) | Karoryfer | Karoryfer.Cowsynth.v1.001 | cowsynth_asthmatic_pad.sfz | 0 | 0.57 | +0.1 +12.3 +12.1 +0.1 +12.4 +12.1 -16.0 | inconsistent: listen |
| 90 | Pad 3 (polysynth) | Karoryfer | Karoryfer.String_Cyborgs.v1.001 | blackheart_Master.sfz | 0 | 1.00 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 | ok |
| 91 | Pad 4 (choir) | FreePats | Synthesizer/SynthPadChoir | *.sfz | 0 | 0.86 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 -12.0 | ok |
| 92 | Pad 5 (bowed) | FreePats | Synthesizer/SynthPadBowed | *.sfz | 0 | 0.86 | +0.1 +0.0 +0.0 -0.0 +0.0 +0.0 -12.0 | ok |
| 93 | Pad 6 (metallic) | FreePats | Synthesizer/SynthCrystal | *.sfz | 0 | 1.00 | +0.4 +0.4 +0.3 +0.3 +0.3 +0.2 +0.0 | ok |
| 94 | Pad 7 (halo) | FreePats | Synthesizer/SynthPadChoir | *.sfz | 0 | 0.86 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 -12.0 | ok |
| 95 | Pad 8 (sweep) | FreePats | Synthesizer/SweepPad | *.sfz | 0 | 1.00 | -0.1 +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 | ok |
| 96 | FX 1 (rain) | FreePats | Synthesizer/SynthCrystal | *.sfz | 0 | 1.00 | +0.4 +0.4 +0.3 +0.3 +0.3 +0.2 +0.0 | ok |
| 97 | FX 2 (soundtrack) | FreePats | Synthesizer/SynthSoundtrack | *.sfz | 0 | 1.00 | -12.0 -12.0 -12.1 -12.1 -12.1 -12.1 -12.1 | detector reads -1 oct vs map (sub-oscillator?) |
| 98 | FX 3 (crystal) | FreePats | Synthesizer/SynthCrystal | *.sfz | 0 | 1.00 | +0.4 +0.4 +0.3 +0.3 +0.3 +0.2 +0.0 | ok |
| 99 | FX 4 (atmosphere) | FreePats | Synthesizer/NewAge | *.sfz | 0 | 1.00 | +0.0 -0.1 +0.0 +0.0 -0.1 +0.0 +0.0 | ok |
| 100 | FX 5 (brightness) | FreePats | Synthesizer/SynthCalliope | *.sfz | 0 | 1.00 | +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 +0.0 | ok |
| 101 | FX 6 (goblins) | FreePats | Synthesizer/SynthGoblins | *.sfz | 0 | 1.00 | +0.0 +0.0 -0.1 +0.0 +0.0 +0.0 +0.0 | ok |
| 102 | FX 7 (echoes) | FreePats | Synthesizer/SynthCrystal | *.sfz | 0 | 1.00 | +0.4 +0.4 +0.3 +0.3 +0.3 +0.2 +0.0 | ok |
| 103 | FX 8 (sci-fi) | FreePats | Synthesizer/SynthSciFi | *.sfz | 0 | 0.86 | +0.0 +0.0 +0.0 +0.0 +0.0 -0.1 -12.0 | ok |
| 104 | Sitar | VCSL | Chordophones/Zithers/Dan Tranh |  | 1 | 1.00 | -0.1 +0.3 -0.1 -0.1 -0.1 -0.1 -0.3 | ok |
| 105 | Banjo | VCSL | Chordophones/Composite Chordophones/Strumstick |  | 1 | 0.86 | +0.0 +11.9 +0.0 +0.0 +0.0 +0.0 +0.0 | ok |
| 106 | Shamisen | VCSL | Chordophones/Zithers/Dan Tranh |  | 1 | 1.00 | -0.1 +0.3 -0.1 -0.1 -0.1 -0.1 -0.3 | ok |
| 107 | Koto | VCSL | Chordophones/Zithers/Dan Tranh |  | 1 | 1.00 | -0.1 +0.3 -0.1 -0.1 -0.1 -0.1 -0.3 | ok |
| 108 | Kalimba | VCSL | Idiophones/Plucked Idiophones/Kalimba, Kenya |  | 1 | 0.86 | +0.0 +0.0 +0.2 +0.4 +0.1 +0.3 -48.1 | ok |
| 109 | Bag pipe | FreePats | Ethnic/Bagpipe | Bagpipe 2*.sfz | 0 | 1.00 | +0.0 -0.8 -0.9 -0.7 -1.3 -1.0 -0.6 | ok |
| 110 | Fiddle | VSCO2 | Strings/Solo Violin | Arco Vib | 0 | 0.86 | -0.1 +0.2 +0.1 +0.1 +0.0 +0.0 -12.0 | ok |
| 111 | Shanai | FreePats | Ethnic/Bagpipe | Bagpipe 2*.sfz | 0 | 1.00 | +0.0 -0.8 -0.9 -0.7 -1.3 -1.0 -0.6 | ok |
| 112 | Tinkle Bell | VCSL | Idiophones/Struck Idiophones/Hand Bells, Nepalese |  | 0 | 0.00 |  | unpitched |
| 113 | Agogo | VCSL | Idiophones/Struck Idiophones/Agogo Bells |  | 0 | 0.00 |  | unpitched |
| 114 | Steel Drums | FreePats | ChromaticPercussion/Hang-D-minor | *.sfz | 0 | 0.86 | +0.3 +0.0 -19.1 +0.1 +0.0 +0.0 +0.0 | ok |
| 115 | Woodblock | VCSL | Idiophones/Struck Idiophones/Woodblock |  | 0 | 0.00 |  | unpitched |
| 116 | Taiko Drum | VCSL | Membranophones/Struck Membranophones/Bass Drum 1 |  | 0 | 0.00 |  | unpitched |
| 117 | Melodic Tom | VCSL | Membranophones/Struck Membranophones/Tom 1 |  | 0 | 0.00 |  | unpitched |
| 118 | Synth Drum | FreePats | Percussion/SynthesizerPercussion | *.sfz | 0 | 0.00 |  | unpitched |
| 119 | Reverse Cymbal | VCSL | Idiophones/Struck Idiophones/Suspended Cymbal 1 |  | 0 | 0.00 |  | unpitched |
| 120 | Guitar Fret Noise | Karoryfer | Karoryfer.Shinyguitar.v1.002 | acoustic_noises.sfz | 0 | 0.00 |  | unpitched |
| 121 | Breath Noise | VCSL | Aerophones/Edge-blown Aerophones/Ocarina, Small |  | 1 | 0.00 |  | unpitched |
| 122 | Seashore | VCSL | Membranophones/Other Membranophones/Ocean Drum |  | 0 | 0.00 |  | unpitched |
| 123 | Bird Tweet | VCSL | Aerophones/Edge-blown Aerophones/Ball Whistle |  | 0 | 0.00 |  | unpitched |
| 124 | Telephone Ring | VCSL | Idiophones/Struck Idiophones/Hand Bells, Nepalese |  | 0 | 0.00 |  | unpitched |
| 125 | Helicopter | VCSL | Idiophones/Struck Idiophones/Ratchet |  | 0 | 0.00 |  | unpitched |
| 126 | Applause | VCSL | Idiophones/Struck Idiophones/Claps |  | 0 | 0.00 |  | unpitched |
| 127 | Gunshot | VCSL | Idiophones/Struck Idiophones/Slapstick |  | 0 | 0.00 |  | unpitched |

128 candidates audited, 12 not clean.
