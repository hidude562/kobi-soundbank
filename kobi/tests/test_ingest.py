import os

import numpy as np
import pytest
import soundfile as sf

from kobi import paths
from kobi.ingest import (default_view, load_folder, load_sfz, note_to_midi, parse_name, parse_sfz)


def _wav(path, n=1000):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fmt = 'AIFF' if path.lower().endswith(('.aif', '.aiff')) else None
    sf.write(path, np.zeros(n), 44100, subtype='PCM_16', format=fmt)


def test_note_names():
    assert note_to_midi('C4') == 60 and note_to_midi('c#4') == 61 and note_to_midi('Db4') == 61
    assert note_to_midi('A0') == 21 and note_to_midi('C-1') == 0 and note_to_midi('G9') == 127
    assert note_to_midi('Snare2') is None and note_to_midi('F') is None and note_to_midi('Timpani3A') is None


def test_parse_name_vcsl_forms():
    p = parse_name('BrettTenor_NV_Main_A#1_vl2_rr1')
    assert (p['note'], p['vel'], p['vel_kind'], p['rr'], p['mic']) == (34, 2, 'vl', 1, 'main') and 'nv' in p['tags']
    p = parse_name('JHPiano_NoSusRel_Close_F#3_vl4_rr1', 'Rel')
    assert p['release'] and p['note'] == 54 and p['mic'] == 'close'
    p = parse_name('KSHarp_A2_mf1')
    assert (p['note'], p['vel'], p['vel_kind'], p['rr']) == (45, 4, 'dyn', 1)
    p = parse_name('glock_loud_C5_01')
    assert (p['note'], p['vel'], p['rr']) == (72, 6, 1) and 'loud' in p['tags']
    p = parse_name('Xylo_Hard_C6_ff_01_far')
    assert (p['note'], p['vel'], p['vel_kind'], p['rr'], p['mic']) == (84, 6, 'dyn', 1, 'far')
    p = parse_name('Snare2_HitNS_v2_rr1_Mid')
    assert p['note'] is None and p['vel'] == 2 and p['rr'] == 1 and 'hitns' in p['tags']
    p = parse_name('Hohner-Special20_Normal_rel_C3', 'Releases/Normal')
    assert p['release'] and p['note'] == 48 and 'normal' in p['tags']
    p = parse_name('Mbira6_Normal_MainSpirit_A4_k1_vl3_rr2')
    assert (p['note'], p['vel'], p['rr'], p['mic']) == (69, 3, 2, 'mainspirit')
    p = parse_name('snare_f1')
    assert p['note'] is None and (p['vel'], p['vel_kind'], p['rr']) == (5, 'dyn', 1)
    p = parse_name('susCymb1_hit_f1')
    assert p['note'] is None and p['vel'] == 5
    p = parse_name('b2_mf_1')
    assert p['note'] == 47 and p['vel'] == 4 and p['rr'] == 1       # a real lower-case note
    p = parse_name('D#2_vib_mf_1')
    assert (p['note'], p['vel'], p['rr']) == (39, 4, 1) and 'vib' in p['tags']
    p = parse_name('Player_vl2_rr1_A-1')                       # octave -1: VCSL's Knight / Kawai lowest notes
    assert (p['note'], p['vel'], p['rr'], p['mic']) == (9, 2, 1, 'player')
    assert parse_name('Player_vl1_rr1_Bb-1')['note'] == 10 and parse_name('snare_hit-1')['note'] is None


def test_sfz_parser_hierarchy_include_define(tmp_path):
    inc = tmp_path / 'maps'
    inc.mkdir()
    (inc / 'low.sfz').write_text('<region> sample=$DIR\\low c1.wav key=$LOW lovel=1 hivel=64\n')
    _wav(str(tmp_path / 'Samples' / 'low c1.wav'))
    _wav(str(tmp_path / 'Samples' / 'hi.wav'))
    (tmp_path / 'main.sfz').write_text(
        '// comment\n<control> default_path=Samples/ set_cc64=0\n#define $DIR .\n#define $LOW c1\n'
        '<global> ampeg_release=0.5 sw_default=c2\n<master> volume=-3\n<group> trigger=attack tune=10\n'
        '#include "maps/low.sfz"\n<group> transpose=1\n<region> sample=hi.wav lokey=c4 hikey=g4 pitch_keycenter=e4 '
        'seq_length=2 seq_position=2 sw_last=c2 sw_label=Sus\n'
        '<region> sample=hi.wav key=70 locc64=64 hicc64=127\n'
        '<region> sample=hi.wav key=71 trigger=release\n'
        '<group> lokey=5 hikey=2\n<region> sample=hi.wav\n')
    raw, control = parse_sfz(str(tmp_path / 'main.sfz'))
    assert control['default_path'] == 'Samples/' and len(raw) == 5
    inst = load_sfz(str(tmp_path / 'main.sfz'))
    assert not inst.missing and len(inst.regions) == 4       # hikey < lokey dropped
    r0 = inst.regions[0]
    assert os.path.basename(r0.sample) == 'low c1.wav' and r0.lokey == r0.hikey == r0.pitch_keycenter == 24
    assert r0.hivel == 64 and r0.tune == 10 and r0.volume_db == -3 and r0.opcodes['ampeg_release'] == '0.5'
    r1 = inst.regions[1]
    assert (r1.lokey, r1.hikey, r1.pitch_keycenter, r1.tune, r1.seq_position, r1.sw_last) == (60, 67, 64, 100, 2, 36)
    assert inst.sw_default == 36 and inst.keyswitches() == {36: 'Sus'}
    view = default_view(inst)
    assert [r.pitch_keycenter for r in view] == [24, 64]        # pedal-gated and release regions excluded
    assert [r.pitch_keycenter for r in default_view(inst, release=True)] == [71]


def test_sfz_case_insensitive_sample_path(tmp_path):
    _wav(str(tmp_path / 'Samples' / 'Note.WAV'))
    (tmp_path / 'a.sfz').write_text('<region> sample=samples\\note.wav key=60\n')
    inst = load_sfz(str(tmp_path / 'a.sfz'))
    assert not inst.missing and inst.regions[0].sample.endswith('Samples/Note.WAV')


def test_folder_reader_spreads_keys_velocities_and_rr(tmp_path):
    d = tmp_path / 'Inst'
    for n in ('C3', 'G3', 'C4'):
        for v in (1, 2):
            for rr in (1, 2):
                _wav(str(d / 'Sustain' / f'Inst_Sus_Main_{n}_vl{v}_rr{rr}.wav'))
                _wav(str(d / 'Sustain' / f'Inst_Sus_Far_{n}_vl{v}_rr{rr}.wav'))
    _wav(str(d / 'Releases' / 'Inst_Rel_Main_C3_vl1_rr1.wav'))
    inst = load_folder(str(d), extend=6)
    view = default_view(inst)
    assert len(view) == 12 and all('main' in r.tags for r in view)          # far mic dropped
    by_key = {}
    for r in view:
        by_key.setdefault(r.pitch_keycenter, set()).add((r.lokey, r.hikey, r.lovel, r.hivel, r.seq_position, r.seq_length))
    assert (48 - 6, 51) in {(a, b) for a, b, *_ in by_key[48]} and any(a == 52 and b == 57 for a, b, *_ in by_key[55])
    assert any(a == 58 and b == 66 for a, b, *_ in by_key[60])
    assert {(lv, hv) for _, _, lv, hv, _, _ in by_key[48]} == {(1, 63), (64, 127)}
    assert {(sp, sl) for *_, sp, sl in by_key[48]} == {(1, 2), (2, 2)}
    assert len(default_view(inst, release=True)) == 1


@pytest.mark.skipif(not os.path.isdir(os.path.join(paths.SOURCES, 'FreePats')), reason='sample sources not pulled (see SOURCES.md)')
def test_real_sources_smoke():
    from kobi.gm_map import PROGRAMS
    from kobi.ingest import load_candidate
    for num in (0, 21, 65, 80):
        inst = load_candidate(PROGRAMS[num].cands[0], PROGRAMS[num].name)
        assert inst is not None and not inst.missing and default_view(inst), PROGRAMS[num].name


def test_include_relative_to_root_and_builtin_samples(tmp_path):
    (tmp_path / 'maps').mkdir()
    (tmp_path / 'maps' / 'a.sfz').write_text('#include "maps/b.sfz"\n#include "maps/b.sfz"\n')
    (tmp_path / 'maps' / 'b.sfz').write_text('<region> sample=*silence key=1\n<region> sample=s.wav key=$K\n')
    _wav(str(tmp_path / 's.wav'))
    (tmp_path / 'main.sfz').write_text('#define $K 40\n#include "maps/a.sfz"\n#define $K 41\n#include "maps/a.sfz"\n')
    inst = load_sfz(str(tmp_path / 'main.sfz'))
    assert [r.pitch_keycenter for r in inst.regions] == [40, 40, 41, 41] and not inst.missing


def test_directives_in_the_middle_of_a_line(tmp_path):
    # Headroom Piano: the key is #define'd inside the region line, the sample name comes from an include
    (tmp_path / 'Data').mkdir()
    (tmp_path / 'Data' / 'sample.txt').write_text('sample=P $VEL $KEY.wav\npitch_keycenter=$KEY\n')
    for k in (21, 24):
        _wav(str(tmp_path / f'P L1 {k}.wav'))
    (tmp_path / 'main.sfz').write_text(
        '#define $VEL L1\n'
        '<region> #define $KEY 21 lokey=21 hikey=22 #include "Data/sample.txt"\n'
        '<region> #define $KEY 24 lokey=23 hikey=25 #include "Data/sample.txt"\n'
        '#include "Data/none.sfz""\n')                                  # Swirly's stray quote: ignored
    inst = load_sfz(str(tmp_path / 'main.sfz'))
    assert not inst.missing and [(r.lokey, r.hikey, r.pitch_keycenter) for r in inst.regions] == [(21, 22, 21), (23, 25, 24)]
    assert [os.path.basename(r.sample) for r in inst.regions] == ['P L1 21.wav', 'P L1 24.wav']


def test_layers_crossfaded_out_at_the_defaults_are_silent(tmp_path):
    for n in ('p', 'f', 'click'):
        _wav(str(tmp_path / f'{n}.wav'))
    (tmp_path / 'sax.sfz').write_text(
        '<control> set_cc1=64\n'
        '<region> sample=p.wav key=60 xfin_hicc1=30 xfout_locc1=30\n'         # mod-wheel blend, both audible at 64
        '<region> sample=f.wav key=60 xfin_locc1=30 xfin_hicc1=127\n'
        '<region> sample=click.wav key=60 xfin_hicc121=127\n')                 # key noise, faded in by CC121 (0)
    assert [os.path.basename(r.sample) for r in default_view(load_sfz(str(tmp_path / 'sax.sfz')))] == ['p.wav', 'f.wav']
    (tmp_path / 'gated.sfz').write_text('<region> sample=p.wav key=60 xfin_locc100=1 xfin_hicc100=2\n')
    assert len(default_view(load_sfz(str(tmp_path / 'gated.sfz')))) == 1           # every layer faded out: kept


def test_missing_sample_rescued_from_set(tmp_path):
    _wav(str(tmp_path / 'Samples' / 'acoustic' / 'e2.wav'))
    (tmp_path / 'Programs').mkdir()
    (tmp_path / 'Programs' / 'p.sfz').write_text('<region> sample=acoustic\\e2.wav key=40\n')
    inst = load_sfz(str(tmp_path / 'Programs' / 'p.sfz'), search_root=str(tmp_path))
    assert not inst.missing and inst.regions[0].sample.endswith('Samples/acoustic/e2.wav')


def test_first_controller_window_assumed_when_default_hits_nothing(tmp_path):
    _wav(str(tmp_path / 's.wav'))
    (tmp_path / 'g.sfz').write_text('<region> sample=s.wav key=60 locc107=16 hicc107=24\n<region> sample=s.wav key=61 locc107=25 hicc107=40\n'
                                    '<region> sample=s.wav key=62\n<region> sample=s.wav key=63 locc64=64 hicc64=127\n')
    view = default_view(load_sfz(str(tmp_path / 'g.sfz')))
    assert [r.pitch_keycenter for r in view] == [60, 62]     # first CC107 window; pedal gate (a default exists) still applies


def test_iowa_names_and_first_position(tmp_path):
    from kobi.ingest import pick_first_position
    d = tmp_path / 'Violin'
    for string, notes in (('sulG', ['G3', 'A3', 'D4', 'A4']), ('sulD', ['D4', 'A4', 'E5']), ('sulA', ['A4', 'E5']), ('sulE', ['E5', 'A5'])):
        for n in notes:
            for dyn in ('pp', 'ff'):
                _wav(str(d / f'Violin.arco.{dyn}.{string}.{n}.stereo.aif'))
                _wav(str(d / f'Violin.arco.{dyn}.{string}.{n}.mono.aif'))
    inst = load_folder(str(d), source='Iowa')
    assert all('stereo' in r.tags for r in inst.regions) and len(inst.regions) == 22
    pick_first_position(inst)
    by_note = {}
    for r in inst.regions:
        by_note.setdefault(r.pitch_keycenter, set()).add(r.sample.split('.')[3])
    assert by_note == {55: {'sulG'}, 57: {'sulG'}, 62: {'sulD'}, 69: {'sulA'}, 76: {'sulE'}, 81: {'sulE'}}
    assert all(not any(t.startswith('sul') for t in r.tags) for r in inst.regions)
    r = next(r for r in inst.regions if r.pitch_keycenter == 62)
    assert (r.lokey, r.hikey) == (60, 65) and {(x.lovel, x.hivel) for x in inst.regions if x.pitch_keycenter == 62} == {(1, 63), (64, 127)}


def test_apply_gain_folds_into_region_volumes_and_is_reversible(tmp_path):
    from kobi.levels import apply_gain, bake, BAKED
    p = tmp_path / 'x.sfz'
    p.write_text('// header\n<control> default_path=./\n<global> ampeg_release=0.3\n'
                 '<region> sample=a.wav key=60\n<region> sample=b.wav key=61 volume=-6\n')
    apply_gain(str(p), 10.0)
    s = p.read_text()
    assert BAKED in s and '<global> ampeg_release=0.3 volume=10.0' in s and 'key=61 volume=4.00' in s and 'key=60\n' in s
    apply_gain(str(p), 4.0)                       # re-apply: regions move by the difference only
    s = p.read_text()
    assert 'volume=4.0' in s.split('<global>')[1].split('\n')[0] and 'key=61 volume=-2.00' in s
    apply_gain(str(p), 0.0)                       # back to raw
    assert 'key=61 volume=-6.00' in p.read_text()
    q = tmp_path / 'old.sfz'                      # a file from before the fix: global set, regions never got it
    q.write_text('<global> volume=8.0\n<region> sample=b.wav key=61 volume=-6\n')
    assert bake(str(q)) and 'volume=2.00' in q.read_text() and not bake(str(q))


def test_a_single_window_extra_layer_stays_off_at_its_default(tmp_path):
    _wav(str(tmp_path / 's.wav'))
    (tmp_path / 'u.sfz').write_text('<region> sample=s.wav key=60\n<region> sample=s.wav key=60 locc100=1 amplitude_oncc100=100\n')
    view = default_view(load_sfz(str(tmp_path / 'u.sfz')))
    assert len(view) == 1 and 'locc100' not in view[0].opcodes          # Black And Blue's unison voice


def test_velocity_crossfades_become_velocity_ranges(tmp_path):
    _wav(str(tmp_path / 's.wav'))
    (tmp_path / 'x.sfz').write_text('<group> lovel=1 xfout_lovel=21 xfout_hivel=52\n<region> sample=s.wav key=60\n'
                                    '<group> xfin_lovel=21 xfin_hivel=52 xfout_lovel=53 xfout_hivel=76\n<region> sample=s.wav key=60\n'
                                    '<group> xfin_lovel=53 xfin_hivel=76\n<region> sample=s.wav key=60\n')
    view = default_view(load_sfz(str(tmp_path / 'x.sfz')))
    assert [(r.lovel, r.hivel) for r in view] == [(1, 36), (37, 64), (65, 127)]
    assert [(r.lovel, r.hivel) for r in default_view(load_sfz(str(tmp_path / 'x.sfz')))] == [(1, 36), (37, 64), (65, 127)]


def test_noise_keys_are_not_notes_of_a_melodic_program():
    from kobi.ingest import Region, _notes_only
    note = Region(sample='/x/sop_60.flac', lokey=60, hikey=60, pitch_keycenter=60)
    click = Region(sample='/x/sop_k_01.flac', lokey=52, hikey=52, pitch_keycenter=52, opcodes={'group_label': 'noises key-clicks 01'})
    fret = Region(sample='/x/noise_palm_rr1.wav', lokey=80, hikey=80, pitch_keycenter=80)
    assert _notes_only(64, 'sustain', [note, click, fret]) == [note]
    assert _notes_only(120, 'oneshot', [click, fret]) == [click, fret]           # an effect program keeps them
    assert _notes_only(36, 'decay', [fret]) == [fret]                            # nothing else to play
