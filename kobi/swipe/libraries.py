"""kobi.swipe.libraries — every library the swipe app may draw alternatives from.

Local libraries are the ones already pulled into ``uncompressed/`` (SOURCES.md).  Remote ones are
free, openly licensed SFZ instruments that are fetched piece by piece into
``uncompressed/Extra/<id>/`` (Iowa instruments into ``uncompressed/Iowa/<name>/``, next to the
ones already there) only when a card needs them.

``hints`` pins a single-instrument library to the programs it can play ({program: strength});
libraries without hints (VCSL, VSCO 2, FreePats, the GM sets) are classified by file names.
Excluded on purpose: NC-licensed sets (jRhodes3c/3d, Rickenbacker 4001, MF Tin Whistle) and the
sfzinstruments repositories that state no licence at all — a pick has to be shippable in the bank.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .gm_words import DRUMS


@dataclass
class Library:
    id: str
    title: str
    license: str
    host: str                      # 'local-sfz' | 'local-folder' | 'github' | 'zip' | 'iowa'
    where: str = ''                # local: source folder under uncompressed/; github: owner/repo; zip: URL; iowa: page
    hints: dict = field(default_factory=dict)
    note: str = ''
    numbered: str = ''             # 'one' / 'zero': SFZ names start with a GM program number (1- or 0-based)
    tags: tuple = ()               # iowa: keep only files with these words (vib / nonvib)
    batch: int = 1                 # 2: added for the second look (2026-09-22); marked "new" on review cards

    @property
    def remote(self) -> bool:
        return self.host in ('github', 'zip', 'iowa')

    @property
    def sf2(self) -> str:
        """An SF2 library's soundfont (host 'sf2'), kept in uncompressed/SF2/."""
        import os
        from .. import paths
        return os.path.join(paths.SOURCES, 'SF2', self.where)

    @property
    def open_licence(self) -> bool:
        low = self.license.lower()
        return not any(w in low for w in ('nc', 'unstated', 'sampling plus'))


def H(*groups) -> dict:
    """H((1.0, 0, 1), (0.5, 3)) -> {0: 1.0, 1: 1.0, 3: 0.5}"""
    out = {}
    for strength, *progs in groups:
        for p in progs:
            out[p] = strength
    return out


KIT = H((1.0, DRUMS))

LOCAL = [
    Library('VCSL', 'Versilian Community Sample Library', 'CC0 1.0', 'local-folder', 'VCSL'),
    Library('VSCO2', 'VS Chamber Orchestra 2 CE', 'CC0 1.0', 'local-folder', 'VSCO2'),
    Library('Iowa', 'University of Iowa MIS', 'unrestricted', 'local-folder', 'Iowa'),
    Library('FreePats', 'FreePats', 'CC0 1.0 (a few CC BY / GPL, see LICENSES.md)', 'local-sfz', 'FreePats'),
    Library('FreePatsGM', 'FreePats GM set', 'CC0 + GPL bundle', 'local-sfz', 'FreePats/SoundSets/FreePatsGM', numbered='one'),
    Library('SSO', 'Sonatina Symphonic Orchestra', 'CC Sampling Plus 1.0 (provenance caveats)', 'local-sfz', 'Sonatina Symphonic Orchestra'),
    # Karoryfer sets: one instrument each, so the programs are pinned and file names only pick among them
    Library('Karoryfer.BigLittleBass', 'Big Little Bass (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Big_Little_Bass_1000', H((1.0, 33, 34), (0.5, 35, 36, 37, 32))),
    Library('Karoryfer.BigRusty', 'Big Rusty Drums (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Big_Rusty_Drums_1100', KIT),
    Library('Karoryfer.BlackBlue', 'Black And Blue Basses (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Black_And_Blue_Basses_1002', H((1.0, 33, 34), (0.5, 35, 36, 37, 32))),
    Library('Karoryfer.MerryOrks', '272 Merry Orks (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer.272_Merry_Orks.v1.001', H((0.8, 52, 53), (0.5, 54, 85, 91))),
    Library('Karoryfer.BearSax', 'Bear Sax (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer.Bear_Sax.v1.004', H((1.0, 67), (0.5, 66))),
    Library('Karoryfer.Bigcat', 'Bigcat Cello (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer_Bigcat_cello.v1.001', H((1.0, 42), (0.5, 45, 41, 43))),
    Library('Karoryfer.BlackGreen', 'Black And Green Guitars (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer_Black_And_Green_Guitars_1000', H((1.0, 27, 28, 29, 30), (0.5, 26, 31))),
    Library('Karoryfer.Caveman', 'Caveman Cosmonaut (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer.Caveman_Cosmonaut.v1.001', H((0.8, 81, 80, 38, 39), (0.5, 84, 87, 90, 62, 63))),
    Library('Karoryfer.Cowsynth', 'Cowsynth (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer.Cowsynth.v1.001', H((0.8, 89, 90), (0.5, 88, 95, 38, 81, 62))),
    Library('Karoryfer.Emily', 'Emilyguitar (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer.Emilyguitar.v1.001', H((1.0, 27), (0.5, 26, 25, 28, 31))),
    Library('Karoryfer.Ergo', 'Ergo electric upright (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer.Ergo_EUB.v1.001', H((1.0, 32), (0.5, 43, 33, 35))),
    Library('Karoryfer.Fashionbass', 'Fashionbass (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer.Fashionbass.v1.001', H((1.0, 33, 34), (0.5, 36, 37))),
    Library('Karoryfer.GogodzeII', 'Gogodze Phu vol II (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer_Gogodze_Phu_vol_II.v1.001', H((0.8, DRUMS), (0.5, 116, 117))),
    Library('Karoryfer.GogodzeI', 'Gogodze Phu vol I (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer.Gogodze_Phu_vol_I.v1.001', H((0.5, 116, 117, 115, 113))),
    Library('Karoryfer.Growlybass', 'Growlybass (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer.Growlybass.v1.002', H((1.0, 33), (0.5, 34, 36, 37))),
    Library('Karoryfer.HorsePulse', 'Horse Pulse bass tagelharpa (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer_Horse_Pulse_1000', H((0.5, 32, 104, 45))),
    Library('Karoryfer.Meatbass', 'Meatbass (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer.Meatbass.v1.001', H((1.0, 43, 32), (0.5, 33))),
    Library('Karoryfer.Pastabass', 'Pastabass (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer.Pastabass.v1.101', H((1.0, 35), (0.5, 33))),
    Library('Karoryfer.Scarypiano', 'Scarypiano (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer.Scarypiano.v1.002', H((0.8, 0, 3), (0.5, 1))),
    Library('Karoryfer.Shinyguitar', 'Shinyguitar (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer.Shinyguitar.v1.002', H((1.0, 25), (0.5, 24, 27, 120))),
    Library('Karoryfer.Squidpipes', 'Squidpipes (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/karoryfer.squidpipes-v1.001', H((1.0, 109), (0.5, 111))),
    Library('Karoryfer.StringCyborgs', 'String Cyborgs (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer.String_Cyborgs.v1.001', H((1.0, 50, 51), (0.5, 90, 92, 48))),
    Library('Karoryfer.Swagbass', 'Swagbass (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer.Swagbass.v1.001', H((1.0, 33), (0.5, 36, 37, 34))),
    Library('Karoryfer.WarTuba', 'War Tuba (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer_War_Tuba_v1002', H((1.0, 58))),
    Library('Karoryfer.Weresax', 'Weresax (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Karoryfer.Weresax.v.1.003', H((1.0, 65), (0.5, 64, 66))),
    Library('Karoryfer.Sneakybass', 'Sneakybass (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Sneakybass_v1.000', H((1.0, 32), (0.5, 43))),
    Library('Karoryfer.Swirly', 'Swirly Drums (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Swirly.Drums_1104', KIT),
    Library('Karoryfer.Unruly', 'Unruly Drums (Karoryfer)', 'CC0 1.0', 'local-sfz', 'Karoryfer/Unruly_Drums_1100', KIT),
    # given by Nathan for the nylon guitar (from ~/Downloads/Classical_Acoustic_Guitar.zip; no licence file came with it)
    Library('ClassicalAcousticGuitar', 'Classical Acoustic Guitar', 'unknown: check before shipping', 'local-sfz',
            'Extra/ClassicalAcousticGuitar', H((1.0, 24), (0.5, 25)), batch=2),
]

GH = 'sfzinstruments/'
REMOTE = [
    # a whole GM bank in SFZ: every program has an intended counterpart
    Library('Discord-GM', 'Discord SFZ GM Bank', 'CC0 / CC BY (per instrument)', 'github', GH + 'Discord-SFZ-GM-Bank', numbered='one',
            note='community GM bank; licence of each instrument is in its SFZ header'),
    # pianos
    Library('SplendidGrandPiano', 'Splendid Grand Piano (Akai)', 'Public Domain', 'github', GH + 'SplendidGrandPiano', H((1.0, 0), (0.8, 1))),
    Library('HeadroomPiano', 'Headroom Piano (Yamaha C3, Bengt Nilsson)', 'CC BY 4.0', 'github', GH + 'BengtNilsson.HeadroomPiano', H((1.0, 0), (0.8, 1))),
    Library('OsirisPiano', 'Osiris Piano (Versilian + Karoryfer)', 'CC0 1.0', 'github', GH + 'Osiris_Piano', H((1.0, 0), (0.5, 1, 3))),
    Library('GregSullivan-EPianos', 'Greg Sullivan E-Pianos (CP80, Pianet T, Wurlitzer)', 'CC BY 3.0', 'github', GH + 'GregSullivan.E-Pianos',
            H((0.8, 2, 4), (0.5, 5, 7))),
    # strings / plucked / folk
    Library('Smolken-DoubleBass', "D. Smolken's Double Bass", 'CC0 1.0', 'github', GH + 'dsmolken.double-bass', H((1.0, 32, 43))),
    Library('Erhu', 'AliExpress Erhu', 'CC0 1.0', 'github', GH + 'aliexpress-erhu', H((1.0, 110), (0.5, 40, 111))),
    Library('CitharaBarbarica', 'Cithara Barbarica (medieval lyre)', 'CC0 1.0', 'github', GH + 'cithara-barbarica', H((0.5, 46, 15, 107))),
    Library('HungarianZither', 'Hungarian Zither', 'CC0 1.0', 'github', GH + 'hungarian_zither', H((1.0, 15), (0.5, 107, 104))),
    Library('Ganjo', 'Ganjo (guitar banjo)', 'CC0 1.0', 'github', GH + 'ganjo', H((1.0, 105))),
    Library('Kay5StringBanjo', 'Kay 5-String Banjo (Flame Studios)', 'GPL 3.0 or later', 'github', GH + 'FlameStudios.Kay5StringBanjo', H((1.0, 105))),
    Library('EtherealwindsHarp', 'Etherealwinds Harp II CE (Versilian)', 'CC0 1.0', 'zip', 'https://versilian-studios.com/Distro/EWHarp2CE_SFZ-Raw.zip',
            H((1.0, 46), (0.5, 15, 107))),
    # winds
    Library('MTG-SoloSax', 'MTG Solo Sax (soprano, alto, tenor, baritone)', 'CC BY 4.0', 'github', GH + 'MTG.SoloSax'),
    Library('IxoxFlute', 'Ixox Flute', 'CC BY 4.0', 'github', GH + 'Ixox.Flute', H((1.0, 73), (0.5, 72, 75, 77, 74))),
    # percussion, mallets
    Library('JLearman-SteelDrum', 'Tenor Steel Drum (Jeff Learman)', 'Unlicense', 'github', GH + 'jlearman.SteelDrum', H((1.0, 114))),
    Library('MSLP-Vibes', 'MSLP Vibes (bandshed)', 'CC BY 3.0', 'zip', 'http://www.bandshed.net/sounds/sfz/vibes.zip', H((1.0, 11))),
    Library('BodyPercussion', 'Body Percussion', 'CC0 1.0', 'github', GH + 'body_percussion', H((0.5, 126, 115))),
    # organs, vocals, misc sets classified by name
    Library('GTownChurch', 'G-Town Church Sampling Project', 'CC Sampling Plus 1.0', 'github', GH + 'GTownChurchSamplingProject'),
    Library('EthanWiner', 'Ethan Winer collection', 'Public Domain', 'github', GH + 'EthanWiner.Soundfonts'),
    Library('LegatoVocal', 'Legato vocal (sfzinstruments tutorial)', 'CC0 1.0', 'github', GH + 'legato_vocal_tutorial', H((0.5, 52, 53, 85, 54))),
    # drum kits (channel 10)
    Library('VirtuosityDrums', 'Virtuosity Drums (Versilian + Karoryfer)', 'CC0 1.0', 'github', GH + 'virtuosity_drums', KIT),
    Library('DRSKit', 'DrumGizmo DRS Kit', 'CC BY 4.0', 'github', GH + 'DrumGizmo.DRSKit', KIT),
    Library('MuldjordKit-sfz', 'DrumGizmo Muldjord Kit (sfz port)', 'CC BY 4.0', 'github', GH + 'DrumGizmo.MuldjordKit', KIT),
    Library('NakedDrums', 'Naked Drums (Wilkinson Audio)', 'CC BY 4.0', 'github', GH + 'WilkinsonAudio.NakedDrums', KIT),
    Library('SamsSonor', "Sam's Sonor drum kit", 'CC BY-SA 4.0', 'github', GH + 'SamsSonor', KIT),
    Library('SMDrums', 'SM Drums', 'Public Domain', 'github', GH + 'SMDrums', KIT),
]

# University of Iowa MIS 2012 pages not pulled yet (brass and solo strings are already local)
IOWA = [
    ('Flute', 'MISFlute2012.html', H((1.0, 73), (0.5, 72, 74, 77, 75))),
    ('AltoFlute', 'MISaltoflute2012.html', H((0.8, 73), (0.5, 77, 75))),
    ('BassFlute', 'MISBassFlute2012.html', H((0.5, 73, 77, 75))),
    ('Oboe', 'MISOboe2012.html', H((1.0, 68), (0.5, 69, 111))),
    ('EbClarinet', 'MISEbClarinet2012.html', H((0.8, 71))),
    ('BbClarinet', 'MISBbClarinet2012.html', H((1.0, 71))),
    ('BassClarinet', 'MISBbBassClarinet2012.html', H((0.5, 71, 70))),
    ('Bassoon', 'MISBassoon2012.html', H((1.0, 70))),
    ('SopranoSax', 'MISBbSopranoSaxophone2012.html', H((1.0, 64))),
    ('AltoSax', 'MISEbAltoSaxophone2012.html', H((1.0, 65))),
    ('Marimba', 'MISMarimba2012.html', H((1.0, 12))),
    ('Vibraphone', 'MISVibraphone2012.html', H((1.0, 11))),
    ('Xylophone', 'MISxylophone2012.html', H((1.0, 13))),
    ('Bells', 'MISBells2012.html', H((1.0, 9), (0.5, 14, 112, 8))),
    ('Crotales', 'MISCrotales2012.html', H((0.8, 112), (0.5, 9, 8))),
]
for name, page, hints in IOWA:
    REMOTE.append(Library(f'Iowa-{name}', f'Iowa MIS {name}', 'unrestricted', 'iowa', page, hints,
                          note='2014 stereo recordings, one note per file'))

# General MIDI soundfonts with an open licence: every program has its GM counterpart (the synth leads, pads
# and effects no SFZ library covers), plus GS variation presets.  Presets are extracted to SFZ + WAV in
# uncompressed/Extra/<id>/ the first time a card needs them; the soundfonts sit in uncompressed/SF2/.
SF2 = [
    Library('FluidR3-GM', 'FluidR3 GM (Frank Wen)', 'MIT', 'sf2', 'FluidR3_GM.sf2', numbered='sf2', batch=2),
    Library('MS-Basic', 'MuseScore MS Basic', 'MIT', 'sf2', 'MS_Basic.sf2', numbered='sf2', batch=2),
    Library('TimGM6mb', 'TimGM6mb (Tim Brechbill)', 'GPL 2.0', 'sf2', 'TimGM6mb.sf2', numbered='sf2', batch=2),
    Library('A320U', 'Airfont 320 update (Milton Paredes)', 'GPL 2.0 or later', 'sf2', 'A320U.sf2', numbered='sf2', batch=2),
]

# built here from other libraries: string samples with the bow's first scratch trimmed off, and the
# layered versions asked for in notes (see catalog.DERIVED)
DERIVED = Library('Derived', 'Made here from the libraries above', 'as its sources', 'derived', 'Derived', batch=2)

ALL = {lib.id: lib for lib in LOCAL + REMOTE + SF2 + [DERIVED]}
