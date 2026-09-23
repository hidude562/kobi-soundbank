"""kobi.swipe.prep — turn a card into something to listen to.

Every card plays the same phrase for its program (``gm_words.REGISTER``): an arpeggio with four
velocities, then a held chord (or one held note for single-line instruments) so loops and
sustains are heard, hits for one-shots, two bars of beat for a kit.

For a remote instrument the phrase decides the download: the SFZ text is fetched, parsed, the
regions those notes and velocities reach are picked (one round-robin, every simultaneous layer),
and only their samples are pulled — capped at ``max_bytes`` per card.  Folder instruments
(VCSL, VSCO 2) that were not audited by gm_map get their octave checked by pitch detection, as
``kobi.audition`` does.  Results are cached on disk by content key, so a restart costs nothing.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import posixpath
import re
import threading

from .. import gm_map, paths
from ..demo import phrase as demo_phrase, write_view_sfz
from ..ingest import default_view, load_candidate, load_sfz
from .catalog import Alt, Catalog, current_cand, lib_root, program_kind
from .fetch import Fetcher, GitHubRepo, RemoteZip
from .gm_words import DRUMS, MONO, REGISTER
from .libraries import ALL
from . import work

PHRASE_VERSION = 4
BANKS = {'slim': 'kobi_slim', 'micro': 'kobi_ultra_hifi_pf'}


class Skip(Exception):
    """This alternative cannot be previewed (not GM-mapped, too big, nothing playable)."""


# ---------------------------------------------------------------------- the phrase

def plan(program: int, kind: str, lo: int = 0, hi: int = 127, keys: list | None = None) -> dict:
    """{'events': [(t, 'on'|'off', key, vel)], 'secs', 'shift'} for ``program`` on an instrument
    playing ``lo``..``hi`` (``keys``: its playable keys, for one-shots)."""
    if kind == 'kit':
        ev, secs = demo_phrase('kit', {})
        return dict(events=ev, secs=secs, shift=0)
    if kind == 'oneshot':
        ks = keys or [60, 62, 64, 67, 69, 72]
        if len(ks) > 6:
            step = len(ks) / 6
            ks = [ks[int(i * step)] for i in range(6)]
        ev = []
        for i, k in enumerate(ks):
            ev += [(i * 0.45, 'on', k, 100), (i * 0.45 + 0.3, 'off', k, 0)]
        return dict(events=ev, secs=len(ks) * 0.45 + 1.6, shift=0)
    root = REGISTER.get(program, 60)
    shift = 0
    while root + shift + 12 > hi + 2 and root + shift - 12 >= lo - 2:
        shift -= 12
    while root + shift < lo - 2 and root + shift + 24 <= hi + 2:
        shift += 12
    r = root + shift

    def clamp(k):
        return min(hi, max(lo, k))
    ev, dur = [], 0.6 if kind == 'decay' else 0.4
    for i, (d, v) in enumerate(zip((0, 4, 7, 12), (84, 96, 76, 108))):
        k = clamp(r + d)
        ev += [(i * 0.42, 'on', k, v), (i * 0.42 + dur, 'off', k, 0)]
    hold = [r + 7] if program in MONO else [r, r + 4, r + 7]
    for k in hold:
        ev += [(1.8, 'on', clamp(k), 100), (4.0, 'off', clamp(k), 0)]
    return dict(events=ev, secs=5.6 if kind == 'decay' else 5.2, shift=shift)


def hits(pl: dict) -> list:
    return sorted({(k, v) for _, ty, k, v in pl['events'] if ty == 'on'})


def needed_regions(view: list, want: list) -> list:
    """The regions (key, velocity) pairs reach: every layer that sounds together, one round robin."""
    out, seen = [], set()
    for key, vel in want:
        on_key = [r for r in view if r.lokey <= key <= r.hikey]
        if not on_key:
            continue
        at_vel = [r for r in on_key if r.lovel <= vel <= r.hivel]
        if not at_vel:
            near = min(on_key, key=lambda r: min(abs(vel - r.lovel), abs(vel - r.hivel)))
            at_vel = [r for r in on_key if (r.lovel, r.hivel) == (near.lovel, near.hivel)]
        first = min((r.seq_position, r.lorand) for r in at_vel)
        for r in at_vel:
            if (r.seq_position, r.lorand) == first and id(r) not in seen:
                seen.add(id(r))
                out.append(r)
    return out


def collapse_variants(view: list) -> list:
    """Keep one round robin / random variant per zone (a partial download has only that one)."""
    zones = {}
    for r in view:
        zones.setdefault((r.lokey, r.hikey, r.lovel, r.hivel, r.sw_last, r.trigger), []).append(r)
    out = []
    for grp in zones.values():
        first = min((r.seq_position, r.lorand) for r in grp)
        for r in grp:
            if (r.seq_position, r.lorand) == first:
                r.seq_position, r.seq_length, r.lorand, r.hirand = 1, 1, 0.0, 1.0
                out.append(r)
    return out


def cover_range(view: list, lo: int, hi: int) -> None:
    """Stretch a layer's outermost zones (per velocity band) so it plays every key from ``lo`` to
    ``hi``: the nearest sample, repitched.  For a quiet layer that has to be on every attack."""
    from ..ingest import cover_keys
    cover_keys(view, lo, hi)


def _range(view: list) -> tuple[int, int]:
    keyed = [r for r in view if r.pitch_keycenter is not None]
    if not keyed:
        return 60, 60
    return min(r.lokey for r in keyed), max(r.hikey for r in keyed)


def _shift_octave(inst, octave: int) -> None:
    for r in inst.regions:
        if r.pitch_keycenter is not None:
            r.pitch_keycenter += 12 * octave
            r.lokey, r.hikey = min(127, max(0, r.lokey + 12 * octave)), min(127, max(0, r.hikey + 12 * octave))


# ---------------------------------------------------------------------- remote libraries

_TEXT = ('.sfz', '.sfzh', '.txt', '.inc', '.h', '.md', '.xml')


def _expand(path: str, defines: dict) -> list:
    """Every spelling of an include path under the values its $variables took anywhere."""
    out = [path.replace('\\', '/')]
    for k in sorted(defines, key=len, reverse=True):
        if any(k in o for o in out):
            out = [o.replace(k, v) for o in out for v in sorted(defines[k])][:64]
    return [o for o in out if '$' not in o]


class Remote:
    """One remote library behind a common face: text files, path lookup, per-file fetch."""

    def __init__(self, lib, fetcher: Fetcher, cache: str):
        self.lib, self.root = lib, lib_root(lib)
        if lib.host == 'github':
            self.repo = GitHubRepo(fetcher, lib.where, self.root, cache)
            self.files = self.repo.tree()['files']
        else:
            self.zip = RemoteZip(fetcher, lib.where, cache)
            self.files = {n: m['size'] for n, m in self.zip.members().items() if '__MACOSX' not in n}
        self._lower = {}
        self._base = {}
        for p in self.files:
            self._lower.setdefault(p.lower(), p)
            self._base.setdefault(os.path.basename(p).lower(), []).append(p)

    def local(self, rel: str) -> str:
        return os.path.join(self.root, rel)

    def fetch(self, rel: str) -> str:
        if self.lib.host == 'github':
            return self.repo.fetch(rel)
        return self.zip.extract(rel, self.local(rel))

    def fetch_text(self) -> None:
        """Every small text file in the library (the fallback when includes cannot be followed)."""
        from concurrent.futures import ThreadPoolExecutor
        todo = [p for p, size in self.files.items()
                if os.path.splitext(p)[1].lower() in _TEXT and size <= 512 * 1024 and not os.path.exists(self.local(p))]
        with ThreadPoolExecutor(6) as ex:
            list(ex.map(self.fetch, todo))

    def lookup(self, rel: str) -> str | None:
        rel = posixpath.normpath(rel.replace('\\', '/'))
        return rel if rel in self.files else self._lower.get(rel.lower())

    def fetch_sfz(self, rel: str) -> None:
        """``rel`` and everything it #includes, following #define'd include paths — not the other
        450 SFZ files a multi-mic kit ships."""
        from concurrent.futures import ThreadPoolExecutor
        top = posixpath.dirname(rel)
        defines: dict = {}
        done, todo = set(), [rel]
        while todo:
            with ThreadPoolExecutor(6) as ex:
                list(ex.map(self.fetch, todo))
            nxt = []
            for p in todo:
                done.add(p)
                with open(self.local(p), encoding='utf-8', errors='replace') as fh:
                    text = fh.read()
                for m in re.finditer(r'#define\s+(\$\w+)\s+(\S+)', text):
                    defines.setdefault(m.group(1), set()).add(m.group(2))
                for m in re.finditer(r'#include\s+"([^"]+)"', text):
                    for inc in _expand(m.group(1), defines):
                        for base in (top, posixpath.dirname(p)):
                            hit = self.lookup(posixpath.join(base, inc))
                            if hit and hit not in done and hit not in nxt:
                                nxt.append(hit)
                                break
            todo = nxt

    def resolve(self, local_path: str) -> str | None:
        """The remote file a region's (possibly mis-cased or mis-pathed) sample refers to."""
        rel = os.path.relpath(local_path, self.root).replace(os.sep, '/')
        if rel in self.files:
            return rel
        if rel.lower() in self._lower:
            return self._lower[rel.lower()]
        hits = self._base.get(os.path.basename(rel).lower(), [])
        parent = os.path.basename(os.path.dirname(rel)).lower()
        same = [h for h in hits if os.path.basename(os.path.dirname(h)).lower() == parent]
        if len(same) == 1:
            return same[0]
        return hits[0] if len(hits) == 1 else None


# ---------------------------------------------------------------------- the preparer

def _key(*parts) -> str:
    return hashlib.sha1('|'.join(str(p) for p in (PHRASE_VERSION,) + parts).encode()).hexdigest()[:16]


class Prep:
    def __init__(self, catalog: Catalog, fetcher: Fetcher, store: str, pool, max_bytes: int = 40 << 20):
        self.cat, self.f, self.pool = catalog, fetcher, pool
        self.cache = os.path.join(store, 'index')
        self.out = os.path.join(store, 'previews')
        self.max_bytes = max_bytes
        self._remotes: dict[str, Remote] = {}
        self._rlock = threading.Lock()
        self._sf2_lock = threading.Lock()
        os.makedirs(self.out, exist_ok=True)

    def remote(self, lib) -> Remote:
        with self._rlock:
            if lib.id not in self._remotes:
                self._remotes[lib.id] = Remote(lib, self.f, self.cache)
            return self._remotes[lib.id]

    # ------------------------------------------------------------------ cache
    def _cached(self, key: str) -> dict | None:
        p = os.path.join(self.out, key + '.json')
        if os.path.exists(p) and os.path.exists(os.path.join(self.out, key + '.mp3')):
            with open(p) as fh:
                return json.load(fh)
        return None

    def _finish(self, key: str, sfz: str, pl: dict, meta: dict) -> dict:
        res = self.pool.submit(work.render_preview, sfz, pl['events'], pl['secs'], os.path.join(self.out, key)).result()
        res.update(meta, key=key, shift=pl['shift'])
        with open(os.path.join(self.out, key + '.json'), 'w') as fh:
            json.dump(res, fh)
        return res

    # ------------------------------------------------------------------ the bank as it is
    def bank_sfz(self, bank: str, program: int) -> str | None:
        gm = os.path.join(paths.ROOT, BANKS[bank], 'GM')
        if program == DRUMS:
            p = os.path.join(gm, 'Drums.sfz')
            return p if os.path.exists(p) else None
        hit = glob.glob(os.path.join(glob.escape(gm), f'{program:03d} *.sfz'))
        return hit[0] if hit else None

    def bank_preview(self, bank: str, program: int, job=None) -> dict:
        sfz = self.bank_sfz(bank, program)
        if sfz is None:
            raise Skip(f'{BANKS[bank]} has no program {program}')
        key = _key('bank', bank, program, int(os.path.getmtime(sfz)))
        hit = self._cached(key)
        if hit:
            return hit
        kind = program_kind(program)
        view = default_view(load_sfz(sfz))
        keyed = [r for r in view if r.pitch_keycenter is not None and 'pitch_keytrack' not in r.opcodes]
        if kind not in ('kit', 'oneshot') and not keyed:          # the bank kept a single unpitched hit
            kind = 'oneshot'
        lo, hi = _range(keyed) if keyed else (0, 127)
        keys = sorted({k for r in view for k in range(r.lokey, r.hikey + 1)})
        pl = plan(program, kind, lo, hi, keys=keys if kind == 'oneshot' else None)
        with open(sfz, encoding='utf-8', errors='replace') as fh:
            head = fh.read(600)
        src = next((ln.split('<-', 1)[1].strip() for ln in head.splitlines() if 'kobi compressed bank' in ln and '<-' in ln), '')
        return self._finish(key, sfz, pl, dict(what='bank', bank=bank, program=program, source=src))

    # ------------------------------------------------------------------ an alternative (or the current source)
    def source_preview(self, program: int, job=None) -> dict:
        c = current_cand(program)
        if c is None:
            raise Skip('no single source (the kit is assembled by kobi.drums)')
        loc = dict(source=c.source, path=c.path, sub=c.sub, kind=c.kind, standin=c.standin, note=c.note,
                   octave=c.octave, tags=list(c.tags))
        alt = Alt('source-%d' % program, c.source, os.path.basename(c.path), 'gm', loc, {program: 1.0})
        return self._alt(alt, program, job, what='source')

    def cached_alt(self, cid: str, program: int) -> dict | None:
        """An alternative's preview result if it was rendered, without rendering it."""
        alt = self.cat.get(cid)
        return self._cached(_key('alt', program, alt.lib, json.dumps(alt.loc, sort_keys=True))) if alt else None

    def alt_preview(self, cid: str, program: int, job=None) -> dict:
        alt = self.cat.get(cid)
        if alt is None:
            raise Skip('unknown alternative')
        return self._alt(alt, program, job, what='alt')

    def _alt(self, alt: Alt, program: int, job, what: str) -> dict:
        key = _key(what, program, alt.lib, json.dumps(alt.loc, sort_keys=True))
        hit = self._cached(key)
        if hit:
            return hit
        kind = program_kind(program)
        lib = ALL.get(alt.lib)

        def say(msg):
            if job is not None:
                job.progress = msg

        if alt.shape == 'derived' and alt.loc['make'] == 'stack':
            return self._stack(alt, program, kind, key, say)

        fetched0 = self.f.total
        inst, audit, partial = self._acquire(alt, lib, program, kind, say)
        full_bytes = self._full_bytes(alt, lib, inst, partial)
        view = default_view(inst)
        if kind == 'kit' and not any(r.lokey <= 36 <= r.hikey for r in view) or \
                kind == 'kit' and not any(r.lokey <= 38 <= r.hikey for r in view):
            raise Skip('not GM-mapped (no kick on 36 / snare on 38)')
        if kind not in ('kit', 'oneshot') and not any(r.pitch_keycenter is not None for r in view):
            kind = 'oneshot'                                          # unpitched hits: play them, not a melody
        octave = int(alt.loc.get('octave') or 0) if alt.shape != 'gm' else 0
        if octave:                                                    # the library's convention, known from gm_map
            _shift_octave(inst, octave)
            view = default_view(inst)
            if partial:
                self._fetch_for(view, program, kind, partial, say)
        elif audit and kind not in ('oneshot', 'kit'):
            say('checking octave')
            octave = self._audit(view, audit, program)
            if octave:
                _shift_octave(inst, octave)
                view = default_view(inst)
                if partial:
                    self._fetch_for(view, program, kind, partial, say)
        matched, tried = 0, 0
        while True:
            lo, hi = _range(view)
            pl = plan(program, kind, lo, hi)
            keep = [r for r in view if os.path.exists(r.sample)]
            keep = collapse_variants(keep) if partial else keep
            if not keep:
                raise Skip('nothing playable (a placeholder, or samples the SFZ names are not in the library)')
            sfz = os.path.join(self.out, 'sfz', key + '.sfz')
            info = write_view_sfz(inst, keep, sfz, kind)
            if kind == 'oneshot':
                pl = plan(program, kind, keys=info['keys'])
            say('rendering')
            meta = dict(what=what, program=program, cid=alt.cid, lib=alt.lib, title=alt.title, octave=octave,
                        matched=matched, regions=len(keep), fetched=self.f.total - fetched0, range=[info['lo'], info['hi']],
                        full_bytes=full_bytes)
            res = self._finish(key, sfz, pl, meta)
            if what != 'alt' or tried == 2:
                return res
            k = self._octave_vs_bank(res, program, kind)
            if not k:
                return res                                   # on the bank's octave (after a move, or as mapped)
            # first pass: an octave away from the bank on the same note, so the map or the patch sits
            # elsewhere: move it.  Second pass still off: the reading was not to be trusted, move it back.
            step = k if tried == 0 else -matched
            say('matching the bank\'s octave' if tried == 0 else 'octave reading unsure: back as mapped')
            octave += step
            matched = step if tried == 0 else 0
            tried = tried + 1 if tried == 0 else 2
            _shift_octave(inst, step)
            view = default_view(inst)
            if partial:
                self._fetch_for(view, program, kind, partial, say)

    def _full_bytes(self, alt: Alt, lib, inst, rem) -> int | None:
        """What the whole instrument weighs on the server (None: it is already on disk)."""
        if lib is None or not lib.remote:
            return None
        if lib.host == 'iowa':
            from ..ingest import parse_name
            want, total = set(alt.loc['tags']), 0
            for url in alt.loc['zips']:
                for name, m in RemoteZip(self.f, url, self.cache).members().items():
                    base = os.path.basename(name)
                    if '__MACOSX' not in name and base.lower().endswith(('.aif', '.aiff', '.wav')) and \
                            want <= set(parse_name(os.path.splitext(base)[0])['tags']):
                        total += m['size']
            return total
        paths = {r.opcodes.get('_remote') or rem.resolve(r.sample) for r in inst.regions}
        return sum(rem.files.get(p, 0) for p in paths if p)

    def _make_trimmed(self, alt: Alt, kind: str, path: str) -> None:
        """A copy of an instrument whose samples start past the bow's (or breath's) first scratch: the
        onset, then ``trim_ms`` further in, with a 12 ms fade-in.  Written as SFZ + WAV, so the bank
        build can use it like any other library."""
        import numpy as np
        import soundfile as sf
        src = alt.loc['src']
        inst = load_candidate(gm_map.Cand(**{k: src[k] for k in ('source', 'path', 'sub', 'kind', 'standin', 'note', 'octave')},
                                           tags=tuple(src['tags'])), alt.title)
        if inst is None:
            raise Skip('source missing on disk')
        view = default_view(inst)
        out_dir = os.path.dirname(path)
        os.makedirs(os.path.join(out_dir, 'samples'), exist_ok=True)
        done = {}
        for r in view:
            if r.sample not in done:
                x, fs = sf.read(r.sample, dtype='float32', always_2d=True)
                env = np.abs(x).max(axis=1)
                win = max(1, int(0.005 * fs))
                env = np.convolve(env, np.ones(win) / win, mode='same')
                onset = int(np.argmax(env > 0.1 * env.max())) if env.max() > 0 else 0
                start = min(len(x) - 1, onset + int(alt.loc['trim_ms'] * fs / 1000))
                y = x[start:].copy()
                fade = min(len(y), int(0.012 * fs))
                y[:fade] *= np.sin(np.linspace(0, np.pi / 2, fade))[:, None] ** 2
                name = os.path.splitext(os.path.basename(r.sample))[0] + '.wav'
                sf.write(os.path.join(out_dir, 'samples', name), y, fs, subtype='PCM_24')
                done[r.sample] = os.path.join(out_dir, 'samples', name)
            r.sample = done[r.sample]
        write_view_sfz(inst, view, path, kind)
        with open(path) as fh:                                   # relative sample paths: the folder can move
            text = fh.read().replace(os.path.join(out_dir, 'samples') + os.sep, 'samples/')
        with open(path, 'w') as fh:
            fh.write(f'// {alt.title}: made by kobi.swipe from {src["source"]} {src["path"]} {" ".join(src["tags"])}\n' + text)

    def _make_resampled(self, alt: Alt, program: int, kind: str, path: str, say, hold: float = 4.0) -> None:
        """A preset played through sfizz every ``step`` keys from ``lo`` to ``hi``, each note held ``hold``
        seconds at velocity 127 and kept as a WAV: its filter, envelope, layers and loops baked in.  Mono
        and centred for a stack layer (the layer's pan places it); ``stereo`` keeps the preset's own
        panning; ``tail`` seconds after the note-off keep its release for kobi.compress to measure.
        The zones meet halfway between the rendered keys; the outer ones reach the source's own range."""
        import numpy as np
        import soundfile as sf
        from ..demo import FS, render
        src = self.cat.get(alt.loc['src'])
        if src is None:
            raise Skip('the resampled preset is no longer in the catalogue')
        src_lib = ALL.get(src.lib)
        if src_lib is None or src_lib.host != 'sf2':
            raise Skip('only soundfont presets are resampled')
        inst, _, _ = self._acquire(src, src_lib, program, kind, say)      # extracts the preset
        lo_src, hi_src = _range(default_view(inst))
        keys = list(range(alt.loc['lo'], alt.loc['hi'] + 1, alt.loc['step']))
        src_path = os.path.join(lib_root(src_lib), src.loc['rel'])
        stereo, tail = bool(alt.loc.get('stereo')), float(alt.loc.get('tail', 0.0))
        with open(src_path) as fh:
            text = fh.read()
        if not stereo:                                             # centred, so a layer's pan places it
            text = re.sub(r'(?<!\S)pan=\S+', '', text)
        text = re.sub(r'default_path=(\S+)', lambda m: f'default_path={os.path.join(os.path.dirname(src_path), m.group(1))}', text)
        out_dir = os.path.dirname(path)
        os.makedirs(os.path.join(out_dir, 'samples'), exist_ok=True)
        tmp = path + '.src.sfz'
        with open(tmp, 'w') as fh:
            fh.write(text)
        lines = []
        try:
            for i, k in enumerate(keys):
                say(f'resampling {src.title}: key {k} ({i + 1}/{len(keys)})')
                x = render(tmp, [(0.0, 'on', k, 127), (hold if tail else hold + 1.0, 'off', k, 0)], hold + tail)
                x = x if stereo else x.mean(axis=1)
                fade = int(0.01 * FS)
                x[-fade:] *= np.linspace(1.0, 0.0, fade) if x.ndim == 1 else np.linspace(1.0, 0.0, fade)[:, None]
                sf.write(os.path.join(out_dir, 'samples', f'k{k:03d}.wav'), x, FS, subtype='PCM_24')
                lo = lo_src if i == 0 else (keys[i - 1] + k) // 2 + 1
                hi = hi_src if i == len(keys) - 1 else (k + keys[i + 1]) // 2
                lines.append(f'<region> sample=k{k:03d}.wav lokey={lo} hikey={hi} pitch_keycenter={k}')
        finally:
            os.remove(tmp)
        with open(path, 'w') as fh:
            fh.write(f'// {alt.title}: made by kobi.swipe, {src.title} ({ALL[src.lib].title}) played every {alt.loc["step"]} keys, '
                     f'{hold:g} s at velocity 127' + (f', {tail:g} s of release' if tail else '') + (', stereo' if stereo else '') +
                     f'\n<control> default_path=samples/\n<global> ampeg_release=0.35\n' + '\n'.join(lines) + '\n')

    def _stack(self, alt: Alt, program: int, kind: str, key: str, say) -> dict:
        """Several versions played together (with gains), and optionally echoes: each layer's regions,
        then the whole set again ``delay`` later and ``gain`` dB down, ``repeats`` times."""
        import copy
        from ..demo import write_view_sfz as write
        fetched0 = self.f.total
        layers = []
        for i, L in enumerate(alt.loc['layers']):
            la = self.cat.get(L['cid'])
            if la is None:
                raise Skip('a layer is no longer in the catalogue')
            say(f'layer {i + 1}: {la.title}')
            res = self.alt_preview(L['cid'], program)            # its own preview: fetched, octave-checked
            inst, _, partial = self._acquire(la, ALL.get(la.lib), program, kind, say)
            if res.get('octave'):
                _shift_octave(inst, int(res['octave']))
            layers.append((inst, default_view(inst), partial, L))
        lo, hi = _range(layers[0][1])
        pl = plan(program, kind, lo, hi)
        done = []
        for i, (inst, view, partial, L) in enumerate(layers):
            if i and L.get('cover'):                              # a layer that must sound on every note of the first
                cover_range(view, lo, hi)
            if partial:                                           # the stack's own notes, not the layer preview's
                self._fetch_for(view, program, kind, partial, say, pl)
            view = [r for r in view if os.path.exists(r.sample)]
            view = collapse_variants(view) if partial else view
            for r in view:
                r.volume_db += L.get('gain', 0.0)
                r.pan = max(-100.0, min(100.0, r.pan + L.get('pan', 0.0)))
            done.append((inst, view))
        layers = done
        echo = alt.loc.get('echo')
        body, n = [], 0
        tmp = os.path.join(self.out, 'sfz', key + '.layer.sfz')
        for inst, view in layers:
            copies = [(r, 0.0) for r in view]
            if echo:
                for k in range(1, echo['repeats'] + 1):
                    for r in view:
                        e = copy.copy(r)
                        e.volume_db = r.volume_db + echo['gain'] * k
                        copies.append((e, echo['delay'] * k))
            write(inst, [r for r, _ in copies], tmp, kind)
            with open(tmp) as fh:
                lines = [ln for ln in fh.read().splitlines() if ln.startswith('<region>')]
            body += [ln + (f' delay={d:g}' if d else '') for ln, (_, d) in zip(lines, copies)]
            n += len(view)
        os.remove(tmp)
        sfz = os.path.join(self.out, 'sfz', key + '.sfz')
        with open(sfz, 'w') as fh:
            fh.write(f'// {alt.title}: layered by kobi.swipe\n<global> ampeg_release={"0.35" if kind != "oneshot" else "0.05"}\n'
                     + '\n'.join(body) + '\n')
        if echo:                                                 # let the last echo ring out
            pl = dict(pl, secs=pl['secs'] + echo['delay'] * echo['repeats'])
        say('rendering')
        meta = dict(what='alt', program=program, cid=alt.cid, lib=alt.lib, title=alt.title, octave=0, matched=0,
                    regions=n, fetched=self.f.total - fetched0, range=[lo, hi], layers=len(layers))
        return self._finish(key, sfz, pl, meta)

    def _octave_vs_bank(self, res: dict, program: int, kind: str) -> int:
        """+k / -k when the alternative's first note sounds k whole octaves (1 or 2: mallets are written low)
        above / below the bank's, else 0
        (the octave to add to the alternative's key map, the pitch audit's sign convention)."""
        if kind in ('kit', 'oneshot') or res.get('f0') is None or 16 <= program <= 23:
            return 0                                         # organ footages make any octave reading a guess
        try:
            bank = self.bank_preview('slim', program)
        except Skip:
            return 0
        if bank.get('f0') is None:
            return 0
        d = (res['f0'] - res.get('shift', 0)) - (bank['f0'] - bank.get('shift', 0))
        k = round(d / 12)                           # sounding an octave high: the samples' true keys are 12 up
        return k if k in (-2, -1, 1, 2) and abs(d - 12 * k) < 0.7 else 0

    # ------------------------------------------------------------------ getting the instrument on disk
    def _acquire(self, alt: Alt, lib, program: int, kind: str, say):
        """(Instrument, audit mode or None, Remote when only part of it is on disk)."""
        if alt.shape == 'gm':
            fields = {k: alt.loc[k] for k in ('source', 'path', 'sub', 'kind', 'standin', 'note', 'octave')}
            inst = load_candidate(gm_map.Cand(**fields, tags=tuple(alt.loc['tags'])), alt.title)
            if inst is None:
                raise Skip('source missing on disk')
            return inst, None, None
        if lib.host == 'local-folder':
            c = gm_map.Cand(lib.where, alt.loc['path'], alt.loc['sub'], kind, tags=tuple(alt.loc['tags']))
            inst = load_candidate(c, alt.title)
            if inst is None:
                raise Skip('folder missing on disk')
            return inst, ('folder' if lib.where != 'Iowa' else None), None
        if lib.host == 'local-sfz':
            root = lib_root(lib)
            return load_sfz(os.path.join(root, alt.loc['rel']), alt.title, lib.id, search_root=root), 'sfz', None
        if lib.host == 'sf2':
            path = os.path.join(lib_root(lib), alt.loc['rel'])
            if not os.path.exists(path):
                say(f'extracting {alt.title} from {os.path.basename(lib.sf2)}')
                with self._sf2_lock:
                    from .sf2 import extract_preset
                    extract_preset(lib.sf2, os.path.dirname(path), alt.loc['preset'], alt.loc['bank'], alt.loc['name'])
            return load_sfz(path, alt.title, lib.id), None, None
        if alt.shape == 'derived' and alt.loc['make'] == 'trim':
            path = os.path.join(lib_root(lib), alt.loc['rel'])
            if not os.path.exists(path):
                say(f'trimming the attack of every sample ({alt.loc["trim_ms"]} ms)')
                self._make_trimmed(alt, kind, path)
            return load_sfz(path, alt.title, lib.id), None, None
        if alt.shape == 'derived' and alt.loc['make'] == 'resample':
            path = os.path.join(lib_root(lib), alt.loc['rel'])
            if not os.path.exists(path):
                self._make_resampled(alt, program, kind, path, say)
            return load_sfz(path, alt.title, lib.id), None, None
        if lib.host == 'iowa':
            return self._acquire_iowa(alt, program, kind, say), None, None
        rem = self.remote(lib)
        say(f'fetching {lib.title}: SFZ text')
        rem.fetch_sfz(alt.loc['rel'])
        inst = load_sfz(rem.local(alt.loc['rel']), alt.title, lib.id)          # no rescue: the mirror is partial
        if not inst.regions:                                                    # includes we could not follow
            say(f'fetching {lib.title}: all SFZ text')
            rem.fetch_text()
            inst = load_sfz(rem.local(alt.loc['rel']), alt.title, lib.id)
        for r in inst.regions:
            if not os.path.exists(r.sample):
                hit = rem.resolve(r.sample)
                if hit:
                    r.sample = rem.local(hit)
                    r.opcodes['_remote'] = hit
        self._fetch_for(default_view(inst), program, kind, rem, say)
        return inst, 'sfz', rem

    def _fetch_for(self, view: list, program: int, kind: str, rem: Remote, say, pl: dict | None = None) -> None:
        if kind == 'oneshot':
            regs = view[:6]
        else:
            lo, hi = _range(view)
            regs = needed_regions(view, hits(pl or plan(program, kind, lo, hi)))
        todo = sorted({r.opcodes['_remote'] for r in regs if '_remote' in r.opcodes and not os.path.exists(r.sample)})
        size = sum(rem.files.get(p, 0) for p in todo)
        if size > self.max_bytes:
            raise Skip(f'preview would need {size / 1e6:.0f} MB of samples')
        for i, p in enumerate(todo):
            say(f'fetching {rem.lib.title}: sample {i + 1}/{len(todo)} ({size / 1e6:.1f} MB)')
            rem.fetch(p)

    def _acquire_iowa(self, alt: Alt, program: int, kind: str, say):
        from ..ingest import parse_name
        root = lib_root(ALL[alt.lib], alt)
        want = set(alt.loc['tags'])
        members = []
        for url in alt.loc['zips']:
            rz = RemoteZip(self.f, url, self.cache)
            for name, m in rz.members().items():
                base = os.path.basename(name)
                if '__MACOSX' in name or not base.lower().endswith(('.aif', '.aiff', '.wav')):
                    continue
                info = parse_name(os.path.splitext(base)[0])
                if info['note'] is None or not want <= set(info['tags']):
                    continue
                members.append((info['note'], info['vel'], rz, name, m['size']))
        if not members:
            raise Skip('no notes in the archive')
        notes = sorted({n for n, *_ in members})
        pl = plan(program, kind, notes[0], notes[-1])
        pick = set()
        for key, vel in hits(pl):
            near = min(notes, key=lambda n: abs(n - key))
            m = max((m for m in members if m[0] == near), key=lambda m: m[1] or 0)
            pick.add((m[3], m[4], m[2]))
        size = sum(s for _, s, _ in pick)
        for i, (name, s, rz) in enumerate(sorted(pick, key=lambda t: t[0])):
            say(f'fetching Iowa {alt.loc["inst"]}: note {i + 1}/{len(pick)} ({size / 1e6:.1f} MB)')
            rz.extract(name, os.path.join(root, os.path.basename(name)))
        c = gm_map.Cand('Iowa', alt.loc['inst'], None, kind, tags=tuple(alt.loc['tags']))
        inst = load_candidate(c, alt.title)
        if inst is None:
            raise Skip('nothing extracted')
        return inst

    def _audit(self, view: list, mode: str, program: int) -> int:
        keyed = sorted((r for r in view if r.pitch_keycenter is not None and os.path.exists(r.sample)),
                       key=lambda r: r.pitch_keycenter)
        if not keyed:
            return 0
        idx = sorted({round(i * (len(keyed) - 1) / 2) for i in range(3)})
        items = [(keyed[i].sample, keyed[i].pitch_keycenter, keyed[i].tune) for i in idx]
        offs = self.pool.submit(work.detect_offsets, items).result()
        good = [o for o in offs if o is not None]
        if not good:
            return 0
        octs = [int(round(o / 12)) for o in good]
        mode_oct = max(set(octs), key=octs.count)
        agree = sum(1 for o, k in zip(good, octs) if k == mode_oct and abs(o - 12 * k) < 1.5) / len(offs)
        if mode_oct == 0:
            return 0
        if mode == 'folder':
            return mode_oct if agree >= 0.6 else 0
        # an SFZ map is the author's statement; overrule it only when every reading agrees, and never
        # on organs and synths, whose sub-octave stops fool the detector
        synthish = set(range(16, 24)) | {38, 39, 50, 51, 54, 62, 63} | set(range(80, 104))
        return mode_oct if agree == 1.0 and abs(mode_oct) == 1 and program not in synthish else 0

    # ------------------------------------------------------------------ after a pick
    def full_fetch(self, cid: str, job=None) -> dict:
        """Everything the picked instrument plays (not the whole library) onto disk."""
        alt = self.cat.get(cid)
        if alt is not None and alt.shape == 'derived' and alt.loc['make'] == 'stack':
            parts = [self.full_fetch(L['cid'], job) for L in alt.loc['layers']]
            return dict(complete=all(p.get('complete') for p in parts), bytes=sum(p.get('bytes', 0) for p in parts),
                        files=sum(p.get('files', 0) for p in parts))
        lib = ALL.get(alt.lib) if alt else None
        if alt is None or lib is None or not lib.remote:
            return dict(complete=True, bytes=0, files=0)
        if lib.host == 'iowa':
            root = lib_root(lib, alt)
            n = size = 0
            from ..ingest import parse_name
            for url in alt.loc['zips']:
                rz = RemoteZip(self.f, url, self.cache)
                for name, m in rz.members().items():
                    base = os.path.basename(name)
                    if '__MACOSX' in name or not base.lower().endswith(('.aif', '.aiff', '.wav')):
                        continue
                    if not set(alt.loc['tags']) <= set(parse_name(os.path.splitext(base)[0])['tags']):
                        continue
                    if job is not None:
                        job.progress = f'full fetch {alt.title}: {n + 1} files'
                    rz.extract(name, os.path.join(root, base))
                    n, size = n + 1, size + m['size']
            return dict(complete=True, bytes=size, files=n, root=root)
        rem = self.remote(lib)
        rem.fetch_sfz(alt.loc['rel'])
        inst = load_sfz(rem.local(alt.loc['rel']), alt.title, lib.id)
        if not inst.regions:
            rem.fetch_text()
            inst = load_sfz(rem.local(alt.loc['rel']), alt.title, lib.id)
        todo = set()
        for r in inst.regions:
            hit = r.opcodes.get('_remote') or (None if os.path.exists(r.sample) else rem.resolve(r.sample))
            if hit and not os.path.exists(rem.local(hit)):
                todo.add(hit)
        size = sum(rem.files.get(p, 0) for p in todo)
        for i, p in enumerate(sorted(todo)):
            if job is not None:
                job.progress = f'full fetch {alt.title}: {i + 1}/{len(todo)} files ({size / 1e6:.0f} MB)'
            rem.fetch(p)
        return dict(complete=True, bytes=size, files=len(todo), sfz=rem.local(alt.loc['rel']))
