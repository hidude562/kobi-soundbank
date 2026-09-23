"""kobi.levels — match the loudness of every program.

Sources differ by 30 dB in recorded level.  For each program's SFZ, single notes at velocity 100
are rendered at the low, middle and high end of the range (or the first hits of a one-shot set),
their loudness measured as the maximum momentary loudness (K-weighted, 400 ms windows, after
ITU-R BS.1770), and a ``<global> volume=`` gain written into the SFZ so the mean lands on the
target.  Percussive and sustained sounds are matched on their loudest 400 ms, which is what the
ear compares when a hit sits against a pad.

    python3 -m kobi.levels [-t -20] [--bank demo/GM] [--no-write]     -> LEVELS.md next to the SFZs
"""
from __future__ import annotations

import argparse
import glob
import os
import re

import numpy as np
from scipy.signal import lfilter

from .demo import FS, render
from .ingest import parse_sfz, _key
from . import paths


def _biquad_shelf(fs, f0=1681.974450955533, gain_db=3.999843853973347, q=0.7071752369554196):
    A = 10 ** (gain_db / 40); w0 = 2 * np.pi * f0 / fs; al = np.sin(w0) / (2 * q); c = np.cos(w0); sA = np.sqrt(A)
    b = [A * ((A + 1) + (A - 1) * c + 2 * sA * al), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - 2 * sA * al)]
    a = [(A + 1) - (A - 1) * c + 2 * sA * al, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - 2 * sA * al]
    return np.array(b) / a[0], np.array(a) / a[0]


def _biquad_highpass(fs, f0=38.13547087602444, q=0.5003270373238773):
    w0 = 2 * np.pi * f0 / fs; al = np.sin(w0) / (2 * q); c = np.cos(w0)
    b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]
    a = [1 + al, -2 * c, 1 - al]
    return np.array(b) / a[0], np.array(a) / a[0]


def k_weight(x: np.ndarray, fs: int) -> np.ndarray:
    """ITU-R BS.1770 K-weighting (pre-filter shelf + RLB high-pass), any sample rate."""
    b1, a1 = _biquad_shelf(fs); b2, a2 = _biquad_highpass(fs)
    return lfilter(b2, a2, lfilter(b1, a1, x, axis=0), axis=0)


def momentary_max_lufs(x: np.ndarray, fs: int, win: float = 0.4, hop: float = 0.1) -> float:
    """Loudest 400 ms window (LUFS-style, channel weights 1)."""
    y = k_weight(x, fs)
    w, h = int(win * fs), int(hop * fs)
    if len(y) < w:
        return -np.inf
    p = np.mean(y ** 2, axis=1)                       # mean over channels of the square
    cs = np.concatenate([[0.0], np.cumsum(p)])
    ms = (cs[w::h] - cs[:-w:h]) / w
    ms = ms[ms > 0]
    return float(-0.691 + 10 * np.log10(ms.max())) if len(ms) else -np.inf


def _keys_of(sfz: str) -> tuple[list, bool]:
    """(key centres to test, keyless?) read back from a generated SFZ."""
    raw, _ = parse_sfz(sfz)
    keyless = any(r.get('pitch_keytrack') == '0' for r in raw)
    centres = sorted({_key(r.get('pitch_keycenter'), 60) for r in raw if r.get('sample')})
    return centres, keyless


def measure(sfz: str, note_s: float = 1.2, tail_s: float = 0.8) -> dict:
    centres, keyless = _keys_of(sfz)
    if not centres:
        return dict(lufs=-np.inf, notes=[])
    if os.path.splitext(os.path.basename(sfz))[0] == 'Drums':
        picks = [k for k in (36, 38, 42) if k in centres] or centres[:3]      # kick, snare, closed hat
    elif keyless:
        picks = centres[:3]
    else:                                   # up to nine centres across the range: three could all land in
        n = min(9, len(centres))            # one louder zone (Pad 6 came out 1.8 dB under the bank)
        picks = sorted({centres[round(i * (len(centres) - 1) / max(1, n - 1))] for i in range(n)})
    vals = []
    for k in picks:
        y = render(sfz, [(0.0, 'on', k, 100), (note_s, 'off', k, 0)], note_s + tail_s)
        vals.append(momentary_max_lufs(y, FS))
    good = [v for v in vals if np.isfinite(v)]
    avg = np.median if len(good) > 3 else np.mean
    return dict(lufs=float(avg(good)) if good else -np.inf, notes=list(zip(picks, vals)))


_GLOBAL = re.compile(r'^<global>(.*)$', re.M)


BAKED = '// gains baked into region volumes'
_REGION_VOL = re.compile(r'^(<region>.*?\svolume=)(-?[\d.]+)', re.M)


def apply_gain(sfz: str, gain_db: float) -> None:
    """Set the bank gain: ``volume=`` on the <global> line for regions without their own volume,
    and folded into the ``volume=`` of every region that has one (in SFZ a region's volume replaces
    the global value instead of adding to it).  Re-applying adjusts by the difference."""
    with open(sfz) as fh:
        s = fh.read()
    m = _GLOBAL.search(s)
    old = 0.0
    if m:
        mv = re.search(r'volume=(-?[\d.]+)', m.group(1))
        old = float(mv.group(1)) if mv else 0.0
        rest = re.sub(r'\s*volume=\S+', '', m.group(1))
        s = s[:m.start()] + f'<global>{rest} volume={gain_db:.1f}' + s[m.end():]
    else:
        s = f'<global> volume={gain_db:.1f}\n' + s
    if BAKED not in s:                       # regions with their own volume never saw the old global gain
        old = 0.0
        s = BAKED + '\n' + s
    delta = gain_db - old
    if abs(delta) > 1e-6:
        s = _REGION_VOL.sub(lambda mm: f'{mm.group(1)}{float(mm.group(2)) + delta:.2f}', s)
    with open(sfz, 'w') as fh:
        fh.write(s)


def bake(sfz: str) -> bool:
    """One-off for files written before this fix: fold the existing global volume into the regions
    that carry their own.  Returns True if the file was changed."""
    with open(sfz) as fh:
        s = fh.read()
    if BAKED in s:
        return False
    m = _GLOBAL.search(s)
    mv = re.search(r'volume=(-?[\d.]+)', m.group(1)) if m else None
    g = float(mv.group(1)) if mv else 0.0
    if abs(g) > 1e-6:
        s = _REGION_VOL.sub(lambda mm: f'{mm.group(1)}{float(mm.group(2)) + g:.2f}', s)
    with open(sfz, 'w') as fh:
        fh.write(BAKED + '\n' + s)
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--bank', default=os.path.join(paths.ROOT, 'demo', 'GM'))
    ap.add_argument('-t', '--target', type=float, default=-23.0, help='target max momentary LUFS of a velocity-100 note')
    ap.add_argument('--max-gain', type=float, default=40.0, help='clamp for the applied gain, dB')
    ap.add_argument('--no-write', action='store_true')
    a = ap.parse_args(argv)
    a.bank = paths.bank(a.bank)
    rows = []
    for sfz in sorted(glob.glob(os.path.join(a.bank, '*.sfz'))):
        name = os.path.splitext(os.path.basename(sfz))[0]
        with open(sfz) as fh:
            head = fh.read(8000)
        mg = _GLOBAL.search(head)
        mv = re.search(r'volume=(-?[\d.]+)', mg.group(1)) if mg else None
        prior = float(mv.group(1)) if mv else 0.0
        if prior and not a.no_write:
            apply_gain(sfz, 0.0)                      # back to the raw level (baked regions included), then set the new gain
        r = measure(sfz)
        gain = 0.0 if not np.isfinite(r['lufs']) else float(np.clip(a.target - r['lufs'], -a.max_gain, a.max_gain))
        if not a.no_write:
            apply_gain(sfz, gain)
        rows.append((name, r['lufs'], gain, r['notes']))
        print(f"{name:34s} {r['lufs']:7.1f} LUFS  gain {gain:+6.1f} dB   " + ' '.join(f'{k}:{v:.0f}' for k, v in r['notes']), flush=True)
    lines = ['# Levels', '', f'Max momentary loudness (K-weighted, 400 ms) of velocity-100 single notes at three points of each '
             f'program\'s range, before gain; the gain written as `<global> volume=` brings the mean to {a.target:g} LUFS '
             f'(clamped to ±{a.max_gain:g} dB).', '', '| program | raw LUFS | gain dB | notes (key:LUFS) |', '|---|---|---|---|']
    for name, lufs, gain, notes in rows:
        lines.append(f"| {name} | {lufs:.1f} | {gain:+.1f} | {' '.join(f'{k}:{v:.0f}' for k, v in notes)} |")
    vals = [l for _, l, _, _ in rows if np.isfinite(l)]
    lines += ['', f'{len(rows)} programs; raw spread {min(vals):.1f} .. {max(vals):.1f} LUFS ({max(vals) - min(vals):.0f} dB).']
    with open(os.path.join(a.bank, 'LEVELS.md'), 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    print(f'raw spread {min(vals):.1f} .. {max(vals):.1f} LUFS; gains written' if not a.no_write else 'measured only')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
