from kobi.dedupe import plan_window


def cell(lo, hi, kc, level):
    return dict(lo=lo, hi=hi, kc=kc, level=level)


def test_same_keycenter_dynamics_become_ordered_layers():
    cs = [cell(58, 62, 60, -30.0), cell(58, 62, 60, -18.0), cell(58, 62, 60, -24.0)]   # soft, loud, medium
    plan_window(cs, 1, 127)
    assert [c['keys'] for c in cs] == [(58, 62)] * 3
    assert (cs[0]['lovel'], cs[0]['hivel']) == (1, 42) and (cs[2]['lovel'], cs[2]['hivel']) == (43, 85) and (cs[1]['lovel'], cs[1]['hivel']) == (86, 127)


def test_many_variants_keep_the_median_one_and_overlapping_ranges_split_at_the_nearest_keycenter():
    cs = [cell(24, 24, 24, -20 - i) for i in range(10)]                     # ten takes, 1 dB apart
    plan_window(cs, 1, 127)
    kept = [c for c in cs if c['keys']]
    assert len(kept) == 1 and abs(kept[0]['level'] + 24.5) <= 0.5 and kept[0]['lovel'] == 1 and kept[0]['hivel'] == 127
    cs = [cell(0, 78, 48, -20.0), cell(0, 88, 60, -20.0), cell(79, 108, 84, -20.0)]   # a pad's overlapping ranges
    plan_window(cs, 1, 127)
    assert [c['keys'] for c in cs] == [(0, 54), (55, 78), (79, 108)]
    cs = [cell(63, 65, 63, -20.0), cell(64, 65, 64, -20.0)]                 # the harpsichord overlap
    plan_window(cs, 1, 127)
    assert [c['keys'] for c in cs] == [(63, 63), (64, 65)]


def test_keyless_regions_do_not_disqualify_a_program(tmp_path):
    from kobi.dedupe import dedupe_sfz
    p = tmp_path / 'm.sfz'
    p.write_text('<control> default_path=../x/\n<region> sample=p.ogg key=60 pitch_keytrack=0 offset=0 end=9\n'
                 '<region> sample=p.ogg pitch_keycenter=60 lokey=58 hikey=62 offset=10 end=19\n')
    assert dedupe_sfz(str(p)) is not None                          # analysed, not skipped
