"""kobi.drums — a General MIDI drum kit (keys 35-81) assembled from the sources.

The Muldjord kit (FreePats, CC BY 4.0) is a real recorded kit but maps its pieces to its own keys
48-66; here its kick, snares, hi-hats, rides, crashes, china and toms are moved to their GM keys.
The auxiliary percussion (claps, tambourine, cowbell, bongos, congas, agogo, cabasa, shaker,
whistle, guiro, claves, wood blocks, triangle ...) comes from VCSL, chosen by the articulation
words in the file names; a few GM sounds no source has get a marked stand-in.  Every key is then
level-matched (velocity-100 hit, K-weighted max momentary loudness) to one target plus a small
per-family offset, so hats do not drown the snare.

    python3 -m kobi.drums [-o demo/GM/Drums.sfz]      -> Drums.sfz + DRUMS.md coverage table
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

import numpy as np

from .demo import FS, render
from .gm_map import ROOT
from .ingest import Region, default_view, load_folder, load_sfz, _MICS, _cc_default, _num
import re
from .levels import momentary_max_lufs
from . import paths

GM_DRUMS = {35: 'Acoustic Bass Drum', 36: 'Bass Drum 1', 37: 'Side Stick', 38: 'Acoustic Snare', 39: 'Hand Clap',
            40: 'Electric Snare', 41: 'Low Floor Tom', 42: 'Closed Hi-Hat', 43: 'High Floor Tom', 44: 'Pedal Hi-Hat',
            45: 'Low Tom', 46: 'Open Hi-Hat', 47: 'Low-Mid Tom', 48: 'Hi-Mid Tom', 49: 'Crash Cymbal 1', 50: 'High Tom',
            51: 'Ride Cymbal 1', 52: 'Chinese Cymbal', 53: 'Ride Bell', 54: 'Tambourine', 55: 'Splash Cymbal', 56: 'Cowbell',
            57: 'Crash Cymbal 2', 58: 'Vibraslap', 59: 'Ride Cymbal 2', 60: 'Hi Bongo', 61: 'Low Bongo', 62: 'Mute Hi Conga',
            63: 'Open Hi Conga', 64: 'Low Conga', 65: 'High Timbale', 66: 'Low Timbale', 67: 'High Agogo', 68: 'Low Agogo',
            69: 'Cabasa', 70: 'Maracas', 71: 'Short Whistle', 72: 'Long Whistle', 73: 'Short Guiro', 74: 'Long Guiro',
            75: 'Claves', 76: 'Hi Wood Block', 77: 'Low Wood Block', 78: 'Mute Cuica', 79: 'Open Cuica', 80: 'Mute Triangle',
            81: 'Open Triangle'}

MULDJORD = os.path.join(ROOT, 'FreePats/Percussion/MuldjordKit/MuldjordKit SFZ+FLAC-20201018/MuldjordKit 20201018.sfz')
BIGRUSTY_ROOT = os.path.join(ROOT, 'Karoryfer/Big_Rusty_Drums_1100')
BIGRUSTY = os.path.join(BIGRUSTY_ROOT, 'Programs/01-full.sfz')
IDIO = 'VCSL/Idiophones/Struck Idiophones/'
MEMB = 'VCSL/Membranophones/Struck Membranophones/'

# level offsets per family (dB) on top of the common target
OFFSET = {'hat': -5.0, 'cymbal': -3.0, 'shaker': -4.0, 'aux': -2.0, 'kick': +1.0, 'snare': 0.0, 'tom': -1.0}


@dataclass
class Piece:
    source: str                 # 'Muldjord' | 'BigRusty' | 'VCSL' | 'VSCO2'
    path: str                   # Muldjord: sample folder name; BigRusty: its own key number; folders: path under uncompressed/
    tags: tuple = ()            # folder sources: words every file must carry ('short*' = prefix)
    tune: float = 0.0           # semitones
    family: str = 'aux'
    standin: bool = False


def M(folder, tune=0.0, family='snare'):
    return Piece('Muldjord', folder, (), tune, family)


def V(path, tags=(), tune=0.0, family='aux', standin=False):
    return Piece('VCSL', path, tuple(tags), tune, family, standin)


def B(key, tune=0.0, family='snare', standin=False):
    return Piece('BigRusty', str(key), (), tune, family, standin)


# Big Rusty Drums (Karoryfer, CC0): kick, side stick, snare, rimshot, toms, hi-hats, crash, ride and bell already
# sit on their GM keys; china (57), sizzle crash (65) and sizzle ride (60) move to 52, 57 and 59
BIGRUSTY_CORE = {
    35: [B(35, family='kick')], 36: [B(36, family='kick')], 37: [B(37)], 38: [B(38)], 40: [B(40)],
    41: [B(41, family='tom')], 42: [B(42, family='hat')], 43: [B(43, family='tom')], 44: [B(44, family='hat')],
    45: [B(45, family='tom')], 46: [B(46, family='hat')], 47: [B(47, family='tom')], 48: [B(47, 2, 'tom')],
    49: [B(49, family='cymbal')], 50: [B(47, 4, 'tom')], 51: [B(51, family='cymbal')], 52: [B(57, family='cymbal')],
    53: [B(53, family='cymbal')], 55: [B(65, 3, 'cymbal', True)], 57: [B(65, family='cymbal')], 59: [B(60, family='cymbal')],
}


KIT = {
    35: [M('KdrumL', family='kick')],
    36: [M('KdrumR', family='kick')],
    37: [V(MEMB + 'Snare Drum, Modern 3', ('xstick',)), V(MEMB + 'Snare Drum, Modern 2', ('xstick',))],
    38: [M('Snare1')],
    39: [V(IDIO + 'Claps', ('clap',))],
    40: [M('Snare2')],
    41: [M('Tom4', -2, 'tom')],
    42: [M('HihatClosed', family='hat')],
    43: [M('Tom4', 0, 'tom')],
    44: [M('HihatClosed', 0, 'hat')],
    45: [M('Tom3', 0, 'tom')],
    46: [M('HihatOpen', family='hat')],
    47: [M('Tom2', 0, 'tom')],
    48: [M('Tom1', -2, 'tom')],
    49: [M('CrashL', family='cymbal')],
    50: [M('Tom1', 0, 'tom')],
    51: [M('RideL', family='cymbal')],
    52: [M('China', family='cymbal')],
    53: [M('RideRBell', family='cymbal')],
    54: [V(IDIO + 'Tambourine 1', ('hit',))],
    55: [Piece('Muldjord', 'CrashR', (), 6.0, 'cymbal', True)],
    56: [V(IDIO + 'Cowbells', ('cowbell1', 'normal'))],
    57: [M('CrashR', family='cymbal')],
    58: [V(IDIO + 'Vibraslap', ())],
    59: [M('RideR', family='cymbal')],
    60: [V(MEMB + 'Bongos', ('bongoh', 'hit1'))],
    61: [V(MEMB + 'Bongos', ('bongol', 'hit1'))],
    62: [V(MEMB + 'Conga', ('quinto', 'hitfm*')), V(MEMB + 'Conga', ('conga', 'hitfm*')), V(MEMB + 'Conga', ('hitfm*',))],
    63: [V(MEMB + 'Conga', ('quinto', 'hitn'))],
    64: [V(MEMB + 'Conga', ('tumba', 'hitn'))],
    65: [V(MEMB + 'Tom 1', ('rims',), standin=True)],
    66: [V(MEMB + 'Tom 2', ('rims',), standin=True)],
    67: [V(IDIO + 'Agogo Bells', ('high',))],
    68: [V(IDIO + 'Agogo Bells', ('low',))],
    69: [V(IDIO + 'Cabasa', ('rub',), family='shaker')],
    70: [V(IDIO + 'Shaker, Small', ('shaker',), family='shaker')],
    71: [V('VCSL/Aerophones/Edge-blown Aerophones/Ball Whistle', ('short',))],
    72: [V('VCSL/Aerophones/Edge-blown Aerophones/Ball Whistle', ('long',))],
    73: [V(IDIO + 'Guiro', ('short*',))],
    74: [V(IDIO + 'Guiro', ('long*',))],
    75: [V(IDIO + 'Claves', ('claves1',))],
    76: [V(IDIO + 'Woodblock', ('click*',))],
    77: [V(IDIO + 'Slit Drum', ('logdrumlo',))],
    78: [V(IDIO + 'Flexatone', ('slap*',), standin=True)],
    79: [V(IDIO + 'Flexatone', ('long',), standin=True)],
    80: [V(IDIO + 'Triangles', ('triangle1', 'hitm'))],
    81: [V(IDIO + 'Triangles', ('triangle1', 'hit'))],
}
assert set(KIT) == set(GM_DRUMS)

_muldjord_cache = None


def _muldjord_regions(folder: str) -> list:
    global _muldjord_cache
    if _muldjord_cache is None:
        _muldjord_cache = default_view(load_sfz(MULDJORD))
    return [r for r in _muldjord_cache if os.path.basename(os.path.dirname(r.sample)) == folder]


_bigrusty_cache = None          # (playable regions, control opcodes)


def _bigrusty():
    global _bigrusty_cache
    if _bigrusty_cache is None:
        inst = load_sfz(BIGRUSTY, search_root=BIGRUSTY_ROOT)
        _bigrusty_cache = (default_view(inst), inst.control)
    return _bigrusty_cache


def _bigrusty_regions(key: int) -> list:
    return [r for r in _bigrusty()[0] if r.lokey <= key <= r.hikey]


def _bigrusty_control() -> dict:
    return _bigrusty()[1]


_AMP_CC = re.compile(r'^amplitude_(?:on)?cc(\d+)$')


def static_amplitude_db(r: Region, control: dict) -> float:
    """Gain in dB that sfizz applies to the region from its amplitude opcodes at the file's default
    controller values: ``amplitude`` (percent) times each ``amplitude_ccN`` depth scaled by the
    controller (multiplicative, as sfizz and ARIA do it) - Big Rusty's per-mic faders."""
    g = _num(r.opcodes.get('amplitude'), 100.0) / 100.0
    for k, v in r.opcodes.items():
        m = _AMP_CC.match(k)
        if m:
            g *= _num(v, 100.0) / 100.0 * _cc_default(int(m.group(1)), control) / 127.0
    return 20 * np.log10(g) if g > 1e-6 else -120.0


def _tag_ok(region: Region, tags: tuple) -> bool:
    rt = set(region.tags)
    for t in tags:
        if t.endswith('*'):
            if not any(x.startswith(t[:-1]) for x in rt):
                return False
        elif t not in rt:
            return False
    return True


SILENT_DB = -60.0      # mic layers whose fader defaults to zero (Big Rusty 'snap' / 'epic') are left out


def piece_regions(p: Piece) -> list:
    if p.source == 'Muldjord':
        regs = _muldjord_regions(p.path)
    elif p.source == 'BigRusty':
        regs = [r for r in _bigrusty_regions(int(p.path)) if r.volume_db + static_amplitude_db(r, _bigrusty_control()) > SILENT_DB]
    else:
        inst = load_folder(os.path.join(ROOT, p.path), source=p.source)
        regs = [r for r in default_view(inst) if _tag_ok(r, p.tags)]
    return regs


def _region_line(r: Region, key: int, tune: float, gain_db: float) -> str:
    op = [f'<region> sample={r.sample}', f'key={key} pitch_keytrack=0 loop_mode=one_shot lovel={r.lovel} hivel={r.hivel}']
    t = r.tune + 100 * tune
    if abs(t) > 0.01:
        op.append(f'tune={t:g}')
    vol = r.volume_db + gain_db + (static_amplitude_db(r, _bigrusty_control()) if any(_AMP_CC.match(k) for k in r.opcodes) or 'amplitude' in r.opcodes else 0.0)
    if abs(vol) > 0.01:
        op.append(f'volume={vol:.1f}')
    if r.seq_length > 1:
        op.append(f'seq_length={r.seq_length} seq_position={r.seq_position}')
    if r.lorand > 0 or r.hirand < 1:
        op.append(f'lorand={r.lorand:g} hirand={r.hirand:g}')
    for k in ('amp_veltrack', 'amp_velcurve_1', 'amp_velcurve_127', 'offset', 'pan', 'ampeg_hold', 'ampeg_decay', 'ampeg_sustain'):
        if k in r.opcodes:
            op.append(f'{k}={r.opcodes[k]}')
    return ' '.join(op)


def _measure_key(lines: list, key: int) -> float:
    tmp = '/tmp/claude-1000/kobi_drum_measure.sfz'
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    with open(tmp, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    y = render(tmp, [(0.0, 'on', key, 100), (0.5, 'off', key, 0)], 1.5)
    return momentary_max_lufs(y, FS)


def verify_bigrusty(key: int = 38) -> float:
    """dB difference between sfizz rendering the original Big Rusty program and our extracted regions
    for one hit: checks the static fader model."""
    from .levels import momentary_max_lufs
    ref = momentary_max_lufs(render(BIGRUSTY, [(0.0, 'on', key, 100), (0.5, 'off', key, 0)], 1.5), FS)
    lines = ['<global> ampeg_release=0.1'] + [_region_line(r, key, 0.0, 0.0) for r in _bigrusty_regions(key)]
    return _measure_key(lines, key) - ref


def build(out: str, target: float = -23.0, max_gain: float = 40.0, core: str = 'bigrusty') -> list:
    kit = dict(KIT)
    if core == 'bigrusty':
        kit.update(BIGRUSTY_CORE)
        for key in (38, 42, 49):
            print(f'  fader model check, key {key}: extracted - original = {verify_bigrusty(key):+.2f} dB', flush=True)
    rows, lines = [], [f'// kobi GM drum kit: {"Big Rusty Drums (Karoryfer, CC0)" if core == "bigrusty" else "Muldjord kit (FreePats, CC BY 4.0)"} '
                       'remapped to GM keys + VCSL percussion (CC0)', '<global> ampeg_release=0.1']
    for key, cands in kit.items():
        chosen, regs = None, []
        for p in cands:
            regs = piece_regions(p)
            if regs:
                chosen = p
                break
        if not regs:
            rows.append(dict(key=key, name=GM_DRUMS[key], source='MISSING', regions=0, lufs=-np.inf, gain=0.0, standin=False, piece=''))
            continue
        raw = [_region_line(r, key, chosen.tune, 0.0) for r in regs]
        lufs = _measure_key(lines[:2] + raw, key)
        gain = 0.0 if not np.isfinite(lufs) else float(np.clip(target + OFFSET.get(chosen.family, 0.0) - lufs, -max_gain, max_gain))
        lines += [f'// {key} {GM_DRUMS[key]}: {chosen.source} {chosen.path.split("/")[-1]} {" ".join(chosen.tags)} '
                  f'({len(regs)} regions, {lufs:.1f} LUFS, gain {gain:+.1f} dB)'] + [_region_line(r, key, chosen.tune, gain) for r in regs]
        vels = len({(r.lovel, r.hivel) for r in regs})
        rr = max(r.seq_length for r in regs)
        rows.append(dict(key=key, name=GM_DRUMS[key], source=chosen.source, piece=chosen.path.split('/')[-1] + (' ' + ' '.join(chosen.tags) if chosen.tags else ''),
                         regions=len(regs), vels=vels, rr=rr, lufs=lufs, gain=gain, standin=chosen.standin, tune=chosen.tune))
        print(f"{key:3d} {GM_DRUMS[key]:20s} {chosen.source:9s} {rows[-1]['piece'][:34]:34s} {len(regs):3d} rgn  {vels} vel  rr{rr}  "
              f"{lufs:6.1f} LUFS  gain {gain:+5.1f}{'  stand-in' if chosen.standin else ''}", flush=True)
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    with open(out, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    md = ['# GM drum kit', '', f'`{out}`: every GM key 35-81.  Core: {core}; '
          f'VCSL (CC0) for the auxiliary percussion.  Each key level-matched to {target:g} LUFS plus a family offset '
          f'({", ".join(f"{k} {v:+g}" for k, v in OFFSET.items())}).', '',
          '| key | GM name | source | piece | regions | vel layers | rr | raw LUFS | gain dB | stand-in |', '|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        md.append(f"| {r['key']} | {r['name']} | {r['source']} | {r['piece']} | {r['regions']} | {r.get('vels', 0)} | {r.get('rr', 0)} | "
                  f"{r['lufs']:.1f} | {r['gain']:+.1f} | {'yes' if r['standin'] else ''} |")
    with open(os.path.join(os.path.dirname(out) or '.', 'DRUMS.md'), 'w') as fh:
        fh.write('\n'.join(md) + '\n')
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('-o', '--out', default=os.path.join(paths.ROOT, 'demo', 'GM', 'Drums.sfz'))
    ap.add_argument('-t', '--target', type=float, default=-23.0)
    ap.add_argument('--core', choices=('bigrusty', 'muldjord'), default='bigrusty')
    a = ap.parse_args(argv)
    rows = build(a.out, a.target, core=a.core)
    missing = [r for r in rows if r['source'] == 'MISSING']
    print(f"{len(rows) - len(missing)}/{len(rows)} GM keys covered, {sum(1 for r in rows if r['standin'])} stand-ins; wrote {a.out}")
    return 1 if missing else 0


if __name__ == '__main__':
    raise SystemExit(main())
