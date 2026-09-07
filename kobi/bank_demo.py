"""kobi.bank_demo — one phrase per program straight from a built bank.

Unlike ``kobi.demo`` (which plays the *sources* through the map), this reads the SFZs of a finished
bank — kobi_ogg, kobi_slim, kobi_ogg_lite, kobi_slim_lite — so what you hear is exactly what the
bank ships: its loops, its envelopes, its levels.  Phrases are played at bank level (no per-program
normalisation) so the balance is audible; only the joined file is scaled if it would clip.

    python3 -m kobi.bank_demo --bank kobi_slim -o demo_bank/kobi_slim
    python3 -m kobi.bank_demo --bank kobi_ogg 0 40 56 --drums      # a few programs
"""
from __future__ import annotations

import argparse
import glob
import os
import re

import numpy as np
import soundfile as sf

from .demo import FS, GAP_S, phrase, render
from . import paths

_OP = re.compile(r'(?<!\S)([\w]+)=(\S+)')


def read_bank_sfz(path: str) -> tuple[str, dict]:
    """(kind, phrase info) for a built program: 'kit' | 'oneshot' | 'decay' | 'sustain', and the
    key centres / range the phrase generator needs."""
    text = open(path).read()
    regions = [l for l in text.split('\n') if l.startswith('<region>')]
    if not regions:
        return 'sustain', dict(keys=[60], lo=60, hi=60, centres=[])
    keyless, centres, keys = 0, set(), set()
    for line in regions:
        ops = dict(_OP.findall(line))
        if 'pitch_keycenter' in ops and ops.get('pitch_keytrack') != '0':
            c = int(ops['pitch_keycenter'])
            centres.add(c)
            keys.update(range(int(ops.get('lokey', c)), int(ops.get('hikey', c)) + 1))
        else:
            k = int(ops.get('key', ops.get('lokey', 60)))
            keyless += 1
            keys.add(k)
    ks = sorted(keys)
    info = dict(keys=ks, lo=ks[0], hi=ks[-1], centres=sorted(centres))
    if os.path.basename(path) == 'Drums.sfz':
        return 'kit', info
    if keyless and not centres:
        return 'oneshot', info
    return ('decay' if 'ampeg_hold' in text else 'sustain'), info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('programs', nargs='*', type=int)
    ap.add_argument('--bank', default='kobi_slim')
    ap.add_argument('-o', '--out', default=None)
    ap.add_argument('--drums', action='store_true')
    a = ap.parse_args(argv)
    bank = paths.bank(a.bank)
    out_dir = a.out or os.path.join(paths.ROOT, 'demo_bank', os.path.basename(bank.rstrip('/')))
    os.makedirs(os.path.join(out_dir, 'programs'), exist_ok=True)
    files = sorted(glob.glob(os.path.join(bank, 'GM', '*.sfz')))
    if a.programs or a.drums:
        want = {f'{n:03d}' for n in a.programs}
        files = [f for f in files if os.path.basename(f)[:3] in want or (a.drums and os.path.basename(f) == 'Drums.sfz')]
    parts, cues, t = [], [], 0.0
    gap = np.zeros((int(GAP_S * FS), 2), dtype=np.float32)
    for sfz in files:
        name = os.path.splitext(os.path.basename(sfz))[0]
        kind, info = read_bank_sfz(sfz)
        ev, secs = phrase(kind, info)
        y = render(sfz, ev, secs)
        pk = float(np.max(np.abs(y)))
        cues.append(dict(t=t, name=name, kind=kind, peak_db=20 * np.log10(pk + 1e-9), notes=len(info['centres']) or len(info['keys'])))
        sf.write(os.path.join(out_dir, 'programs', name + '.wav'), np.clip(y, -1, 1), FS, subtype='PCM_16')
        parts += [y, gap]
        t += len(y) / FS + GAP_S
        print(f"{int(t // 60)}:{t % 60:04.1f}  {name:30s} {kind:8s} peak {cues[-1]['peak_db']:6.1f} dBFS", flush=True)
    full = np.concatenate(parts)
    pk = float(np.max(np.abs(full)))
    if pk > 0.99:
        full = full * (0.99 / pk)
        print(f'joined file scaled by {20 * np.log10(0.99 / pk):.1f} dB to fit')
    wav = os.path.join(out_dir, 'bank_demo.wav')
    sf.write(wav, full, FS, subtype='PCM_16')
    with open(os.path.join(out_dir, 'CUES.md'), 'w') as fh:
        fh.write(f'# {os.path.basename(bank)} — every program\n\nPhrases rendered from the bank itself at its own levels '
                 f'(arpeggio + chord; hits for one-shots; a beat for the kit).\n\n| time | program | kind | peak dBFS |\n|---|---|---|---|\n')
        for c in cues:
            fh.write(f"| {int(c['t'] // 60)}:{c['t'] % 60:04.1f} | {c['name']} | {c['kind']} | {c['peak_db']:.1f} |\n")
    print(f'wrote {wav} ({len(full) / FS / 60:.1f} min, {len(cues)} programs)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
