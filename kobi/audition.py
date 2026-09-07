"""kobi.audition — hear every articulation folder of a source instrument.

    python3 -m kobi.audition VSCO2 'Brass/*' 'Strings/*' [-o demo_audition/vsco2_brass_strings]

For each matching instrument folder and each of its articulation sub-folders (or the folder
itself when it has none), the folder is ingested, its octave convention checked by pitch
detection, a short phrase rendered (arpeggio and chord; short notes for staccato / pizzicato /
spiccato), peak-normalised, and everything joined into one file with a cue sheet.
"""
from __future__ import annotations

import argparse
import glob
import os

import numpy as np
import soundfile as sf

from .demo import FS, GAP_S, normalise, phrase, render, write_view_sfz
from .gm_map import Cand, ROOT
from .ingest import default_view, load_candidate
from .pitch_audit import audit_candidate
from . import paths

SHORT = ('stac', 'stacc', 'staccato', 'pizz', 'pizzt', 'spic', 'short', 'fall', 'buzz')


def articulations(source: str, pattern: str) -> list:
    out = []
    for folder in sorted(glob.glob(os.path.join(ROOT, source, pattern))):
        if not os.path.isdir(folder):
            continue
        subs = sorted(d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d)))
        rel = os.path.relpath(folder, os.path.join(ROOT, source))
        out += [(rel, s) for s in subs] or [(rel, None)]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('source')
    ap.add_argument('patterns', nargs='+')
    ap.add_argument('-o', '--out', default=None)
    a = ap.parse_args(argv)
    out_dir = a.out or os.path.join(paths.ROOT, 'demo_audition', a.source.lower())
    os.makedirs(out_dir, exist_ok=True)
    parts, cues, t = [], [], 0.0
    gap = np.zeros((int(GAP_S * FS), 2), dtype=np.float32)
    for pat in a.patterns:
        for rel, sub in articulations(a.source, pat):
            cand = Cand(a.source, rel, sub, 'sustain')
            res = audit_candidate(cand, rel, n=3)
            if res and res.get('octave_mode') and res['agree'] >= 0.6:
                cand.octave = res['octave_mode']
            inst = load_candidate(cand, rel)
            view = default_view(inst) if inst else []
            if not view:
                print(f'{rel} / {sub}: nothing playable'); continue
            label = f"{rel}/{sub or ''}".rstrip('/')
            stem = label.replace('/', '__').replace(' ', '_')
            kind = 'decay' if sub and sub.lower().replace('-', '') in SHORT else 'sustain'
            info = write_view_sfz(inst, view, os.path.join(out_dir, 'sfz', stem + '.sfz'), kind)
            ev, secs = phrase(kind, info)
            if kind == 'decay':                                          # short notes: no long chord hold
                ev = [(tt, ty, k, v) if ty == 'on' else (min(tt, next(t2 for t2, ty2, k2, _ in ev if ty2 == 'on' and k2 == k) + 0.25), ty, k, v) for tt, ty, k, v in ev]
            audio, pk = normalise(render(os.path.join(out_dir, 'sfz', stem + '.sfz'), ev, secs))
            sf.write(os.path.join(out_dir, stem + '.wav'), audio, FS, subtype='PCM_16')
            cues.append((t, label, len(view), cand.octave, pk, info['lo'], info['hi']))
            print(f"{int(t // 60)}:{t % 60:04.1f}  {label:44s} {len(view):4d} regions  octave {cand.octave:+d}  raw peak {pk:6.1f} dB", flush=True)
            parts += [audio, gap]
            t += len(audio) / FS + GAP_S
    if not parts:
        return 1
    full = np.concatenate(parts)
    sf.write(os.path.join(out_dir, 'audition.wav'), full, FS, subtype='PCM_16')
    with open(os.path.join(out_dir, 'CUES.md'), 'w') as fh:
        fh.write('| time | articulation | regions | octave | raw peak dB | range |\n|---|---|---|---|---|---|\n')
        for t0, label, n, o, pk, lo, hi in cues:
            fh.write(f'| {int(t0 // 60)}:{t0 % 60:04.1f} | {label} | {n} | {o:+d} | {pk:.1f} | {lo}..{hi} |\n')
    print(f'wrote {os.path.join(out_dir, "audition.wav")} ({len(full) / FS / 60:.1f} min)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
