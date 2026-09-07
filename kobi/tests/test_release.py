from kobi.release import cap_line


def test_only_long_sustain_releases_are_capped():
    sus = '<region> sample=a.ogg lokey=1 hikey=2 loop_mode=loop_continuous loop_start=1 loop_end=9 ampeg_release=2.467 offset=0 end=9'
    assert 'ampeg_release=0.500' in cap_line(sus)
    assert cap_line(sus.replace('2.467', '0.314')) == sus.replace('2.467', '0.314')
    decay = '<region> sample=a.ogg lokey=1 hikey=2 loop_start=1 loop_end=9 ampeg_hold=0.15 ampeg_decay=8 ampeg_release=4.0 offset=0 end=9'
    assert cap_line(decay) == decay
    oneshot = '<region> sample=a.ogg key=38 loop_mode=one_shot ampeg_release=3.0 offset=0 end=9'
    assert cap_line(oneshot) == oneshot
