from kobi.slim import _read


def test_read_ignores_extend_copies(tmp_path):
    sfz = tmp_path / 'GM' / 'a.sfz'
    sfz.parent.mkdir()
    sfz.write_text("""<control> default_path=../x/
<region> sample=p.ogg pitch_keycenter=60 lokey=58 hikey=62 lovel=1 hivel=64 offset=0 end=9 volume=1
<region> sample=p.ogg pitch_keycenter=60 lokey=58 hikey=62 lovel=1 hivel=64 offset=0 end=9 volume=1 ampeg_hold=0.1
// kobi.extend: the nearest sampled key copied into every hole of the key x velocity map
<region> sample=p.ogg pitch_keycenter=60 lokey=0 hikey=57 lovel=1 hivel=127 offset=0 end=9 volume=1
""")
    head, samples = _read(str(sfz))
    assert len(samples) == 1
    s = samples[0]
    assert (s['lo'], s['hi'], s['lovel'], s['hivel']) == (58, 62, 1, 64)
    assert len(s['lines']) == 2
    assert not any(l.startswith('// kobi.extend') for l in head)


def test_a_stack_keeps_every_layer(tmp_path):
    from kobi.slim import _with_layers, select
    sfz = tmp_path / 'GM' / 'a.sfz'
    sfz.parent.mkdir()
    sfz.write_text("""<control> default_path=../x/
// layer:1:a
<region> sample=p.ogg pitch_keycenter=60 lokey=0 hikey=66 offset=0 end=9
<region> sample=p.ogg pitch_keycenter=72 lokey=67 hikey=127 offset=10 end=19
// layer:2:b
<region> sample=p.ogg pitch_keycenter=60 lokey=0 hikey=63 offset=20 end=29 volume=-24
<region> sample=p.ogg pitch_keycenter=66 lokey=64 hikey=127 offset=30 end=39 volume=-24
""")
    head, samples = _read(str(sfz))
    assert not any(l.startswith('// layer:') for l in head)
    assert [s['layer'] for s in samples] == ['layer:1:a'] * 2 + ['layer:2:b'] * 2
    for rr in (1, 99):            # same key and velocity window in two layers: not round robins of one note
        kept = select(samples, dict(rr=rr))
        assert sorted(s['offset'] for s in kept) == [0, 10, 20, 30]
        # key ranges are re-spread within each layer, not across the stack
        assert {(s['layer'], s['lo2'], s['hi2']) for s in kept} == {
            ('layer:1:a', 0, 66), ('layer:1:a', 67, 127), ('layer:2:b', 0, 63), ('layer:2:b', 64, 127)}
    last, out = [None], []
    for s in select(samples, dict(rr=1)):
        out += _with_layers(['<region>'], s, last)
    assert out == ['// layer:1:a', '<region>', '<region>', '// layer:2:b', '<region>', '<region>']


def test_thinning_velocity_layers_keeps_the_one_velocity_100_played():
    from kobi.slim import _select
    wins = [(1, 60), (61, 81), (82, 95), (96, 110), (111, 127)]      # Sam's Sonor ride
    samples = [dict(key=51, lo=51, hi=51, lovel=a, hivel=b, keyless=True, vol=0.0, seq=1, rand=0.0, tune=0, offset=i)
               for i, (a, b) in enumerate(wins)]
    kept = _select(samples, dict(vel=3))
    at100 = [s for s in kept if s['lovel2'] <= 100 <= s['hivel2']]
    assert len(kept) == 3 and len(at100) == 1 and (at100[0]['lovel'], at100[0]['hivel']) == (96, 110)
