"""kobi.pitch_audit — does each source's key naming match what the samples sound like?

For every candidate in the GM map, detect the pitch (pYIN) of up to ``n`` keyed samples spread
over the range and compare with the key the SFZ map or the file name claims, after the
candidate's ``octave`` correction.  Folder sources (VCSL, VSCO 2, SSO) have no map, so a
consistent whole-octave offset there means the file names use another octave convention and the
candidate needs ``octave=``; SFZ sources are authoritative, and an octave-below reading on organ
or synth-bass patches is the sub-oscillator fooling the detector.

    python3 -m kobi.pitch_audit [-n 7] [--all-cands] [programs...]      -> PITCH_AUDIT.md
"""
from __future__ import annotations

import argparse
import os
import warnings

import numpy as np
import soundfile as sf

from .gm_map import PROGRAMS
from .ingest import default_view, load_candidate


def detect_midi(path: str, fs_target: int = 22050) -> float | None:
    """Median pYIN pitch (MIDI, fractional) of ~1.2 s after the onset; None when unvoiced."""
    import librosa
    warnings.filterwarnings('ignore')
    x, fs = sf.read(path, dtype='float32', always_2d=True)
    x = x.mean(axis=1)
    if not len(x):
        return None
    env = np.abs(x)
    on = int(np.argmax(env > 0.1 * env.max()))
    seg = x[on + int(0.05 * fs): on + int(1.25 * fs)]
    if len(seg) < fs // 4:
        seg = x[on: on + fs]
    if len(seg) < 4096:
        return None
    seg = librosa.resample(seg, orig_sr=fs, target_sr=fs_target)
    f0, _, vp = librosa.pyin(seg, fmin=25, fmax=4200, sr=fs_target, frame_length=4096, hop_length=512)
    keep = np.isfinite(f0) & (vp > 0.5)
    f0 = f0[keep] if keep.any() else f0[np.isfinite(f0)]
    if not len(f0):
        return None
    return float(69 + 12 * np.log2(np.median(f0) / 440.0))


def audit_candidate(cand, name: str, n: int = 7) -> dict | None:
    if cand.kind in ('oneshot', 'kit'):
        return dict(name=name, cand=cand, n=0, offsets=[], octave_mode=None, agree=0.0, verdict='unpitched')
    inst = load_candidate(cand, name)
    if inst is None:
        return None
    view = sorted((r for r in default_view(inst) if r.pitch_keycenter is not None), key=lambda r: r.pitch_keycenter)
    if not view:
        return dict(name=name, cand=cand, n=0, offsets=[], octave_mode=None, agree=0.0, verdict='unpitched')
    idx = np.unique(np.linspace(0, len(view) - 1, min(n, len(view))).round().astype(int))
    offs = []
    for i in idx:
        r = view[i]
        m = detect_midi(r.sample)
        offs.append(None if m is None else m - r.tune / 100 - r.pitch_keycenter)
    good = [o for o in offs if o is not None]
    if not good:
        return dict(name=name, cand=cand, n=len(offs), offsets=offs, octave_mode=None, agree=0.0, verdict='undetected')
    octs = [int(round(o / 12)) for o in good]
    mode = max(set(octs), key=octs.count)
    agree = sum(1 for o, k in zip(good, octs) if k == mode and abs(o - 12 * k) < 1.5) / len(offs)
    if mode == 0 and agree >= 0.6:
        verdict = 'ok'
    elif agree >= 0.6:
        verdict = f'names {abs(mode)} octave{"s" if abs(mode) > 1 else ""} {"low" if mode > 0 else "high"}: set octave={cand.octave + mode}' \
            if cand.source in ('VCSL', 'VSCO2', 'SSO') else f'detector reads {mode:+d} oct vs map (sub-oscillator?)'
    else:
        verdict = 'inconsistent: listen'
    return dict(name=name, cand=cand, n=len(offs), offsets=offs, octave_mode=mode, agree=agree, verdict=verdict)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('programs', nargs='*', type=int)
    ap.add_argument('-n', type=int, default=7, help='samples per candidate')
    ap.add_argument('--all-cands', action='store_true', help='every candidate, not just the first ingestible one')
    a = ap.parse_args(argv)
    nums = set(a.programs) if a.programs else set(range(128))
    rows = []
    for p in PROGRAMS:
        if p.num not in nums:
            continue
        for c in p.cands:
            res = audit_candidate(c, p.name, a.n)
            if res is None:
                continue
            res['program'] = p.num
            rows.append(res)
            offs = ' '.join(f'{o:+5.1f}' if o is not None else '  n/a' for o in res['offsets'])
            print(f"{p.num:3d} {p.name:24s} {c.source:9s} {c.path[-34:]:34s} {c.sub or '':14s} oct={c.octave:+d} "
                  f"agree {res['agree']:.2f} [{offs}] {res['verdict']}", flush=True)
            if not a.all_cands:
                break
    if not a.programs:
        lines = ['# Pitch audit', '', 'Detected pitch minus claimed key (semitones) for samples spread over each candidate\'s '
                 'range, after the candidate\'s octave correction.  Folder sources with a consistent whole-octave offset '
                 'need `octave=` in gm_map; SFZ sources are authoritative.', '',
                 '| # | program | source | instrument | sub | octave | agree | offsets | verdict |', '|---|---|---|---|---|---|---|---|---|']
        for r in rows:
            c = r['cand']
            lines.append(f"| {r['program']} | {r['name']} | {c.source} | {c.path} | {c.sub or ''} | {c.octave} | {r['agree']:.2f} | "
                         f"{' '.join(f'{o:+.1f}' if o is not None else 'n/a' for o in r['offsets'])} | {r['verdict']} |")
        bad = [r for r in rows if r['verdict'] not in ('ok', 'unpitched')]
        lines += ['', f"{len(rows)} candidates audited, {len(bad)} not clean."]
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'PITCH_AUDIT.md'), 'w') as fh:
            fh.write('\n'.join(lines) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
