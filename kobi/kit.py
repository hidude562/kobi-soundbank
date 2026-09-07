"""kobi.kit — tidy the drum kit: one take per hit, and Latin percussion that decays.

Two things the kit build left behind.  Alternate takes of a hit landed on the same velocity window,
so one MIDI note fired them all (four vibraslaps at once is a rattle that never ends); they become
round robins, and a take on a broader velocity window than its neighbours is dropped as redundant.
And the sustained Latin instruments — vibraslap, maracas, whistles, guiros, cuica, triangle, shaker,
cabasa, tambourine — are one-shots recorded with their full ring, so they play out for seconds
whatever the music does; ``DECAY`` gives each a short hold and a decay to silence (sfizz's
exp(-9 t / T): -78 dB at T), keeping the strike and losing the tail.

    python3 -m kobi.kit kobi_ogg kobi_slim ...
"""
from __future__ import annotations

import argparse
import glob
import os
import re
from . import paths

_OP = re.compile(r'(?<!\S)([\w]+)=(\S+)')

# GM key -> (hold s, decay s)
DECAY = {
    54: (0.05, 0.5),    # tambourine
    58: (0.10, 0.6),    # vibraslap
    69: (0.05, 0.4),    # cabasa
    70: (0.05, 0.4),    # maracas
    71: (0.15, 0.3),    # short whistle
    72: (0.30, 0.6),    # long whistle
    73: (0.05, 0.3),    # short guiro
    74: (0.10, 0.5),    # long guiro
    78: (0.10, 0.4),    # mute cuica
    79: (0.15, 0.5),    # open cuica
    80: (0.05, 0.4),    # mute triangle
    81: (0.10, 1.2),    # open triangle
    82: (0.05, 0.3),    # shaker
}


def _set(line: str, **kv) -> str:
    for k, v in kv.items():
        if re.search(rf'(?<!\S){k}=', line):
            line = re.sub(rf'(?<!\S){k}=\S+', f'{k}={v}', line)
        else:
            line += f' {k}={v}'
    return line


def tidy_kit(path: str, decay: dict = DECAY) -> dict:
    original = open(path).read()
    lines = original.split('\n')
    regions = [(i, dict(_OP.findall(l))) for i, l in enumerate(lines) if l.startswith('<region>')]
    by_key: dict = {}
    for i, o in regions:
        k = o.get('key', o.get('lokey'))
        if k is None:
            continue
        w = (int(o.get('lovel', 1)), int(o.get('hivel', 127)))
        by_key.setdefault(int(k), {}).setdefault(w, {}).setdefault((o['sample'], o.get('offset', '')), []).append(i)
    robins = dropped = decayed = 0
    delete: set = set()
    for k, windows in by_key.items():
        # a window that strictly contains another on the same key is redundant: its takes would sound
        # on top of the finer layers
        for w in list(windows):
            if any(o != w and o[0] >= w[0] and o[1] <= w[1] for o in windows):
                for idx in windows[w].values():
                    delete.update(idx); dropped += 1
                del windows[w]
        for w, notes in windows.items():
            if len(notes) > 1:
                for pos, idx in enumerate(notes.values(), 1):
                    for i in idx:
                        lines[i] = _set(lines[i], seq_length=len(notes), seq_position=pos)
                    robins += 1
        if k in decay:
            hold, dec = decay[k]
            for notes in windows.values():
                for idx in notes.values():
                    for i in idx:
                        lines[i] = _set(lines[i], ampeg_hold=f'{hold:g}', ampeg_decay=f'{dec:g}', ampeg_sustain=0, ampeg_release=f'{dec:g}')
                        decayed += 1
    text = '\n'.join(l for i, l in enumerate(lines) if i not in delete)
    if text != original:
        with open(path, 'w') as fh:
            fh.write(text)
    return dict(robins=robins, dropped=dropped, decayed=decayed)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('banks', nargs='+')
    a = ap.parse_args(argv)
    for bank in a.banks:
        bank = paths.bank(bank)
        p = os.path.join(bank, 'GM', 'Drums.sfz')
        if not os.path.exists(p):
            continue
        s = tidy_kit(p)
        print(f'{os.path.basename(bank):18s} kit: {s["robins"]} takes became round robins, {s["dropped"]} redundant takes dropped, '
              f'{s["decayed"]} Latin regions given a decay', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
