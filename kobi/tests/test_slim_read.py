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
