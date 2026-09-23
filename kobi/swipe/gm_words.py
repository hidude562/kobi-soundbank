"""kobi.swipe.gm_words — which GM programs an instrument's name says it could play.

``classify(text)`` reads a library / folder / SFZ name and returns {program: strength}: 1.0 when the
name is the program's instrument (``violin`` for Violin), 0.5 when it is a related timbre worth
hearing as a stand-in (``fiddle`` for Violin).  Program 128 is the drum kit.

``REGISTER`` is where each program's preview phrase sits, so the bank's current sound and every
alternative play the same notes; ``MONO`` programs end on a held note instead of a chord.
"""
from __future__ import annotations

import re

DRUMS = 128

FAMILIES = ['Piano', 'Chromatic percussion', 'Organ', 'Guitar', 'Bass', 'Strings', 'Ensemble', 'Brass',
            'Reed', 'Pipe', 'Synth lead', 'Synth pad', 'Synth effects', 'Ethnic', 'Percussive', 'Sound effects']


def family(num: int) -> str:
    return 'Drum kit' if num == DRUMS else FAMILIES[num // 8]


# preview root note per program (the phrase is an arpeggio from here plus a held chord or note)
REGISTER = {p: 60 for p in range(128)}
REGISTER.update({
    8: 72, 9: 84, 10: 76, 11: 65, 12: 60, 13: 77, 14: 65, 15: 62,
    24: 52, 25: 52, 26: 52, 27: 55, 28: 45, 29: 52, 30: 45, 31: 64,
    32: 36, 33: 36, 34: 36, 35: 36, 36: 36, 37: 36, 38: 36, 39: 36,
    40: 67, 41: 60, 42: 48, 43: 36, 44: 60, 45: 60, 46: 60, 47: 43,
    56: 65, 57: 53, 58: 41, 59: 65, 60: 57, 61: 60, 62: 55, 63: 55,
    64: 67, 65: 63, 66: 56, 67: 48, 68: 69, 69: 62, 70: 48, 71: 62,
    72: 84, 73: 72, 74: 72, 75: 72, 76: 67, 77: 67, 78: 79, 79: 72,
    104: 60, 105: 60, 106: 57, 107: 60, 108: 67, 109: 64, 110: 67, 111: 67,
    112: 79, 113: 67, 114: 64, 115: 67, 116: 45, 117: 50, 118: 50,
})

# single-line instruments: end on a held note, not a chord
MONO = set(range(40, 44)) | set(range(56, 61)) | set(range(64, 88)) | {22, 109, 110, 111}


def _p(s: str) -> re.Pattern:
    return re.compile(s)


# program -> (exact, related); matched against ``norm(text)``
PATTERNS: dict[int, tuple[str, str | None]] = {
    0: (r'grand ?piano|\bgrand\b|steinway|concert grand|yamaha c[3-7]|\bcf ?3\b|salamander|splendid|headroom|osiris|\bpiano\b(?!.*(electric|e piano|toy|pianet))',
        r'upright|\bpiano\b'),
    1: (r'bright.*piano|piano.*bright', r'grand ?piano|\bpiano\b|upright'),
    2: (r'\bcp ?80\b|\bcp ?70\b|electric grand', r'\be ?piano\b|electric piano|rhodes|wurli'),
    3: (r'honky|tack piano|detuned piano|saloon|scary piano', r'upright|\bpiano\b'),
    4: (r'rhodes|\be ?piano\b|electric piano|wurli|pianet|suitcase', r'fm piano|dx ?7|tx81z.*piano'),
    5: (r'fm ?piano|\bdx ?7\b|\bfm\b.*piano', r'rhodes|\be ?piano\b|electric piano|wurli'),
    6: (r'harpsichord|clavecin|cembalo|virginal|spinet', r'clavichord|\blute\b'),
    7: (r'clavinet|\bclav\b|clavi ?synth', r'pianet|harpsichord'),
    8: (r'celest[ae]|celesta', r'glock|music ?box|toy piano|crotal'),
    9: (r'glock', r'celest|crotal|orchestra bells|\bbells\b'),
    10: (r'music ?box', r'celest|kalimba|toy piano|glock|mbira'),
    11: (r'vibraphone|\bvibes\b|vibraharp', r'marimba|glock|metallophone'),
    12: (r'marimba', r'xylo|balafon|vibraphone'),
    13: (r'xylophone|\bxylo\b', r'marimba|balafon|glock'),
    14: (r'tubular|\bchimes\b|church bell', r'\bbells?\b|crotal|gong'),
    15: (r'dulcimer|cimbalom|santur|santoor|yangqin|zither|hackbrett', r'psaltery|lyre|cithara|koto|dan tranh|mandolin|lap ?harp'),
    16: (r'drawbar|hammond|\bb ?3\b|tonewheel|jazz organ', r'\borgan\b'),
    17: (r'percussive organ|perc organ', r'drawbar|hammond|\borgan\b'),
    18: (r'rock organ|leslie|farfisa|vox continental', r'drawbar|hammond|\borgan\b'),
    19: (r'church organ|church.*\borgan\b|pipe organ|orgue|kirchen|cathedral|principal|diapason|plenum', r'\borgan\b|harmonium'),
    20: (r'reed organ|harmonium|pump organ|melodeon|renaissance organ|portative|regal', r'accordion|\borgan\b|concertina'),
    21: (r'accordion|akkordeon|bayan|musette', r'concertina|harmonium|bandoneon'),
    22: (r'harmonica|blues harp|mouth ?organ', r'melodica|accordion'),
    23: (r'bandoneon|tango|concertina', r'accordion'),
    24: (r'nylon|classical guitar|spanish.*guitar|flamenco|guitarra', r'acoustic guitar|\bguitar\b(?!.*(electric|bass))'),
    25: (r'steel string|acoustic guitar|steel guitar|ovation|dreadnought|folk guitar|12 ?string|acoustic (five|six)',
         r'\bguitar\b(?!.*bass)|nylon|ukulele'),
    26: (r'jazz guitar|hollow ?body|archtop|guitar.*jazz|jazz.*guitar', r'clean|electric guitar'),
    27: (r'clean|electric guitar|strat|telecaster', r'\bguitar\b(?!.*bass)'),
    28: (r'guitar.*(mute|palm|staccato|funky|choke)|(mute|palm|funky).*guitar', r'electric guitar|clean'),
    29: (r'overdrive|crunch|\bdrive\b|\bod\b', r'dist|electric guitar'),
    30: (r'distort|\bdist\d?\b|metal|high ?gain|fuzz', r'overdrive|crunch'),
    31: (r'guitar.*harmonic|harmonic.*guitar', r'clean|electric guitar'),
    32: (r'upright bass|double ?bass.*pizz|pizz.*(double ?bass|contrabass)|acoustic bass|standup|sneaky|\beub\b|electric upright|double ?bass(?!.*arco)',
         r'contrabass|double ?bass|bass.*pluck'),
    33: (r'finger.*\bbass|\bbass.*finger|jazz bass|precision|\b[pj] ?bass\b|electric bass|bass guitar', r'\bbass\b'),
    34: (r'\bpick(ed)?\b|plectrum', r'electric bass|bass guitar|\bbass\b'),
    35: (r'fretless|pasta', r'electric bass|bass guitar|\bbass\b'),
    36: (r'\bslap|\bpop\b|angry', r'electric bass|bass guitar|\bbass\b'),
    37: (r'\bslap|\bpop\b|swag', r'electric bass|bass guitar|\bbass\b'),
    38: (r'synth ?bass|moog bass|\b303\b|analog bass|sub ?bass|bass synth', r'\bsynth\b'),
    39: (r'synth ?bass|moog bass|\b303\b|analog bass|sub ?bass|bass synth', r'\bsynth\b'),
    40: (r'\bviolin\b(?!.*(section|ensemble|violins))|violino|geige|solo violin', r'fiddle|erhu|\bviolins?\b'),
    41: (r'\bviola\b(?!.*(section|ensemble|gamba))', r'violin|cello'),
    42: (r'\bcello\b(?!.*(section|celli))|violoncello', r'celli|viola|gamba'),
    43: (r'contrabass|double ?bass|string bass|kontrabass|\bbass solo\b', r'cello|basses'),
    44: (r'trem', r'strings?|violins|section'),
    45: (r'pizz', r'strings?|violins|section|pluck'),
    46: (r'\bharp\b(?!.*(sichord|hohner|blues))|\barpa\b|harp ?[i2]|concert harp|folk harp', r'lyre|cithara|zither|psaltery|lap ?harp|kantele'),
    47: (r'timpani|\btimp\b|kettle', r'bass drum|\btom\b'),
    48: (r'string(s)? ?(section|ensemble|orchestra)|violins|all strings|full strings|\bsection\b|1st violins|2nd violins|celli',
         r'\bviolin\b|\bviola\b|\bcello\b|\bstrings?\b'),
    49: (r'string(s)? ?(section|ensemble|orchestra)|violins|all strings|full strings|\bsection\b|celli|slow strings',
         r'\bviolin\b|\bviola\b|\bcello\b|\bstrings?\b'),
    50: (r'synth ?strings?|string machine|solina|string cyborgs?', r'\bstrings?\b|\bpad\b'),
    51: (r'synth ?strings?|string machine|solina|string cyborgs?', r'\bstrings?\b|\bpad\b'),
    52: (r'choir|chorus|\baah|\bvocal|\bvoices?\b|singers?|merry orks', r'\bvox\b|soprano voice|\bhum\b'),
    53: (r'\booh|\bhum\b|choir|chorus|\bvoices?\b|merry orks', r'\bvocal|\bvox\b'),
    54: (r'synth ?voice|\bvox\b|vocoder|synth ?choir', r'choir|chorus|\bvoices?\b|\bvocal'),
    55: (r'orch(estra)? ?hit|\bstab\b', r'\bhits?\b|brass section|marcato'),
    56: (r'trumpet(?!.*(mute|harmon|straight|cup))|cornet|flugel', r'trumpet|\bbrass\b'),
    57: (r'trombone|sackbut', r'euphonium|baritone horn|\bbrass\b'),
    58: (r'\btuba\b|sousaphone|euphonium', r'\bbrass\b|bass trombone'),
    59: (r'(mute|harmon|straight|cup).*trumpet|trumpet.*(mute|harmon|straight|cup)', r'trumpet'),
    60: (r'french horn|\bf horn\b|\bhorns?\b(?!.*(english|section|shofar))|waldhorn', r'\bbrass\b|mellophone'),
    61: (r'brass (section|ensemble)|all brass|\bhorns section|big band', r'trumpet|trombone|french horn|\bbrass\b'),
    62: (r'synth ?brass|brass synth', r'\bbrass\b'),
    63: (r'synth ?brass|brass synth', r'\bbrass\b'),
    64: (r'soprano sax|sopr\w* ?sax|saxello|\bsoprano\b.*\bsax', r'\bsax'),
    65: (r'alto sax|\balto\b.*sax|sax.*\balto\b|were sax|weresax', r'\bsax'),
    66: (r'tenor sax|\btenor\b.*sax|sax.*\btenor\b', r'\bsax'),
    67: (r'bari(tone)? sax|\bbari\b|bear ?sax|baritone.*sax|sax.*baritone', r'\bsax'),
    68: (r'\boboe\b|hautbois', r'english horn|cor anglais|shawm|krumhorn|duduk'),
    69: (r'english horn|cor anglais|anglais', r'\boboe\b'),
    70: (r'bassoon|fagott', r'bass clarinet|\boboe\b'),
    71: (r'clarinet|klarinette|chalumeau', r'\bsax'),
    72: (r'piccolo|\bfife\b', r'\bflute\b'),
    73: (r'\bflute\b(?!.*(pan|bass))|flauto|alto flute', r'recorder|piccolo|bass flute'),
    74: (r'recorder|blockfl', r'tin ?whistle|\bflute\b|ocarina'),
    75: (r'pan ?flute|pan ?pipes?|syrinx|zampo', r'\bflute\b|ocarina|recorder|bottle'),
    76: (r'bottle|\bjug\b', r'ocarina|pan ?flute|\bflute\b'),
    77: (r'shakuhachi|bansuri|\bdizi\b|\bney\b|\bxiao\b', r'\bflute\b|recorder'),
    78: (r'whistle', r'piccolo|recorder|ocarina'),
    79: (r'ocarina', r'recorder|\bflute\b|whistle'),
    80: (r'square|\bpulse\b|chiptune|8 ?bit|game ?boy', r'\blead\b|\bsynth\b'),
    81: (r'\bsaw|sawtooth|supersaw|caveman|cosmonaut', r'\blead\b|\bsynth\b'),
    82: (r'calliope|steam organ', r'\bflute\b|\blead\b'),
    83: (r'chiff', r'\blead\b|calliope'),
    84: (r'charang|dist.*lead|guitar lead', r'\blead\b'),
    85: (r'voice lead|vox lead|lead.*voice', r'synth ?voice|choir|\bvox\b'),
    86: (r'fifths|\b5ths?\b', r'\blead\b'),
    87: (r'bass ?lead|bass and lead', r'\blead\b|synth ?bass'),
    88: (r'new ?age|fantasia', r'\bpad\b'),
    89: (r'warm|analog pad|asthmatic', r'\bpad\b'),
    90: (r'polysynth|poly ?synth|juno|jupiter|prophet|oberheim|blackheart', r'\bpad\b|\bsynth\b'),
    91: (r'choir pad|pad.*choir|space voice', r'choir|\bpad\b'),
    92: (r'bowed|bow pad', r'\bpad\b|glass'),
    93: (r'metallic|metal pad|bell pad', r'\bpad\b'),
    94: (r'\bhalo\b|angel', r'\bpad\b|choir'),
    95: (r'sweep', r'\bpad\b'),
    96: (r'\brain\b', r'\bpad\b|\bfx\b|drops'),
    97: (r'soundtrack|cinematic', r'\bpad\b|\bfx\b'),
    98: (r'crystal', r'glass|\bbells?\b|\bfx\b'),
    99: (r'atmos|ambien|texture|drone', r'\bpad\b|\bfx\b'),
    100: (r'brightness', r'\bpad\b|\bfx\b'),
    101: (r'goblin', r'\bfx\b|weird'),
    102: (r'echo', r'\bfx\b|\bpad\b'),
    103: (r'sci ?fi|\bspace\b|alien', r'\bfx\b'),
    104: (r'sitar|tanpura|sarod|veena', r'zither|koto|dan tranh|\boud\b|\bsaz\b|bouzouki|tagelharpa'),
    105: (r'banjo|ganjo', r'mandolin|ukulele|strumstick'),
    106: (r'shamisen|sanshin|sanxian', r'banjo|koto|sitar|dan tranh'),
    107: (r'\bkoto\b|guzheng|\bzheng\b|dan tranh|kayagum|gayageum', r'zither|\bharp\b|dulcimer|cithara'),
    108: (r'kalimba|mbira|thumb piano|sanza|likembe|nyunga', r'music ?box|marimba|balafon'),
    109: (r'bag ?pipe|\bdudy\b|\bgaita\b|squid ?pipes|uilleann|highland', r'shawm|chanter|drone'),
    110: (r'fiddle|\bviolin\b|erhu|kemen', r'\bviola\b'),
    111: (r'shanai|shehnai|suona|zurna|shawm|duduk|mizmar|kr?umhorn|crumhorn', r'\boboe\b|bag ?pipe'),
    112: (r'tinkle|sleigh|jingle|hand ?bells?|finger cymbal|crotal|mark tree|bell tree', r'\bbells?\b|triangle'),
    113: (r'agogo|cowbell', r'\bbells?\b'),
    114: (r'steel ?drum|steel ?pan|\bhang\b|handpan|tank drum', r'marimba|vibraphone'),
    115: (r'wood ?block|temple block|claves?\b', r'\bblock\b|log drum|slit drum'),
    116: (r'taiko|odaiko|bass drum|gran cassa|epic drum', r'\btoms?\b|frame drum'),
    117: (r'\btoms?\b|tom ?tom|roto', r'\bdrum\b'),
    118: (r'synth drum|electronic drum|simmons|\b[89]0[89]\b|drum machine', r'\bdrums?\b'),
    119: (r'reverse|cymbal|cymbal swell', r'crash|gong|tam ?tam'),
    120: (r'fret noise|string noise|guitar noise|squeak|guitar.*nois', r'\bnois'),
    121: (r'breath|air noise', r'\bnois'),
    122: (r'\bsea\b|ocean|\bwaves?\b|\bsurf\b', r'\brain\b|\bnois'),
    123: (r'\bbird|tweet|chirp', r'whistle'),
    124: (r'\btele ?phone|\bring(ing)?\b', r'\bbells?\b'),
    125: (r'helicopter|rotor|ratchet', r'\bnois'),
    126: (r'applause|\bclaps?\b|crowd|body percussion', r'\bclap'),
    127: (r'\bgun|gunshot|slapstick|\bwhip\b|explosion', r'\bsnare\b|\bslap'),
    DRUMS: (r'drum ?kit|\bkit\b|drumset|drums? (full|complete|basic|standard)|(full|complete|basic|standard) drums?', None),
}
# names that rule a program out whatever else they say
_ACOUSTIC_PIANO_NOT = r'tx81z|electric|\be ?piano|rhodes|wurli|pianet|\btoy\b|\bfm\b'
_BASSES_NOT = r'drum|synth|guitar|strumstick|harp|upright|double|contra|\bbass solo\b|clarinet|flute|trombone|recorder|tuba'
NOT = {0: _ACOUSTIC_PIANO_NOT, 1: _ACOUSTIC_PIANO_NOT, 3: _ACOUSTIC_PIANO_NOT,
       24: r'bass|electric', 25: r'bass|electric', 32: r'guitar|synth|drum|clarinet|flute|trombone|tuba|recorder',
       33: _BASSES_NOT, 34: _BASSES_NOT, 35: _BASSES_NOT, 36: _BASSES_NOT + r'|stick', 37: _BASSES_NOT + r'|stick',
       40: r'section|ensemble', 42: r'section', 43: r'drum|guitar|clarinet|flute|trombone|tuba|recorder|synth',
       44: r'dan tranh|mandolin|zither|guitar|harp', 45: r'guitar|harp', 48: r'guitar', 49: r'guitar', 50: r'guitar', 51: r'guitar',
       30: r'var ?metal|cymbal|gong|triangle', 46: r'harpsichord|hohner|harmonica', 56: r'mute|section', 60: r'english|section',
       73: r'pan|bass flute', 110: r'section', 117: r'synth'}
# never a note: release layers, pedal and key noises
_ALWAYS_NOT = re.compile(r'\brel\b|\breleases?\b|\bpedals?\b|key ?(click|noise|off|up)|\bnoise ?floor|\bmic ?test')
# effects and noises: only the sound-effect programs and the synth FX block want them
_NOISY = re.compile(r'\bnois|\bfx\b|\bbtb\b|behind the bridge|gliss|\bbreath|\bsqueak|\bslide\b|\bscrape|\bknock')
_NOISY_OK = set(range(96, 104)) | set(range(119, 128))
# short articulations are no stand-in for a sustained program
_SHORT = re.compile(r'\bstacc?(ato)?\b|\bstac\b|\bspic|\bpizz|\bpluck|marcato|\bshort|col legno|\bharmonics?\b|\bhits?\b|\bfall\b|\bbuzz\b|\bflutter')
_SUSTAINED = set(range(16, 24)) | {40, 41, 42, 43, 44, 48, 49, 50, 51, 52, 53, 54} | set(range(56, 96)) | {109, 110, 111}
_COMPILED = {k: (_p(a), _p(b) if b else None) for k, (a, b) in PATTERNS.items()}
_NOT = {k: _p(v) for k, v in NOT.items()}

# glued words a library name leaves together ("Growlybass", "Shinyguitar")
_GLUED = re.compile(r'(?<=[a-z])(bass|guitar|piano|sax|drums|cello|tuba|pipes|organ|synth)(?=s?\b)')
_JUNK = re.compile(r'\b(test|template|keymap|mapping|mappings|includes?|controls?|modules?|init|blank|demo)\b')


def norm(text: str) -> str:
    t = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)             # camelCase → words
    t = re.sub(r'([A-Z])([A-Z][a-z])', r'\1 \2', t)            # DRSKit → DRS Kit
    t = t.lower()
    t = re.sub(r"[_\-./,()\[\]+&'#]+", ' ', t)
    t = _GLUED.sub(r' \1', t)
    return re.sub(r'\s+', ' ', t).strip()


# inside a drum-kit library, the file names say which program is the whole kit
KIT_FILE = re.compile(r'\bfull\b|complete|\bkit\b|\bbasic\b|standard|drum ?set|\ball\b|\bdrums\b|\bgm\b')


def junk(text: str) -> bool:
    return bool(_JUNK.search(norm(text)))


def _excluded(t: str, p: int) -> bool:
    return bool(_ALWAYS_NOT.search(t) or (p in _NOT and _NOT[p].search(t)) or (p in _SUSTAINED and _SHORT.search(t))
                or (p not in _NOISY_OK and _NOISY.search(t)))


def excluded(text: str, program: int) -> bool:
    """Whether ``text`` rules itself out for ``program`` whatever else it says (a release layer, a noise
    articulation, a staccato for a sustained program)."""
    return _excluded(norm(text), program)


def classify(text: str, only: set | None = None) -> dict:
    """{program: strength} for the GM programs ``text`` names (1.0 exact, 0.5 related)."""
    t = norm(text)
    out = {}
    for p, (exact, related) in _COMPILED.items():
        if only is not None and p not in only:
            continue
        if _excluded(t, p):
            continue
        if exact.search(t):
            out[p] = 1.0
        elif related is not None and related.search(t):
            out[p] = 0.5
    return out
