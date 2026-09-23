"""kobi.evendecay — decaying programs whose key zones die away at different speeds.

kobi.compress rebuilds a decaying note from its first second of recording, a flattened loop and one
or more stacked envelope regions, each zone fitted to its own recording.  Where the recordings
disagree, neighbouring keys ring on at very different levels: a second into a note, the Sonatina
celeste's G zone is at -32 dB while C and E are near -40, so a held C-E-G chord collapses onto the G
and the program seems to play one note at a time.  kobi.balance cannot see this — it matches attacks.

This step renders each zone (its regions alone, velocity 100, through sfizz), measures its level
``at`` seconds in, draws the trend across the keys (running median over the zone and two neighbours
on either side, per velocity band) and scales the zone's ``ampeg_decay`` times until its level there
follows the trend (factor 0.5-2; zones within ``tol`` dB are left alone).  Attacks are not touched.
Runs on a bank's original regions and re-applies kobi.extend afterwards, like kobi.balance.

    python3 -m kobi.evendecay kobi_ogg [--at 1.0] [--tol 3]
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import tempfile

import numpy as np

from .demo import FS, render
from .extend import extend_sfz, strip_fills
from . import paths

_OP = re.compile(r'(?<!\S)([\w]+)=(\S+)')
_DECAY = re.compile(r'(?<!\S)ampeg_decay=(\S+)')
SILENT_DB = -80.0


def _scaled(line: str, k: float) -> str:
    return _DECAY.sub(lambda m: f'ampeg_decay={float(m.group(1)) * k:.3f}', line)


def level_at(head: list, zone_lines: list, key: int, at: float, k: float = 1.0, vel: int = 100) -> float:
    """dB (RMS) of the zone's note ``at`` seconds after its attack, decays scaled by ``k``."""
    with tempfile.NamedTemporaryFile('w', suffix='.sfz', delete=False) as fh:
        fh.write('\n'.join(head + [_scaled(l, k) for l in zone_lines]) + '\n')
        tmp = fh.name
    try:
        x = render(tmp, [(0.0, 'on', key, vel), (at + 1.0, 'off', key, 0)], at + 0.3).mean(axis=1)
    finally:
        os.remove(tmp)
    seg = x[int((at - 0.2) * FS):int((at + 0.2) * FS)]
    return float(10 * np.log10(np.mean(seg ** 2) + 1e-12))


def even_sfz(path: str, at: float = 1.0, tol: float = 3.0) -> dict | None:
    text = open(path).read()
    lines = strip_fills(text.split('\n'))
    ctl = next((l for l in lines if l.startswith('<control>')), '')
    m = re.search(r'default_path=(\S+)', ctl)
    if not m:
        return None
    folder = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(path)), m.group(1)))
    head = [re.sub(r'default_path=\S+', f'default_path={folder}/', ctl)] + [l for l in lines if l.startswith('<global>')]
    zones = {}
    for i, line in enumerate(lines):
        if not line.startswith('<region>'):
            continue
        o = dict(_OP.findall(line))
        if o.get('pitch_keytrack') == '0' or 'ampeg_decay' not in o or float(o.get('ampeg_sustain', '100')) > 0:
            continue
        key = (int(o['lokey']), int(o['hikey']), int(o.get('lovel', 1)), int(o.get('hivel', 127)))
        zones.setdefault(key, []).append(i)
    if len(zones) < 3:
        return None
    bands = {}
    for key, idx in zones.items():
        kc = int(dict(_OP.findall(lines[idx[0]])).get('pitch_keycenter', key[0]))
        play = min(max(kc, key[0]), key[1])
        bands.setdefault(key[2:], []).append((kc, play, idx))
    changed, before, after = 0, [], []
    for (lovel, hivel), band in bands.items():
        band.sort()
        vel = min(max(100, lovel), hivel)                      # a velocity the zone answers to
        levels = [level_at(head, [lines[i] for i in idx], play, at, vel=vel) for _, play, idx in band]
        sounding = [n for n, v in enumerate(levels) if v > SILENT_DB]   # a note that has ended is no trend
        for pos, n in enumerate(sounding):
            _, play, idx = band[n]
            near = [levels[m] for m in sounding[max(0, pos - 2):pos + 3]]
            trend = float(np.median(near))
            off = levels[n] - trend
            before.append(abs(off))
            if abs(off) <= tol or len(near) < 3:
                after.append(abs(off))
                continue
            zl = [lines[i] for i in idx]
            lo, hi = (0.5, 1.0) if off > 0 else (1.0, 2.0)      # too loud later: shorter decays; too quiet: longer
            for _ in range(7):
                mid = (lo * hi) ** 0.5
                if level_at(head, zl, play, at, mid, vel) > trend:
                    hi = mid
                else:
                    lo = mid
            k = (lo * hi) ** 0.5
            after.append(abs(level_at(head, zl, play, at, k, vel) - trend))
            for i in idx:
                lines[i] = _scaled(lines[i], k)
            changed += 1
    if not before:
        return None
    res = dict(zones=len(zones), changed=changed, worst_before=max(before), worst_after=max(after))
    if changed:
        with open(path, 'w') as fh:
            fh.write('\n'.join(lines))
        extend_sfz(path)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('banks', nargs='+')
    ap.add_argument('--at', type=float, default=1.0, help='seconds after the attack where the fall is compared')
    ap.add_argument('--tol', type=float, default=3.0, help='dB a zone may differ from its neighbours before it is changed')
    a = ap.parse_args(argv)
    for bank in a.banks:
        root = paths.bank(bank)
        rows = []
        for f in sorted(glob.glob(os.path.join(root, 'GM', '[0-9]*.sfz'))):
            r = even_sfz(f, a.at, a.tol)
            if r and r['changed']:
                rows.append((os.path.basename(f)[:-4], r))
                print(f"{os.path.basename(f)[:-4]:34s} {r['changed']:3d}/{r['zones']:3d} zones  worst off-trend "
                      f"{r['worst_before']:5.1f} -> {r['worst_after']:4.1f} dB", flush=True)
        with open(os.path.join(root, 'EVENDECAY.md'), 'w') as fh:
            fh.write(f'# Even decay\n\nZones whose level {a.at:g} s after the attack strayed more than {a.tol:g} dB from their neighbours, '
                     'decay times rescaled (x0.5-2).\n\n| program | zones changed | worst before dB | worst after dB |\n|---|---|---|---|\n')
            for name, r in rows:
                fh.write(f"| {name} | {r['changed']}/{r['zones']} | {r['worst_before']:.1f} | {r['worst_after']:.1f} |\n")
        print(f'{bank}: {len(rows)} programs evened')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
