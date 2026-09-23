import re

from kobi.kit import tidy_kit


def test_alternates_become_round_robins_broad_windows_go_and_latin_keys_decay(tmp_path):
    p = tmp_path / 'Drums.sfz'
    p.write_text("""<control> default_path=../Drums/
<region> sample=p.ogg key=58 loop_mode=one_shot offset=0 end=9
<region> sample=p.ogg key=58 loop_mode=one_shot offset=10 end=19
<region> sample=p.ogg key=81 lovel=1 hivel=63 loop_mode=one_shot offset=20 end=29
<region> sample=p.ogg key=81 lovel=64 hivel=127 loop_mode=one_shot offset=30 end=39
<region> sample=p.ogg key=81 lovel=1 hivel=127 loop_mode=one_shot offset=40 end=49
<region> sample=p.ogg key=38 lovel=1 hivel=127 loop_mode=one_shot offset=50 end=59
""")
    s = tidy_kit(str(p))
    lines = [l for l in p.read_text().split('\n') if l.startswith('<region>')]
    assert s == dict(robins=2, dropped=1, decayed=4)
    assert len(lines) == 5 and not any('offset=40' in l for l in lines)            # the 1-127 triangle take is gone
    vib = [l for l in lines if 'key=58' in l]
    assert sorted(re.search(r'seq_position=(\d)', l).group(1) for l in vib) == ['1', '2'] and all('seq_length=2' in l for l in vib)
    assert all('ampeg_hold=0.1 ampeg_decay=0.6 ampeg_sustain=0' in l for l in vib)
    assert 'ampeg' not in [l for l in lines if 'key=38' in l][0]                    # the snare is untouched
    assert tidy_kit(str(p)) == dict(robins=2, dropped=0, decayed=4)                  # idempotent in effect


def test_a_kit_with_nothing_to_drop_is_still_written(tmp_path):
    p = tmp_path / 'Drums.sfz'
    p.write_text("<control> default_path=../Drums/\n<region> sample=p.ogg key=72 loop_mode=one_shot offset=0 end=9\n")
    assert tidy_kit(str(p))['decayed'] == 1
    assert 'ampeg_decay=0.6' in p.read_text()


def test_kit_targets_are_read_from_the_kit_sources_comments(tmp_path):
    from kobi.kit import targets_from
    src = tmp_path / 'Drums.sfz'
    src.write_text('// kobi GM drum kit\n<global> ampeg_release=0.1\n'
                   '// 81 Open Triangle: VCSL Triangles triangle1 hit (12 regions, -57.7 LUFS, gain +32.7 dB)\n'
                   '<region> sample=a.wav key=81\n// 36 Bass Drum 1: Pick 36  (8 regions, -41.5 LUFS, gain +19.5 dB)\n'
                   '// 99 Missing: x (0 regions, -inf LUFS, gain +0.0 dB)\n')
    t = targets_from(str(src))
    assert set(t) == {81, 36} and abs(t[81] + 25.0) < 1e-9 and abs(t[36] + 22.0) < 1e-9
