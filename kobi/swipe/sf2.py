"""kobi.swipe.sf2 — extract a SoundFont 2 preset into an SFZ instrument (samples as WAV).

Taken from sfz-compress (sfz_compress/sf2.py, same author) so the swipe app can offer the open GM
soundfonts (FluidR3 GM, MS Basic, TimGM6mb) as versions of every program.

Resolves the SF2 generator model into explicit SFZ regions: instrument-zone
generators override the instrument's global zone, preset-zone generators add
to them (ranges intersect), and everything is written out fully resolved.
Regions are grouped per (instrument, velocity range) so a velocity layer is
one ``<group>`` — the layout the compressor's dropout planner understands.

    python3 -m kobi.swipe.sf2 bank.sf2 --program 40 -o out/Violin
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

# SF2 generator operators used here.
G_START = 0; G_END = 1; G_STARTLOOP = 2; G_ENDLOOP = 3; G_START_COARSE = 4
G_CUTOFF = 8; G_FILTER_Q = 9; G_PAN = 17
G_DELAY = 33; G_ATTACK = 34; G_HOLD = 35; G_DECAY = 36; G_SUSTAIN = 37; G_RELEASE = 38
G_KEYRANGE = 43; G_VELRANGE = 44; G_STARTLOOP_COARSE = 45; G_ATTEN = 48
G_ENDLOOP_COARSE = 50; G_COARSE_TUNE = 51; G_FINE_TUNE = 52; G_SAMPLE_MODES = 54
G_SCALE_TUNING = 56; G_EXCLUSIVE = 57; G_ROOT_KEY = 58
_RANGE_GENS = (G_KEYRANGE, G_VELRANGE)
_NON_ADDITIVE = (G_SAMPLE_MODES, G_EXCLUSIVE, G_ROOT_KEY, 41, 53)


def _tc_to_s(tc: float) -> float:
    return 2.0 ** (tc / 1200.0)


def _gens_of(bag) -> dict[int, int]:
    """Signed generator amounts of a zone (ranges excluded)."""
    out = {}
    for oper, g in bag.gens.items():
        if oper in _RANGE_GENS:
            continue
        out[oper] = g.word if oper == G_SAMPLE_MODES else g.short
    return out


def _range_of(bag, oper, default):
    g = bag.gens.get(oper)
    if g is None:
        return default
    lo, hi = g.amount_as_sorted_range
    return (int(lo), int(hi))


def _intersect(a, b):
    return (max(a[0], b[0]), min(a[1], b[1]))


def list_presets(sf2_path) -> list[tuple[int, int, str]]:
    from sf2utils.sf2parse import Sf2File
    with open(sf2_path, "rb") as f:
        sf2 = Sf2File(f)
        return [(p.bank, p.preset, p.name) for p in sf2.presets
                if hasattr(p, "bank") and p.name != "EOP"]


def extract_preset(sf2_path, out_dir, program: int, bank: int = 0,
                   name: str | None = None) -> Path:
    """Write ``<out_dir>/<name>.sfz`` + ``samples/*.wav`` for one preset."""
    from sf2utils.sf2parse import Sf2File

    out_dir = Path(out_dir)
    samples_dir = out_dir / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)

    with open(sf2_path, "rb") as f:
        sf2 = Sf2File(f)
        preset = next((p for p in sf2.presets
                       if getattr(p, "bank", None) == bank and getattr(p, "preset", None) == program), None)
        if preset is None:
            raise KeyError(f"preset bank {bank} program {program} not in {sf2_path}")
        inst_name = name or preset.name.strip()

        # Preset zones: an optional global zone (no instrument) + instrument zones.
        p_global = {}
        p_zones = []
        for bag in preset.bags:
            if bag.instrument is None:
                if not p_zones:
                    p_global = _gens_of(bag)
                continue
            p_zones.append(bag)

        written: dict[int, str] = {}   # id(sample) -> file name
        regions: list[dict] = []

        for pz in p_zones:
            p_gens = dict(p_global); p_gens.update(_gens_of(pz))
            p_key = _range_of(pz, G_KEYRANGE, (0, 127))
            p_vel = _range_of(pz, G_VELRANGE, (0, 127))
            inst = pz.instrument

            i_global = {}
            i_zones = []
            for bag in inst.bags:
                if bag.sample is None:
                    if not i_zones:
                        i_global = _gens_of(bag)
                    continue
                i_zones.append(bag)
            i_gkey = _range_of(inst.bags[0], G_KEYRANGE, (0, 127)) if inst.bags and inst.bags[0].sample is None else (0, 127)
            i_gvel = _range_of(inst.bags[0], G_VELRANGE, (0, 127)) if inst.bags and inst.bags[0].sample is None else (0, 127)

            for iz in i_zones:
                s = iz.sample
                if s is None or s.end - s.start < 48:
                    continue
                gens = dict(i_global); gens.update(_gens_of(iz))
                # Preset generators are additive offsets.
                for oper, amt in p_gens.items():
                    if oper in _NON_ADDITIVE:
                        continue
                    gens[oper] = gens.get(oper, 0) + amt
                key = _intersect(_intersect(_range_of(iz, G_KEYRANGE, i_gkey), p_key), (0, 127))
                vel = _intersect(_intersect(_range_of(iz, G_VELRANGE, i_gvel), p_vel), (0, 127))
                if key[0] > key[1] or vel[0] > vel[1]:
                    continue

                # Sample file (once per SF2 sample, at its own rate).
                sid = id(s)
                if sid not in written:
                    fname = re.sub(r"[^A-Za-z0-9_.-]+", "_", s.name.strip()) or f"sample{len(written)}"
                    base = fname
                    n = 1
                    while fname + ".wav" in written.values():
                        n += 1
                        fname = f"{base}_{n}"
                    data = np.frombuffer(s.raw_sample_data, dtype="<i2")
                    sf.write(str(samples_dir / (fname + ".wav")), data, s.sample_rate, subtype="PCM_16")
                    written[sid] = fname + ".wav"
                fname = written[sid]

                r = {"sample": fname, "lokey": key[0], "hikey": key[1],
                     "lovel": vel[0], "hivel": vel[1]}
                root = gens.get(G_ROOT_KEY)
                r["pitch_keycenter"] = int(root) if root is not None and 0 <= root <= 127 else int(s.original_pitch)
                tune = gens.get(G_FINE_TUNE, 0) + int(s.pitch_correction)
                if tune:
                    r["tune"] = int(tune)
                if gens.get(G_COARSE_TUNE):
                    r["transpose"] = int(gens[G_COARSE_TUNE])
                if gens.get(G_SCALE_TUNING, 100) != 100:
                    r["pitch_keytrack"] = int(gens[G_SCALE_TUNING])

                modes = gens.get(G_SAMPLE_MODES, 0) & 3
                if modes in (1, 3):
                    ls = s.start_loop + gens.get(G_STARTLOOP, 0) + 32768 * gens.get(G_STARTLOOP_COARSE, 0)
                    le = s.end_loop + gens.get(G_ENDLOOP, 0) + 32768 * gens.get(G_ENDLOOP_COARSE, 0)
                    n_frames = s.end - s.start
                    ls, le = max(int(ls), 0), min(int(le), n_frames)
                    if le - ls >= 2:
                        r["loop_mode"] = "loop_continuous" if modes == 1 else "loop_sustain"
                        r["loop_start"] = ls
                        r["loop_end"] = le - 1   # SF2 end is exclusive, SFZ inclusive
                offset = gens.get(G_START, 0) + 32768 * gens.get(G_START_COARSE, 0)
                if offset > 0:
                    r["offset"] = int(offset)

                # initialAttenuation (cB): players clamp it to >= 0 and, by
                # long-standing EMU convention, apply only 0.4 of it.
                atten = max(gens.get(G_ATTEN, 0), 0) * 0.4
                if atten:
                    r["volume"] = round(-atten / 10.0, 2)
                pan = gens.get(G_PAN, 0)
                if pan:
                    r["pan"] = round(max(min(pan / 5.0, 100.0), -100.0), 1)

                # Volume envelope (SF2 defaults: -12000 tc ~ 1 ms).
                def env(oper, default_tc=-12000):
                    return round(_tc_to_s(gens.get(oper, default_tc)), 4)
                delay, attack, hold = env(G_DELAY), env(G_ATTACK), env(G_HOLD)
                decay, release = env(G_DECAY), env(G_RELEASE)
                sus_cb = max(gens.get(G_SUSTAIN, 0), 0)
                sustain = 100.0 * 10 ** (-sus_cb / 200.0)
                if delay > 0.002:
                    r["ampeg_delay"] = delay
                if attack > 0.002:
                    r["ampeg_attack"] = attack
                if hold > 0.002:
                    r["ampeg_hold"] = hold
                if decay > 0.002 or sustain < 99.9:
                    r["ampeg_decay"] = decay
                    r["ampeg_sustain"] = round(sustain, 1)
                r["ampeg_release"] = max(release, 0.005)

                fc = gens.get(G_CUTOFF)
                if fc is not None and fc < 13500:
                    r["fil_type"] = "lpf_2p"
                    r["cutoff"] = round(8.176 * 2 ** (fc / 1200.0), 1)
                    q = gens.get(G_FILTER_Q, 0)
                    if q:
                        r["resonance"] = round(q / 10.0, 1)
                excl = gens.get(G_EXCLUSIVE, 0)
                if excl:
                    r["group"] = int(excl)
                    r["off_by"] = int(excl)
                r["_layer"] = (inst.name.strip(), vel)
                regions.append(r)

    if not regions:
        raise ValueError(f"preset {inst_name}: no usable zones")

    # Group by (instrument, velocity range) so a layer is one <group>.
    lines = [f"// {inst_name} — extracted from {Path(sf2_path).name} (bank {bank}, program {program})",
             "<control> default_path=samples/", ""]
    layers: dict = {}
    for r in regions:
        layers.setdefault(r["_layer"], []).append(r)
    for (iname, vel), rs in layers.items():
        label = re.sub(r'\s+', '_', iname)
        lines.append(f"<group> lovel={vel[0]} hivel={vel[1]} group_label={label}")
        for r in sorted(rs, key=lambda x: (x["lokey"], x["lovel"])):
            opc = " ".join(f"{k}={v}" for k, v in r.items()
                           if not k.startswith("_") and k not in ("lovel", "hivel"))
            lines.append(f"<region> {opc}")
        lines.append("")
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", inst_name).strip("_") or f"program{program}"
    sfz_path = out_dir / f"{safe}.sfz"
    sfz_path.write_text("\n".join(lines) + "\n")
    logger.info("extracted %s: %d regions, %d samples", inst_name, len(regions), len(written))
    return sfz_path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Extract an SF2 preset to SFZ")
    ap.add_argument("sf2", type=Path)
    ap.add_argument("--program", type=int, required=True)
    ap.add_argument("--bank", type=int, default=0)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--name", default=None)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print(extract_preset(args.sf2, args.output, args.program, args.bank, args.name))


if __name__ == "__main__":
    main()
