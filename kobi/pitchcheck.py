"""kobi.pitchcheck — what a note really sounds like, from two detectors that must agree.

A library's key map is not always right (the Discord GM pizzicato's top three files sound about
4 semitones above their names), and kobi.compress only searches +-51 cents around the mapped
pitch, so such a note kept its wrong key — and a loop built on the wrong period.  ``measure``
reads the note twice, with pYIN (octave-folded; a reading on the search bound is a miss) and
with subharmonic summation over +-7 semitones of the expected pitch, and only reports a pitch
when the two agree.  Unpitched and inharmonic sounds (drums, bells, timpani, noise) mostly come
out as "no agreement", which callers treat as "trust the map".
"""
from __future__ import annotations

import warnings

import numpy as np

AGREE_CENTS = 30.0         # the two detectors within this of each other
SEARCH_CENTS = 700.0       # the summation looks this far either side of the expected pitch


def _mono(x: np.ndarray) -> np.ndarray:
    return x.mean(axis=1) if x.ndim == 2 else x


def shs_cents(x: np.ndarray, fs: int, want: float) -> float | None:
    """Subharmonic summation: cents from ``want`` of the f0 whose first 8 harmonics carry the most
    energy (dB above a -60 dB floor, harmonic h weighted 0.84^(h-1))."""
    seg = x[:int(0.5 * fs)]
    if len(seg) < int(0.05 * fs) or np.abs(seg).max() < 1e-5:
        return None
    n = 1 << 17
    mag = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), n))
    s = np.clip(20 * np.log10(mag / mag.max() + 1e-9) + 60, 0, None)
    fr = np.fft.rfftfreq(n, 1 / fs)
    cs = np.arange(-SEARCH_CENTS, SEARCH_CENTS + 1, 2.0)
    f0s = want * 2 ** (cs / 1200)
    score = np.zeros(len(cs))
    for h in range(1, 9):
        fh = f0s * h
        ok = fh < fs / 2 - 200
        score[ok] += 0.84 ** (h - 1) * np.interp(fh[ok], fr, s)
    return float(cs[int(np.argmax(score))])


def pyin_cents(x: np.ndarray, fs: int, want: float) -> float | None:
    """Median pYIN pitch, cents from ``want`` folded into +-600 (the octave is not the question here)."""
    import librosa
    warnings.filterwarnings('ignore')
    lo, hi = max(25.0, want / 2.3), min(fs / 2 - 100, want * 2.3)
    frame = 4096 if want < 150 else 2048
    while lo < 2 * fs / frame and frame < 16384:       # librosa needs two periods of fmin per frame
        frame *= 2
    if len(x) < frame * 2 or np.abs(x).max() < 1e-5:
        return None
    f, voiced, _ = librosa.pyin(x, fmin=lo, fmax=hi, sr=fs, frame_length=frame)
    good = f[voiced & np.isfinite(f)]
    good = good[(good > lo * 1.03) & (good < hi / 1.03)]
    if len(good) < 3:
        return None
    c = 1200 * np.log2(float(np.median(good)) / want)
    return float(c - 1200 * np.round(c / 1200))


def measure(x: np.ndarray, fs: int, want: float, start: float = 0.03, dur: float = 0.67) -> dict:
    """``x``: a note from its onset.  Returns dict(pyin, shs, cents): ``cents`` is the agreed deviation
    from ``want`` (their mean), or None when the detectors disagree or find nothing."""
    m = _mono(np.asarray(x, dtype=np.float32))
    m = m[int(start * fs):int((start + dur) * fs)]
    p = pyin_cents(m, fs, want)
    h = shs_cents(m, fs, want)
    ok = p is not None and h is not None and abs(p - h) <= AGREE_CENTS
    return dict(pyin=p, shs=h, cents=(p + h) / 2 if ok else None)


def deviation(x: np.ndarray, fs: int, want: float, gate: float = 30.0) -> float | None:
    """Cents the note (``x`` from its onset) sits from ``want`` when both detectors agree it is more than
    ``gate`` off, else None.  The summation runs first (~10 ms); pYIN (~1 s) only on a suspect."""
    m = _mono(np.asarray(x, dtype=np.float32))
    m = m[int(0.03 * fs):int(0.7 * fs)]
    h = shs_cents(m, fs, want)
    if h is None or abs(h) <= gate:
        return None
    p = pyin_cents(m, fs, want)
    if p is None or abs(p - h) > AGREE_CENTS or abs((p + h) / 2) <= gate:
        return None
    return (p + h) / 2


def onset(x: np.ndarray, fs: int) -> int:
    """First sample within 20 dB of the note's peak (5 ms envelope)."""
    env = np.abs(_mono(x))
    win = max(1, int(0.005 * fs))
    env = np.convolve(env, np.ones(win) / win, mode='same')
    return int(np.argmax(env > 0.1 * env.max())) if env.max() > 0 else 0
