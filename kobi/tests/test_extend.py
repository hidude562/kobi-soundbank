import re

from kobi.extend import extend_sfz

SFZ = """<control> default_path=../x/
<global> volume=1
<region> sample=p.ogg pitch_keycenter=40 lokey=38 hikey=42 lovel=1 hivel=64 offset=0 end=10
<region> sample=p.ogg pitch_keycenter=40 lokey=38 hikey=42 lovel=1 hivel=64 offset=0 end=10 ampeg_hold=0.3
<region> sample=p.ogg pitch_keycenter=60 lokey=58 hikey=62 lovel=1 hivel=64 offset=20 end=30
<region> sample=p.ogg pitch_keycenter=60 lokey=58 hikey=62 lovel=70 hivel=127 offset=40 end=50
<region> sample=p.ogg key=72 offset=60 end=70
"""
OP = re.compile(r'(?<!\S)([\w]+)=(\S+)')


def _regions(text):
    out = []
    for l in text.split('\n'):
        if l.startswith('<region>'):
            o = dict(OP.findall(l))
            o.setdefault('lokey', o.get('key')); o.setdefault('hikey', o.get('key'))     # a bare key= region
            out.append(o)
    return out


def _cells_covering(regs, k, v):
    return {(o['lokey'], o['hikey'], o.get('lovel', '1'), o.get('hivel', '127')) for o in regs
            if int(o['lokey']) <= k <= int(o['hikey']) and int(o.get('lovel', 1)) <= v <= int(o.get('hivel', 127))}


def test_every_hole_is_filled_once_by_the_nearest_cell_and_the_step_is_idempotent(tmp_path):
    p = tmp_path / 'a.sfz'
    p.write_text(SFZ)
    filled = extend_sfz(str(p))
    assert filled > 0
    text = p.read_text()
    regs = _regions(text)
    for k in range(128):
        for v in range(1, 128):
            assert len(_cells_covering(regs, k, v)) == 1, (k, v)     # covered, and never by two cells
    # the original regions are untouched
    assert text.startswith(SFZ.rstrip('\n'))
    # below the bottom sample: the nearest key (40) serves every velocity — its one layer is closer
    # than key 60's loud layer — and its stacked pair is copied together
    below = [o for o in regs if int(o['lokey']) == 0 and int(o['hikey']) <= 37]
    assert {o['pitch_keycenter'] for o in below} == {'40'} and len(below) == 2
    # between 62 and 72 the nearest key's layers tile the velocities: key 60 soft below, loud above
    at65 = lambda v: {o['pitch_keycenter'] + ':' + o['offset'] for o in regs if int(o['lokey']) <= 65 <= int(o['hikey']) and int(o['lovel']) <= v <= int(o['hivel'])}
    assert at65(30) == {'60:20'} and at65(100) == {'60:40'} and at65(67) == {'60:20'}
    # above the top sample the bare key=72 region became a full-velocity range keeping its keycenter
    top = [o for o in regs if int(o['hikey']) == 127]
    assert any(o['pitch_keycenter'] == '72' and o['lokey'] == '73' for o in top)
    assert extend_sfz(str(p)) == 0
    assert p.read_text() == text
    # a bank extended under an older policy is re-done from its originals, not extended twice
    p.write_text(text.replace('lokey=73 hikey=127', 'lokey=73 hikey=120'))
    extend_sfz(str(p))
    assert p.read_text() == text


def test_keyless_programs_are_left_alone(tmp_path):
    p = tmp_path / 'fx.sfz'
    p.write_text('<region> sample=h.ogg key=60 pitch_keytrack=0 offset=0 end=1\n')
    assert extend_sfz(str(p)) is None
    assert 'key=60' in p.read_text()


def test_strip_fills_handles_old_wording_and_a_marker_in_the_header():
    from kobi.extend import strip_fills
    lines = ['<control> default_path=x/', '// kobi.extend: the nearest sampled cell copied into every hole', '<global> volume=1',
             '<region> sample=a offset=0 end=1 lokey=10 hikey=20', '// kobi.extend: old wording', '<region> sample=a offset=0 end=1 lokey=0 hikey=9']
    assert strip_fills(lines) == ['<control> default_path=x/', '<global> volume=1', '<region> sample=a offset=0 end=1 lokey=10 hikey=20']


def test_a_mixed_program_is_extended_and_its_keyless_region_is_left_alone(tmp_path):
    p = tmp_path / 'm.sfz'
    p.write_text("""<control> default_path=../x/
<region> sample=p.ogg key=60 pitch_keytrack=0 loop_mode=one_shot offset=0 end=9
<region> sample=p.ogg pitch_keycenter=60 lokey=58 hikey=62 offset=10 end=19
""")
    assert extend_sfz(str(p)) > 0
    text = p.read_text()
    assert 'key=60 pitch_keytrack=0' in text                      # untouched, still on its own key
    regs = [l for l in text.split('\n') if l.startswith('<region>') and 'pitch_keytrack=0' not in l]
    assert any('lokey=0' in l for l in regs) and any('hikey=127' in l for l in regs)
