"""kobi.postfilter — tighten a built bank in place-ish: drop the notes that never looped, thin the
key map to a musical spacing, and shorten the kit by looping what can be looped.

Three rules, each of which the earlier build could not apply because it works per note rather than
per instrument:

1. **Drop failed one-shots.**  A note the pipeline could not loop is a plain (gated) transcode: it
   sounds unlike its looped neighbours and costs several times as much.  Where an instrument looped
   most of its notes, the odd failure is better deleted and its key range handed to the neighbours
   than kept as an oddity.  Where an instrument looped almost nothing (a drum-like or noise source)
   the failures *are* the instrument, so they stay.

2. **Sample every N semitones.**  A fourth (5 semitones) is about as far as a harmonic instrument
   can be transposed before the formants move audibly, so keys are thinned to that spacing and the
   ranges re-spread.

3. **Shorten the kit.**  Cymbals, rides, china and splash ring for seconds; the rest of a kit does
   not.  For those GM keys a cross-faded loop is cut from the steady part of the decay and the
   natural decay restored with an SFZ envelope, so the file holds an attack and a short loop
   instead of a long tail.  Everything else is simply capped.

Re-packs from the source bank's lossless ``.pcm`` cache, so nothing is re-encoded twice.

    python3 -m kobi.postfilter --src kobi_ultra_hifi --out kobi_ultra_hifi_pf
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil

import numpy as np
import soundfile as sf

from . import packing
from .slim import _read, _rewrite, select
from . import paths

# GM drum keys that ring: crash 1 and 2, ride 1 and 2, china, ride bell, splash, open hi-hat
CYMBALS = {46, 49, 51, 52, 53, 55, 57, 59}
MIN_SPACE = 5          # semitones between sampled keys: a fourth
KIT_MAX_S = 1.2        # a kit hit that is not looped is capped here
CYMBAL_ATTACK_S = 0.35 # kept verbatim before the loop starts
CYMBAL_LOOP_S = 0.25
XFADE_S = 0.06


def cymbal_loop(path: str, attack_s: float = CYMBAL_ATTACK_S, loop_s: float = CYMBAL_LOOP_S,
                xfade_s: float = XFADE_S) -> tuple | None:
    """Cut a cross-faded loop from the steady part of a cymbal's decay.

    Returns (audio, loop_start, loop_end, hold_s, decay_T) or None when the hit is too short or
    still too transient to loop.  The loop's own level is flattened so the SFZ envelope, not the
    sample, carries the decay; the tail of the loop is cross-faded onto the audio that precedes its
    start, which is what makes the seam continuous for noise.
    """
    x, fs = sf.read(path, dtype='float64', always_2d=True)
    n_att, n_loop, n_xf = int(attack_s * fs), int(loop_s * fs), int(xfade_s * fs)
    if len(x) < n_att + n_loop + n_xf + int(0.2 * fs):
        return None
    env = np.abs(x).max(axis=1)
    peak = int(np.argmax(env))
    a = peak + n_att                                   # loop starts this far after the strike
    if a + n_loop + n_xf > len(x):
        return None
    # a smooth envelope, to flatten the loop and to fit the decay the SFZ has to restore
    w = max(64, int(0.02 * fs))
    sm = np.convolve(env, np.ones(w) / w, mode='same') + 1e-9
    if sm[a] < sm[peak] * 10 ** (-40 / 20):            # already died away: nothing worth looping
        return None
    seg = x[a - n_xf: a + n_loop + n_xf].copy()
    g = sm[a - n_xf: a + n_loop + n_xf]
    seg *= (sm[a] / g)[:, None]                        # flatten: the envelope moves to the SFZ
    loop = seg[n_xf: n_xf + n_loop].copy()
    ramp = 0.5 * (1 - np.cos(np.linspace(0, np.pi, n_xf)))[:, None]
    loop[-n_xf:] = seg[n_xf + n_loop - n_xf: n_xf + n_loop] * (1 - ramp) + seg[:n_xf] * ramp
    out = np.concatenate([x[:a], loop])                 # the strike verbatim, then the flattened loop
    ls, le = a, a + n_loop - 1
    # the decay the envelope must restore, from the recording's own fall after the loop point
    tail = sm[a:]
    t = np.arange(len(tail)) / fs
    good = tail > tail[0] * 10 ** (-45 / 20)
    if good.sum() < int(0.15 * fs):
        return None
    T = float(-np.polyfit(t[good], np.log(tail[good] / tail[0]), 1)[0])
    decay_T = float(np.clip(9.0 / max(T, 1e-3), 0.15, 30.0))     # sfizz: exp(-9 t / T)
    return out, ls, le, a / fs, decay_T


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=paths.bank('kobi_ogg_lite25'),
                    help='a compressed bank (it must still have its .pcm cache)')
    ap.add_argument('--out', default=paths.bank('kobi_ultra_hifi_pf'))
    ap.add_argument('--min-space', type=int, default=MIN_SPACE)
    ap.add_argument('--max-vel', type=int, default=1)
    ap.add_argument('--kit-max', type=float, default=KIT_MAX_S)
    ap.add_argument('--min-loop-frac', type=float, default=0.5)
    ap.add_argument('-q', '--quality', type=float, default=0.0)
    ap.add_argument('--rate-div', type=int, default=2)
    ap.add_argument('--stereo', action='store_true', help='keep the source channels (default: mono downmix)')
    ap.add_argument('--no-cymbal-loops', action='store_true')
    ap.add_argument('--sfx-notes', type=int, default=1, help='samples to keep in a one-shot effect program; the '
                                                             'survivor answers on every key instead of only its own')
    a = ap.parse_args(argv)
    a.src = paths.bank(a.src)
    a.out = paths.bank(a.out)
    rate_div, mono = a.rate_div, not a.stereo
    print(f'source bank {a.src}: re-packing at rate_div {rate_div}, {"mono" if mono else "stereo"}, q{a.quality:g}')
    shutil.rmtree(a.out, ignore_errors=True)
    os.makedirs(os.path.join(a.out, 'GM'))
    rows, total = [], 0
    for sfz in sorted(glob.glob(os.path.join(a.src, 'GM', '*.sfz'))):
        name = os.path.splitext(os.path.basename(sfz))[0]
        head, samples0 = _read(sfz)
        samples = list(samples0)
        if not samples or not samples[0].get('stem'):
            continue
        folder = os.path.basename(os.path.dirname(samples[0]['file']))
        cache = os.path.join(a.src, '.pcm', folder)
        os.makedirs(os.path.join(a.out, folder), exist_ok=True)
        kit = name == 'Drums'
        sfx = not kit and bool(samples) and all(x['keyless'] for x in samples)
        dropped_sfx = 0
        if sfx and a.sfx_notes and len(samples) > a.sfx_notes:
            # a GM effect is one sound, not a set of takes: keep the loudest (longest among near-equals)
            peaks = {}
            for x in samples:
                y, _ = sf.read(os.path.join(cache, x['pcm']), always_2d=True)
                peaks[x['stem']] = (float(np.abs(y).max()), x['length'])
            top = max(p for p, _ in peaks.values())
            samples = sorted(samples, key=lambda x: (peaks[x['stem']][0] > top * 0.7, peaks[x['stem']][1]), reverse=True)
            dropped_sfx = len(_read(sfz)[1]) - a.sfx_notes
            samples = samples[:a.sfx_notes]
        looped = sum(1 for s in samples if s['loop_local'])
        dropped_fail = 0
        if not kit and samples and looped / len(samples) >= a.min_loop_frac:
            keep = [s for s in samples if s['loop_local']]
            dropped_fail = len(samples) - len(keep)
            samples = keep
        pol = dict(rr=1, vel=a.max_vel) if kit else dict(rr=1, vel=a.max_vel, space=a.min_space)
        kept = select(samples, pol)
        # the kit: loop what rings, cap the rest
        entries, extra = [], {}
        for s in kept:
            src = os.path.join(cache, s['pcm'])
            loop, cap = s['loop_local'], None
            if kit:
                key = s['key']
                made = None
                if key in CYMBALS and not a.no_cymbal_loops and not loop:
                    made = cymbal_loop(src)
                if made is not None:
                    audio, ls, le, hold, decay_T = made
                    src = os.path.join(a.out, folder, 'tmp_' + os.path.splitext(s['pcm'])[0] + '.flac')
                    sf.write(src, audio, s['rate'], subtype='PCM_16')
                    loop = [ls, le]
                    extra[s['stem']] = dict(hold=hold, decay=decay_T)
                else:
                    cap = a.kit_max
            entries.append(dict(stem=s['stem'], path=src, loop=loop, max_s=cap))
        groups = {}
        for s, e in zip(kept, entries):
            groups.setdefault(s['packfile'], []).append((s, e))
        lines = list(head)
        for packfile, grp in groups.items():
            index = packing.pack_notes([e for _, e in grp], os.path.join(a.out, folder, packfile),
                                       a.quality, mono=mono, rate_div=rate_div)
            for s, _ in grp:
                pos = dict(index[s['stem']], file=packfile)
                for l in s['lines']:
                    l = _rewrite(l, s, pos)
                    if sfx:                     # one sound, playable from any key
                        l = re.sub(r'(?<!\S)key=(\d+)', r'lokey=0 hikey=127 pitch_keycenter=\1', l)
                    ex = extra.get(s['stem'])
                    if ex and pos['loop']:
                        l = l.replace('loop_mode=one_shot', 'loop_mode=loop_continuous')
                        l += (f" loop_start={pos['loop'][0]} loop_end={pos['loop'][1]} ampeg_hold={ex['hold']:.3f}"
                              f" ampeg_decay={ex['decay']:.2f} ampeg_sustain=0 ampeg_release={ex['decay']:.2f}")
                    lines.append(l)
        for f in glob.glob(os.path.join(a.out, folder, 'tmp_*')):
            os.remove(f)
        with open(os.path.join(a.out, 'GM', name + '.sfz'), 'w') as fh:
            fh.write('\n'.join(lines) + '\n')
        after = sum(os.path.getsize(os.path.join(a.out, folder, f)) for f in os.listdir(os.path.join(a.out, folder)))
        before = sum(x['size'] for x in samples0)
        total += after
        rows.append((name, len(samples0), len(kept), dropped_fail + dropped_sfx, len(extra), before / 1e6, after / 1e6))
        print(f'{name[:30]:30s} {len(samples0):4d} -> {len(kept):4d} notes'
              f'{f", {dropped_fail} un-looped dropped" if dropped_fail else "":28s}'
              f'{f", {len(extra)} cymbals looped" if extra else "":22s} {before/1e6:5.2f} -> {after/1e6:5.2f} MB', flush=True)
    md = ['# Post-filtered bank', '', f'From `{os.path.basename(a.src)}`: un-looped notes dropped where an instrument looped at '
          f'least {a.min_loop_frac:.0%} of its keys, keys thinned to {a.min_space} semitones, kit hits capped at {a.kit_max:g} s '
          f'with cymbals and rides looped instead.', '',
          '| program | notes before | after | un-looped dropped | cymbals looped | MB before | MB after |',
          '|---|---|---|---|---|---|---|']
    md += [f'| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]:.2f} | {r[6]:.2f} |' for r in rows]
    md += ['', f'**Total {total/1e6:.2f} MB in {sum(r[2] for r in rows)} notes.**']
    from . import extend
    extend.extend_bank(a.out)
    with open(os.path.join(a.out, 'SIZES.md'), 'w') as fh:
        fh.write('\n'.join(md) + '\n')
    print(f'\nwrote {a.out}: {total/1e6:.2f} MB, {sum(r[2] for r in rows)} notes, '
          f'{sum(r[3] for r in rows)} un-looped dropped, {sum(r[4] for r in rows)} cymbals looped')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
