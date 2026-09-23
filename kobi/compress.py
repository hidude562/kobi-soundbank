"""kobi.compress — the compressed kobi bank.

Every program's playable regions go through the dctjoin pipeline: sustains keep at most 0.5 s of
recorded attack and bridge into a 0.5 s untouched dctloop loop; decaying notes are flattened,
looped and their envelope refitted as SFZ envelope regions; one-shots and the drum kit are
transcoded as they are (tail silence trimmed, the kit's mic layers mixed down to one file per
hit).  Everything is Ogg Vorbis at the given quality, one folder per program, one SFZ per program
in ``<out>/GM`` in the layout the GM renderer expects.  ``SIZES.md`` compares against the source.

    python3 -m kobi.compress [--out kobi_ogg] [-q 1] [--loop 0.5] [-j 8] [programs...] [--drums]
    python3 -m kobi.compress --all --kinds decay --decay-attack 0.05 --decay-bridge 0.08   # rebuild decays, join at the impulse
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sys
import time
from multiprocessing import Pool

import numpy as np
import soundfile as sf

from . import packing, paths
from .gm_map import PROGRAMS
from .ingest import default_view, load_candidate, load_sfz, _num

from .paths import use_dctjoin
use_dctjoin()
from dctjoin.gm import GM_PROGRAMS  # noqa: E402

BANK = os.path.join(paths.ROOT, 'demo', 'GM')
OUT = paths.bank('kobi_ogg')
_GAIN = re.compile(r'<global>[^\n]*?volume=(-?[\d.]+)')


def _hz(key: int, tune_cents: float) -> float:
    return 440.0 * 2 ** ((key - 69 + tune_cents / 100.0) / 12.0)


def _trim_tail(x: np.ndarray, fs: int, floor_db: float = -70.0, hold_s: float = 0.05) -> np.ndarray:
    """Cut trailing silence: after the last point within ``floor_db`` of the peak (+ a short hold)."""
    env = np.abs(x).max(axis=1)
    thr = env.max() * 10 ** (floor_db / 20)
    last = int(np.max(np.flatnonzero(env > thr))) if env.max() > 0 else len(x)
    end = min(len(x), last + int(hold_s * fs))
    y = x[:end].copy()
    n = min(len(y), int(0.005 * fs))
    if n:
        y[-n:] *= np.linspace(1, 0, n)[:, None]
    return y


def _transcode(sources: list, gains_db: list, dst_ogg: str, quality: float, lossless: bool = False,
               max_s: float | None = None) -> float:
    """Mix ``sources`` (same rate) at their *relative* gains (the loudest layer at 0 dB), trim,
    encode.  Returns the dB the SFZ region must add back: the common gain that was left out plus
    any peak normalisation applied, so no level is lost to clipping in the file."""
    from dctjoin.unaltered import encode_ogg
    g_ref = max(gains_db)
    gains_db = [g - g_ref for g in gains_db]
    mix, fs = None, None
    for src, g in zip(sources, gains_db):
        x, f = sf.read(src, dtype='float64', always_2d=True)
        if x.shape[1] == 1 and mix is not None and mix.shape[1] == 2:
            x = np.repeat(x, 2, axis=1)
        if mix is not None and mix.shape[1] == 1 and x.shape[1] == 2:
            mix = np.repeat(mix, 2, axis=1)
        x = x * 10 ** (g / 20)
        if mix is None:
            mix, fs = x, f
        else:
            n = max(len(mix), len(x))
            mix = np.pad(mix, ((0, n - len(mix)), (0, 0))) + np.pad(x, ((0, n - len(x)), (0, 0)))
    y = _trim_tail(mix, fs)
    if max_s and len(y) > int(max_s * fs):        # the gate: nothing un-looped rings on for half a minute
        y = y[:int(max_s * fs)].copy()
        f = min(len(y), int(0.15 * fs))
        y[-f:] *= np.linspace(1, 0, f)[:, None]
    pk = float(np.abs(y).max())
    norm_db = 0.0
    if pk > 0.999:
        y *= 0.999 / pk
        norm_db = 20 * np.log10(pk / 0.999)
    if lossless:                       # packed later, encoded once with the rest of the program
        sf.write(dst_ogg, y, fs, subtype='PCM_16', format='FLAC')
        return g_ref + norm_db
    tmp = dst_ogg[:-4] + '.tmp.wav'
    sf.write(tmp, y, fs, subtype='PCM_16')
    encode_ogg(tmp, dst_ogg, quality)
    os.remove(tmp)
    return g_ref + norm_db


TASK_TIMEOUT_S = 120
PACK = True          # one Ogg per program (see kobi.packing) instead of one per note
PCM_CACHE = '.pcm'   # lossless per-note intermediates kept for re-packing (kobi.slim); safe to delete
DECAY_LADDER = [dict(max_attack_s=0.5, bridge_s=0.35), dict(max_attack_s=0.3, bridge_s=0.2), dict(max_attack_s=0.15, bridge_s=0.1)]
ATTACK = 0.5         # sustains: seconds of recorded attack kept before the bridge into the loop
MAX_UNLOOPED_S = 3.0 # a note that could not be looped is a plain transcode: cap it (with a fade) so one
                     # failed piano note cannot cost 30 s of audio and sound nothing like its neighbours
MAX_ONESHOT_S = 6.0  # one-shot programs and kit hits are meant to ring out, but not indefinitely
DECAY = dict(max_attack_s=1.0, bridge_s=0.85)      # decaying notes: transient kept, then a long harmonic cross-fade onto a loop
                                                 # taken at 1 s where the timbre has settled (chosen by ear, 2026-09-05)


# programs whose notes have no single pitch a detector can agree on (bells, timpani, the orchestra hit's
# chord, the fifths lead, percussion and effects -- steel drums are tuned, so they are checked): their
# maps are trusted as they are
NO_PITCH_CHECK = {14, 47, 55, 86} | set(range(112, 128)) - {114}


def _pitch_fix(src: str, f0: float) -> float | None:
    """Cents the source note really sits from ``f0`` (the pitch its map claims) when kobi.pitchcheck's
    two detectors agree it is more than 30 cents off, else None."""
    from .pitchcheck import deviation, onset
    x, fs = sf.read(src, dtype='float32', always_2d=True)
    return deviation(x[onset(x, fs):], fs, f0)


def _check_refined(t: dict, rep, out: dict) -> None:
    """The replication refines the pitch from ``t['f0']`` on six harmonics, and an inharmonic note (a
    steel pan's upper modes) can pull it off: the jSteelDrum D4 takes sit 17 cents sharp and it read
    them 32 flat, so the bank played them 50 sharp.  When kobi.pitchcheck's two detectors agree the
    note is more than 20 cents from what the replication used, their reading sets key and tune."""
    from dctjoin.sfz import key_and_tune
    from .pitchcheck import deviation, onset
    used = getattr(rep, 'f0_used', None)
    if not used:
        return
    x, fs = sf.read(t['src'], dtype='float32', always_2d=True)
    d = deviation(x[onset(x, fs):], fs, used, gate=20.0)
    if d is None:
        return
    key, cents = key_and_tune(used * 2 ** (d / 1200))
    out.update(keycenter=key, tune=-cents, pitch_fix=out.get('pitch_fix', 0.0) + 1200 * np.log2(used * 2 ** (d / 1200) / t['f0']))


def _alarm(signum, frame):
    raise TimeoutError(f'replication exceeded {TASK_TIMEOUT_S} s')


def _task(t: dict) -> dict:
    """One region (or one mixed hit) -> compressed file + the numbers its region line needs.  A
    replication that runs past TASK_TIMEOUT_S is abandoned and the file transcoded plain."""
    import signal
    from dctjoin.decay import replicate_decaying
    from dctjoin.unaltered import replicate_unaltered
    out = dict(t)
    pack = t.get('pack', False)
    fmt = 'flac' if pack else 'ogg'
    dst = os.path.join(t['out_dir'], t['stem'] + ('.flac' if pack else '.ogg'))
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(TASK_TIMEOUT_S)
    try:
        if t.get('check_pitch') and t['kind'] in ('sustain', 'decay'):
            # a mislabelled note: kobi.compress refines the pitch only within +-51 cents of the map's, so
            # it would keep the wrong key -- and loop on the wrong period.  Start from what it sounds like.
            fix = _pitch_fix(t['src'], t['f0'])
            if fix is not None:
                t = dict(t, f0=t['f0'] * 2 ** (fix / 1200))
                out['pitch_fix'] = fix
        if t['kind'] == 'sustain':
            rep = replicate_unaltered(t['src'], t['out_dir'], t['loop_s'], f0=t['f0'], format=fmt, quality=t['quality'],
                                      preview=False, sfizz=False, note_sfz=False, stem=t['stem'], bits=16,
                                      max_attack_s=t.get('attack', ATTACK))
            out.update(ok=True, sample=os.path.basename(rep.outputs['audio']), keycenter=rep.keycenter, tune=-rep.tune_cents,
                       loop_start=rep.loop_start, loop_end=rep.loop_end, release=rep.release_sfz)
        elif t['kind'] == 'decay':
            # a note too short for the long attack gets progressively shorter ones before the plain fallback
            settings = [t.get('decay', DECAY)] + [d for d in DECAY_LADDER if d['max_attack_s'] < t.get('decay', DECAY)['max_attack_s']]
            rep, err = None, None
            for d in settings:
                try:
                    rep = replicate_decaying(t['src'], t['out_dir'], t['loop_s'], f0=t['f0'], format=fmt, quality=t['quality'],
                                             preview=False, sfizz=False, stem=t['stem'], bits=16, **d)
                    out['decay_used'] = d
                    break
                except ValueError as e:
                    err = e
            if rep is None:
                raise err
            out.update(ok=True, sample=os.path.basename(rep.outputs['audio']), keycenter=rep.keycenter, tune=-rep.tune_cents,
                       loop_start=rep.loop_start, loop_end=rep.loop_end, hold=rep.hold_s, envelope=rep.envelope, release=rep.release_sfz)
        else:
            rep = None
        if rep is not None and t.get('check_pitch'):
            _check_refined(t, rep, out)
        if rep is None and t['kind'] not in ('sustain', 'decay'):
            add = _transcode(t['sources'], t['gains'], dst, t['quality'], lossless=pack, max_s=MAX_ONESHOT_S)
            out.update(ok=True, sample=os.path.basename(dst), add_db=add)
        for j in glob.glob(os.path.join(t['out_dir'], t['stem'] + '*.json')):
            os.remove(j)
    except Exception as e:                                        # fall back to the plain transcode, no loop
        signal.alarm(0)
        try:
            cap = MAX_ONESHOT_S if t['kind'] in ('oneshot', 'kit') else MAX_UNLOOPED_S
            add = _transcode([t['src']] if 'src' in t else t['sources'], [0.0] if 'src' in t else t['gains'], dst,
                             t['quality'], lossless=pack, max_s=cap)
            out.update(ok=False, fallback=True, sample=os.path.basename(dst), add_db=add, error=f'{type(e).__name__}: {str(e)[:70]}')
        except Exception as e2:
            out.update(ok=False, fallback=False, error=f'{type(e2).__name__}: {str(e2)[:70]}')
    signal.alarm(0)
    for k in ('sources', 'gains'):
        out.pop(k, None)
    out['size'] = os.path.getsize(os.path.join(t['out_dir'], out['sample'])) if out.get('sample') and os.path.exists(os.path.join(t['out_dir'], out['sample'])) else 0
    return out


def _extras(r) -> str:
    s = ''
    if r.seq_length > 1:
        s += f' seq_length={r.seq_length} seq_position={r.seq_position}'
    if r.lorand > 0 or r.hirand < 1:
        s += f' lorand={r.lorand:g} hirand={r.hirand:g}'
    if abs(getattr(r, 'pan', 0.0)) >= 0.5:
        s += f' pan={r.pan:g}'
    return s


def _region_line(r, res: dict, kind: str, key_override: int | None = None) -> list:
    """SFZ region line(s) for one compressed region.  ``key_override``: the key a keyless one-shot got."""
    from dctjoin.decay import region_lines_decay
    vol = r.volume_db + res.get('add_db', 0.0)
    pk = f" offset={res['offset']} end={res['end']}" if 'offset' in res else ''
    if key_override is not None:
        line = f"<region> sample={res['sample']} key={key_override} pitch_keytrack=0 loop_mode=one_shot lovel={r.lovel} hivel={r.hivel}"
        if abs(vol) > 0.01:
            line += f' volume={vol:.1f}'
        return [line + pk + _extras(r)]
    if res.get('fallback') or kind in ('oneshot', 'kit') or 'loop_end' not in res:
        key = f'lokey={r.lokey} hikey={r.hikey} pitch_keycenter={r.pitch_keycenter}' if r.pitch_keycenter is not None and kind not in ('kit',) \
            else f'key={r.lokey} pitch_keytrack=0'
        line = f"<region> sample={res['sample']} {key} lovel={r.lovel} hivel={r.hivel} loop_mode=one_shot" if kind in ('oneshot', 'kit') \
            else f"<region> sample={res['sample']} {key} lovel={r.lovel} hivel={r.hivel} ampeg_release=0.35"
        tune = r.tune - res.get('pitch_fix', 0.0)          # a plain transcode keeps the source's map: correct it there
        if abs(tune) > 0.01:
            line += f' tune={tune:g}'
        if abs(vol) > 0.01:
            line += f' volume={vol:.1f}'
        return [line + pk + _extras(r)]
    if kind == 'decay':
        lines = region_lines_decay(res['sample'], res['keycenter'], res['tune'], res['loop_start'], res['loop_end'], res['hold'],
                                   res['envelope'], res['release'], r.lokey, r.hikey, r.lovel, r.hivel)
        if abs(vol) > 0.01:
            lines = [re.sub(r'volume=(-?[\d.]+)', lambda m: f'volume={float(m.group(1)) + vol:.2f}', l) for l in lines]
        return [l + ' loop_mode=loop_continuous' + pk + _extras(r) for l in lines]
    line = (f"<region> sample={res['sample']} pitch_keycenter={res['keycenter']} lokey={r.lokey} hikey={r.hikey} "
            f"lovel={r.lovel} hivel={r.hivel} tune={int(round(res['tune']))} loop_mode=loop_continuous "
            f"loop_start={res['loop_start']} loop_end={res['loop_end']} ampeg_release={res['release']:.3f}")
    if abs(vol) > 0.01:
        line += f' volume={vol:.1f}'
    return [line + pk + _extras(r)]


def _pack_results(results: dict, out_dir: str, folder: str, out: str, quality: float, keep_pcm: bool = True) -> dict:
    """Concatenate one program's notes into a single Ogg per (rate, channels) and rewrite each result
    to address the packed file: sample, offset / end, loop points shifted.  The lossless per-note
    intermediates move to the build cache so a slimmer bank can be re-packed without a second lossy
    generation.  Returns the pack index (also written as pack.json beside the audio)."""
    entries = []
    for stem in sorted(results):
        res = results[stem]
        path = os.path.join(out_dir, res['sample']) if res.get('sample') else None
        if not path or not os.path.exists(path):
            continue
        loop = (int(res['loop_start']), int(res['loop_end'])) if res.get('loop_end') is not None and not res.get('fallback') else None
        entries.append(dict(stem=stem, path=path, loop=loop))
    groups = packing.group_by_format(entries)
    index = {}
    for (rate, ch), group in groups.items():
        name = 'pack.ogg' if len(groups) == 1 else f'pack_{rate}_{ch}.ogg'
        for stem, v in packing.pack_notes(group, os.path.join(out_dir, name), quality).items():
            v['file'] = name
            index[stem] = v
    cache = os.path.join(out, PCM_CACHE, folder)
    if keep_pcm and index:
        os.makedirs(cache, exist_ok=True)
    for stem, v in index.items():
        res = results[stem]
        src = os.path.join(out_dir, res['sample'])
        res['pcm'] = res['sample']
        res['sample'] = v['file']
        res['offset'], res['end'] = v['start'], v['start'] + v['length'] - 1
        if v['loop']:
            res['loop_start'], res['loop_end'] = v['loop']
        if keep_pcm:
            shutil.move(src, os.path.join(cache, res['pcm']))
        elif os.path.exists(src):
            os.remove(src)
    if index:
        with open(os.path.join(out_dir, 'pack.json'), 'w') as fh:
            json.dump({stem: dict(v, pcm=results[stem]['pcm']) for stem, v in index.items()}, fh, indent=1)
    return index


def _bank_gain(num) -> float:
    path = os.path.join(BANK, 'Drums.sfz' if num == 'drums' else f'{num:03d} {GM_PROGRAMS[num][0]}.sfz')
    if os.path.exists(path):
        m = _GAIN.search(open(path).read(4000))
        if m:
            return float(m.group(1))
    return 0.0


def compress_program(num: int, out: str, quality: float, loop_s: float, jobs: int, pack: bool = PACK, keep_pcm: bool = True) -> dict | None:
    from .gm_map import LAYERS
    from .ingest import load_program_view
    p = PROGRAMS[num]
    got = load_program_view(num, p.name)
    if got is not None:
        kind, view = got
        c = p.cands[0]
        source_desc = ' + '.join(f'{cc.source}:{(cc.sub or cc.path).rstrip("/").split("/")[-1]}' for cc, *_ in LAYERS[num]) if num in LAYERS else f'{c.source}: {c.path} {c.sub or ""}'
        folder = f'{num:03d}_' + re.sub(r'[^A-Za-z0-9]+', '_', GM_PROGRAMS[num][0]).strip('_')
        out_dir = os.path.join(out, folder)
        shutil.rmtree(out_dir, ignore_errors=True)
        os.makedirs(out_dir, exist_ok=True)
        tasks, per_region = [], []
        cache = {}
        for i, r in enumerate(view):
            if kind in ('oneshot', 'kit') or r.pitch_keycenter is None:
                key = (r.sample, round(r.volume_db, 2))
                if key not in cache:
                    cache[key] = f'{i:04d}'
                    tasks.append(dict(kind='oneshot', sources=[r.sample], gains=[0.0], out_dir=out_dir, stem=cache[key], quality=quality, pack=pack))
                per_region.append((r, cache[key]))
            else:
                stem = f'{i:04d}_{r.pitch_keycenter}'
                # the pitch the sample itself sounds at: a region with tune=+t plays it t cents up, so it
                # sits t cents below its key (this was _hz(key, +t), which put the hint 2t cents off and,
                # past ~25 cents of tune, outside the refinement's reach)
                tasks.append(dict(kind=kind, src=r.sample, out_dir=out_dir, stem=stem, f0=_hz(r.pitch_keycenter, -r.tune),
                                  loop_s=loop_s, quality=quality, decay=DECAY, pack=pack, attack=ATTACK,
                                  check_pitch=num not in NO_PITCH_CHECK))
                per_region.append((r, stem))
        t0 = time.time()
        with Pool(jobs) as pool:
            results = {res['stem']: res for res in pool.imap_unordered(_task, tasks, chunksize=1)}
        if pack:
            _pack_results(results, out_dir, folder, out, quality, keep_pcm)
        lines = [f'// kobi compressed bank: {p.name} <- {source_desc} ({kind}, loop {loop_s}s, ogg q{quality:g}{", packed" if pack else ""})',
                 f'<control> default_path=../{folder}/' + (' set_hdcc72=0.35' if kind == 'decay' else ''),
                 f'<global> volume={_bank_gain(num):.1f}']
        from .ingest import _groupby, _MICS
        keyless = [r for r, _ in per_region if r.pitch_keycenter is None]
        keymap = {g: 60 + i for i, g in enumerate(_groupby(keyless, lambda r: tuple(t for t in r.tags if t not in _MICS)))}
        n_ok = n_fb = n_fail = 0
        fixes = sorted({(r.pitch_keycenter, round(results[stem]['pitch_fix']), os.path.basename(r.sample)) for r, stem in per_region
                        if results[stem].get('pitch_fix') is not None})
        layer = None
        for r, stem in per_region:
            res = results[stem]
            if not res.get('sample'):
                n_fail += 1
                continue
            n_ok += res.get('ok', False)
            n_fb += bool(res.get('fallback'))
            tag = next((t for t in r.tags if t.startswith('layer:')), None)
            if tag and tag != layer:                  # a stack: kobi.balance levels each layer on its own
                lines.append(f'// {tag}')
                layer = tag
            ko = keymap[tuple(t for t in r.tags if t not in _MICS)] if r.pitch_keycenter is None else None
            lines += _region_line(r, res, kind, ko)
        os.makedirs(os.path.join(out, 'GM'), exist_ok=True)
        sfz_path = os.path.join(out, 'GM', f'{num:03d} {GM_PROGRAMS[num][0]}.sfz')
        with open(sfz_path, 'w') as fh:
            fh.write('\n'.join(lines) + '\n')
        from .levels import bake
        bake(sfz_path)                    # region volumes replace the global one in SFZ: fold the bank gain in
        src_bytes = sum(os.path.getsize(f) for f in {r.sample for r in view} if os.path.exists(f))
        ogg_bytes = sum(os.path.getsize(os.path.join(out_dir, f)) for f in os.listdir(out_dir) if f.endswith('.ogg'))
        errs = [res['error'] for res in results.values() if res.get('error')][:3]
        return dict(num=num, name=p.name, kind=kind, source=source_desc, regions=len(view), files=len(tasks), ok=n_ok,
                    fallback=n_fb, failed=n_fail, src_mb=src_bytes / 1e6, ogg_mb=ogg_bytes / 1e6, seconds=time.time() - t0, errors=errs,
                    pitch_fixes=fixes)
    return None


def compress_drums(out: str, quality: float, jobs: int, pack: bool = PACK, keep_pcm: bool = True) -> dict:
    """The composite kit (demo/GM/Drums.sfz): regions sharing key, velocity window and round robin
    slot are the mic layers of one hit and get mixed into one file."""
    inst = load_sfz(os.path.join(BANK, 'Drums.sfz'))
    view = [r for r in inst.regions if r.trigger == 'attack' and r.volume_db > -60]     # no silent-by-default layers
    out_dir = os.path.join(out, 'Drums')
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir, exist_ok=True)
    groups = {}
    for r in view:
        groups.setdefault((r.lokey, r.lovel, r.hivel, r.seq_position, r.seq_length, round(r.lorand, 3), round(r.hirand, 3), round(r.tune, 1)), []).append(r)
    tasks, lines = [], ['// kobi compressed bank: GM drum kit (kobi.drums), mic layers mixed per hit', '<control> default_path=../Drums/',
                        f'<global> volume={_bank_gain("drums"):.1f} ampeg_release=0.1']
    for i, (k, rs) in enumerate(sorted(groups.items())):
        stem = f'{k[0]:03d}_{k[1]:03d}_{k[3]}_{i:04d}'
        tasks.append(dict(kind='oneshot', sources=[r.sample for r in rs], gains=[r.volume_db for r in rs], out_dir=out_dir, stem=stem, quality=quality, pack=pack))
    t0 = time.time()
    with Pool(jobs) as pool:
        results = {res['stem']: res for res in pool.imap_unordered(_task, tasks, chunksize=4)}
    if pack:
        _pack_results(results, out_dir, 'Drums', out, quality, keep_pcm)
    n_ok = 0
    for i, (k, rs) in enumerate(sorted(groups.items())):
        stem = f'{k[0]:03d}_{k[1]:03d}_{k[3]}_{i:04d}'
        res = results[stem]
        if not res.get('sample'):
            continue
        n_ok += 1
        r = rs[0]
        line = f"<region> sample={res['sample']} key={k[0]} pitch_keytrack=0 loop_mode=one_shot lovel={k[1]} hivel={k[2]}"
        if 'offset' in res:
            line += f" offset={res['offset']} end={res['end']}"
        if abs(k[7]) > 0.01:
            line += f' tune={k[7]:g}'
        if abs(res.get('add_db', 0.0)) > 0.01:
            line += f" volume={res['add_db']:.1f}"          # the layers' common gain, kept out of the file
        lines.append(line + _extras(r))
    with open(os.path.join(out, 'GM', 'Drums.sfz'), 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    from .levels import bake
    bake(os.path.join(out, 'GM', 'Drums.sfz'))
    src_bytes = sum(os.path.getsize(f) for f in {r.sample for r in view} if os.path.exists(f))
    ogg_bytes = sum(os.path.getsize(os.path.join(out_dir, f)) for f in os.listdir(out_dir) if f.endswith('.ogg'))
    return dict(num='drums', name='Drum kit', kind='kit', source='kobi.drums', regions=len(view), files=len(tasks), ok=n_ok, fallback=0,
                failed=len(tasks) - n_ok, src_mb=src_bytes / 1e6, ogg_mb=ogg_bytes / 1e6, seconds=time.time() - t0, errors=[])


def _row(r: dict) -> str:
    return (f"{str(r['num']):>5} {r['name']:24s} {r['kind']:8s} {r['regions']:5d} rgn {r['files']:5d} files  ok {r['ok']:5d} fb {r['fallback']:3d} "
            f"fail {r['failed']:3d}  {r['src_mb']:7.1f} MB -> {r['ogg_mb']:6.1f} MB ({r['src_mb'] / max(r['ogg_mb'], 1e-9):5.1f}x)  {r['seconds']:5.0f}s"
            + (f"  pitch fixed on {len(r['pitch_fixes'])}" if r.get('pitch_fixes') else '')
            + (f"  e.g. {r['errors'][0]}" if r['errors'] else ''))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('programs', nargs='*', type=int)
    ap.add_argument('--out', default=OUT)
    ap.add_argument('-q', '--quality', type=float, default=1.0)
    ap.add_argument('--loop', type=float, default=0.5)
    ap.add_argument('-j', '--jobs', type=int, default=8)
    ap.add_argument('--drums', action='store_true')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--resume', action='store_true', help='skip programs whose SFZ already exists in <out>/GM')
    ap.add_argument('--decay-attack', type=float, default=DECAY['max_attack_s'], help='seconds of recorded attack kept on decaying notes (0.05 = join right after the transient)')
    ap.add_argument('--decay-bridge', type=float, default=DECAY['bridge_s'])
    ap.add_argument('--attack', type=float, default=ATTACK, help='seconds of recorded attack kept on sustained notes')
    ap.add_argument('--kinds', default='', help='only programs of these kinds, e.g. decay')
    ap.add_argument('--no-pack', action='store_true', help='one Ogg per note instead of one per program')
    ap.add_argument('--no-pcm-cache', action='store_true', help='do not keep the lossless intermediates kobi.slim re-packs from')
    a = ap.parse_args(argv)
    a.out = paths.bank(a.out)
    DECAY.update(max_attack_s=a.decay_attack, bridge_s=a.decay_bridge)
    globals()['ATTACK'] = a.attack
    os.makedirs(os.path.join(a.out, 'GM'), exist_ok=True)
    rows = []
    nums = list(range(128)) if a.all else a.programs
    kinds = set(a.kinds.split(',')) - {''}
    for n in nums:
        if a.resume and os.path.exists(os.path.join(a.out, 'GM', f'{n:03d} {GM_PROGRAMS[n][0]}.sfz')):
            continue
        if kinds and PROGRAMS[n].cands[0].kind not in kinds:
            continue
        r = compress_program(n, a.out, a.quality, a.loop, a.jobs, pack=not a.no_pack, keep_pcm=not a.no_pcm_cache)
        if r:
            rows.append(r)
            print(_row(r), flush=True)
    if (a.drums or a.all) and not (a.resume and os.path.exists(os.path.join(a.out, 'GM', 'Drums.sfz'))):
        r = compress_drums(a.out, a.quality, a.jobs, pack=not a.no_pack, keep_pcm=not a.no_pcm_cache)
        rows.append(r)
        print(_row(r), flush=True)
    if rows:
        with open(os.path.join(a.out, 'sizes.jsonl'), 'a') as fh:
            for r in rows:
                fh.write(json.dumps(dict(r, loop=a.loop, quality=a.quality, attack=a.attack, decay=dict(DECAY))) + '\n')
        from . import dedupe, extend, kit, release
        release.cap_bank(a.out)              # sustained notes release like an instrument, not like a hall
        if os.path.exists(os.path.join(a.out, 'GM', 'Drums.sfz')):
            kit.tidy_kit(os.path.join(a.out, 'GM', 'Drums.sfz'))   # one take per hit; Latin percussion decays
            if a.drums or a.all:                                   # each piece at the level kobi.drums chose for it
                fixed = kit.level_kit(os.path.join(a.out, 'GM', 'Drums.sfz'), kit.targets_from(os.path.join(BANK, 'Drums.sfz')))
                if fixed:
                    print('kit pieces re-levelled (dB):', ' '.join(f'{k}:{d:+g}' for k, d in sorted(fixed.items())), flush=True)
        dedupe.dedupe_bank(a.out)            # one note per key and velocity before the map is extended
        extend.extend_bank(a.out)
        write_sizes_md(a.out)
    return 0


def write_sizes_md(out: str) -> None:
    """SIZES.md from every record in <out>/sizes.jsonl, the latest record per program winning."""
    recs = {}
    with open(os.path.join(out, 'sizes.jsonl')) as fh:
        for line in fh:
            r = json.loads(line); recs[str(r['num'])] = r
    rows = sorted(recs.values(), key=lambda r: (r['num'] == 'drums', int(r['num']) if str(r['num']).isdigit() else 999))
    if rows:
        src, ogg = sum(r['src_mb'] for r in rows), sum(r['ogg_mb'] for r in rows)
        print(f'total: {src:.0f} MB source -> {ogg:.1f} MB ogg ({src / max(ogg, 1e-9):.1f}x), {sum(r["files"] for r in rows)} files, '
              f'{sum(r["seconds"] for r in rows) / 60:.1f} min')
        loops = sorted({r.get('loop', 0.5) for r in rows}); dec = rows[0].get('decay', {})
        md = ['# Compressed bank sizes', '', f'Loop {", ".join(f"{l:g}" for l in loops)} s, Ogg Vorbis q{rows[0].get("quality", 1):g}; decaying notes: '
              f'{dec.get("max_attack_s", "?")} s attack budget with a {dec.get("bridge_s", "?")} s harmonic cross-fade.  fb = regions that fell back to a plain transcode.', '',
              '| # | program | kind | source | regions | files | fb | source MB | ogg MB | ratio |', '|---|---|---|---|---|---|---|---|---|---|']
        md += [f"| {r['num']} | {r['name']} | {r['kind']} | {r['source']} | {r['regions']} | {r['files']} | {r['fallback']} | "
               f"{r['src_mb']:.1f} | {r['ogg_mb']:.2f} | {r['src_mb'] / max(r['ogg_mb'], 1e-9):.1f}x |" for r in rows]
        md += ['', f'**Total: {src:.0f} MB -> {ogg:.1f} MB ({src / max(ogg, 1e-9):.0f}x), {sum(r["files"] for r in rows)} files.**']
        fixed = [r for r in rows if r.get('pitch_fixes')]
        if fixed:
            md += ['', '## Notes retuned from their maps', '', 'Source notes that kobi.pitchcheck\'s two detectors agree sit more than 30 cents '
                   'from the pitch their map gives (keycenter, cents, file); compressed from the pitch they really have.', '']
            md += [f"- {r['num']} {r['name']}: " + ', '.join(f'{k} {c:+d}c {f}' for k, c, f in r['pitch_fixes']) for r in fixed]
        with open(os.path.join(out, 'SIZES.md'), 'w') as fh:
            fh.write('\n'.join(md) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
