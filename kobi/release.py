"""kobi.release — cap the release of sustained notes.

dctjoin measures each sustained note's ``ampeg_release`` from the recording's own tail, and a string
section or a contrabass recorded in a hall takes 2–4 s to die away.  Applied to a staccato passage
that smears every note into the next (Beethoven's fifth: 0.14 s notes with 4 s tails, hundreds of
voices alive at once, the polyphony cap cutting them off).  A General MIDI instrument releases in
well under a second; this step caps ``ampeg_release`` of looped, sustaining regions at ``MAX_S``.
Decaying notes (piano and friends, with ``ampeg_hold``) keep their pedal-aware release.

    python3 -m kobi.release kobi_ogg kobi_slim ...
"""
from __future__ import annotations

import argparse
import glob
import os
import re
from . import paths

MAX_S = 0.5
_REL = re.compile(r'(?<!\S)ampeg_release=([\d.]+)')


def cap_line(line: str, max_s: float = MAX_S) -> str:
    if not line.startswith('<region>') or 'ampeg_hold=' in line or 'loop_mode=loop_continuous' not in line and 'loop_start=' not in line:
        return line
    return _REL.sub(lambda m: f'ampeg_release={min(float(m.group(1)), max_s):.3f}' if float(m.group(1)) > max_s else m.group(0), line)


def cap_sfz(path: str, max_s: float = MAX_S) -> int:
    lines = open(path).read().split('\n')
    out = [cap_line(l, max_s) for l in lines]
    n = sum(1 for a, b in zip(lines, out) if a != b)
    if n:
        with open(path, 'w') as fh:
            fh.write('\n'.join(out))
    return n


def cap_bank(bank: str, max_s: float = MAX_S) -> dict:
    stats = dict(programs=0, regions=0)
    for sfz in sorted(glob.glob(os.path.join(bank, 'GM', '*.sfz'))):
        n = cap_sfz(sfz, max_s)
        if n:
            stats['programs'] += 1
            stats['regions'] += n
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('banks', nargs='+')
    ap.add_argument('--max', type=float, default=MAX_S)
    a = ap.parse_args(argv)
    for bank in a.banks:
        bank = paths.bank(bank)
        s = cap_bank(bank, a.max)
        print(f'{os.path.basename(bank):18s} release capped at {a.max:g} s on {s["regions"]} sustaining regions in {s["programs"]} programs', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
