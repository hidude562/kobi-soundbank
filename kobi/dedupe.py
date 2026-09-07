"""kobi.dedupe — one note per key and velocity.

Several source libraries record a key more than once — soft / medium / loud strikes, alternate
takes, microphone positions, synth variants — and where the ingest did not tell them apart they
all landed on overlapping key and velocity ranges, so one MIDI note fires two, three, eleven samples
at once (18 programs of the compressed bank; the slim builds then kept an arbitrary one per key, so
timbre jumped from key to key).

Per program, for every velocity window, the keyboard is partitioned among the overlapping notes:
each key goes to the note whose keycenter is nearest.  Notes that share a keycenter are told apart
by their raw loudness (loudest 400 ms of the first second, K-weighted, before any volume): up to
four with a spread of ``DYNAMIC_DB`` or more are dynamic layers and get consecutive velocity
windows, quietest first; otherwise they are variants and the one nearest the median loudness is
kept.  Programs that are stacks by design (gm_map.LAYERS) and regions that already alternate
(seq_* / lorand) are left alone.  Runs before kobi.balance and re-applies kobi.extend afterwards.

    python3 -m kobi.dedupe kobi_ogg kobi_ogg_lite kobi_ogg_lite25
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
DYNAMIC_DB = 6.0
MAX_LAYERS = 4


def _set(line: str, **kv) -> str:
    for k, v in kv.items():
        if re.search(rf'(?<!\S){k}=', line):
            line = re.sub(rf'(?<!\S){k}=\S+', f'{k}={v}', line)
        else:
            line += f' {k}={v}'
    return line


def plan_window(cells: list[dict], lovel: int, hivel: int, dynamic_db: float = DYNAMIC_DB) -> None:
    """Cells of one velocity window: [{lo, hi, kc, level}].  Sets each cell's new ``keys`` (a
    contiguous range or None) and, for dynamic layers, ``lovel`` / ``hivel``.  Pure."""
    for c in cells:
        c['keys'] = None
        c['lovel'], c['hivel'] = lovel, hivel
    won: dict = {id(c): [] for c in cells}
    for k in range(128):
        cand = [c for c in cells if c['lo'] <= k <= c['hi']]
        if not cand:
            continue
        if len(cand) == 1:
            won[id(cand[0])].append(k)
            continue
        best = min(abs(c['kc'] - k) for c in cand)
        near = [c for c in cand if abs(c['kc'] - k) == best]
        if len(near) == 1:
            won[id(near[0])].append(k)
            continue
        levels = [c['level'] for c in near]
        if len(near) <= MAX_LAYERS and max(levels) - min(levels) >= dynamic_db:
            order = sorted(near, key=lambda c: c['level'])
            n = len(order)
            for rank, c in enumerate(order):
                c['lovel'] = lovel + round((hivel - lovel + 1) * rank / n)
                c['hivel'] = lovel + round((hivel - lovel + 1) * (rank + 1) / n) - 1
                won[id(c)].append(k)
        else:                                            # variants: the one nearest the median loudness
            med = float(np.median(levels))
            keep = min(near, key=lambda c: (abs(c['level'] - med), c['kc']))
            won[id(keep)].append(k)
    for c in cells:
        ks = won[id(c)]
        if ks:
            c['keys'] = (min(ks), max(ks))               # nearest-keycenter partitions are contiguous


def dedupe_sfz(path: str, dynamic_db: float = DYNAMIC_DB) -> dict | None:
    text = open(path).read()
    lines = strip_fills(text.split('\n'))
    m = re.search(r'default_path=(\S+)', text)
    if not m:
        return None
    folder = os.path.normpath(os.path.join(os.path.dirname(path), m.group(1)))
    regions = [(i, dict(_OP.findall(l))) for i, l in enumerate(lines) if l.startswith('<region>')]
    if not regions or all(o.get('pitch_keytrack', '100') == '0' for _, o in regions):
        return None
    # cells: one per (note, key range, velocity window); a note's stacked envelopes share a cell
    cells: dict = {}
    for i, o in regions:
        if 'offset' not in o or o.get('seq_length') or o.get('lorand'):
            continue
        if o.get('pitch_keytrack', '100') == '0':   # sounds on its own key, never transposed: outside the partition
            continue
        key = o.get('key')
        lo, hi = int(o.get('lokey', key or 0)), int(o.get('hikey', key or 127))
        lv, hv = int(o.get('lovel', 1)), int(o.get('hivel', 127))
        c = cells.setdefault((o['sample'], o['offset'], lo, hi, lv, hv),
                             dict(sample=o['sample'], offset=int(o['offset']), end=int(o['end']), lo=lo, hi=hi, lv=lv, hv=hv,
                                  kc=int(o.get('pitch_keycenter', key or (lo + hi) // 2)), lines=[]))
        c['lines'].append(i)
    # any key where two cells of one window collide?
    windows: dict = {}
    for c in cells.values():
        windows.setdefault((c['lv'], c['hv']), []).append(c)
    clash = any(sum(1 for c in cs if c['lo'] <= k <= c['hi']) > 1 for cs in windows.values() for k in range(128))
    if not clash:
        return dict(layers=0, dropped=0, moved=0)
    audio: dict = {}
    for c in cells.values():
        if c['sample'] not in audio:
            audio[c['sample']] = sf.read(os.path.join(folder, c['sample']), dtype='float32', always_2d=True)
        x, fs = audio[c['sample']]
        seg = x[c['offset']: min(c['end'] + 1, c['offset'] + fs)]
        if len(seg) < int(0.4 * fs):
            seg = np.concatenate([seg, np.zeros((int(0.4 * fs) - len(seg), seg.shape[1]), dtype=seg.dtype)])
        c['level'] = momentary_max_lufs(seg, fs)
        if not np.isfinite(c['level']):
            c['level'] = -120.0
    layers = dropped = moved = 0
    delete: set = set()
    for (lv, hv), cs in windows.items():
        plan_window(cs, lv, hv, dynamic_db)
        for c in cs:
            if c['keys'] is None:
                delete.update(c['lines'])
                dropped += 1
                continue
            lo, hi = c['keys']
            if (lo, hi) != (c['lo'], c['hi']):
                moved += 1
            if (c['lovel'], c['hivel']) != (lv, hv):
                layers += 1
            for i in c['lines']:
                l = lines[i]
                if re.search(r'(?<!\S)key=\d+', l):
                    l = re.sub(r'(?<!\S)key=(\d+)', lambda mm: f'lokey={lo} hikey={hi}' + ('' if 'pitch_keycenter=' in l else f' pitch_keycenter={mm.group(1)}'), l)
                lines[i] = _set(l, lokey=lo, hikey=hi, lovel=c['lovel'], hivel=c['hivel'])
    lines = [l for i, l in enumerate(lines) if i not in delete]
    with open(path, 'w') as fh:
        fh.write('\n'.join(lines))
    extend_sfz(path)
    return dict(layers=layers, dropped=dropped, moved=moved)


def _layered_programs() -> set:
    try:
        from .gm_map import LAYERS
        return set(LAYERS)
    except Exception:
        return set()


def dedupe_bank(bank: str, dynamic_db: float = DYNAMIC_DB) -> dict:
    stats = dict(programs=0, changed=0, layers=0, dropped=0, moved=0)
    layered = _layered_programs()
    for sfz in sorted(glob.glob(os.path.join(bank, 'GM', '*.sfz'))):
        base = os.path.basename(sfz)
        if base == 'Drums.sfz' or (base[:3].isdigit() and int(base[:3]) in layered):
            continue
        r = dedupe_sfz(sfz, dynamic_db)
        if r is None:
            continue
        stats['programs'] += 1
        if any(r.values()):
            stats['changed'] += 1
            for k in ('layers', 'dropped', 'moved'):
                stats[k] += r[k]
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('banks', nargs='+')
    ap.add_argument('--dynamic-db', type=float, default=DYNAMIC_DB)
    a = ap.parse_args(argv)
    for bank in a.banks:
        bank = paths.bank(bank)
        s = dedupe_bank(bank, a.dynamic_db)
        print(f'{os.path.basename(bank):18s} {s["programs"]} pitched programs, {s["changed"]} had colliding notes: '
              f'{s["layers"]} cells became velocity layers, {s["moved"]} had their key range re-cut, {s["dropped"]} variants dropped', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
