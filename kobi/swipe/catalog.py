"""kobi.swipe.catalog — every alternative the app can offer, ranked per GM program.

An ``Alt`` is one playable instrument in one library: an SFZ file (FreePats, Karoryfer, SSO, the
remote repositories and zips) or a sample folder with an optional articulation sub-folder and tag
filter (VCSL, VSCO 2, Iowa).  gm_map's own fallback candidates come first-class, with the octave
and tag corrections the pitch audit found for them.

Local libraries are scanned once at start-up (file names only, no audio is read).  Remote libraries
are indexed in the background — a GitHub tree listing or a zip directory each, a few KB — and
join the ranking as their index lands.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass, field

from .. import gm_map, paths
from .gm_words import DRUMS, KIT_FILE, classify, excluded, junk, norm
from .libraries import ALL, DERIVED, LOCAL, REMOTE, SF2, Library

ROOT = paths.SOURCES
AUDIO = ('.wav', '.flac', '.aif', '.aiff', '.ogg')
MAX_PER_LIB = 3               # variants of one library offered for one program


@dataclass
class Alt:
    cid: str
    lib: str
    title: str
    shape: str                          # 'sfz' | 'folder' | 'gm'
    loc: dict                           # sfz: {rel}; folder: {path, sub, tags}; gm: gm_map.Cand fields; iowa: {inst, zips, tags}
    programs: dict = field(default_factory=dict)
    listed: bool = False                # one of gm_map's fallback candidates
    license: str = ''                   # when the file's licence differs from its library's

    def licence(self) -> str:
        lib = ALL.get(self.lib)
        return self.license or (lib.license if lib else '')

    def to_json(self) -> dict:
        lib = ALL.get(self.lib)
        return dict(cid=self.cid, lib=self.lib, lib_title=lib.title if lib else self.lib, title=self.title,
                    license=self.licence(), remote=bool(lib and lib.remote), shape=self.shape,
                    listed=self.listed, host=lib.host if lib else 'local', new=bool(lib and lib.batch >= 2))


# FreePats banks that are not CC0 (uncompressed/FreePats/LICENSES.md)
_FREEPATS_LICENCE = {'FSS-SteelStringGuitar': 'GNU GPL', 'SalamanderGrandPiano': 'CC BY 3.0 (Alexander Holm)',
                     'MuldjordKit': 'CC BY 4.0'}


def _file_licence(lib: Library, rel: str) -> str:
    if lib.id == 'FreePats':
        return next((v for k, v in _FREEPATS_LICENCE.items() if k in rel), 'CC0 1.0')
    return ''


def _cid(lib: str, loc: dict) -> str:
    return hashlib.sha1((lib + json.dumps(loc, sort_keys=True)).encode()).hexdigest()[:12]


def lib_root(lib: Library, alt: Alt | None = None) -> str:
    if lib.host in ('local-sfz', 'local-folder'):
        return os.path.join(ROOT, lib.where)
    if lib.host == 'iowa':
        return os.path.join(ROOT, 'Iowa', alt.loc['inst'] if alt else lib.id.split('-', 1)[1])
    return os.path.join(ROOT, 'Extra', lib.id)


def _programs_for(lib: Library, text: str) -> dict:
    """Programs a file of ``lib`` named ``text`` can play."""
    if lib.numbered:
        m = re.match(r'(\d{3})\b', os.path.basename(text))
        if not m:
            return {}
        n = int(m.group(1)) - (1 if lib.numbered == 'one' else 0)
        if n == 128:                                     # FreePats GM numbers its kit 129
            n = DRUMS
        return {n: 0.9} if 0 <= n <= DRUMS else {}
    if not lib.hints:
        return classify(text)
    if DRUMS in lib.hints:                               # a kit library: only files that are whole kits
        base = norm(os.path.splitext(os.path.basename(text))[0])     # "Hihat.sfz" in a folder named ...Kit is a piece
        kit = KIT_FILE.search(base) and not junk(text)
        rest = {p: s for p, s in lib.hints.items() if p != DRUMS}
        strength = lib.hints[DRUMS] * (1.0 if re.search(r'\bgm\b', base) else 0.9)    # a GM-mapped kit first
        return {DRUMS: strength, **({} if not rest else classify(text, only=set(rest)))} if kit else classify(text, only=set(rest))
    found = classify(text, only=set(lib.hints))
    if found:
        return {p: max(s, lib.hints[p] * 0.9) for p, s in found.items()}
    return {p: s * 0.75 for p, s in lib.hints.items() if not excluded(text, p)}


# ---------------------------------------------------------------------- local scanning

_FOLDER_DEPTH = {'VCSL': 3, 'VSCO2': 2, 'Iowa': 1}
# VCSL's organological categories name no instrument ("Zithers" holds the pianos); any other parent
# folder does ("TX81Z" says Piano 1 is an FM patch)
_GENERIC_PARENT = re.compile(r'phones$|^zithers$', re.I)
_IOWA_TAGS = ('vib', 'novib', 'nonvib', 'arco', 'pizz')


def _scan_folder_lib(lib: Library) -> list:
    base = os.path.join(ROOT, lib.where)
    depth = _FOLDER_DEPTH.get(lib.where, 2)
    seen, out = set(), []
    for d, dirs, files in os.walk(base):
        dirs[:] = [x for x in dirs if not x.startswith('.') and x != 'Assets']
        if not any(f.lower().endswith(AUDIO) for f in files):
            continue
        rel = os.path.relpath(d, base)
        parts = rel.split(os.sep)
        if len(parts) < depth:
            continue
        inst, sub = os.sep.join(parts[:depth]), (parts[depth] if len(parts) > depth else None)
        tagsets = [()]
        if lib.where == 'Iowa':
            words = {w.lower() for f in files for w in re.split(r'[._ ]', f)}
            tagsets = [(t,) for t in _IOWA_TAGS if t in words] or [()]
        for tags in tagsets:
            key = (inst, sub, tags)
            if key in seen:
                continue
            seen.add(key)
            name = os.path.basename(inst)
            parent = os.path.basename(os.path.dirname(inst))
            context = parent if lib.where == 'VCSL' and parent and not _GENERIC_PARENT.search(parent) else ''
            text = ' '.join([context, name, sub or '', *tags])
            if junk(text):
                continue
            progs = _programs_for(lib, text)
            if not progs:
                continue
            loc = dict(path=inst, sub=sub, tags=list(tags))
            out.append(Alt(_cid(lib.id, loc), lib.id, ' / '.join(x for x in (name, sub, ' '.join(tags)) if x), 'folder', loc, progs))
    return out


def _sfz_label(rel: str, folders_too: bool = False) -> str:
    """The SFZ's name; with its folders when the name alone is ambiguous (Black And Green's ord.sfz
    in black/t1, green/t1 ...)."""
    parts = rel.replace('\\', '/').split('/')
    stem = re.sub(r'\s+', ' ', os.path.splitext(parts[-1])[0].replace('_', ' ')).strip()
    folders = [f for f in parts[:-1] if f.lower() not in ('programs', 'sfz', 'presets', 'instruments')]
    if folders and folders_too:
        stem = ' '.join(folders[-2:]).replace('_', ' ') + ' / ' + stem
    return stem


def _sfz_alts(lib: Library, rels: list, sizes: dict | None = None) -> list:
    out = []
    for rel in rels:
        if junk(rel) or os.path.basename(rel).startswith(('_', '.')):
            continue
        if sizes is not None and sizes.get(rel, 1 << 20) < 120:     # "//dummy <region> sample=*sine" placeholders
            continue
        parts = rel.split('/')
        if lib.id == 'FreePats':
            if parts[0] == 'SoundSets':
                continue
            text = ' '.join(parts[1:])                  # the category folder would mislead the classifier
        elif lib.id == 'SSO':
            if parts[0] in ('sfz_compressor', 'scripts') or parts[0].endswith('Notation'):
                continue                                 # a build tree, and a second copy of every patch
            text = rel
        elif lib.id == 'Discord-GM':
            if len(parts) != 3 or parts[1] not in ('Melodic', 'Drums'):
                continue                                 # the multi-program bank files and per-program internals
            text = parts[2] if parts[1] == 'Melodic' else parts[2]
            progs = _programs_for(lib, text) if parts[1] == 'Melodic' else {DRUMS: 0.9}
            loc = dict(rel=rel)
            out.append(Alt(_cid(lib.id, loc), lib.id, _sfz_label(rel), 'sfz', loc, progs))
            continue
        else:                                            # a kit is named by its file, not by the library
            text = rel if DRUMS in lib.hints else lib.title + ' ' + rel
        progs = _programs_for(lib, text)
        if progs:
            loc = dict(rel=rel)
            out.append(Alt(_cid(lib.id, loc), lib.id, _sfz_label(rel), 'sfz', loc, progs, license=_file_licence(lib, rel)))
    seen = {}
    for a in out:
        seen[a.title] = seen.get(a.title, 0) + 1
    for a in out:
        if seen[a.title] > 1:
            a.title = _sfz_label(a.loc['rel'], folders_too=True)
    return out


def _scan_sfz_lib(lib: Library) -> list:
    base = os.path.join(ROOT, lib.where)
    rels = sorted(os.path.relpath(p, base).replace(os.sep, '/') for p in
                  glob.glob(os.path.join(glob.escape(base), '**', '*.sfz'), recursive=True))
    return _sfz_alts(lib, rels)


# ---------------------------------------------------------------------- GM soundfonts

def _safe(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9_-]+', '_', name).strip('_') or 'preset'


def _scan_sf2_lib(lib: Library) -> list:
    """One alternative per preset: bank 0 for its program, the GS variation banks as further versions
    of the same program, bank 128 for the kit.  Nothing is extracted until a card needs it."""
    from .sf2 import list_presets
    if not os.path.exists(lib.sf2):
        return []
    out = []
    for bank, preset, name in list_presets(lib.sf2):
        if bank == 128:
            progs = {DRUMS: 0.9}
        elif 0 <= preset <= 127:
            progs = {preset: 0.9 if bank == 0 else 0.75}
        else:
            continue
        name = name.strip()
        folder = f'{bank:03d}-{preset:03d}_{_safe(name)}'
        loc = dict(rel=f'{folder}/{_safe(name)}.sfz', bank=bank, preset=preset, name=name)
        title = name if bank in (0, 128) else f'{name} (variation bank {bank})'
        out.append(Alt(_cid(lib.id, loc), lib.id, title, 'sfz', loc, progs))
    return out


# ---------------------------------------------------------------------- made here, from notes
# Versions asked for in notes on the first pass: the bank's viola with the bow's first scratch trimmed
# off (a derived instrument written to uncompressed/Extra/Derived/), and layered versions of two picks.
_IOWA_VIOLA = dict(source='Iowa', path='Viola', sub=None, kind='sustain', standin=False, note='', octave=0, tags=['arco'])
_RECORDER, _OVERBLOWN = 'f8e9ac8d86ec', '932e656d6a4a'           # VCSL Baroque Alto Recorder SusVib, G-Town Overblown Flute
_FAKE_GLASS, _GLASS_2019 = 'ddacf9ce3b1c', '3630f1a03852'        # G-Town Fake Glass Harmonica, FreePats Glass-20191227
_A320_SOLO_VOX, _A320_OOHS = '6b2c1c0c6449', 'da132a67bcd0'      # A320U presets 0:85 Solo Vox, 0:53 Voice Oohs


def _derived_loc(title: str, loc: dict) -> dict:
    """Derived instruments written to disk get a folder of their own under uncompressed/Extra/Derived/."""
    return dict(loc, rel=f'{_safe(title)}/{_safe(title)}.sfz') if loc['make'] in ('trim', 'resample') else loc


def _derived_cid(title: str, loc: dict) -> str:
    return _cid(DERIVED.id, _derived_loc(title, loc))


# A GM soundfont's presets are a few hundred milliseconds of audio on a tiny loop, shaped by the synth's
# filter and envelope: too short for kobi.compress to find a loop of its own, and the bank's players have
# no filter.  Resampled, the preset is played through sfizz every ``step`` keys and each held note kept.
_SOLO_VOX_RS = ('A320U Solo Vox, resampled', dict(make='resample', src=_A320_SOLO_VOX, lo=24, hi=96, step=3))
_OOHS_RS = ('A320U Voice Oohs, resampled', dict(make='resample', src=_A320_OOHS, lo=24, hi=96, step=3))
DERIVED_ALTS = [
    (41, 'Iowa viola, clean attack (40 ms trimmed)', dict(make='trim', src=_IOWA_VIOLA, trim_ms=40)),
    (41, 'Iowa viola, clean attack (90 ms trimmed)', dict(make='trim', src=_IOWA_VIOLA, trim_ms=90)),
    # the overblown flute is 11.4 dB louder than the recorder on its own (-28.7 vs -40.1 LUFS), so these put it
    # 14 / 19 / 24 dB under the recorder: just audible on each attack.  It only has C3..D5; ``cover`` stretches
    # it over the recorder's whole range so every note gets it.
    (75, 'Recorder + overblown flute, just audible (14 dB under)', dict(make='stack', layers=[
        dict(cid=_RECORDER, gain=0.0), dict(cid=_OVERBLOWN, gain=-25.4, cover=True)])),
    (75, 'Recorder + overblown flute, barely (19 dB under)', dict(make='stack', layers=[
        dict(cid=_RECORDER, gain=0.0), dict(cid=_OVERBLOWN, gain=-30.4, cover=True)])),
    (75, 'Recorder + overblown flute, faint (24 dB under)', dict(make='stack', layers=[
        dict(cid=_RECORDER, gain=0.0), dict(cid=_OVERBLOWN, gain=-35.4, cover=True)])),
    (98, 'Fake Glass Harmonica + Glass 2019, 300 ms echo', dict(make='stack', layers=[dict(cid=_FAKE_GLASS, gain=0.0), dict(cid=_GLASS_2019, gain=0.0)],
                                                               echo=dict(delay=0.3, gain=-6.0, repeats=2))),
    (98, 'Fake Glass Harmonica + softer Glass 2019, one echo', dict(make='stack', layers=[dict(cid=_FAKE_GLASS, gain=0.0), dict(cid=_GLASS_2019, gain=-5.0)],
                                                                   echo=dict(delay=0.3, gain=-9.0, repeats=1))),
    (98, 'Fake Glass Harmonica + Glass 2019, no echo', dict(make='stack', layers=[dict(cid=_FAKE_GLASS, gain=0.0), dict(cid=_GLASS_2019, gain=0.0)])),
    # asked for by name: the A320U soundfont's Solo Vox and Voice Oohs together, at their own levels
    (53, *_SOLO_VOX_RS),
    (53, *_OOHS_RS),
    (53, 'A320U Solo Vox 70% right + Voice Oohs 70% left', dict(make='stack', layers=[
        dict(cid=_derived_cid(*_SOLO_VOX_RS), gain=0.0, pan=70.0), dict(cid=_derived_cid(*_OOHS_RS), gain=0.0, pan=-70.0)])),
] + [
    # the soundfont picks whose notes compressed to 2-14 ms blips (a single-cycle loop is too short for
    # kobi.compress to find one of its own): resampled in stereo, with 1.5 s of their own release
    (program, f'{title}, resampled', dict(make='resample', src=cid, lo=24, hi=96, step=3, stereo=True, tail=1.5))
    for program, title, cid in [(62, 'FluidR3 Synth Brass 3', 'd87df9a0062d'), (81, 'FluidR3 Saw Wave', '03f04826236c'),
                                (83, 'MS Basic Chiffer Lead', '3080f4d38e80'), (88, 'FluidR3 Fantasia', 'b3177b4b0439'),
                                (96, 'FluidR3 Ice Rain', '9ce8ddbf279a')]
]


def _derived_alts() -> list:
    out = []
    for program, title, loc in DERIVED_ALTS:
        loc = _derived_loc(title, loc)
        out.append(Alt(_cid(DERIVED.id, loc), DERIVED.id, title, 'derived', loc, {program: 1.2}))
    return out


# ---------------------------------------------------------------------- gm_map's own candidates

def _gm_loc(c) -> dict:
    return dict(source=c.source, path=c.path, sub=c.sub, kind=c.kind, standin=c.standin, note=c.note,
                octave=c.octave, tags=list(c.tags))


def current_cand(num: int):
    """The gm_map candidate the bank was built from (the first one on disk)."""
    if num == DRUMS:
        return None
    for c in gm_map.PROGRAMS[num].cands:
        if c.resolve()[1]:
            return c
    return None


def program_kind(num: int) -> str:
    if num == DRUMS:
        return 'kit'
    c = current_cand(num) or gm_map.PROGRAMS[num].cands[0]
    return c.kind


def _identity(source: str, path: str, sub, tags) -> tuple:
    return (source, os.path.normpath(path), sub or '', tuple(tags or ()))


def _gm_alts() -> tuple[list, dict]:
    """(fallback candidates as Alts, {program: identity of the current source})."""
    out, current = [], {}
    for p in gm_map.PROGRAMS:
        cur = current_cand(p.num)
        if cur is not None:
            current[p.num] = _identity(cur.source, cur.path, cur.sub, cur.tags)
        for c in p.cands:
            if c is cur or not c.resolve()[1]:
                continue
            loc = _gm_loc(c)
            lib = {'FreePats': 'FreePats', 'VCSL': 'VCSL', 'VSCO2': 'VSCO2', 'Iowa': 'Iowa', 'SSO': 'SSO'}.get(c.source, c.source)
            if c.source == 'Karoryfer':
                lib = next((l.id for l in LOCAL if l.where == 'Karoryfer/' + c.path), 'Karoryfer')
            title = os.path.basename(c.path) + (f' / {c.sub}' if c.sub and c.source not in ('FreePats', 'Karoryfer') else '')
            lic = next((v for k, v in _FREEPATS_LICENCE.items() if k in c.path), 'CC0 1.0') if c.source == 'FreePats' else ''
            out.append(Alt(_cid('gm', loc), lib, title, 'gm', loc, {p.num: 1.0}, listed=True, license=lic))
    merged = {}                                          # one candidate listed for several programs
    for a in out:
        if a.cid in merged:
            merged[a.cid].programs.update(a.programs)
        else:
            merged[a.cid] = a
    return list(merged.values()), current


def _alt_identity(a: Alt) -> tuple | None:
    """What an alternative plays, so one instrument reached two ways (a gm_map fallback and the same
    file found by the scan) is offered once."""
    lib = ALL.get(a.lib)
    if a.shape == 'gm':
        if a.loc['source'] in ('FreePats', 'Karoryfer'):
            c = gm_map.Cand(a.loc['source'], a.loc['path'], a.loc['sub'])
            path, n = c.resolve()
            return ('sfz', os.path.normpath(path)) if n else None
        return _identity(a.loc['source'], a.loc['path'], a.loc['sub'], a.loc['tags'])
    if lib and lib.host == 'local-folder':
        return _identity(lib.where, a.loc['path'], a.loc['sub'], a.loc['tags'])
    if lib and lib.host == 'local-sfz':
        return ('sfz', os.path.normpath(os.path.join(ROOT, lib.where, a.loc['rel'])))
    return None


# ---------------------------------------------------------------------- the catalogue

class Catalog:
    def __init__(self, fetch_ctx=None):
        self.lock = threading.Lock()
        self.alts: dict[str, Alt] = {}
        self.indexed: dict[str, str] = {}     # remote library id -> 'ok' | error text
        self.current: dict[int, tuple] = {}
        self.ctx = fetch_ctx
        self._current_sfz: dict[int, str] = {}

    def scan_local(self) -> None:
        gm, self.current = _gm_alts()
        found = []
        for lib in LOCAL:
            if not os.path.isdir(os.path.join(ROOT, lib.where)):
                continue
            found += _scan_folder_lib(lib) if lib.host == 'local-folder' else _scan_sfz_lib(lib)
        for lib in SF2:
            found += _scan_sf2_lib(lib)
        found += _derived_alts()
        for p in gm_map.PROGRAMS:                        # the SFZ file the bank was built from, to leave out
            c = current_cand(p.num)
            if c is not None and c.source in ('FreePats', 'Karoryfer'):
                self._current_sfz[p.num] = os.path.normpath(c.resolve()[0])
        with self.lock:
            listed = {_alt_identity(a): a for a in gm}
            listed.pop(None, None)
            for a in gm:
                self.alts[a.cid] = a
            for a in found:
                twin = listed.get(_alt_identity(a))
                if twin is not None:                     # keep gm_map's version, with the scan's other programs
                    for p, st in a.programs.items():
                        twin.programs.setdefault(p, st)
                else:
                    self.alts[a.cid] = a

    def index_remote(self, lib: Library) -> int:
        """List a remote library's instruments (no audio).  Returns how many joined."""
        from .fetch import GitHubRepo, RemoteZip, iowa_zips
        ctx = self.ctx
        if lib.host == 'github':
            repo = GitHubRepo(ctx.fetcher, lib.where, lib_root(lib), ctx.cache)
            sfzs = sorted(repo.sfz_files())
            alts = _sfz_alts(lib, sfzs, repo.tree()['files'])
            if not alts and len(sfzs) == 1 and DRUMS in lib.hints:          # a kit library of one file: that is the kit
                loc = dict(rel=sfzs[0])
                alts = [Alt(_cid(lib.id, loc), lib.id, _sfz_label(sfzs[0]), 'sfz', loc, {DRUMS: lib.hints[DRUMS]})]
        elif lib.host == 'zip':
            rz = RemoteZip(ctx.fetcher, lib.where, ctx.cache)
            mem = rz.members()
            alts = _sfz_alts(lib, sorted(n for n in mem if n.lower().endswith('.sfz') and '__MACOSX' not in n),
                             {n: m['size'] for n, m in mem.items()})
        elif lib.host == 'iowa':
            inst = lib.id.split('-', 1)[1]
            groups = {}
            for z in iowa_zips(ctx.fetcher, lib.where, ctx.cache):
                words = [w.lower() for w in re.split(r'[._ ]', os.path.basename(z.replace('%20', ' ')))]
                tags = tuple(w for w in words if w in _IOWA_TAGS or w in ('rubber', 'yarn', 'cord', 'hard', 'soft', 'brass', 'plastic',
                                                                            'rosewood', 'bowed', 'arco', 'dampen', 'nodamp'))
                groups.setdefault(tags, []).append(z)
            alts = []
            for tags, zips in groups.items():
                loc = dict(inst=inst, zips=zips, tags=list(tags))
                alts.append(Alt(_cid(lib.id, loc), lib.id, ' '.join([inst, *tags]), 'folder', loc, dict(lib.hints)))
        else:
            alts = []
        with self.lock:
            for a in alts:
                self.alts[a.cid] = a
            self.indexed[lib.id] = 'ok'
        return len(alts)

    def index_all_remote(self, log=print) -> None:
        for lib in REMOTE:
            if lib.id in self.indexed:
                continue
            try:
                n = self.index_remote(lib)
                log(f'indexed {lib.title}: {n} instruments')
            except Exception as e:                       # a dead link costs one library, not the app
                with self.lock:
                    self.indexed[lib.id] = f'error: {e}'
                log(f'index failed {lib.title}: {e}')

    def get(self, cid: str) -> Alt | None:
        return self.alts.get(cid)

    def ranked(self, program: int, exclude: set = frozenset()) -> list:
        """Alternatives for ``program``, best first, libraries interleaved so the deck moves from
        library to library instead of through ten variants of one."""
        cur = self.current.get(program)
        cur_sfz = self._current_sfz.get(program)
        with self.lock:
            pool = [a for a in self.alts.values() if program in a.programs and a.cid not in exclude]
        scored = []
        for a in pool:
            if cur is not None and _alt_identity(a) == cur:
                continue
            lib = ALL.get(a.lib)
            if cur_sfz and lib and lib.host == 'local-sfz' and a.shape == 'sfz' and \
                    os.path.normpath(os.path.join(ROOT, lib.where, a.loc['rel'])) == cur_sfz:
                continue
            s = a.programs[program] + (0.3 if a.listed else 0.0)
            if lib is not None:
                s += 0.05 if lib.license.startswith(('CC0', 'Public', 'MIT')) else 0.0
                s -= 0.0 if lib.open_licence else 0.2
                s -= 0.05 if 'GPL' in a.licence() else 0.0      # shippable, but copyleft: after the permissive ones
            scored.append((s, a))
        by_lib = {}
        for s, a in sorted(scored, key=lambda t: (-t[0], len(t[1].title), t[1].title)):
            by_lib.setdefault(a.lib, []).append((s, a))
        for k in by_lib:
            by_lib[k] = by_lib[k][:MAX_PER_LIB]
        order = sorted(by_lib, key=lambda k: -by_lib[k][0][0])
        out = []
        for r in range(MAX_PER_LIB):
            rnd = [by_lib[k][r] for k in order if len(by_lib[k]) > r]
            out += [a for _, a in sorted(rnd, key=lambda t: -t[0])]
        return out

    def counts(self) -> dict:
        with self.lock:
            return dict(alts=len(self.alts), remote_indexed=sum(1 for v in self.indexed.values() if v == 'ok'),
                        remote_total=len(REMOTE), remote_errors={k: v for k, v in self.indexed.items() if v != 'ok'})
