"""kobi.audit — does a built bank play in tune and at an even level?

Renders every key of every pitched program (its sampled span, 6 keys either side) at velocity 100
through sfizz, one note at a time, and reads each note's pitch (kobi.pitchcheck: pYIN and
subharmonic summation must agree, octave-folded) and loudness (max momentary LUFS, as kobi.levels
measures).  The kit is rendered piece by piece.  Writes <bank>/AUDIT.md and AUDIT.json.

    python3 -m kobi.audit kobi_slim [programs...] [-j 18]

A note is "off" past 35 cents; one the detectors disagree on is "unsure" (unpitched and inharmonic
sounds, and some low notes).  Programs kobi.compress does not pitch-check (bells, timpani, the
orchestra hit, the fifths lead, percussion and effects) are listed but not counted.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
from multiprocessing import Pool

import numpy as np

from . import paths
from .compress import NO_PITCH_CHECK
from .demo import FS, render
from .levels import momentary_max_lufs
from .pitchcheck import measure

NOTE_S, VEL, OFF_CENTS = 1.0, 100, 35.0
_OP = re.compile(r'(?<!\S)(\w+)=(\S+)')


def _span(path: str):
    text = open(path).read()
    fill = text.find('// kobi.extend')
    kcs = [int(o['pitch_keycenter']) for o in (dict(_OP.findall(l)) for l in text[:fill if fill > 0 else None].split('\n')
           if l.startswith('<region>')) if 'pitch_keycenter' in o and o.get('pitch_keytrack') != '0']
    return (min(kcs), max(kcs)) if kcs else None


def _kit_keys(path: str) -> list:
    return sorted({int(o.get('key', o.get('lokey', -1))) for o in (dict(_OP.findall(l)) for l in open(path).read().split('\n')
                   if l.startswith('<region>'))} - {-1})


def audit_program(path: str) -> dict | None:
    name = os.path.basename(path)[:-4]
    if name == 'Drums':
        rows = []
        for k in _kit_keys(path):
            x = render(os.path.abspath(path), [(0.0, 'on', k, VEL), (NOTE_S, 'off', k, 0)], NOTE_S)
            rows.append(dict(key=k, lufs=momentary_max_lufs(x, FS) if np.abs(x).max() > 1e-6 else -np.inf))
        return dict(name=name, kit=True, rows=rows)
    span = _span(path)
    if span is None:
        return None
    rows = []
    for k in range(max(21, span[0] - 6), min(108, span[1] + 6) + 1):
        x = render(os.path.abspath(path), [(0.0, 'on', k, VEL), (NOTE_S, 'off', k, 0)], NOTE_S)
        lufs = momentary_max_lufs(x, FS) if np.abs(x).max() > 1e-6 else -np.inf
        m = measure(x, FS, 440.0 * 2 ** ((k - 69) / 12))
        rows.append(dict(key=k, lufs=float(lufs), cents=m['cents'], pyin=m['pyin'], shs=m['shs']))
    return dict(name=name, span=list(span), rows=rows)


def summary(r: dict) -> dict:
    lufs = np.array([x['lufs'] for x in r['rows'] if np.isfinite(x['lufs'])])
    out = dict(name=r['name'], median=float(np.median(lufs)) if len(lufs) else float('-inf'),
               spread=float(np.percentile(lufs, 95) - np.percentile(lufs, 5)) if len(lufs) else 0.0,
               silent=[x['key'] for x in r['rows'] if not np.isfinite(x['lufs'])])
    if r.get('kit'):
        return out
    cents = [x for x in r['rows'] if x['cents'] is not None]
    out.update(checked=int(r['name'][:3]) not in NO_PITCH_CHECK, measured=len(cents), unsure=len(r['rows']) - len(cents),
               off=[(x['key'], round(x['cents'])) for x in cents if abs(x['cents']) > OFF_CENTS],
               median_cents=float(np.median([abs(x['cents']) for x in cents])) if cents else float('nan'))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('bank')
    ap.add_argument('programs', nargs='*', help='three-digit program numbers or "Drums"; default all')
    ap.add_argument('-j', '--jobs', type=int, default=os.cpu_count())
    a = ap.parse_args(argv)
    bank = paths.bank(a.bank)
    files = sorted(glob.glob(os.path.join(bank, 'GM', '*.sfz')))
    if a.programs:
        files = [f for f in files if os.path.basename(f)[:3] in a.programs or os.path.basename(f)[:-4] in a.programs]
    with Pool(a.jobs) as pool:
        res = [r for r in pool.map(audit_program, files, chunksize=1) if r]
    json_path = os.path.join(bank, 'AUDIT.json')
    if a.programs and os.path.exists(json_path):               # a partial run updates the full record
        old = {r['name']: r for r in json.load(open(json_path))}
        old.update({r['name']: r for r in res})
        res = sorted(old.values(), key=lambda r: r['name'])
    with open(json_path, 'w') as fh:
        json.dump(res, fh)
    sums = [summary(r) for r in res]
    progs = [s for s in sums if 'measured' in s]
    checked = [s for s in progs if s['checked']]
    meds = np.array([s['median'] for s in progs if np.isfinite(s['median'])])
    md = ['# Bank audit', '', f'Every key of each pitched program (sampled span +-6 keys) at velocity {VEL}, rendered one note at a time '
          f'through sfizz.  Pitch: kobi.pitchcheck (pYIN and subharmonic summation must agree; octave-folded); a note is off past '
          f'{OFF_CENTS:g} cents.  Loudness: max momentary LUFS (K-weighted, 400 ms), the measure kobi.levels sets programs by.', '',
          f'**Pitch:** {sum(len(s["off"]) for s in checked)} notes off in {sum(1 for s in checked if s["off"])} of {len(checked)} checked programs; '
          f'{sum(s["measured"] for s in checked)} notes measured, {sum(s["unsure"] for s in checked)} unsure.  '
          f'**Loudness:** program medians {meds.min():.1f} .. {meds.max():.1f} LUFS (median {np.median(meds):.1f}); '
          f'{sum(1 for s in progs if abs(s["median"] - np.median(meds)) > 1.5)} programs more than 1.5 dB from it; '
          f'{sum(1 for s in progs if s["spread"] > 3)} with a key-to-key spread (5-95%) over 3 dB.', '',
          '| program | pitch: median dev | off > 35c | unsure | loudness median | spread 5-95% | notes |', '|---|---|---|---|---|---|---|']
    for s in progs:
        note = '' if s['checked'] else 'not pitch-checked'
        if s['silent']:
            note += f' silent: {s["silent"][:8]}'
        off = ' '.join(f'{k}:{c:+d}' for k, c in s['off'][:10]) + (' ...' if len(s['off']) > 10 else '')
        md.append(f"| {s['name']} | {s['median_cents']:.0f}c | {len(s['off'])} {off} | {s['unsure']} | {s['median']:.1f} | {s['spread']:.1f} | {note.strip()} |")
    kit = next((r for r in res if r.get('kit')), None)
    if kit:
        md += ['', '## Kit', '', 'Each piece alone at velocity 100 (max momentary LUFS).', '',
               ' '.join(f"{x['key']}:{x['lufs']:.0f}" for x in kit['rows'])]
    with open(os.path.join(bank, 'AUDIT.md'), 'w') as fh:
        fh.write('\n'.join(md) + '\n')
    print('\n'.join(md[:6]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
