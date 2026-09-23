import numpy as np

from kobi.balance import plan


def test_plan_brings_every_note_to_the_median_within_the_clamp():
    d = plan({'a': -30.0, 'b': -20.0, 'c': -10.0, 'd': -50.0, 'f': -20.0, 'e': -np.inf}, clamp=12.0)
    assert d['b'] == 0.0 and d['f'] == 0.0      # the median (-20) stays
    assert d['a'] == 10.0 and d['c'] == -10.0
    assert d['d'] == 12.0          # -50 wants +30, clamped
    assert d['e'] == 0.0           # silence is left alone


def _stack_sfz(tmp_path, marked: bool):
    """Two layers of two notes each, one packed WAV: layer a at 0 / -6 dB, layer b 24 dB under a."""
    import soundfile as sf
    fs = 44100
    t = np.arange(fs) / fs
    amps = [0.5, 0.25, 0.5 * 10 ** (-24 / 20), 0.25 * 10 ** (-24 / 20)]
    sf.write(tmp_path / 'pack.wav', np.concatenate([a * np.sin(2 * np.pi * 440 * t) for a in amps]), fs)
    lines = ['<control> default_path=./', '<global> volume=0']
    for n in range(4):
        if marked and n in (0, 2):
            lines.append(f'// layer:{"ab"[n // 2]}')
        lines.append(f'<region> sample=pack.wav lokey={60 + 12 * (n % 2)} hikey={71 + 12 * (n % 2)} pitch_keycenter={60 + 12 * (n % 2)} '
                     f'offset={n * fs} end={(n + 1) * fs - 1} volume=0.0')
    path = tmp_path / 'stack.sfz'
    path.write_text('\n'.join(lines) + '\n')
    return path


def _region_volumes(path):
    import re
    return [float(re.search(r'volume=(-?[\d.]+)', l).group(1)) for l in path.read_text().split('\n') if l.startswith('<region>')][:4]


def test_a_marked_stack_keeps_its_layer_balance(tmp_path):
    from kobi.balance import balance_sfz
    path = _stack_sfz(tmp_path, marked=True)
    r = balance_sfz(str(path), clamp=60.0)
    v = _region_volumes(path)
    assert r['stack_layers'] == 2
    assert abs((v[1] - v[0]) - 6.0) < 0.3 and abs((v[3] - v[2]) - 6.0) < 0.3     # evened within each layer
    assert abs(v[2] - v[0]) < 0.3                                                   # b stays 24 dB under a


def test_an_unmarked_program_is_levelled_as_one(tmp_path):
    from kobi.balance import balance_sfz
    path = _stack_sfz(tmp_path, marked=False)
    balance_sfz(str(path), clamp=60.0)
    v = _region_volumes(path)
    assert v[2] - v[0] > 20.0                                                       # the quiet notes brought up
