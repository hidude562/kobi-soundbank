from kobi.release import cap_line


def test_only_long_sustain_releases_are_capped():
    sus = '<region> sample=a.ogg lokey=1 hikey=2 loop_mode=loop_continuous loop_start=1 loop_end=9 ampeg_release=2.467 offset=0 end=9'
    assert 'ampeg_release=0.500' in cap_line(sus)
    assert cap_line(sus.replace('2.467', '0.314')) == sus.replace('2.467', '0.314')
    decay = '<region> sample=a.ogg lokey=1 hikey=2 loop_start=1 loop_end=9 ampeg_hold=0.15 ampeg_decay=8 ampeg_release=4.0 offset=0 end=9'
    assert cap_line(decay) == decay
    oneshot = '<region> sample=a.ogg key=38 loop_mode=one_shot ampeg_release=3.0 offset=0 end=9'
    assert cap_line(oneshot) == oneshot


def test_held_sounds_get_their_releases_doubled_once(tmp_path):
    from kobi.release import HELD_MARK, cap_sfz
    held, other = tmp_path / '048 String Ensemble 1.sfz', tmp_path / '056 Trumpet.sfz'
    body = ('<control> default_path=../x/\n<region> sample=p.ogg key=60 loop_mode=loop_continuous loop_start=1 loop_end=9 ampeg_release=0.250\n'
            '<region> sample=p.ogg key=62 loop_mode=loop_continuous loop_start=1 loop_end=9 ampeg_release=3.000\n'
            '<region> sample=p.ogg key=64 ampeg_hold=0.3 ampeg_release=1.500\n')
    held.write_text(body); other.write_text(body)
    cap_sfz(str(held)); cap_sfz(str(other))
    rel = lambda p: [l.split('ampeg_release=')[1] for l in p.read_text().split('\n') if 'ampeg_release=' in l]
    assert rel(held) == ['0.500', '1.000', '1.500'] and HELD_MARK in held.read_text()     # decaying notes keep theirs
    assert rel(other) == ['0.250', '0.500', '1.500']
    cap_sfz(str(held))
    assert rel(held) == ['0.500', '1.000', '1.500']                                         # not doubled twice
