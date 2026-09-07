"""kobi.ingest — read source instruments into one region model.

Two readers feed the same ``Instrument`` / ``Region`` model:

* ``load_sfz(path)`` — FreePats and Karoryfer programs.  Handles ``#include``, ``#define``,
  ``<control>`` ``default_path``, the global / master / group / region hierarchy, note names in
  key opcodes, opcode values containing spaces, Windows path separators and letter case, and keeps
  every opcode it does not interpret in ``Region.opcodes``.
* ``load_folder(folder, sub)`` — VCSL and VSCO 2: bare WAV whose file names carry the note, the
  velocity layer or dynamic, round robin / take, articulation and microphone.  Key and velocity
  ranges are spread over the notes and layers actually present; round robins become
  ``seq_position`` variants; release samples are tagged ``trigger='release'``.

``default_view(inst)`` returns the regions a plain note-on would play: the default keyswitch,
attack triggers only, CC gates satisfied by the file's own ``set_cc`` defaults.

    python3 -m kobi.ingest              # ingest the first candidate of every GM program -> INGEST.md
    python3 -m kobi.ingest 0 33 66      # a few programs, verbose
"""
from __future__ import annotations

import collections
import os
import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- model

@dataclass
class Region:
    sample: str                          # absolute path (may not exist: see Instrument.missing)
    lokey: int = 0
    hikey: int = 127
    pitch_keycenter: int | None = 60     # None: keyless one-shot (percussion without a note)
    lovel: int = 1
    hivel: int = 127
    tune: float = 0.0                    # cents, transpose folded in
    volume_db: float = 0.0
    pan: float = 0.0
    loop_start: int | None = None
    loop_end: int | None = None
    loop_mode: str | None = None
    seq_position: int = 1
    seq_length: int = 1
    lorand: float = 0.0
    hirand: float = 1.0
    trigger: str = 'attack'
    sw_last: int | None = None           # keyswitch that selects this region
    sw_label: str = ''
    tags: tuple = ()                     # articulation / dynamic / mic words (lower case)
    opcodes: dict = field(default_factory=dict)   # everything else, raw

    @property
    def key(self) -> int:
        return self.pitch_keycenter if self.pitch_keycenter is not None else (self.lokey + self.hikey) // 2


@dataclass
class Instrument:
    name: str
    source: str                          # 'VCSL' | 'VSCO2' | 'FreePats' | 'Karoryfer'
    origin: str                          # the .sfz file or the sample folder
    regions: list
    sw_default: int | None = None
    control: dict = field(default_factory=dict)
    missing: list = field(default_factory=list)   # sample paths that do not exist

    def keyswitches(self) -> dict:
        """{sw_last: label} over all regions that have one."""
        out = {}
        for r in self.regions:
            if r.sw_last is not None:
                out.setdefault(r.sw_last, r.sw_label or f'sw{r.sw_last}')
        return out


# --------------------------------------------------------------------------- notes

_NOTE = re.compile(r'^([A-Ga-g])(#|b)?(-?\d)$')
_SEMI = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}


def note_to_midi(s: str) -> int | None:
    """'C4' / 'c#4' / 'Db-1' -> MIDI number (C4 = 60); None if not a note name."""
    m = _NOTE.match(s.strip())
    if not m:
        return None
    n = _SEMI[m.group(1).lower()] + {'#': 1, 'b': -1, None: 0}[m.group(2)]
    return 12 * (int(m.group(3)) + 1) + n


def _key(v, default=None):
    """SFZ key opcode: an integer or a note name."""
    if v is None:
        return default
    v = str(v).strip()
    try:
        return int(float(v))
    except ValueError:
        n = note_to_midi(v)
        return default if n is None else n


def _num(v, default=0.0):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------- SFZ reader

_HEADER = re.compile(r'<(\w+)>')
_OPCODE = re.compile(r'(?<![\w$])([\w$]+)=')


def _resolve_case(path: str) -> str | None:
    """Existing path for ``path`` ignoring letter case in each component (Windows-authored SFZs)."""
    if os.path.exists(path):
        return path
    parts = os.path.normpath(path).split(os.sep)
    cur = os.sep if path.startswith(os.sep) else '.'
    for p in parts:
        if p in ('', '.'):
            continue
        cand = os.path.join(cur, p)
        if os.path.exists(cand):
            cur = cand
            continue
        try:
            names = os.listdir(cur)
        except OSError:
            return None
        hit = [n for n in names if n.lower() == p.lower()]
        if not hit:
            return None
        cur = os.path.join(cur, hit[0])
    return cur


def _sfz_text(path: str, defines: dict, stack: tuple, root_dir: str | None = None) -> list:
    """Lines of ``path`` with comments removed, ``#define`` applied and ``#include`` inlined.  A file
    may be included any number of times (Karoryfer re-includes one mapping per ``#define``); only
    a file including itself, directly or indirectly, is refused.  Include paths are relative to the
    top-level file's folder (the SFZ rule); the including file's folder is tried second."""
    root_dir = root_dir or os.path.dirname(os.path.abspath(path))
    out = []
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            i = line.find('//')
            if i >= 0:
                line = line[:i]
            s = line.strip()
            if not s:
                continue
            if s.startswith('#define'):
                m = re.match(r'#define\s+(\$\w+)\s+(\S+)', s)
                if m:
                    defines[m.group(1)] = m.group(2)
                continue
            for k in sorted(defines, key=len, reverse=True):
                if k in line:
                    line = line.replace(k, defines[k])
                    s = line.strip()
            if s.startswith('#include'):
                m = re.match(r'#include\s+"([^"]+)"', s)
                if m:
                    rel = m.group(1).replace('\\', '/')
                    inc = _resolve_case(os.path.join(root_dir, rel)) or \
                        _resolve_case(os.path.join(os.path.dirname(path), rel))
                    if inc and os.path.abspath(inc) not in stack:
                        out.extend(_sfz_text(inc, defines, stack + (os.path.abspath(inc),), root_dir))
                continue
            out.append(line.rstrip('\n'))
    return out


def _parse_opcodes(body: str) -> dict:
    body = body.replace('\n', ' ')
    ms = list(_OPCODE.finditer(body))
    ops = {}
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(body)
        ops[m.group(1)] = body[m.end():end].strip()
    return ops


def parse_sfz(path: str) -> tuple[list, dict]:
    """(merged opcode dicts, one per <region>; the <control> opcodes).  Each region dict also
    carries ``_default_path`` (as in force at that point) and ``_dir`` (the SFZ's folder)."""
    text = '\n'.join(_sfz_text(path, {}, (os.path.abspath(path),)))
    parts = _HEADER.split(text)
    control, glob_, master, group = {}, {}, {}, {}
    regions = []
    for header, body in zip(parts[1::2], parts[2::2]):
        ops = _parse_opcodes(body)
        if header == 'control':
            control.update(ops)
        elif header == 'global':
            glob_, master, group = ops, {}, {}
        elif header == 'master':
            master, group = ops, {}
        elif header == 'group':
            group = ops
        elif header == 'region':
            merged = {**glob_, **master, **group, **ops}
            merged['_default_path'] = control.get('default_path', '')
            merged['_dir'] = os.path.dirname(os.path.abspath(path))
            regions.append(merged)
    return regions, control


_TAKEN = {'sample', 'lokey', 'hikey', 'key', 'pitch_keycenter', 'lovel', 'hivel', 'tune', 'transpose', 'volume',
          'pan', 'loop_start', 'loop_end', 'loop_mode', 'seq_position', 'seq_length', 'lorand', 'hirand',
          'trigger', 'sw_last', 'sw_label', '_default_path', '_dir'}


def region_from_opcodes(d: dict) -> Region | None:
    sample = d.get('sample')
    if not sample or sample.startswith('*'):     # *silence, *sine ... are built-in generators
        return None
    rel = os.path.join(d.get('_default_path', '').replace('\\', '/'), sample.replace('\\', '/'))
    path = os.path.normpath(os.path.join(d.get('_dir', ''), rel))
    key = _key(d.get('key'))
    lokey = _key(d.get('lokey'), key if key is not None else 0)
    hikey = _key(d.get('hikey'), key if key is not None else 127)
    kc = _key(d.get('pitch_keycenter'), key if key is not None else 60)
    if hikey < lokey:
        return None
    lovel, hivel = int(_num(d.get('lovel'), 0)), int(_num(d.get('hivel'), 127))
    if hivel < lovel:
        return None
    return Region(sample=path, lokey=lokey, hikey=hikey, pitch_keycenter=kc, lovel=max(1, lovel), hivel=hivel,
                  tune=_num(d.get('tune')) + 100 * _num(d.get('transpose')), volume_db=_num(d.get('volume')),
                  pan=_num(d.get('pan')),
                  loop_start=int(_num(d['loop_start'])) if 'loop_start' in d else None,
                  loop_end=int(_num(d['loop_end'])) if 'loop_end' in d else None,
                  loop_mode=d.get('loop_mode'),
                  seq_position=int(_num(d.get('seq_position'), 1)), seq_length=int(_num(d.get('seq_length'), 1)),
                  lorand=_num(d.get('lorand'), 0.0), hirand=_num(d.get('hirand'), 1.0),
                  trigger=d.get('trigger', 'attack'), sw_last=_key(d.get('sw_last')), sw_label=d.get('sw_label', ''),
                  opcodes={k: v for k, v in d.items() if k not in _TAKEN})


def _audio_index(root: str) -> dict:
    """basename (lower case) -> [paths] for every audio file under ``root``."""
    idx = {}
    for d, _, fs in os.walk(root):
        for f in fs:
            if f.lower().endswith(('.wav', '.flac', '.ogg', '.aif', '.aiff')):
                idx.setdefault(f.lower(), []).append(os.path.join(d, f))
    return idx


def _rescue(path: str, index: dict) -> str | None:
    """A sample whose relative path is wrong (Shinyguitar writes ``acoustic/x.wav`` from Programs/
    while the files sit in Samples/acoustic/): the unique file in the set with the same name and
    parent folder, else the unique file with the same name."""
    hits = index.get(os.path.basename(path).lower(), [])
    parent = os.path.basename(os.path.dirname(path)).lower()
    same_parent = [h for h in hits if os.path.basename(os.path.dirname(h)).lower() == parent]
    if len(same_parent) == 1:
        return same_parent[0]
    return hits[0] if len(hits) == 1 else None


def load_sfz(path: str, name: str | None = None, source: str = 'sfz', search_root: str | None = None) -> Instrument:
    """``search_root``: folder searched for samples whose written path does not exist."""
    raw, control = parse_sfz(path)
    regions, missing, index = [], [], None
    for d in raw:
        r = region_from_opcodes(d)
        if r is None:
            continue
        real = _resolve_case(r.sample)
        if real is None and search_root:
            if index is None:
                index = _audio_index(search_root)
            real = _rescue(r.sample, index)
        if real is None:
            missing.append(r.sample)
        else:
            r.sample = real
        regions.append(r)
    sw_default = None
    for d in raw:
        if 'sw_default' in d:
            sw_default = _key(d['sw_default'])
            break
    if sw_default is None and 'sw_default' in control:
        sw_default = _key(control['sw_default'])
    return Instrument(name=name or os.path.splitext(os.path.basename(path))[0], source=source, origin=path,
                      regions=regions, sw_default=sw_default, control=control, missing=missing)


# --------------------------------------------------------------------------- folder reader (VCSL / VSCO 2)

_DYN = {'ppp': 0, 'pp': 1, 'p': 2, 'mp': 3, 'mf': 4, 'f': 5, 'ff': 6, 'fff': 7}
_DYN_WORDS = {'quieter': 1, 'quiet': 1, 'soft': 2, 'softer': 2, 'med': 3, 'medium': 3, 'loud': 6, 'louder': 6, 'hard': 6}
_MIC_PREF = ['main', 'mainspirit', 'mid', 'close', 'sum', 'player', 'stereo', 'room', 'spirit', 'outrigger', 'far', 'omni', 'mono']
_MICS = set(_MIC_PREF)
_RELEASE = {'rel', 'release', 'releases', 'nosusrel', 'lowrel', 'highrel', 'susrel', 'rels'}
_SPLIT = re.compile(r'[_\- .]+')
_AUDIO = ('.wav', '.flac', '.aif', '.aiff')


def parse_name(stem: str, rel_dir: str = '') -> dict:
    """Decode a VCSL / VSCO-style file name.  Returns note (MIDI or None), vel (layer index or
    None), vel_kind ('vl' | 'dyn' | None), rr (round robin / take index or None), mic, release
    (bool) and tags (the remaining words, lower case, folder words included)."""
    out = dict(note=None, vel=None, vel_kind=None, rr=None, mic=None, release=False, tags=[])
    nums = []
    for tok in _SPLIT.split(stem):
        if not tok:
            continue
        low = tok.lower()
        # lower-case f1 / p2 are a dynamic plus a take number (snare_f1.wav), not the notes F1 / P2
        n = None if re.fullmatch(r'[fp]\d+', tok) else note_to_midi(tok)
        if n is not None and out['note'] is None:
            out['note'] = n
            continue
        m = re.fullmatch(r'vl?(\d+)', low)
        if m and out['vel'] is None:
            out['vel'], out['vel_kind'] = int(m.group(1)), 'vl'
            continue
        m = re.fullmatch(r'(rr|r|var|take)(\d+)', low)
        if m:
            out['rr'] = int(m.group(2))
            continue
        m = re.fullmatch(r'(ppp|pp|p|mp|mf|f|ff|fff)(\d*)', low)
        if m and out['vel_kind'] != 'vl':
            out['vel'], out['vel_kind'] = _DYN[m.group(1)], 'dyn'
            if m.group(2):
                nums.append(int(m.group(2)))
            continue
        if low in _DYN_WORDS and out['vel'] is None:
            out['vel'], out['vel_kind'] = _DYN_WORDS[low], 'dyn'
            out['tags'].append(low)
            continue
        if low.isdigit():
            nums.append(int(low))
            continue
        if re.fullmatch(r'k\d+', low):      # kalimba key index
            continue
        if low in _MICS:
            out['mic'] = low
            continue
        if low in _RELEASE:
            out['release'] = True
        out['tags'].append(low)
    if out['rr'] is None and nums:
        out['rr'] = nums[-1]
    for part in re.split(r'[/\\]', rel_dir):
        low = part.strip().lower()
        if low and low not in out['tags']:
            if 'rel' in low.split()[0][:3] or low in _RELEASE:
                out['release'] = True
            out['tags'].append(low)
    return out


def _spread_keys(regions: list, extend: int) -> None:
    """Give each distinct key centre the range up to half-way to its neighbours."""
    keyed = [r for r in regions if r.pitch_keycenter is not None]
    centres = sorted({r.pitch_keycenter for r in keyed})
    lo, hi = {}, {}
    for i, c in enumerate(centres):
        lo[c] = max(0, c - extend) if i == 0 else (centres[i - 1] + c) // 2 + 1
        hi[c] = min(127, c + extend) if i == len(centres) - 1 else (c + centres[i + 1]) // 2
    for r in keyed:
        r.lokey, r.hikey = lo[r.pitch_keycenter], hi[r.pitch_keycenter]


def _spread_velocities(group: list, layers: list) -> None:
    """Split 1..127 equally over the velocity layers present in ``layers`` (ascending)."""
    n = len(layers)
    for r in group:
        j = layers.index(r.opcodes['_vel'])
        r.lovel = 1 + (j * 127) // n if j else 1
        r.hivel = ((j + 1) * 127) // n if j < n - 1 else 127


def load_folder(folder: str, sub: str | None = None, name: str | None = None, source: str = 'VCSL',
                extend: int = 6, mic: str | None = None) -> Instrument:
    """Ingest a VCSL / VSCO 2 instrument folder (optionally one sub-folder).  Keeps one microphone
    (``mic`` or the most preferred one present), spreads keys and velocities, numbers round robins."""
    root = os.path.join(folder, sub) if sub else folder
    files = []
    for d, _, fs in os.walk(root):
        for f in fs:
            if f.lower().endswith(_AUDIO):
                files.append(os.path.join(d, f))
    files.sort()
    parsed = [(p, parse_name(os.path.splitext(os.path.basename(p))[0], os.path.relpath(os.path.dirname(p), root)
                             if os.path.dirname(p) != root else '')) for p in files]
    mics = {info['mic'] for _, info in parsed if info['mic']}
    keep_mic = mic or next((m for m in _MIC_PREF if m in mics), None)
    regions = []
    for p, info in parsed:
        if info['mic'] and keep_mic and info['mic'] != keep_mic:
            continue
        tags = tuple(dict.fromkeys(info['tags'] + ([info['mic']] if info['mic'] else [])))
        regions.append(Region(sample=p, pitch_keycenter=info['note'], trigger='release' if info['release'] else 'attack',
                              tags=tags, opcodes={'_vel': info['vel'] if info['vel'] is not None else 0,
                                                  '_vel_kind': info['vel_kind'], '_rr': info['rr'] if info['rr'] is not None else 0}))
    respread(regions, extend)          # articulation groups (same non-mic tags, trigger) share key/vel spreading
    return Instrument(name=name or os.path.basename(folder.rstrip('/')), source=source, origin=root, regions=regions)


# open strings (MIDI) of the Iowa string instruments, by the word in the folder / file name
_OPEN_STRINGS = {'violin': {'sulg': 55, 'suld': 62, 'sula': 69, 'sule': 76},
                 'viola': {'sulc': 48, 'sulg': 55, 'suld': 62, 'sula': 69},
                 'cello': {'sulc': 36, 'sulg': 43, 'suld': 50, 'sula': 57},
                 'bass': {'sulc': 24, 'sule': 28, 'sula': 33, 'suld': 38, 'sulg': 43}}


def pick_first_position(inst: Instrument, extend: int = 6) -> None:
    """Iowa recorded every note on every string it fits on (``sulG`` ...).  Keep, per note, the
    string a player would use in first position: the highest open string at or below the note.
    The ``sul`` words are then dropped from the tags and key / velocity / round-robin ranges are
    spread again over what is left."""
    name = os.path.basename(inst.origin.rstrip('/')).lower()
    strings = next((v for k, v in _OPEN_STRINGS.items() if k in name), None)
    if not strings:
        return
    keep = []
    for r in inst.regions:
        sul = next((t for t in r.tags if t in strings), None)
        if sul is None or r.pitch_keycenter is None:
            keep.append(r)
            continue
        playable = [k for k, o in strings.items() if o <= r.pitch_keycenter]
        best = max(playable, key=lambda k: strings[k]) if playable else min(strings, key=strings.get)
        if sul == best:
            r.tags = tuple(t for t in r.tags if t not in strings)
            keep.append(r)
    inst.regions = keep
    respread(inst.regions, extend)


def respread(regions: list, extend: int = 6) -> None:
    """Recompute key ranges, velocity ranges and round-robin numbering per articulation group."""
    def art(r):
        return (r.trigger, tuple(t for t in r.tags if t not in _MICS))
    for _, grp in _groupby(regions, art).items():
        _spread_keys(grp, extend)
        for _, per_key in _groupby(grp, lambda r: r.pitch_keycenter).items():
            layers = sorted({r.opcodes['_vel'] for r in per_key})
            _spread_velocities(per_key, layers)
            for _, per_vel in _groupby(per_key, lambda r: r.opcodes['_vel']).items():
                per_vel.sort(key=lambda r: (r.opcodes['_rr'], r.sample))
                for i, r in enumerate(per_vel):
                    r.seq_position, r.seq_length = i + 1, len(per_vel)


def _groupby(items, key):
    out = collections.OrderedDict()
    for it in items:
        out.setdefault(key(it), []).append(it)
    return out


# --------------------------------------------------------------------------- default view

_CC_DEFAULT = {7: 100, 10: 64, 11: 127}
# controllers whose default is meaningful on its own (mod wheel, volume, pan, expression, pedals):
# a region gated behind one of these stays silent by default even if no region passes
_CC_CONVENTIONAL = {1, 7, 10, 11, 64, 65, 66, 67, 68, 69}
_GATE = re.compile(r'^(on_)?(lo|hi)(hd)?cc(\d+)$')


def _gates(r: Region) -> dict:
    """{cc: [lo, hi]} from the region's locc/hicc opcodes; cc -1 marks an on_locc/on_hicc trigger."""
    gates = {}
    for k, v in r.opcodes.items():
        m = _GATE.match(k)
        if not m:
            continue
        if m.group(1):                      # on_locc / on_hicc: CC-triggered region, never by note-on
            gates[-1] = [1.0, 0.0]
            continue
        cc = int(m.group(4))
        gates.setdefault(cc, [0.0, 127.0])
        gates[cc][0 if m.group(2) == 'lo' else 1] = _num(v, 0.0 if m.group(2) == 'lo' else 127.0)
    return gates


def _cc_default(cc: int, control: dict) -> float:
    if f'set_cc{cc}' in control:
        return _num(control[f'set_cc{cc}'], 0.0)
    if f'set_hdcc{cc}' in control:
        return 127 * _num(control[f'set_hdcc{cc}'], 0.0)
    return float(_CC_DEFAULT.get(cc, 0))


def _gated_out(r: Region, control: dict, assume: dict | None = None) -> bool:
    """True if a CC gate on the region is not satisfied by the controller values in force: the
    file's ``set_cc`` defaults, overridden by ``assume`` (see ``_assumed_ccs``)."""
    for cc, (lo, hi) in _gates(r).items():
        if cc == -1:
            return True
        val = assume[cc] if assume and cc in assume else _cc_default(cc, control)
        if not lo <= val <= hi:
            return True
    return False


def _assumed_ccs(regions: list, control: dict) -> dict:
    """For a CC whose gates exclude every gated region at the default value, the author expects the
    host to set it (Shinyguitar gates all layers behind CC100=1; the Bigcat cello selects one of four
    variants with CC107): assume the lowest window, i.e. the first variant."""
    windows = {}
    for r in regions:
        for cc, (lo, hi) in _gates(r).items():
            if cc >= 0 and cc not in _CC_CONVENTIONAL and f'set_cc{cc}' not in control and f'set_hdcc{cc}' not in control:
                windows.setdefault(cc, []).append((lo, hi))
    return {cc: min(lo for lo, _ in ws) for cc, ws in windows.items()
            if not any(lo <= _cc_default(cc, control) <= hi for lo, hi in ws)}


def default_view(inst: Instrument, keyswitch: int | None = None, release: bool = False) -> list:
    """Regions a plain note-on plays: attack (or 'first') triggers, one keyswitch (``keyswitch``,
    else the file's ``sw_default``, else the most used one), CC gates satisfied by defaults.
    ``release=True`` returns the release-trigger regions under the same selection instead."""
    sws = inst.keyswitches()
    if sws:
        if keyswitch is None:
            keyswitch = inst.sw_default if inst.sw_default in sws else \
                collections.Counter(r.sw_last for r in inst.regions if r.sw_last is not None).most_common(1)[0][0]
    want = ('release', 'release_key') if release else ('attack', 'first')
    pool = [r for r in inst.regions if r.trigger in want and (r.sw_last is None or r.sw_last == keyswitch)]
    assume = _assumed_ccs(pool, inst.control)
    return [r for r in pool if not _gated_out(r, inst.control, assume)]


# --------------------------------------------------------------------------- candidates

def load_candidate(cand, name: str | None = None) -> Instrument | None:
    """Ingest a ``gm_map.Cand``: folder sources (VCSL, VSCO2, SSO) through ``load_folder`` with the
    candidate's ``octave`` correction and ``tags`` filter applied, SFZ sources through ``load_sfz``.
    None when nothing is on disk."""
    from .gm_map import ROOT, SSO_ROOT
    if cand.source in ('VCSL', 'VSCO2', 'SSO', 'Iowa'):
        folder = os.path.join(SSO_ROOT if cand.source == 'SSO' else os.path.join(ROOT, cand.source), cand.path)
        if not os.path.isdir(folder):
            return None
        inst = load_folder(folder, cand.sub, name or os.path.basename(cand.path), source=cand.source)
        if cand.tags:
            want = set(cand.tags)
            inst.regions = [r for r in inst.regions if want <= set(r.tags)]
            respread(inst.regions)
        if cand.source == 'Iowa':
            pick_first_position(inst)
        if cand.octave:
            for r in inst.regions:
                if r.pitch_keycenter is not None:
                    r.pitch_keycenter += 12 * cand.octave
                    r.lokey, r.hikey = min(127, max(0, r.lokey + 12 * cand.octave)), min(127, max(0, r.hikey + 12 * cand.octave))
        return inst
    if cand.source in ('FreePats', 'Karoryfer'):
        path, n = cand.resolve()
        if n == 0:
            return None
        inst = load_sfz(path, name or os.path.basename(cand.path), source=cand.source,
                        search_root=os.path.join(ROOT, cand.source, cand.path))
        if cand.octave:                      # a map written at another octave (Karoryfer basses, cello)
            for r in inst.regions:
                if r.pitch_keycenter is not None:
                    r.pitch_keycenter += 12 * cand.octave
                    r.lokey, r.hikey = min(127, max(0, r.lokey + 12 * cand.octave)), min(127, max(0, r.hikey + 12 * cand.octave))
        return inst
    return None


def summarize(inst: Instrument) -> dict:
    """Numbers for the ingest report."""
    import soundfile as sf
    view = default_view(inst)
    rel = default_view(inst, release=True)
    keyed = [r for r in view if r.pitch_keycenter is not None]
    centres = sorted({r.pitch_keycenter for r in keyed})
    layers = collections.Counter()
    for _, grp in _groupby(keyed, lambda r: r.pitch_keycenter).items():
        layers[len({(r.lovel, r.hivel) for r in grp})] += 1
    rr = max((r.seq_length for r in view), default=1)
    files = {r.sample for r in view}
    size = sum(os.path.getsize(f) for f in files if os.path.exists(f))
    fmt = ''
    for f in sorted(files):
        if os.path.exists(f):
            i = sf.info(f)
            fmt = f'{i.samplerate / 1000:g}k {i.subtype.lower().replace("pcm_", "")} {i.channels}ch {os.path.splitext(f)[1][1:]}'
            break
    return dict(name=inst.name, source=inst.source, regions=len(inst.regions), playable=len(view), release=len(rel),
                keyless=sum(1 for r in view if r.pitch_keycenter is None),
                key_lo=centres[0] if centres else None, key_hi=centres[-1] if centres else None, notes=len(centres),
                vel_layers=max(layers) if layers else 0, rr=rr,
                looped=sum(1 for r in view if r.loop_end is not None and r.loop_mode not in ('no_loop', 'one_shot')),
                keyswitches=len(inst.keyswitches()), missing=len(inst.missing), files=len(files), mb=size / 1e6, fmt=fmt)


def _nn(n):
    if n is None:
        return '-'
    return f'{"C C#D D#E F F#G G#A A#B "[(n % 12) * 2:(n % 12) * 2 + 2].strip()}{n // 12 - 1}'


def main(argv=None) -> int:
    import sys
    from .gm_map import PROGRAMS, DRUMS
    argv = sys.argv[1:] if argv is None else argv
    nums = [int(a) for a in argv if a.isdigit()] or list(range(128))
    rows, problems = [], []
    for p in PROGRAMS:
        if p.num not in nums:
            continue
        for c in p.cands:
            inst = load_candidate(c, name=p.name)
            if inst is None:
                continue
            s = summarize(inst)
            s.update(program=p.num, cand=f'{c.source}:{c.path}' + (f' [{c.sub}]' if c.sub else ''), kind=c.kind)
            rows.append(s)
            if s['missing'] or s['playable'] == 0 or (s['notes'] < 3 and not s['keyless'] and c.kind != 'oneshot'):
                problems.append(s)
            break
        else:
            rows.append(dict(program=p.num, name=p.name, cand='(no ingestible candidate)', kind='', source='', regions=0,
                             playable=0, release=0, keyless=0, key_lo=None, key_hi=None, notes=0, vel_layers=0, rr=0,
                             looped=0, keyswitches=0, missing=0, files=0, mb=0.0, fmt=''))
    if not argv:
        for c in DRUMS:
            inst = load_candidate(c, name='Drum kit')
            s = summarize(inst)
            s.update(program='drums', cand=f'{c.source}:{c.path}', kind='kit')
            rows.append(s)
    hdr = ('| # | program | candidate | kind | regions | playable | rel | notes | range | vel | rr | looped | ks | files | MB | format |'
           '\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    lines = [f"| {r['program']} | {r['name']} | {r['cand']} | {r['kind']} | {r['regions']} | {r['playable']} | {r['release']} | "
             f"{r['notes']}{' +' + str(r['keyless']) + ' keyless' if r['keyless'] else ''} | {_nn(r['key_lo'])}..{_nn(r['key_hi'])} | "
             f"{r['vel_layers']} | {r['rr']} | {r['looped']} | {r['keyswitches']} | {r['files']} | {r['mb']:.0f} | {r['fmt']} |"
             for r in rows]
    tot = sum(r['mb'] for r in rows)
    text = (f'# Ingest report\n\nFirst ingestible candidate per program (see MAPPING.md).  playable = regions a plain '
            f'note-on reaches (default keyswitch, attack trigger, CC gates at their defaults); rel = release-trigger '
            f'regions; notes = distinct key centres; vel = most velocity layers on one note; rr = longest round robin; '
            f'looped = playable regions with loop points; ks = keyswitches in the file.\n\n{hdr}\n' + '\n'.join(lines) +
            f'\n\nSource audio reached by the playable regions: {tot:.0f} MB in {sum(r["files"] for r in rows)} files.\n')
    if not argv:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'INGEST.md'), 'w') as fh:
            fh.write(text)
    for r in rows:
        print(f"{str(r['program']):>5} {r['name']:26s} {r['source']:9s} play {r['playable']:4d}/{r['regions']:<5d} rel {r['release']:3d} "
              f"notes {r['notes']:3d} {_nn(r['key_lo']):>4}..{_nn(r['key_hi']):<4} vel {r['vel_layers']} rr {r['rr']:2d} loop {r['looped']:3d} "
              f"ks {r['keyswitches']:2d} miss {r['missing']:2d} {r['mb']:6.0f}MB {r['fmt']}")
    print(f'{len(rows)} instruments, {tot:.0f} MB of source audio; {len(problems)} to look at')
    for s in problems:
        print(f"  CHECK {s['program']:>5} {s['name']}: playable {s['playable']}, notes {s['notes']}, missing {s['missing']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())


def load_program_view(num, name=None):
    """(kind, regions) for a GM program: its first ingestible candidate's default view, or for a
    layered program (gm_map.LAYERS) every layer's view with the layer gain folded into the region
    volumes.  None when nothing is on disk."""
    from .gm_map import LAYERS, PROGRAMS
    p = PROGRAMS[num]
    if num in LAYERS:
        out = []
        for cand, gain, *rest in LAYERS[num]:
            pan = rest[0] if rest else 0.0
            inst = load_candidate(cand, name or p.name)
            if inst is None:
                continue
            for r in default_view(inst):
                r.volume_db += gain
                r.pan = max(-100.0, min(100.0, r.pan + pan))
                r.tags = tuple(r.tags) + (f'layer:{cand.source}:{cand.path.split("/")[-1]}',)
                out.append(r)
        return ('sustain', out) if out else None
    for c in p.cands:
        inst = load_candidate(c, name or p.name)
        if inst is None:
            continue
        view = default_view(inst)
        if view:
            return (c.kind, view)
    return None
