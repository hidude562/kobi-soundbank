"""kobi.repack — re-pack a built bank from its lossless cache without re-running the pipeline.

Packing decisions (the guard between notes, the padding after each loop, the encoder settings) are
applied when a program's notes are concatenated, not when they are replicated.  So changing one of
them costs a re-pack — minutes — rather than a rebuild.  The SFZ keeps its regions and only the
addresses change: sample, offset, end and the loop bounds.

    python3 -m kobi.repack kobi_ogg kobi_ogg_lite       # in place, with the current packing.PAD_S
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
from multiprocessing import Pool

import soundfile as sf

from . import packing
from . import paths

_OP = re.compile(r'(?<!\S)([\w]+)=(\S+)')


def _readdress(line: str, pos: dict) -> str:
    """Point a region at its new place in the re-packed file, changing nothing else.  (slim's
    _rewrite also re-spreads keys and drops round robins, which a re-pack must not do.)"""
    line = re.sub(r'sample=\S+', f"sample={pos['file']}", line)
    line = re.sub(r'offset=\d+', f"offset={pos['start']}", line)
    line = re.sub(r'end=\d+', f"end={pos['start'] + pos['length'] - 1}", line)
    if pos['loop']:
        line = re.sub(r'loop_start=\d+', f"loop_start={pos['loop'][0]}", line)
        line = re.sub(r'loop_end=\d+', f"loop_end={pos['loop'][1]}", line)
    return line


def repack_program(job: dict) -> dict:
    bank, folder, quality = job['bank'], job['folder'], job['quality']
    src = os.path.join(bank, folder)
    idx = json.load(open(os.path.join(src, 'pack.json')))
    sfz = job['sfz']
    text = open(sfz).read()
    before = sum(os.path.getsize(os.path.join(src, f)) for f in os.listdir(src) if f.endswith('.ogg'))
    # the format each pack was written in has to be preserved
    fmt = {}
    for name in {v['file'] for v in idx.values()}:
        i = sf.info(os.path.join(src, name))
        pcm = sf.info(os.path.join(bank, '.pcm', folder, next(v['pcm'] for v in idx.values() if v['file'] == name)))
        fmt[name] = (max(1, int(round(pcm.samplerate / i.samplerate))), i.channels == 1)
    groups: dict = {}
    for stem, v in sorted(idx.items()):
        groups.setdefault(v['file'], []).append((stem, v))
    new_index = {}
    for name, grp in groups.items():
        rate_div, mono = fmt[name]
        entries = [dict(stem=stem, path=os.path.join(bank, '.pcm', folder, v['pcm']),
                        loop=(v['loop'][0] - v['start'], v['loop'][1] - v['start']) if v['loop'] else None)
                   for stem, v in grp]
        for stem, nv in packing.pack_notes(entries, os.path.join(src, name), quality, mono=mono, rate_div=rate_div).items():
            nv['file'] = name
            nv['pcm'] = idx[stem]['pcm']
            new_index[stem] = nv
    by_off = {(v['file'], v['start']): stem for stem, v in idx.items()}
    lines = []
    for line in text.split('\n'):
        if not line.startswith('<region>'):
            lines.append(line)
            continue
        o = dict(_OP.findall(line))
        stem = by_off.get((o['sample'], int(o['offset']))) if 'offset' in o else None
        if stem is None:
            lines.append(line)
            continue
        lines.append(_readdress(line, new_index[stem]))
    with open(sfz, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    with open(os.path.join(src, 'pack.json'), 'w') as fh:
        json.dump(new_index, fh, indent=1)
    after = sum(os.path.getsize(os.path.join(src, f)) for f in os.listdir(src) if f.endswith('.ogg'))
    return dict(folder=folder, notes=len(idx), before=before, after=after)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('banks', nargs='+')
    ap.add_argument('-q', '--quality', type=float, default=1.0)
    ap.add_argument('-j', '--jobs', type=int, default=3)
    a = ap.parse_args(argv)
    for bank in a.banks:
        bank = paths.bank(bank)
        jobs = []
        for sfz in sorted(glob.glob(os.path.join(bank, 'GM', '*.sfz'))):
            m = re.search(r'default_path=(\S+)', open(sfz).read())
            if not m:
                continue
            folder = os.path.basename(os.path.normpath(os.path.join(bank, 'GM', m.group(1))))
            if os.path.exists(os.path.join(bank, folder, 'pack.json')):
                jobs.append(dict(bank=bank, folder=folder, sfz=sfz, quality=a.quality))
        with Pool(a.jobs) as pool:
            res = list(pool.imap_unordered(repack_program, jobs))
        b, af = sum(r['before'] for r in res), sum(r['after'] for r in res)
        print(f'{os.path.basename(bank):18s} {len(res):3d} programs, {sum(r["notes"] for r in res):5d} notes: '
              f'{b/1e6:6.1f} -> {af/1e6:6.1f} MB ({(1 - af/max(b,1))*100:.0f}% smaller)  pad {packing.PAD_S*1000:.0f} ms', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
