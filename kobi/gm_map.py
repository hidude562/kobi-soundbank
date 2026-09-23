"""kobi.gm_map — which source instrument plays each General MIDI program.

Sources, in the priority Nathan set: VCSL, then FreePats, then Karoryfer.  Every candidate names a
real place under uncompressed/ (kobi.paths.SOURCES):

    VCSL      folder of bare WAVs (VCSL's own file names carry note, velocity layer, round robin)
              plus an optional sub-folder (articulation / mic position) to use
    FreePats  a bank folder and a glob for the .sfz file that defines the instrument
    Karoryfer a set folder and a glob for the .sfz program to use

``kind`` says how the pipeline treats the samples: 'sustain' (attack + untouched dctloop loop via
the bridge), 'decay' (flatten, loop, envelope back), 'oneshot' (no loop, just encode), 'kit' (a
GM-mapped drum kit, encoded as is).  ``standin`` marks a timbre that is not the named instrument.

    python3 -m kobi.gm_map            # validate every path on disk and write MAPPING.md
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from . import paths

ROOT = paths.SOURCES
SSO_ROOT = paths.SSO                                            # only CC0 pieces are used from here

# VSCO 2 Community Edition (CC0, pulled 2026-09-04) is the fourth source: it supplies the orchestra the
# first three lack.  University of Iowa MIS (unrestricted, pulled 2026-09-05; 2014 stereo ff recordings) is
# the fifth, put first for solo brass and solo strings at Nathan's request.  No open source here has a real
# choir or an English horn.


@dataclass
class Cand:
    source: str                 # 'VCSL' | 'FreePats' | 'Karoryfer' | 'SSO' | 'VSCO2'
    path: str                   # folder under ROOT/<source>/ (VCSL/FreePats/Karoryfer), or an SSO folder name
    sub: str | None = None      # folder sources: sub-folder to use; FreePats/Karoryfer: glob for the .sfz
    kind: str = 'sustain'
    standin: bool = False
    note: str = ''
    octave: int = 0             # folder sources: file names are this many octaves below the true pitch
    tags: tuple = ()            # folder sources: keep only files carrying all these name words

    def resolve(self) -> tuple[str, int]:
        """(resolved path or glob hit, sample/sfz count) — 0 means missing."""
        base = os.path.join(SSO_ROOT, self.path) if self.source == 'SSO' else os.path.join(ROOT, self.source, self.path)
        if self.source in ('VCSL', 'VSCO2', 'SSO', 'Iowa'):
            d = os.path.join(base, self.sub) if self.sub else base
            return d, sum(len(glob.glob(os.path.join(glob.escape(d), '**', ext), recursive=True))
                          for ext in ('*.wav', '*.flac', '*.aif', '*.aiff'))
        hits = glob.glob(os.path.join(glob.escape(base), '**', self.sub or '*.sfz'), recursive=True)
        return (hits[0] if hits else base), len(hits)


@dataclass
class Program:
    num: int
    name: str
    cands: list = field(default_factory=list)


def V(path, sub=None, kind='sustain', standin=False, note='', octave=0, tags=()):
    return Cand('VCSL', path, sub, kind, standin, note, octave, tags)


def O(path, sub=None, kind='sustain', standin=False, note='', octave=0, tags=()):
    return Cand('VSCO2', path, sub, kind, standin, note, octave, tags)


def I(path, sub=None, kind='sustain', standin=False, note='', octave=0, tags=()):
    return Cand('Iowa', path, sub, kind, standin, note, octave, tags)


def F(path, sfz='*.sfz', kind='sustain', standin=False, note='', octave=0):
    return Cand('FreePats', path, sfz, kind, standin, note, octave)


def K(path, sfz='*.sfz', kind='sustain', standin=False, note='', octave=0):
    return Cand('Karoryfer', path, sfz, kind, standin, note, octave)


def S(folder, kind='sustain', standin=True, note='SSO fork sample (check provenance before release)'):
    return Cand('SSO', folder, None, kind, standin, note)


PIANO = 'Chordophones/Zithers/'
IDIO = 'Idiophones/Struck Idiophones/'
MEMB = 'Membranophones/Struck Membranophones/'
EDGE = 'Aerophones/Edge-blown Aerophones/'

PROGRAMS = [
    # ---- 0-7 piano
    Program(0, 'Acoustic Grand Piano', [V(PIANO + 'Grand Piano, Steinway B', 'NoSus', 'decay'), F('Piano/SalamanderGrandPiano', 'SalamanderGrandPiano-V3*.sfz', 'decay', note='CC BY 3.0 Alexander Holm')]),
    Program(1, 'Bright Acoustic Piano', [V(PIANO + 'Grand Piano, Kawai', 'Sustains', 'decay', octave=1), F('Piano/UprightPianoKW-small-bright', kind='decay')]),
    Program(2, 'Electric Grand Piano', [V('Electrophones/TX81Z/Piano 1', None, 'decay', True, octave=1), F('Piano/PianoFB', kind='decay', standin=True)]),
    Program(3, 'Honky-tonk Piano', [V(PIANO + 'Upright Piano, Knight', None, 'decay', True, 'detune two layers in the SFZ', octave=1), F('Piano/UprightPianoKW', kind='decay', standin=True)]),
    Program(4, 'Electric Piano 1', [V('Electrophones/TX81Z/FM Piano', None, 'decay'), F('ElectricPiano/FM-Piano1', kind='decay')]),
    Program(5, 'Electric Piano 2', [F('ElectricPiano/FM-Piano2', kind='decay'), V('Electrophones/TX81Z/FM Piano', None, 'decay')]),
    Program(6, 'Harpsichord', [V(PIANO + 'Harpsichord, Flemish', None, 'decay', octave=1), V(PIANO + 'Harpsichord, French', None, 'decay', octave=1)]),
    Program(7, 'Clavinet', [V('Electrophones/TX81Z/Clavisynth', None, 'decay', octave=2)]),
    # ---- 8-15 chromatic percussion
    Program(8, 'Celesta', [S('Celeste', 'decay', False, 'SSO fork celeste, CC0'), V(IDIO + 'Glockenspiel', None, 'decay', True, octave=1)]),
    Program(9, 'Glockenspiel', [V(IDIO + 'Glockenspiel', None, 'decay', octave=1)]),
    Program(10, 'Music Box', [V('Idiophones/Plucked Idiophones/Kalimba, Kenya', None, 'decay', True, octave=1), S('Celeste', 'decay')]),
    Program(11, 'Vibraphone', [V(IDIO + 'Vibraphone', None, 'decay', octave=1)]),
    Program(12, 'Marimba', [V(IDIO + 'Marimba', None, 'decay', octave=1)]),
    Program(13, 'Xylophone', [V(IDIO + 'Xylophone', None, 'decay', octave=1), F('ChromaticPercussion/Xylophone-MediumMallets', kind='decay')]),
    Program(14, 'Tubular Bells', [V(IDIO + 'Tubular Bells 1', None, 'decay', octave=1), F('ChromaticPercussion/TubularBells', kind='decay')]),
    Program(15, 'Dulcimer', [V('Chordophones/Zithers/Dan Tranh', None, 'decay', True, octave=1), V(PIANO + 'Psaltery, Bowed and Plucked', None, 'decay', True)]),
    # ---- 16-23 organ
    Program(16, 'Drawbar Organ', [F('Organ/DrawbarOrganEmulation')]),
    Program(17, 'Percussive Organ', [F('Organ/PercussiveOrganEmulation')]),
    Program(18, 'Rock Organ', [F('Organ/RockOrganEmulation')]),
    Program(19, 'Church Organ', [V(EDGE + 'Pipe Organ', 'Loud'), F('Organ/ChurchOrganEmulation')]),
    Program(20, 'Reed Organ', [V(EDGE + 'Renaissance Organ', '8\'', standin=True, octave=1), F('Organ/ButtonAccordionHN', standin=True)]),
    Program(21, 'Accordion', [F('Organ/ButtonAccordionHN', 'PRESET*tuned.sfz')]),
    Program(22, 'Harmonica', [V('Aerophones/Free Aerophones/Harmonica-Hohner-Special20-C', 'Sustains', octave=1, tags=('normal',))]),
    Program(23, 'Tango Accordion', [F('Organ/ButtonAccordionHN', 'PRESET*tuned.sfz', standin=True)]),
    # ---- 24-31 guitar
    Program(24, 'Acoustic Guitar (nylon)', [F('Guitar/SpanishClassicalGuitar', kind='decay')]),
    Program(25, 'Acoustic Guitar (steel)', [K('Karoryfer.Shinyguitar.v1.002', 'acoustic_five.sfz', 'decay', note='FreePats FSS steel guitar is GPL, excluded')]),
    Program(26, 'Electric Guitar (jazz)', [F('ElectricGuitar/EGuitarFSBS-jazz', '*jazz bridge 2*.sfz', 'decay')]),
    Program(27, 'Electric Guitar (clean)', [F('ElectricGuitar/EGuitarFSBS-clean', '*clean bridge 2*.sfz', 'decay'), K('Karoryfer.Emilyguitar.v1.001', 'emily_clean.sfz', 'decay')]),
    Program(28, 'Electric Guitar (muted)', [K('Karoryfer_Black_And_Green_Guitars_1000', '05-green_staccato.sfz', 'decay', True)]),
    Program(29, 'Overdriven Guitar', [F('ElectricGuitar/EGuitarFSBS-dist1', '*dist1 bridge*.sfz', 'decay')]),
    Program(30, 'Distortion Guitar', [F('ElectricGuitar/EGuitarFSBS-dist2', '*dist2 bridge*.sfz', 'decay')]),
    Program(31, 'Guitar Harmonics', [F('ElectricGuitar/EGuitarFSBS-clean', '*clean bridge 2*.sfz', 'decay', True, 'no harmonics articulation in any source')]),
    # ---- 32-39 bass
    Program(32, 'Acoustic Bass', [K('Sneakybass_v1.000', '02-sneakybass_pluck.sfz', 'decay', octave=-1, note='map written an octave up'), K('Karoryfer.Meatbass.v1.001', '04_pizz.sfz', 'decay')]),
    Program(33, 'Electric Bass (finger)', [F('ElectricGuitar/FingerBassYR', kind='decay'), K('Black_And_Blue_Basses_1002', '05-darkblack_pluck.sfz', 'decay', octave=-1)]),
    Program(34, 'Electric Bass (pick)', [F('ElectricGuitar/PickedBassYR', kind='decay'), K('Black_And_Blue_Basses_1002', '03-babyblue_all.sfz', 'decay', octave=-1)]),
    Program(35, 'Fretless Bass', [K('Karoryfer.Pastabass.v1.101', 'fetuccine.sfz', 'decay', octave=-1, note='Pastabass is a fretless; map written an octave up')]),
    Program(36, 'Slap Bass 1', [K('Karoryfer.Growlybass.v1.002', 'growlybass_angry.sfz', 'decay', True, octave=-1)]),
    Program(37, 'Slap Bass 2', [K('Karoryfer.Swagbass.v1.001', 'swagbass.sfz', 'decay', True)]),
    Program(38, 'Synth Bass 1', [F('Synthesizer/SynthBass1')]),
    Program(39, 'Synth Bass 2', [F('Synthesizer/SynthBass2'), F('Synthesizer/LatelyBass')]),
    # ---- 40-47 strings
    Program(40, 'Violin', [I('Violin', tags=('arco',), note='Iowa 2014, ff only'), O('Strings/Solo Violin', 'Arco Vib')]),
    Program(41, 'Viola', [I('Viola', tags=('arco',)), O('Strings/Viola Section', 'susvib', standin=True, note='section', octave=1)]),
    Program(42, 'Cello', [I('Cello', tags=('arco',)), K('Karoryfer_Bigcat_cello.v1.001', '01- Bowed*.sfz', octave=1, note='map written an octave down'), O('Strings/Cello Section', 'susvib', standin=True, octave=1)]),
    Program(43, 'Contrabass', [I('DoubleBass', tags=('arco',)), K('Karoryfer.Meatbass.v1.001', '02_arco_3vel.sfz'), K('Karoryfer.Ergo_EUB.v1.001', 'ergo_arco.sfz')]),
    Program(44, 'Tremolo Strings', [O('Strings/Violin Section', 'Trem', octave=1)]),
    Program(45, 'Pizzicato Strings', [O('Strings/Violin Section', 'Pizz', 'decay', octave=1), K('Karoryfer_Bigcat_cello.v1.001', '03- Plucked.sfz', 'decay', True, octave=1)]),
    Program(46, 'Orchestral Harp', [V('Chordophones/Composite Chordophones/Concert Harp', None, 'decay'), F('OrchestralStrings/ConcertHarp', kind='decay')]),
    Program(47, 'Timpani', [F('Percussion/Timpani', kind='decay', note='VCSL timpani mapped by FreePats; VCSL file names carry no note')]),
    # ---- 48-55 ensemble
    Program(48, 'String Ensemble 1', [O('Strings/Viola Section', 'susvib', octave=1)]),
    Program(49, 'String Ensemble 2', [O('Strings/Violin Section', 'susVib', octave=1)]),
    Program(50, 'Synth Strings 1', [F('Synthesizer/SynthStrings1')]),
    Program(51, 'Synth Strings 2', [F('Synthesizer/SynthStrings2')]),
    Program(52, 'Choir Aahs', [F('Synthesizer/SynthPadChoir', standin=True, note='no open choir; SSO chorus has unclear provenance'), S('Chorus')]),
    Program(53, 'Voice Oohs', [F('Synthesizer/SynthPadChoir', standin=True), S('Chorus')]),
    Program(54, 'Synth Voice', [F('Synthesizer/SynthPadChoir')]),
    Program(55, 'Orchestra Hit', [F('Synthesizer/SynthBrass1', standin=True)]),
    # ---- 56-63 brass
    Program(56, 'Trumpet', [I('Trumpet', tags=('vib',)), O('Brass/Trumpet', 'sus', octave=1)]),
    Program(57, 'Trombone', [I('TenorTrombone'), O('Brass/Tenor Trombone', 'sus', octave=1), O('Brass/OldTrombone', 'Sustain', octave=1)]),
    Program(58, 'Tuba', [K('Karoryfer_War_Tuba_v1002', '2-solo-poly.sfz'), I('Tuba')]),
    Program(59, 'Muted Trumpet', [O('Brass/Trumpet', 'straightM-sus', octave=1), O('Brass/Trumpet', 'harmonM-sus', octave=1)]),
    Program(60, 'French Horn', [I('Horn'), O('Brass/F Horn', 'sus', octave=1)]),
    Program(61, 'Brass Section', [I('Trumpet', tags=('novib',), standin=True, note='layer trumpet + trombone + horn in the SFZ'), O('Brass/Trumpet', 'sus', standin=True, octave=1)]),
    Program(62, 'Synth Brass 1', [F('Synthesizer/SynthBrass1')]),
    Program(63, 'Synth Brass 2', [F('Synthesizer/SynthBrass2')]),
    # ---- 64-71 reed
    Program(64, 'Soprano Sax', [V('Aerophones/Reed Aerophones/Saxello', 'Non-Vibrato', octave=1)]),
    Program(65, 'Alto Sax', [K('Karoryfer.Weresax.v.1.003', 'alto_map_forte_condenser.sfz')]),
    Program(66, 'Tenor Sax', [V('Aerophones/Reed Aerophones/Tenor Saxophone', 'Vibrato', octave=1), F('Reed/TenorSaxophone')]),
    Program(67, 'Baritone Sax', [K('Karoryfer.Bear_Sax.v1.004', '2-solo-poly.sfz')]),
    Program(68, 'Oboe', [O('Woodwinds/Oboe', 'Sus', octave=1)]),
    Program(69, 'English Horn', [O('Woodwinds/Oboe', 'Sus', standin=True, note='no cor anglais in any source', octave=1), S('Cor Anglais')]),
    Program(70, 'Bassoon', [O('Woodwinds/Bassoon', 'sus', octave=1)]),
    Program(71, 'Clarinet', [F('Reed/Clarinet'), O('Woodwinds/Clarinet', 'susLong', octave=1)]),
    # ---- 72-79 pipe
    Program(72, 'Piccolo', [O('Woodwinds/Piccolo', 'Sus', octave=1)]),
    Program(73, 'Flute', [O('Woodwinds/Flute', 'susvib', octave=1), O('Woodwinds/Flute', 'susNV', octave=1)]),
    Program(74, 'Recorder', [V(EDGE + 'Baroque Alto Recorder', 'Sustain', octave=1), F('Wind/Recorder', 'Recorder-2*.sfz')]),
    Program(75, 'Pan Flute', [V(EDGE + 'Ocarina, Typical', 'Sustains', standin=True, octave=1)]),
    Program(76, 'Blown Bottle', [V(EDGE + 'Ocarina, Small', None, standin=True, octave=1)]),
    Program(77, 'Shakuhachi', [V(EDGE + 'Baroque Tenor Recorder', 'Sustain', standin=True, octave=1)]),
    Program(78, 'Whistle', [V(EDGE + 'Ball Whistle', None, 'oneshot')]),
    Program(79, 'Ocarina', [V(EDGE + 'Ocarina, Typical', 'Sustains', octave=1), F('Wind/Ocarina')]),
    # ---- 80-87 synth lead
    Program(80, 'Lead 1 (square)', [F('Synthesizer/SynthSquare')]),
    Program(81, 'Lead 2 (sawtooth)', [K('Karoryfer.Caveman_Cosmonaut.v1.001', 'main.sfz', standin=True)]),
    Program(82, 'Lead 3 (calliope)', [F('Synthesizer/SynthCalliope')]),
    Program(83, 'Lead 4 (chiff)', [F('Synthesizer/SynthCalliope', standin=True)]),
    Program(84, 'Lead 5 (charang)', [F('Synthesizer/SynthBassLead', standin=True)]),
    Program(85, 'Lead 6 (voice)', [F('Synthesizer/SynthPadChoir', standin=True)]),
    Program(86, 'Lead 7 (fifths)', [F('Synthesizer/SynthFifths')]),
    Program(87, 'Lead 8 (bass + lead)', [F('Synthesizer/SynthBassLead')]),
    # ---- 88-95 synth pad
    Program(88, 'Pad 1 (new age)', [F('Synthesizer/NewAge')]),
    Program(89, 'Pad 2 (warm)', [K('Karoryfer.Cowsynth.v1.001', 'cowsynth_asthmatic_pad.sfz', standin=True)]),
    Program(90, 'Pad 3 (polysynth)', [K('Karoryfer.String_Cyborgs.v1.001', 'blackheart_Master.sfz', standin=True)]),
    Program(91, 'Pad 4 (choir)', [F('Synthesizer/SynthPadChoir')]),
    Program(92, 'Pad 5 (bowed)', [F('Synthesizer/SynthPadBowed')]),
    Program(93, 'Pad 6 (metallic)', [F('Synthesizer/SynthCrystal', standin=True)]),
    Program(94, 'Pad 7 (halo)', [F('Synthesizer/SynthPadChoir', standin=True)]),
    Program(95, 'Pad 8 (sweep)', [F('Synthesizer/SweepPad')]),
    # ---- 96-103 synth fx
    Program(96, 'FX 1 (rain)', [F('Synthesizer/SynthCrystal', standin=True)]),
    Program(97, 'FX 2 (soundtrack)', [F('Synthesizer/SynthSoundtrack')]),
    Program(98, 'FX 3 (crystal)', [F('Synthesizer/SynthCrystal')]),
    Program(99, 'FX 4 (atmosphere)', [F('Synthesizer/NewAge', standin=True)]),
    Program(100, 'FX 5 (brightness)', [F('Synthesizer/SynthCalliope', standin=True)]),
    Program(101, 'FX 6 (goblins)', [F('Synthesizer/SynthGoblins')]),
    Program(102, 'FX 7 (echoes)', [F('Synthesizer/SynthCrystal', standin=True)]),
    Program(103, 'FX 8 (sci-fi)', [F('Synthesizer/SynthSciFi')]),
    # ---- 104-111 ethnic
    Program(104, 'Sitar', [V('Chordophones/Zithers/Dan Tranh', None, 'decay', True, octave=1)]),
    Program(105, 'Banjo', [V('Chordophones/Composite Chordophones/Strumstick', None, 'decay', True, octave=1)]),
    Program(106, 'Shamisen', [V('Chordophones/Zithers/Dan Tranh', None, 'decay', True, octave=1)]),
    Program(107, 'Koto', [V('Chordophones/Zithers/Dan Tranh', None, 'decay', octave=1)]),
    Program(108, 'Kalimba', [V('Idiophones/Plucked Idiophones/Kalimba, Kenya', None, 'decay', octave=1), F('Ethnic/Kalimba', kind='decay')]),
    Program(109, 'Bag pipe', [F('Ethnic/Bagpipe', 'Bagpipe 2*.sfz')]),
    Program(110, 'Fiddle', [I('Violin', tags=('arco',)), O('Strings/Solo Violin', 'Arco Vib')]),
    Program(111, 'Shanai', [F('Ethnic/Bagpipe', 'Bagpipe 2*.sfz', standin=True)]),
    # ---- 112-119 percussive
    Program(112, 'Tinkle Bell', [V(IDIO + 'Hand Bells, Nepalese', None, 'decay'), V(IDIO + 'Finger Cymbals', None, 'oneshot')]),
    Program(113, 'Agogo', [V(IDIO + 'Agogo Bells', None, 'oneshot')]),
    Program(114, 'Steel Drums', [F('ChromaticPercussion/Hang-D-minor', kind='decay', note='handpan')]),
    Program(115, 'Woodblock', [V(IDIO + 'Woodblock', None, 'oneshot')]),
    Program(116, 'Taiko Drum', [V(MEMB + 'Bass Drum 1', None, 'oneshot', True), V(MEMB + 'Frame Drum', None, 'oneshot', True)]),
    Program(117, 'Melodic Tom', [V(MEMB + 'Tom 1', None, 'oneshot')]),
    Program(118, 'Synth Drum', [F('Percussion/SynthesizerPercussion', kind='oneshot')]),
    Program(119, 'Reverse Cymbal', [V(IDIO + 'Suspended Cymbal 1', None, 'oneshot', note='reverse the sample')]),
    # ---- 120-127 sound effects
    Program(120, 'Guitar Fret Noise', [K('Karoryfer.Shinyguitar.v1.002', 'acoustic_noises.sfz', 'oneshot')]),
    Program(121, 'Breath Noise', [V(EDGE + 'Ocarina, Small', None, 'oneshot', True, octave=1)]),
    Program(122, 'Seashore', [V('Membranophones/Other Membranophones/Ocean Drum', None, 'oneshot')]),
    Program(123, 'Bird Tweet', [V(EDGE + 'Ball Whistle', None, 'oneshot', True)]),
    Program(124, 'Telephone Ring', [V(IDIO + 'Hand Bells, Nepalese', None, 'oneshot', True)]),
    Program(125, 'Helicopter', [V(IDIO + 'Ratchet', None, 'oneshot', True)]),
    Program(126, 'Applause', [V(IDIO + 'Claps', None, 'oneshot')]),
    Program(127, 'Gunshot', [V(IDIO + 'Slapstick', None, 'oneshot'), V(IDIO + 'Anvil', None, 'oneshot', True)]),
]
assert len(PROGRAMS) == 128 and [p.num for p in PROGRAMS] == list(range(128))


# ---- picks from the swipe app (python3 -m kobi.swipe): an alternative picked for a program there goes first
def _pick_cand(pick: dict, kind: str) -> Cand | None:
    loc, root = pick['loc'], pick.get('root') or ''
    note = f"swipe pick: {pick.get('lib_title', '')} ({pick.get('license', '')})" + (f" — {pick['note']}" if pick.get('note') else '')
    octave = int(pick.get('octave') or 0)
    if pick['shape'] == 'gm':                                   # the app's octave comes on top of the candidate's own
        return Cand(loc['source'], loc['path'], loc['sub'], loc['kind'], loc['standin'], loc['note'] or note,
                    loc['octave'] + octave, tuple(loc['tags']))
    if pick['shape'] == 'folder':
        if 'inst' in loc:                                       # an Iowa instrument the app fetched
            return Cand('Iowa', loc['inst'], None, kind, note=note, octave=octave, tags=tuple(loc['tags']))
        return Cand(root.split('/')[0], loc['path'], loc['sub'], kind, note=note, octave=octave, tags=tuple(loc['tags']))
    if pick['shape'] in ('sfz', 'derived') and 'rel' in loc:   # root: Karoryfer/<set>, FreePats, Extra/<library> ...
        source, _, path = root.partition('/')
        return Cand(source, path, glob.escape(loc['rel']), kind, note=note, octave=octave)
    return None


def apply_picks(programs: list, path: str, layers_out: dict | None = None) -> list:
    """Put each pick recorded in ``path`` (SWIPE_PICKS.json) first among its program's candidates, once
    its samples are all on disk.  Returns [(program number, Cand)] for what was applied.  A layered pick
    goes into ``layers_out`` (gm_map.LAYERS) as its stack of (candidate, gain, pan); an echo on it is
    recorded in SWIPE_PICKS but not built (the bank's players have no delay).  The drum kit is
    assembled by kobi.drums, so a kit pick is only recorded."""
    if not os.path.exists(path):
        return []
    import json
    with open(path) as fh:
        picks = json.load(fh)
    applied = []
    for key, row in picks.items():
        num, pick = int(key), row.get('pick')
        if row.get('verdict') != 'replace' or not pick or not pick.get('complete') or num >= len(programs):
            continue
        prog = programs[num]
        kind = next((c.kind for c in prog.cands if c.resolve()[1]), prog.cands[0].kind)
        if pick.get('layers'):                                  # a layered pick: a stack, as for the brass section
            layers = [(_pick_cand(L, kind), float(L.get('gain', 0.0)), float(L.get('pan', 0.0)), dict(cover=bool(L.get('cover'))))
                      for L in pick['layers']]
            layers = [x for x in layers if x[0] is not None and x[0].resolve()[1]]
            if not layers:
                continue
            if layers_out is not None:
                layers_out[num] = layers
            prog.cands = [layers[0][0]] + prog.cands
            applied.append((num, layers[0][0]))
            continue
        cand = _pick_cand(pick, kind)
        if cand is None or not cand.resolve()[1]:
            continue
        prog.cands = [cand] + [c for c in prog.cands if (c.source, c.path, c.sub, c.tags) != (cand.source, cand.path, cand.sub, cand.tags)]
        if layers_out is not None:                              # a single instrument picked over a stack (the brass section)
            layers_out.pop(num, None)
        applied.append((num, cand))
    return applied



# programs built as a stack of several instruments: (candidate, gain dB).  Each layer keeps its own
# key range, so a note sounds on every layer whose instrument can play it.
# (candidate, gain dB, pan): the section is seated across the stereo field — trumpets left, saxes
# either side of centre, trombone centre-right, horns right (SFZ pan, -100..100)
LAYERS = {
    61: [(I('Trumpet', tags=('novib',)), 0.0, -40), (I('Horn'), -2.0, 40), (I('TenorTrombone'), -3.0, 20),
         (K('Karoryfer.Weresax.v.1.003', 'alto_map_forte_condenser.sfz'), -5.0, -15),
         (V('Aerophones/Reed Aerophones/Tenor Saxophone', 'Vibrato', octave=1), -5.0, 15)],
}

# KOBI_SWIPE_PICKS=0 reads the map as written (the swipe app itself compares against the bank as built)
APPLIED_PICKS = apply_picks(PROGRAMS, os.path.join(paths.ROOT, 'SWIPE_PICKS.json'), LAYERS) \
    if os.environ.get('KOBI_SWIPE_PICKS', '1') != '0' else []

# channel 10: kobi.drums assembles the GM kit (keys 35-81) from the Muldjord kit remapped to GM keys plus VCSL
# percussion; these entries are the raw kits it draws on (Muldjord maps its pieces to keys 48-66, not GM)
DRUMS = [
    F('Percussion/MuldjordKit', kind='kit', note='CC BY 4.0 acoustic kit, own key layout 48-66; remapped by kobi.drums'),
    K('Unruly_Drums_1100', '03-kit-complete.sfz', 'kit', note='CC0 alternative'),
    K('Swirly.Drums_1104', 'Full_kit.sfz', 'kit', note='CC0 alternative'),
]


def validate() -> list[dict]:
    rows = []
    for p in PROGRAMS:
        for i, c in enumerate(p.cands):
            path, n = c.resolve()
            rows.append(dict(program=p.num, name=p.name, rank=i, source=c.source, path=c.path, sub=c.sub or '', kind=c.kind,
                             standin=c.standin, note=c.note, octave=c.octave, tags=c.tags, resolved=path, count=n, ok=(n != 0)))
    return rows


def main() -> int:
    rows = validate()
    bad = [r for r in rows if not r['ok']]
    first = {r['program']: r for r in rows if r['rank'] == 0}
    by_src = {}
    for r in first.values():
        by_src[r['source']] = by_src.get(r['source'], 0) + 1
    standins = sum(1 for r in first.values() if r['standin'])
    gaps = sum(1 for r in first.values() if r['source'] == 'SSO')
    lines = ['# GM program mapping', '',
             f'Primary source per program: ' + ', '.join(f'{k} {v}' for k, v in sorted(by_src.items())) +
             f'.  {standins} stand-ins (a related timbre, not the named instrument); {gaps} programs served from the SSO fork.  '
             f'Candidates are listed in priority order; the first one that exists is used.  octave: file names sit that many '
             f'octaves below the true pitch (from the pitch audit); tags: only files carrying these words.', '',
             '| # | program | rank | source | instrument | sub / sfz | kind | stand-in | octave | tags | on disk | note |', '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        lines.append(f"| {r['program']} | {r['name']} | {r['rank']} | {r['source']} | {r['path']} | {r['sub']} | {r['kind']} | "
                     f"{'yes' if r['standin'] else ''} | {r['octave'] or ''} | {' '.join(r['tags'])} | {'MISSING' if not r['ok'] else r['count']} | {r['note']} |")
    lines += ['', '## Drums (channel 10)', '', '| rank | source | path | sfz | note | on disk |', '|---|---|---|---|---|---|']
    for i, c in enumerate(DRUMS):
        path, n = c.resolve()
        lines.append(f'| {i} | {c.source} | {c.path} | {c.sub or ""} | {c.note} | {"MISSING" if n == 0 else n} |')
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'MAPPING.md'), 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    print(f'{len(PROGRAMS)} programs, {len(rows)} candidates, {len(bad)} missing on disk')
    for r in bad:
        print(f'  MISSING {r["program"]:3d} {r["name"]:24s} {r["source"]}: {r["path"]} / {r["sub"]}')
    print('primary sources:', by_src, f'| stand-ins {standins}, VSCO2/SSO gaps {gaps}')
    for num, c in APPLIED_PICKS:
        print(f'  swipe pick first for {num:3d} {PROGRAMS[num].name}: {c.source}: {c.path} {c.sub or ""}')
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
