import numpy as np

from kobi.pitchcheck import deviation, measure


def _tone(f0, fs=44100, secs=1.0):
    t = np.arange(int(fs * secs)) / fs
    return sum(0.6 ** h * np.sin(2 * np.pi * f0 * (h + 1) * t) for h in range(6)).astype(np.float32) * np.exp(-t)[:, None].T[0]


def test_a_mislabelled_note_is_measured_and_a_good_one_left_alone():
    want = 830.61                                           # G#5: the pizzicato file named G#4 that sounds C5 -20c
    off = deviation(_tone(want * 2 ** (380 / 1200)), 44100, want)
    assert off is not None and abs(off - 380) < 15
    assert deviation(_tone(want), 44100, want) is None
    assert deviation(_tone(want * 2 ** (20 / 1200)), 44100, want) is None      # within the 30-cent gate
    m = measure(_tone(110.0 * 2 ** (-60 / 1200)), 44100, 110.0)
    assert m['cents'] is not None and abs(m['cents'] + 60) < 15
