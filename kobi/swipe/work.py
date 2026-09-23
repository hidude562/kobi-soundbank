"""kobi.swipe.work — the CPU-heavy steps, run in a process pool so the server stays responsive.

``render_preview`` plays a phrase through sfizz, levels it to a common loudness (so the louder of
two cards does not win by being louder), and writes FLAC + MP3 next to a small waveform sketch.
``detect_offsets`` is the pitch audit's pYIN reading on a few samples.
"""
from __future__ import annotations

import os
import subprocess

TARGET_LUFS = -16.0          # loudest 400 ms window of every preview
PEAK = 0.891                 # -1 dBFS


def _peaks(x, bins: int = 120) -> list:
    import numpy as np
    m = np.abs(x).max(axis=1)
    edges = np.linspace(0, len(m), bins + 1).astype(int)
    return [round(float(m[a:b].max()) if b > a else 0.0, 3) for a, b in zip(edges[:-1], edges[1:])]


def render_preview(sfz: str, events: list, secs: float, out_base: str) -> dict:
    import numpy as np
    import soundfile as sf
    from ..demo import FS, render
    from ..levels import momentary_max_lufs
    x = render(sfz, events, secs)
    raw_peak = float(np.abs(x).max()) if len(x) else 0.0
    if raw_peak < 1e-5:
        raise RuntimeError('the phrase rendered silent')
    lufs = momentary_max_lufs(x, FS)
    gain = TARGET_LUFS - lufs
    x = x * (10 ** (gain / 20))
    pk = float(np.abs(x).max())
    if pk > PEAK:
        x *= PEAK / pk
    fade = int(0.03 * FS)
    x[-fade:] *= np.linspace(1.0, 0.0, fade)[:, None]
    os.makedirs(os.path.dirname(out_base), exist_ok=True)
    sf.write(out_base + '.flac', x.astype('float32'), FS, subtype='PCM_16')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', out_base + '.flac', '-c:a', 'libmp3lame', '-b:a', '192k',
                    out_base + '.mp3'], check=True)
    return dict(lufs=round(lufs, 1), gain_db=round(gain, 1), raw_peak_db=round(20 * np.log10(raw_peak), 1),
                secs=round(len(x) / FS, 2), wave=_peaks(x), f0=_first_note(x, FS, events))


def _first_note(x, fs: int, events: list):
    """Median pYIN pitch (MIDI) of the phrase's first note, which sounds alone; None when unvoiced."""
    import warnings
    import numpy as np
    import librosa
    on = sorted(t for t, ty, *_ in events if ty == 'on')
    if len(on) < 2 or on[1] - on[0] < 0.25:
        return None
    warnings.filterwarnings('ignore')
    seg = x[int((on[0] + 0.03) * fs):int(on[1] * fs)].mean(axis=1)
    seg = librosa.resample(seg, orig_sr=fs, target_sr=22050)
    f0, _, vp = librosa.pyin(seg, fmin=25, fmax=4200, sr=22050, frame_length=2048, hop_length=256)
    ok = np.isfinite(f0) & (vp > 0.3)
    return round(float(69 + 12 * np.log2(np.median(f0[ok]) / 440)), 2) if ok.sum() >= 3 else None


def detect_offsets(items: list) -> list:
    """[(sample path, key centre, tune cents)] -> detected pitch minus claimed key, per item (None: unvoiced)."""
    from ..pitch_audit import detect_midi
    out = []
    for path, key, tune in items:
        try:
            m = detect_midi(path)
        except Exception:
            m = None
        out.append(None if m is None else m - tune / 100 - key)
    return out
