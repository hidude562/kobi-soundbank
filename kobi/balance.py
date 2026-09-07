"""kobi.balance — make every note of a program the same loudness, so dynamics come from velocity.

Measured across the slim bank before this step, the velocity layers of a program differed by a
median of 10.6 dB (up to 30), in 11 programs a *softer* layer was louder than the one above it, and
notes within one layer varied by 3–10 dB from key to key — the recordings' own levels plus mixed
sources, never reconciled.  A player then applies its velocity curve on top, so the range was both
exaggerated and inconsistent between instruments.

This step measures each note's intrinsic loudness (loudest 400 ms of its first second, K-weighted,
with the region's ``volume`` — or the ``<global>`` volume it inherits — applied) and writes a per-region ``volume`` offset that brings every
note of the program to the program's median.  Velocity then changes the sample (timbre) and the
level through the curve only, the same way for every instrument.  Corrections are clamped to
``clamp`` dB; drums and keyless programs are left to their own tools.  Runs on a bank's original
regions and re-applies kobi.extend afterwards; the program-level target is kobi.levels' job.

    python3 -m kobi.balance kobi_ogg kobi_ogg_lite kobi_ogg_lite25
"""
from __future__ import annotations

import argparse
import glob
import os
import re

import numpy as np
import soundfile as sf

from .extend import extend_sfz, strip_fills
from .levels import momentary_max_lufs
from . import paths

_OP = re.compile(r'(?<!\S)([\w]+)=(\S+)')
MEASURE_S = 1.0


def plan(levels: dict, clamp: float = 12.0) -> dict:
    """Per-note gain deltas (dB) that bring every measured level to the median, clamped."""
    vals = [v for v in levels.values() if np.isfinite(v)]
    if not vals:
        return {k: 0.0 for k in levels}
    ref = float(np.median(vals))
    return {k: float(np.clip(ref - v, -clamp, clamp)) if np.isfinite(v) else 0.0 for k, v in levels.items()}


def balance_sfz(path: str, clamp: float = 12.0) -> dict | None:
    text = open(path).read()
    lines = strip_fills(text.split('\n'))
    m = re.search(r'default_path=(\S+)', text)
    if not m:
        return None
    folder = os.path.normpath(os.path.join(os.path.dirname(path), m.group(1)))
    regions = [(i, dict(_OP.findall(l))) for i, l in enumerate(lines) if l.startswith('<region>')]
    # a region without its own volume plays at the <global> volume, and in SFZ a region volume
    # *replaces* the global one — so that is both its baseline and what a written volume must include
    gm = next((re.search(r'volume=(-?[\d.]+)', l) for l in lines if l.startswith('<global>')), None)
    gvol = float(gm.group(1)) if gm else 0.0
    # a program may mix pitched and keyless regions (a plucked instrument with an unpitched artefact);
    # every note is levelled the same way, so only a wholly keyless program (an effect) is skipped
    if not regions or all(o.get('pitch_keytrack', '100') == '0' for _, o in regions):
        return None
    audio: dict = {}
    raw: dict = {}                       # note -> sample loudness
    stack: dict = {}                     # note -> volumes of the regions that sound together
    layer_of: dict = {}
    for _, o in regions:
        if 'offset' not in o or 'end' not in o:
            continue
        key = (o['sample'], o['offset'])
        stack.setdefault(key, []).append(float(o.get('volume', gvol)))
        if key in raw:
            continue
        if o['sample'] not in audio:
            audio[o['sample']] = sf.read(os.path.join(folder, o['sample']), dtype='float32', always_2d=True)
        x, fs = audio[o['sample']]
        a, b = int(o['offset']), int(o['end'])
        seg = x[a: min(b + 1, a + int(MEASURE_S * fs))]
        if len(seg) < int(0.4 * fs):               # shorter than the meter window: its energy within one window
            seg = np.concatenate([seg, np.zeros((int(0.4 * fs) - len(seg), seg.shape[1]), dtype=seg.dtype)])
        raw[key] = momentary_max_lufs(seg, fs)
        layer_of[key] = (int(o.get('lovel', 1)), int(o.get('hivel', 127)))
    # a decaying note is a stack of regions (one sample, several envelopes) that sound together and
    # all start at full level, so its opening loudness is the sample at their summed amplitude
    levels = {k: raw[k] + 20 * np.log10(sum(10 ** (v / 20) for v in stack[k])) for k in raw}
    if len(levels) < 2:
        return None
    deltas = plan(levels, clamp)
    written = []
    for i, o in regions:
        key = (o.get('sample'), o.get('offset'))
        d = deltas.get(key, 0.0)
        vol = float(o.get('volume', gvol)) + d
        written.append(vol)
        if 'volume' in o:
            lines[i] = re.sub(r'(?<!\S)volume=-?[\d.]+', f"volume={vol:.1f}", lines[i])
        else:                                            # explicit from now on: nothing plays at a stale global
            lines[i] += f' volume={vol:.1f}'
    # the global is now only bookkeeping (kobi.levels reads it as the prior gain): keep it truthful
    med = float(np.median(written)) if written else gvol
    for i, l in enumerate(lines):
        if l.startswith('<global>'):
            lines[i] = re.sub(r'\s*volume=-?[\d.]+', '', l) + f' volume={med:.1f}'
            break
    else:
        lines.insert(next(i for i, l in enumerate(lines) if l.startswith('<')), f'<global> volume={med:.1f}')
    with open(path, 'w') as fh:
        fh.write('\n'.join(lines))
    extend_sfz(path)
    keys = [k for k, v in levels.items() if np.isfinite(v)]             # silent notes measure -inf
    before = np.array([levels[k] for k in keys])
    after = before + np.array([deltas[k] for k in keys])
    layers: dict = {}
    for k in keys:
        layers.setdefault(layer_of[k], []).append(levels[k])
    layer_spread = (max(np.median(v) for v in layers.values()) - min(np.median(v) for v in layers.values())) if len(layers) > 1 else 0.0
    return dict(notes=len(levels), layers=len(layers), std_before=float(before.std()), std_after=float(after.std()),
                layer_spread_before=float(layer_spread), max_delta=float(np.abs(list(deltas.values())).max()),
                clamped=int(sum(1 for d in deltas.values() if abs(d) >= clamp - 1e-9)))


def balance_bank(bank: str, clamp: float = 12.0) -> list:
    rows = []
    for sfz in sorted(glob.glob(os.path.join(bank, 'GM', '*.sfz'))):
        if os.path.basename(sfz) == 'Drums.sfz':
            continue
        r = balance_sfz(sfz, clamp)
        if r:
            r['name'] = os.path.basename(sfz)[:-4]
            rows.append(r)
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('banks', nargs='+')
    ap.add_argument('--clamp', type=float, default=12.0, help='largest per-note correction, dB')
    a = ap.parse_args(argv)
    for bank in a.banks:
        bank = paths.bank(bank)
        rows = balance_bank(bank, a.clamp)
        multi = [r for r in rows if r['layers'] > 1]
        print(f'{os.path.basename(bank):18s} {len(rows)} programs balanced: note-to-note std {np.mean([r["std_before"] for r in rows]):.1f} -> '
              f'{np.mean([r["std_after"] for r in rows]):.1f} dB; layer spread was {np.median([r["layer_spread_before"] for r in multi]):.1f} dB median '
              f'over {len(multi)} multi-layer programs; {sum(r["clamped"] for r in rows)} notes hit the {a.clamp:g} dB clamp', flush=True)
        with open(os.path.join(bank, 'BALANCE.md'), 'w') as fh:
            fh.write('# Per-note balance\n\nEvery note brought to its program\'s median intrinsic loudness (loudest 400 ms of the first '
                     f'second, K-weighted); corrections clamped to {a.clamp:g} dB.\n\n| program | notes | layers | note std before | after | layer spread before | largest correction |\n|---|---|---|---|---|---|---|\n')
            for r in rows:
                fh.write(f"| {r['name']} | {r['notes']} | {r['layers']} | {r['std_before']:.1f} | {r['std_after']:.1f} | {r['layer_spread_before']:.1f} | {r['max_delta']:.1f} |\n")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
