"""kobi.slim — a smaller bank from the compressed one by dropping and truncating samples.

Nothing is re-replicated: the compressed Ogg files are the input.  A ladder of policies is
applied bank-wide, one rung further each step until the total fits the target:

    round robins -> 1, velocity layers capped (3, then 2, then 1), sampled keys thinned to a
    minimum spacing (pitch-shifting covers the gaps), one-shots and kit hits truncated.

Decaying notes keep all their envelope regions (they share one file).  Velocity windows and key
ranges are re-spread over what is kept.  Writes ``<out>/GM/*.sfz`` and per-program folders, and
``SIZES.md`` with the rung used and per-program counts.

    python3 -m kobi.slim [--src kobi_ogg] [--out kobi_slim] [--target-mb 25]
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import subprocess

import json

import numpy as np
import soundfile as sf

from . import packing
from . import paths

SRC = paths.bank('kobi_ogg')
OUT = paths.bank('kobi_slim')

LADDER = [dict(rr=1), dict(rr=1, vel=3), dict(rr=1, vel=3, space=2), dict(rr=1, vel=2, space=2), dict(rr=1, vel=2, space=3),
          dict(rr=1, vel=2, space=4), dict(rr=1, vel=1, space=4), dict(rr=1, vel=1, space=5), dict(rr=1, vel=1, space=6),
          dict(rr=1, vel=1, space=8), dict(rr=1, vel=1, space=12)]
DRUM_LADDER = [dict(rr=1), dict(rr=1, vel=4), dict(rr=1, vel=3), dict(rr=1, vel=3, max_s=2.5), dict(rr=1, vel=2, max_s=2.0),
               dict(rr=1, vel=2, max_s=1.5), dict(rr=1, vel=1, max_s=1.5), dict(rr=1, vel=1, max_s=1.0), dict(rr=1, vel=1, max_s=0.8),
               dict(rr=1, vel=1, max_s=0.6), dict(rr=1, vel=1, max_s=0.5)]
SFX_MAX_S = 3.0
MAX_UNLOOPED_S = 3.0     # gate for a pitched note that never got a loop, however the bank was built
# when dropping notes is not enough (an ultra-light bank), the encoder itself becomes a lever: lower
# Vorbis quality, then a mono downmix.  Both are applied when the notes are re-packed, so they cost
# no extra lossy generation.
# Measured on packed programs, relative to Vorbis q1 at the source rate and channels: q0 gives 0.76,
# a mono downmix a further 0.79, half the sample rate a further 0.5.  q-1 is NOT here: below q0
# libvorbis changes mode and comes out ~15% *larger* on this short, transient-rich material.
CODEC = [dict(), dict(quality=0.5), dict(quality=0.0), dict(quality=0.0, mono=True),
         dict(quality=0.0, mono=True, rate_div=2), dict(quality=0.0, mono=True, rate_div=4)]
Q_SCALE = {1.0: 1.0, 0.5: 0.90, 0.0: 0.76}                  # rough; the build-and-measure loop corrects it
CODEC_DAMAGE = [0.0, 1.5, 3.0, 4.5, 7.0, 10.0]              # how each codec step compares with a rung of content

_OP = re.compile(r'(?<!\S)([\w]+)=(\S+)')


def _read(sfz: str):
    """(header lines, samples) where a sample = dict(file, size, key, keyless, lovel, hivel, seq, rand, lines, dur)."""
    from .extend import strip_fills
    head, samples = [], {}
    folder = None
    layer = None                                    # a stacked program's '// layer:' (kobi.compress)
    # only the sampled notes: kobi.extend's copies share a note's sample and offset but carry the
    # ranges of the holes they fill, and would overwrite the note's own range and layer here
    for line in strip_fills(open(sfz).read().split('\n')):
        if line.startswith('// layer:'):
            layer = line[3:]
            continue
        if not line.startswith('<region>'):
            head.append(line)
            m = re.search(r'default_path=(\S+)', line)
            if m:
                folder = os.path.normpath(os.path.join(os.path.dirname(sfz), m.group(1)))
            continue
        ops = dict(_OP.findall(line))
        f = ops['sample']
        ident = (f, ops.get('offset', ''))          # a packed bank: one file, notes told apart by offset
        s = samples.setdefault(ident, dict(file=os.path.join(folder, f), lines=[], key=None, keyless=False, layer=layer,
                                           offset=int(ops['offset']) if 'offset' in ops else None))
        s['lines'].append(line)
        if 'pitch_keycenter' in ops:
            s['key'] = int(ops['pitch_keycenter']); s['lo'] = int(ops['lokey']); s['hi'] = int(ops['hikey'])
        else:
            s['key'] = int(ops['key']); s['keyless'] = True; s['lo'] = s['hi'] = s['key']
        s['lovel'], s['hivel'] = int(ops.get('lovel', 1)), int(ops.get('hivel', 127))
        s['seq'] = int(ops.get('seq_position', 1)); s['rand'] = float(ops.get('lorand', 0))
        s['tune'] = round(float(ops.get('tune', 0))); s['vol'] = float(ops.get('volume', 0))
    pack = None
    if folder and os.path.exists(os.path.join(folder, 'pack.json')):
        pack = json.load(open(os.path.join(folder, 'pack.json')))
        bps, by_off = {}, {}
        for stem, v in pack.items():
            by_off[(v['file'], v['start'])] = (stem, v)
        for name in {v['file'] for v in pack.values()}:
            span = max(v['start'] + v['length'] for v in pack.values() if v['file'] == name)
            bps[name] = os.path.getsize(os.path.join(folder, name)) / max(span, 1)
    for s in samples.values():
        if pack is not None and s['offset'] is not None:
            stem, v = by_off[(os.path.basename(s['file']), s['offset'])]
            s.update(stem=stem, pcm=v['pcm'], packfile=v['file'], length=v['length'], rate=v['rate'], channels=v.get('channels', 1),
                     loop_local=[v['loop'][0] - v['start'], v['loop'][1] - v['start']] if v['loop'] else None,
                     dur=v['length'] / v['rate'], size=int(v['length'] * bps[v['file']]))
        else:
            s['size'] = os.path.getsize(s['file']) if os.path.exists(s['file']) else 0
    return head, list(samples.values())


def _duration(path: str) -> float:
    try:
        return sf.info(path).duration
    except Exception:
        return 0.0


def select(samples: list, pol: dict) -> list:
    """Apply one policy: returns the kept samples with new lo/hi/lovel/hivel set.  The layers of a
    stacked program all sound on every note, so each is thinned on its own."""
    out = []
    for layer in dict.fromkeys(s.get('layer') for s in samples):
        out += _select([s for s in samples if s.get('layer') == layer], pol)
    return out


def _with_layers(lines: list, s: dict, last: list) -> list:
    """``lines`` preceded by the sample's '// layer:' line when the layer changes (``last``: [layer so far])."""
    if s.get('layer') and s['layer'] != last[0]:
        last[0] = s['layer']
        return ['// ' + s['layer']] + lines
    return lines


def _select(samples: list, pol: dict) -> list:
    # 1. round robins: one per (key, velocity window)
    keep = {}
    for s in samples:
        if s['vol'] < -60:                      # silent layer: never worth a file
            continue
        k = (s['key'], s['lovel'], s['hivel'], s['tune'] if s['keyless'] else 0)   # kit layers at other tunings belong to one hit; pitched tunes are per-sample detune
        if pol.get('rr', 99) == 1:
            if k not in keep or (s['seq'], s['rand'], -s['vol']) < (keep[k]['seq'], keep[k]['rand'], -keep[k]['vol']):
                keep[k] = s
        else:
            keep[(k, s['seq'], s['rand'])] = s
    kept = list(keep.values())
    # 2. velocity layers per key
    nv = pol.get('vel')
    by_key = {}
    for s in kept:
        by_key.setdefault(s['key'], []).append(s)
    out = []
    for key, ss in by_key.items():
        wins = sorted({(s['lovel'], s['hivel']) for s in ss})
        if nv and len(wins) > nv:
            # velocity 100 keeps the layer it played before: programs and kit pieces are levelled at 100,
            # and a source's neighbouring layers can be far apart (Sam's Sonor ride: 82-95 is 13 dB under
            # 96-110, and [40, 90, 120] handed velocity 100 to it)
            want = {1: [100], 2: [55, 100], 3: [40, 100, 124], 4: [30, 70, 100, 124]}[nv]
            chosen = []
            for v in want:                  # the window that plays velocity v, else the nearest one
                w = next((w for w in wins if w[0] <= v <= w[1]), None) or min(wins, key=lambda w: abs((w[0] + w[1]) / 2 - v))
                if w not in chosen:
                    chosen.append(w)
            wins_kept = sorted(chosen)
        else:
            wins_kept = wins
        # re-spread the windows over 1..127
        centres = [(a + b) / 2 for a, b in wins_kept]
        new = {}
        for i, w in enumerate(wins_kept):
            lo = 1 if i == 0 else int((centres[i - 1] + centres[i]) / 2) + 1
            hi = 127 if i == len(wins_kept) - 1 else int((centres[i] + centres[i + 1]) / 2)
            new[w] = (lo, hi)
        for s in ss:
            w = (s['lovel'], s['hivel'])
            if w in new:
                s = dict(s); s['lovel2'], s['hivel2'] = new[w]
                out.append(s)
    # 3. key spacing (pitched keys only)
    sp = pol.get('space')
    pitched = sorted({s['key'] for s in out if not s['keyless']})
    if sp and sp > 1 and len(pitched) > 2:
        kept_keys, last = [], -99
        for k in pitched:
            if k - last >= sp:
                kept_keys.append(k); last = k
        if pitched[-1] not in kept_keys and pitched[-1] - kept_keys[-1] >= max(2, sp // 2):
            kept_keys.append(pitched[-1])
        out = [s for s in out if s['keyless'] or s['key'] in kept_keys]
    # re-spread key ranges of the pitched samples
    pitched = sorted({s['key'] for s in out if not s['keyless']})
    lo_all = min((s['lo'] for s in samples if not s['keyless']), default=0)
    hi_all = max((s['hi'] for s in samples if not s['keyless']), default=127)
    rng = {}
    for i, k in enumerate(pitched):
        lo = lo_all if i == 0 else (pitched[i - 1] + k) // 2 + 1
        hi = hi_all if i == len(pitched) - 1 else (k + pitched[i + 1]) // 2
        rng[k] = (lo, hi)
    for s in out:
        if not s['keyless']:
            s['lo2'], s['hi2'] = rng[s['key']]
        else:
            s['lo2'] = s['hi2'] = s['key']
    return out


def _est_size(s: dict, pol: dict) -> int:
    n = s['size']
    max_s = pol.get('max_s')
    if max_s and s.get('dur', 0) > max_s:
        n = int(n * max_s / s['dur'])
    n = int(n * Q_SCALE.get(pol.get('quality', 1.0), 1.0))
    if pol.get('mono') and s.get('channels', 1) > 1:
        n = int(n * 0.79)
    n = int(n / pol.get('rate_div', 1))
    return n


def _rewrite(line: str, s: dict, pos: dict | None = None) -> str:
    """``pos``: the note's new place in the re-packed file (start / length / loop)."""
    if pos is not None:
        line = re.sub(r'sample=\S+', f"sample={pos['file']}", line)
        line = re.sub(r'offset=\d+', f"offset={pos['start']}", line)
        line = re.sub(r'end=\d+', f"end={pos['start'] + pos['length'] - 1}", line)
        if pos['loop']:
            line = re.sub(r'loop_start=\d+', f"loop_start={pos['loop'][0]}", line)
            line = re.sub(r'loop_end=\d+', f"loop_end={pos['loop'][1]}", line)
    line = re.sub(r'lokey=\d+ hikey=\d+', f"lokey={s['lo2']} hikey={s['hi2']}", line)
    line = re.sub(r'lovel=\d+ hivel=\d+', f"lovel={s['lovel2']} hivel={s['hivel2']}", line)
    line = re.sub(r' seq_length=\d+ seq_position=\d+', '', line)
    line = re.sub(r' lorand=\S+ hirand=\S+', '', line)
    return line


def _truncate(src: str, dst: str, max_s: float, quality: float = 1.0) -> None:
    x, fs = sf.read(src, dtype='float64', always_2d=True)
    n = int(max_s * fs)
    if len(x) > n:
        x = x[:n].copy()
        f = min(n, int(0.08 * fs))
        x[-f:] *= np.linspace(1, 0, f)[:, None]
    tmp = dst[:-4] + '.tmp.wav'
    sf.write(tmp, x, fs, subtype='PCM_16')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', tmp, '-c:a', 'libvorbis', '-q:a', str(quality), dst], check=True)
    os.remove(tmp)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=SRC)
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--target-mb', type=float, default=25.0)
    ap.add_argument('-q', '--quality', type=float, default=1.0, help='Vorbis quality when re-packing')
    ap.add_argument('--max-vel', type=int, default=0, help='cap velocity layers everywhere (1 = one layer per key); '
                                                           'the budget it frees goes to the encoder ladder instead')
    ap.add_argument('--codec-step', type=int, default=-1, help='pin the encoder step (index into CODEC) instead of '
                                                               'letting the search choose; the content ladder then does the fitting')
    a = ap.parse_args(argv)
    a.src = paths.bank(a.src)
    a.out = paths.bank(a.out)
    progs = []
    for sfz in sorted(glob.glob(os.path.join(a.src, 'GM', '*.sfz'))):
        head, samples = _read(sfz)
        name = os.path.splitext(os.path.basename(sfz))[0]
        kind = 'kit' if name == 'Drums' else ('sfx' if all(s['keyless'] or any('loop_mode=one_shot' in l for l in s['lines']) for s in samples) else 'pitched')
        if kind != 'pitched':
            for s in samples:
                s['dur'] = _duration(s['file'])
        progs.append(dict(name=name, sfz=sfz, head=head, samples=samples, kind=kind))
    full = sum(s['size'] for p in progs for s in p['samples'])
    def plan_for(rung: int, kit_rung: int, codec: dict | None = None):
        codec = codec or {}
        total, plan = 0, {}
        for p in progs:
            if p['kind'] == 'kit':
                pol = dict(DRUM_LADDER[min(kit_rung, len(DRUM_LADDER) - 1)], **codec)
            elif p['kind'] == 'sfx':
                pol = dict(LADDER[min(rung, len(LADDER) - 1)], max_s=SFX_MAX_S, **codec); pol.pop('space', None)
            else:
                pol = dict(LADDER[min(rung, len(LADDER) - 1)], **codec)
            if a.max_vel:
                pol = dict(pol, vel=min(pol.get('vel', 99), a.max_vel))
            kept = select(p['samples'], pol)
            size = sum(_est_size(s, pol) for s in kept)
            plan[p['name']] = (pol, kept, size)
            total += size
        return plan, total
    # the pitched rung is stepped first; the kit then takes the least aggressive rung that fits the rest.
    # ``scale`` corrects the estimate once a build has been measured (the layers kept are the loudest,
    # so they cost more per sample than the file average the estimate is drawn from).
    cis = [a.codec_step] if a.codec_step >= 0 else range(len(CODEC))
    steps = sorted(((rung + CODEC_DAMAGE[ci], rung, ci) for rung in range(len(LADDER)) for ci in cis))
    def pick(scale: float, quiet: bool = False):
        last = None
        for _, rung, ci in steps:
            for kit_rung in range(len(DRUM_LADDER)):
                plan, total = plan_for(rung, kit_rung, CODEC[ci])
                last = (rung, kit_rung, ci, plan, total)
                if total * scale <= a.target_mb * 1e6:
                    if not quiet:
                        print(f'rung {rung} codec {CODEC[ci] or "q1 stereo"}: kit rung {kit_rung} -> {total * scale / 1e6:.1f} MB', flush=True)
                    return last
            if not quiet:
                print(f'rung {rung} codec {CODEC[ci] or "q1 stereo"}: -> {total * scale / 1e6:.1f} MB', flush=True)
        return last
    rung, kit_rung, ci, plan, total = pick(1.0)
    for attempt in range(4):
        rows, real = _write_bank(progs, plan, a)
        if real <= a.target_mb * 1e6 * 1.02 or attempt == 3:
            break
        scale = real / max(total, 1)
        print(f'built {real / 1e6:.1f} MB against an estimate of {total / 1e6:.1f} MB; re-picking with the measured '
              f'{scale:.2f}x correction', flush=True)
        rung, kit_rung, ci, plan, total = pick(scale, quiet=True)
    from . import extend
    extend.extend_bank(a.out)
    _report(rows, real, full, a, rung, kit_rung, CODEC[ci])
    print(f'wrote {a.out}: {real / 1e6:.1f} MB in {sum(r[3] for r in rows)} files (pitched rung {rung}, kit rung {kit_rung}, codec {CODEC[ci] or "q1 stereo"})')
    return 0


def _write_bank(progs, plan, a):
    """Write the bank for one plan; returns (per-program rows, actual bytes)."""
    shutil.rmtree(a.out, ignore_errors=True)
    os.makedirs(os.path.join(a.out, 'GM'))
    rows, real = [], 0
    for p in progs:
        pol, kept, _ = plan[p['name']]
        folder = os.path.basename(os.path.dirname(kept[0]['file'])) if kept else p['name']
        os.makedirs(os.path.join(a.out, folder), exist_ok=True)
        lines = list(p['head'])
        last_layer = [None]
        if kept and kept[0].get('stem'):                       # packed bank: re-pack what survives
            cache = os.path.join(a.src, '.pcm', folder)
            groups = {}
            for s in kept:
                groups.setdefault(s['packfile'], []).append(s)
            for packfile, group in groups.items():
                entries = []
                for s in group:
                    src = os.path.join(cache, s['pcm'])
                    if not os.path.exists(src):                # no build cache: slice the packed audio (second lossy pass)
                        src = os.path.join(a.out, folder, 'tmp_' + s['pcm'])
                        packing.slice_packed(s['file'], s['offset'], s['length'], src)
                    cap = pol.get('max_s')
                    if not s['loop_local'] and p['kind'] == 'pitched':
                        cap = min(cap or MAX_UNLOOPED_S, MAX_UNLOOPED_S)
                    entries.append(dict(stem=s['stem'], path=src, loop=s['loop_local'], max_s=cap))
                index = packing.pack_notes(entries, os.path.join(a.out, folder, packfile), pol.get('quality', a.quality), mono=pol.get('mono', False), rate_div=pol.get('rate_div', 1))
                for f in glob.glob(os.path.join(a.out, folder, 'tmp_*')):
                    os.remove(f)
                for s in group:
                    pos = dict(index[s['stem']], file=packfile)
                    lines += _with_layers([_rewrite(l, s, pos) for l in s['lines']], s, last_layer)
            real += sum(os.path.getsize(os.path.join(a.out, folder, f)) for f in groups)
        else:
            for s in kept:
                dst = os.path.join(a.out, folder, os.path.basename(s['file']))
                if pol.get('max_s') and s.get('dur', 0) > pol['max_s']:
                    _truncate(s['file'], dst, pol['max_s'])
                else:
                    shutil.copy2(s['file'], dst)
                real += os.path.getsize(dst)
                lines += _with_layers([_rewrite(l, s) for l in s['lines']], s, last_layer)
        with open(os.path.join(a.out, 'GM', p['name'] + '.sfz'), 'w') as fh:
            fh.write('\n'.join(lines) + '\n')
        keys = len({s['key'] for s in kept}); vels = max((len({(s['lovel2'], s['hivel2']) for s in kept if s['key'] == k}) for k in {s['key'] for s in kept}), default=0)
        after = sum(os.path.getsize(os.path.join(a.out, folder, f)) for f in os.listdir(os.path.join(a.out, folder)) if f.endswith('.ogg'))
        rows.append((p['name'], p['kind'], len(p['samples']), len(kept), keys, vels, sum(s['size'] for s in p['samples']) / 1e6, after / 1e6))
    return rows, real


def _report(rows, real, full, a, rung, kit_rung, codec):
    md = ['# Slim bank', '', f'From the compressed bank ({full / 1e6:.1f} MB) by dropping and truncating only, target {a.target_mb:g} MB.  '
          f'Rung {rung}: pitched programs {LADDER[min(rung, len(LADDER) - 1)]}, kit (rung {kit_rung}) {DRUM_LADDER[min(kit_rung, len(DRUM_LADDER) - 1)]}, one-shot effects '
          f'truncated to {SFX_MAX_S} s; encoder {codec or "Vorbis q1, source channels"}.  Velocity windows and key ranges re-spread over what is kept.', '',
          '| program | kind | files before | files after | keys | vel layers | MB before | MB after |', '|---|---|---|---|---|---|---|---|']
    md += [f'| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]:.2f} | {r[7]:.2f} |' for r in rows]
    md += ['', f'**Total {real / 1e6:.1f} MB in {sum(r[3] for r in rows)} files (from {full / 1e6:.1f} MB in {sum(r[2] for r in rows)}).**']
    with open(os.path.join(a.out, 'SIZES.md'), 'w') as fh:
        fh.write('\n'.join(md) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
