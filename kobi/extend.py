"""kobi.extend — give every pitched program the full keyboard.

A sampled instrument stops where its samples stop: a bass recorded from E1 to A2 is silent for a
MIDI note outside that range, where a General MIDI synth would transpose its nearest sample.  This
step fills the holes in each pitched program's key x velocity map: every (key, velocity) that no
region covers gets a copy of the nearest sampled cell — nearest by keycenter, preferring a cell
whose velocity layer matches — with its key range and velocity window set to exactly the hole.
Copying into the holes, rather than stretching existing ranges, means nothing that already sounds
is changed and no key can trigger twice; the result covers keys 0–127 at velocities 1–127 and a
second run changes nothing.  Drums and keyless programs (effects, ``pitch_keytrack=0``) are left
alone — transposing a helicopter is not a feature.

    python3 -m kobi.extend kobi_ogg kobi_slim ...
"""
from __future__ import annotations

import argparse
import glob
import os
import re

import numpy as np
from . import paths

_OP = re.compile(r'(?<!\S)([\w]+)=(\S+)')
MARKER = '// kobi.extend: the nearest sampled key copied into every hole of the key x velocity map'


def strip_fills(lines: list[str]) -> list[str]:
    """The SFZ lines without this step's copied regions (a tool that changes region volumes runs on
    the originals and re-extends afterwards)."""
    out = list(lines)
    while True:
        i = next((k for k, l in enumerate(out) if l.startswith('// kobi.extend')), None)   # any wording of the marker
        if i is None:
            return out
        if not any(l.startswith('<region>') for l in out[:i]):
            del out[i]                                   # a marker that drifted into the header (slim copies comments there)
            continue
        j = i + 1
        while j < len(out) and (out[j].startswith('<region>') or out[j].startswith('// kobi.extend')):
            j += 1
        del out[i:j]


def _cells(lines: list[str]):
    """Regions grouped by (lokey, hikey, lovel, hivel): stacked envelopes and round robins of one
    note share a cell and are copied together.  None for a keyless program."""
    cells: dict = {}
    for i, l in enumerate(lines):
        if not l.startswith('<region>'):
            continue
        o = dict(_OP.findall(l))
        if o.get('pitch_keytrack', '100') == '0':
            continue                                     # a keyless region sounds on its own key only:
                                                         # it is not part of the key map and is left as it is
        key = o.get('key')
        lo, hi = int(o.get('lokey', key if key is not None else 0)), int(o.get('hikey', key if key is not None else 127))
        lv, hv = int(o.get('lovel', 1)), int(o.get('hivel', 127))
        kc = int(o.get('pitch_keycenter', key if key is not None else (lo + hi) // 2))
        c = cells.setdefault((lo, hi, lv, hv), dict(lo=lo, hi=hi, lv=lv, hv=hv, kc=kc, lines=[]))
        c['kc'] = min(c['kc'], kc)
        c['lines'].append(i)
    return list(cells.values())                      # empty for a wholly keyless program (an effect)


def _uncovered(cells: list[dict], k: int) -> list[tuple[int, int]]:
    """Velocity intervals of key k that no cell covers."""
    spans = sorted((c['lv'], c['hv']) for c in cells if c['lo'] <= k <= c['hi'])
    holes, v = [], 1
    for lv, hv in spans:
        if lv > v:
            holes.append((v, lv - 1))
        v = max(v, hv + 1)
    if v <= 127:
        holes.append((v, 127))
    return holes


def _donors(cells: list[dict], k: int, lv: int, hv: int):
    """How to fill velocities [lv, hv] of key k: the nearest sampled key, its velocity layers tiling
    the hole (a velocity none of them has goes to the layer closest to it).  Yields (cell, lv, hv)."""
    kc = min(cells, key=lambda c: (abs(c['kc'] - k), c['kc']))['kc']
    layers = [c for c in cells if c['kc'] == kc]
    seen: set = set()
    layers = [c for c in layers if not (c['lv'], c['hv']) in seen and not seen.add((c['lv'], c['hv']))]
    run, start = None, lv
    for v in range(lv, hv + 2):
        d = None if v > hv else min(layers, key=lambda c: (0 if c['lv'] <= v <= c['hv'] else min(abs(v - c['lv']), abs(v - c['hv'])), c['lv']))
        if d is not run:
            if run is not None:
                yield run, start, v - 1
            run, start = d, v


def _copy(line: str, lo: int, hi: int, lv: int, hv: int) -> str:
    o = dict(_OP.findall(line))
    if 'key' in o and 'lokey' not in o:
        line = re.sub(r'(?<!\S)key=(\d+)', lambda m: f'lokey={lo} hikey={hi}' + ('' if 'pitch_keycenter' in o else f' pitch_keycenter={m.group(1)}'), line)
    else:
        line = re.sub(r'(?<!\S)lokey=\d+', f'lokey={lo}', line)
        line = re.sub(r'(?<!\S)hikey=\d+', f'hikey={hi}', line)
    line = re.sub(r'(?<!\S)lovel=\d+', f'lovel={lv}', line) if 'lovel' in o else line + f' lovel={lv}'
    line = re.sub(r'(?<!\S)hivel=\d+', f'hivel={hv}', line) if 'hivel' in o else line + f' hivel={hv}'
    return line


def extend_sfz(path: str) -> int | None:
    """Fill one program's map in place.  Returns the number of (key, velocity) holes filled, or None
    when the program is not pitched.  Fills from an earlier run are recomputed, so the step is
    idempotent and a changed policy can be re-applied to a finished bank."""
    text = open(path).read()
    lines = strip_fills(text.split('\n'))               # an earlier run's fills: redo them from the originals
    cells = _cells(lines)
    if not cells:
        return None
    # holes, keyed by (donor, velocity window) -> keys, then runs of adjacent keys -> one rectangle each
    groups: dict = {}
    filled = 0
    for k in range(128):
        for lv, hv in _uncovered(cells, k):
            for d, a, b in _donors(cells, k, lv, hv):
                groups.setdefault((id(d), a, b), (d, []))[1].append(k)
            filled += hv - lv + 1
    if not filled:
        if '\n'.join(lines) != text:
            with open(path, 'w') as fh:
                fh.write('\n'.join(lines))
        return 0
    new_lines = []
    for (_, lv, hv), (d, keys) in groups.items():
        runs, start = [], keys[0]
        for a, b in zip(keys, keys[1:] + [None]):
            if b != a + 1:
                runs.append((start, a))
                start = b
        for lo, hi in runs:
            for i in d['lines']:
                new_lines.append(_copy(lines[i], lo, hi, lv, hv))
    last = max(i for i, l in enumerate(lines) if l.startswith('<region>'))
    lines[last + 1:last + 1] = [MARKER] + new_lines
    try:
        _compensate(lines, os.path.dirname(path))
    except Exception as e:                              # a bank without audio next to it: copies keep the donor's volume
        lines.insert(lines.index(MARKER) + 1, f'// kobi.extend: transposition loudness not compensated ({e})')
    out = '\n'.join(lines)
    if out == text:                                     # the same fills as last time: nothing changed
        return 0
    with open(path, 'w') as fh:
        fh.write(out)
    return filled


def _compensate(lines: list[str], gm_dir: str) -> None:
    """A copy played far from its keycenter is transposed by the player, and a sample transposed up
    gets shorter and brighter — louder to the ear and to a K-weighted meter.  For every copied
    region, measure the donor's opening loudness at its natural pitch and time-scaled to the copy's
    middle key, and put the difference into the copy's volume so the extended range sits at the
    level of the sampled one."""
    import soundfile as sf
    from fractions import Fraction
    from scipy.signal import resample_poly
    from .levels import momentary_max_lufs
    m = next((re.search(r'default_path=(\S+)', l) for l in lines if l.startswith('<control>')), None)
    if not m:
        raise ValueError('no default_path')
    folder = os.path.normpath(os.path.join(gm_dir, m.group(1)))
    gm = next((re.search(r'volume=(-?[\d.]+)', l) for l in lines if l.startswith('<global>')), None)
    gvol = float(gm.group(1)) if gm else 0.0
    start = lines.index(MARKER) + 1
    audio: dict = {}
    natural: dict = {}
    for i in range(start, len(lines)):
        l = lines[i]
        if not l.startswith('<region>'):
            break
        o = dict(_OP.findall(l))
        if 'offset' not in o or 'end' not in o:
            continue
        kc = int(o.get('pitch_keycenter', 60))
        mid = (int(o['lokey']) + int(o['hikey'])) / 2
        semis = (mid - kc) * float(o.get('pitch_keytrack', 100)) / 100 + float(o.get('tune', 0)) / 100
        if abs(semis) < 0.5:
            continue
        if o['sample'] not in audio:
            audio[o['sample']] = sf.read(os.path.join(folder, o['sample']), dtype='float32', always_2d=True)
        x, fs = audio[o['sample']]
        a, b = int(o['offset']), int(o['end'])
        r = 2.0 ** (semis / 12)                          # playback rate: the sample is this much shorter
        key = (o['sample'], a)
        if key not in natural:
            natural[key] = momentary_max_lufs(x[a: min(b + 1, a + fs)], fs)
        seg = x[a: min(b + 1, a + int(fs * 1.2 * max(r, 1.0)))]
        f = Fraction(r).limit_denominator(64)
        y = resample_poly(seg, f.denominator, f.numerator, axis=0)
        if len(y) < int(0.4 * fs):
            y = np.concatenate([y, np.zeros((int(0.4 * fs) - len(y), y.shape[1]), dtype=y.dtype)])
        transposed = momentary_max_lufs(y, fs)
        if not (np.isfinite(natural[key]) and np.isfinite(transposed)):
            continue
        delta = natural[key] - transposed
        vol = float(o.get('volume', gvol)) + delta
        lines[i] = re.sub(r'(?<!\S)volume=-?[\d.]+', f'volume={vol:.1f}', l) if 'volume' in o else l + f' volume={vol:.1f}'


def extend_bank(bank: str) -> dict:
    stats = dict(programs=0, changed=0, holes=0)
    for sfz in sorted(glob.glob(os.path.join(bank, 'GM', '*.sfz'))):
        if os.path.basename(sfz) == 'Drums.sfz':
            continue
        r = extend_sfz(sfz)
        if r is None:
            continue
        stats['programs'] += 1
        if r:
            stats['changed'] += 1
            stats['holes'] += r
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('banks', nargs='+')
    a = ap.parse_args(argv)
    for bank in a.banks:
        bank = paths.bank(bank)
        s = extend_bank(bank)
        print(f'{os.path.basename(bank):20s} {s["programs"]:3d} pitched programs, {s["changed"]:3d} extended, '
              f'{s["holes"]} (key, velocity) holes filled', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
