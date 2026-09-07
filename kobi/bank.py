"""kobi.bank — (re)build programs of the GM bank in demo/GM from the map and level them.

    python3 -m kobi.bank 40 41 56 57 60 61      # rebuild these programs' SFZs and re-measure their gain
    python3 -m kobi.bank --all

Each program's first ingestible candidate is written as a plain SFZ named the way the GM renderer
expects (``NNN Name.sfz``), then ``kobi.levels`` measures it and writes the ``<global> volume=``
that puts it on the bank target.  Drums are built by ``kobi.drums`` and left alone here.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

from .demo import write_view_sfz
from .gm_map import PROGRAMS
from .ingest import default_view, load_candidate
from .levels import apply_gain, measure

from .paths import use_dctjoin
use_dctjoin()
from dctjoin.gm import GM_PROGRAMS  # noqa: E402  (the renderer's program names)

BANK = os.path.join(paths.ROOT, 'demo', 'GM')


def build_program(num: int, target: float = -23.0, max_gain: float = 40.0, bank: str = BANK) -> dict | None:
    from .gm_map import LAYERS
    from .ingest import Instrument, load_program_view
    p = PROGRAMS[num]
    got = load_program_view(num, p.name)
    if got is None:
        return None
    kind, view = got
    inst = Instrument(name=p.name, source='layers' if num in LAYERS else p.cands[0].source, origin=f'program {num}', regions=view)
    path = os.path.join(bank, f'{num:03d} {GM_PROGRAMS[num][0]}.sfz')
    write_view_sfz(inst, view, path, kind)
    m = measure(path)
    gain = 0.0 if not np.isfinite(m['lufs']) else float(np.clip(target - m['lufs'], -max_gain, max_gain))
    apply_gain(path, gain)
    desc = ' + '.join(f'{c.source}:{c.path.split("/")[-1]} {g:+g} dB' for c, g, *_ in LAYERS[num]) if num in LAYERS else \
        f'{p.cands[0].source}:{p.cands[0].path}'
    return dict(num=num, name=p.name, cand=desc, regions=len(view), lufs=m['lufs'], gain=gain, path=path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('programs', nargs='*', type=int)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('-t', '--target', type=float, default=-23.0)
    a = ap.parse_args(argv)
    nums = list(range(128)) if a.all else a.programs
    for n in nums:
        r = build_program(n, a.target)
        if r is None:
            print(f'{n:3d} {PROGRAMS[n].name}: nothing ingestible')
        else:
            print(f"{r['num']:3d} {r['name']:24s} {r['cand'][:60]:60s} {r['regions']:4d} regions  {r['lufs']:6.1f} LUFS  gain {r['gain']:+5.1f} dB", flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
