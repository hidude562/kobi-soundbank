import numpy as np

from kobi.balance import plan


def test_plan_brings_every_note_to_the_median_within_the_clamp():
    d = plan({'a': -30.0, 'b': -20.0, 'c': -10.0, 'd': -50.0, 'f': -20.0, 'e': -np.inf}, clamp=12.0)
    assert d['b'] == 0.0 and d['f'] == 0.0      # the median (-20) stays
    assert d['a'] == 10.0 and d['c'] == -10.0
    assert d['d'] == 12.0          # -50 wants +30, clamped
    assert d['e'] == 0.0           # silence is left alone
