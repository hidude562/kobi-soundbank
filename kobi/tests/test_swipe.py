import io
import json
import os
import zipfile

import numpy as np
import soundfile as sf

import kobi.swipe  # noqa: F401  (sets KOBI_SWIPE_PICKS=0 before gm_map is read)
from kobi import gm_map
from kobi.ingest import Region
from kobi.swipe.fetch import RemoteZip
from kobi.swipe.gm_words import DRUMS, classify
from kobi.swipe.prep import _expand, collapse_variants, needed_regions, plan


def test_classifier_names_the_instrument_not_its_neighbours():
    assert classify('Solo Violin Arco Vib')[40] == 1.0
    assert 124 not in classify('Vibraphone')                  # "phone" is not a telephone
    assert 6 not in classify('Flute sus')                      # nor "lute" a harpsichord stand-in
    assert 0 not in classify('TX81Z Piano 1') and 4 in classify('TX81Z Piano 1')
    assert 40 not in classify('Violin pizz')                   # a short articulation is no sustained violin
    assert 0 not in classify('Grand Piano Kawai Rel')          # release layers are never an instrument
    assert classify('growlybass angry')[36] == 1.0             # glued library names are split
    assert DRUMS in classify('DrumGizmo DRSKit')
    assert classify('Black And Green Guitars btb') == {}       # behind-the-bridge noise plays no guitar program
    assert 33 not in classify('Finger Cymbals') and classify('FingerBassYR')[33] == 1.0


def test_phrase_moves_by_octaves_into_the_range():
    p = plan(73, 'sustain')                                    # flute at C5 on a full keyboard
    assert p['shift'] == 0 and min(k for _, t, k, _ in p['events'] if t == 'on') == 72
    p = plan(73, 'sustain', lo=48, hi=76)                      # an instrument that tops out at E5
    assert p['shift'] == -12 and max(k for _, t, k, _ in p['events']) <= 76
    held = [k for t, ty, k, _ in plan(40, 'sustain')['events'] if ty == 'on' and t >= 1.8]
    assert len(held) == 1                                      # a violin holds one note, not a chord
    assert len([k for t, ty, k, _ in plan(0, 'decay')['events'] if ty == 'on' and t >= 1.8]) == 3


def test_needed_regions_take_every_layer_but_one_round_robin():
    def reg(s, lo, hi, lv, hv, seq=1, mic='a'):
        return Region(sample=s, lokey=lo, hikey=hi, pitch_keycenter=lo, lovel=lv, hivel=hv, seq_position=seq, seq_length=2,
                      tags=(mic,))
    view = [reg('a1', 60, 62, 1, 127, 1, 'close'), reg('a2', 60, 62, 1, 127, 2, 'close'),
            reg('b1', 60, 62, 1, 127, 1, 'room'), reg('c1', 63, 65, 1, 64), reg('c2', 63, 65, 65, 127)]
    got = sorted(r.sample for r in needed_regions(view, [(60, 100), (64, 100)]))
    assert got == ['a1', 'b1', 'c2']
    kept = collapse_variants([r for r in view if r.sample in ('a1', 'b1', 'c2')])
    assert all(r.seq_length == 1 for r in kept) and len(kept) == 3


def test_include_paths_expand_over_define_values():
    got = _expand('mappings/$MIC/$PIECE.sfz', {'$MIC': {'close', 'room'}, '$PIECE': {'kick'}})
    assert sorted(got) == ['mappings/close/kick.sfz', 'mappings/room/kick.sfz']
    assert _expand('a/$UNKNOWN.sfz', {}) == []


class _BytesFetcher:
    """Serves an in-memory file the way Fetcher.range does."""

    def __init__(self, data):
        self.data, self.calls = data, []

    def range(self, url, start, end, label=''):
        self.calls.append((start, end))
        n = len(self.data)
        chunk = self.data[start:] if start < 0 else self.data[start:end + 1]
        return chunk, n


def test_remote_zip_reads_one_member_without_the_rest(tmp_path):
    buf = io.BytesIO()
    big = os.urandom(300_000)
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('Samples/big.wav', big)
        z.writestr('Samples/note.wav', b'RIFF' + b'x' * 5000)
        z.writestr('inst.sfz', '<region> sample=Samples/note.wav\n')
    f = _BytesFetcher(buf.getvalue())
    rz = RemoteZip(f, 'http://example/lib.zip', str(tmp_path / 'cache'))
    assert set(rz.members()) == {'Samples/big.wav', 'Samples/note.wav', 'inst.sfz'}
    out = rz.extract('Samples/note.wav', str(tmp_path / 'lib' / 'Samples' / 'note.wav'))
    assert open(out, 'rb').read() == b'RIFF' + b'x' * 5000
    fetched = sum((e - s + 1) if s >= 0 else -s for s, e in f.calls)
    assert fetched < 80_000                                    # the directory and one member, not the 300 KB one
    rz2 = RemoteZip(_BytesFetcher(b''), 'http://example/lib.zip', str(tmp_path / 'cache'))
    assert 'inst.sfz' in rz2.members()                         # the directory is cached on disk


def test_picks_go_first_once_complete(tmp_path, monkeypatch):
    lib = tmp_path / 'Extra' / 'SomePiano'
    (lib / 'Samples').mkdir(parents=True)
    sf.write(str(lib / 'Samples' / 'c4.wav'), np.zeros(100), 44100)
    (lib / 'Piano [v2].sfz').write_text('<region> sample=Samples/c4.wav key=60\n')
    monkeypatch.setattr(gm_map, 'ROOT', str(tmp_path))
    programs = [gm_map.Program(0, 'Acoustic Grand Piano', [gm_map.Cand('VCSL', 'nowhere', None, 'decay')])]
    pick = dict(shape='sfz', loc=dict(rel='Piano [v2].sfz'), root='Extra/SomePiano', lib_title='Some Piano',
                license='CC0 1.0', octave=0, complete=False)
    path = tmp_path / 'SWIPE_PICKS.json'
    path.write_text(json.dumps({'0': dict(verdict='replace', pick=pick)}))
    assert gm_map.apply_picks(programs, str(path)) == []       # still fetching: not applied
    pick['complete'] = True
    path.write_text(json.dumps({'0': dict(verdict='replace', pick=pick)}))
    applied = gm_map.apply_picks(programs, str(path))
    assert len(applied) == 1 and programs[0].cands[0].source == 'Extra' and programs[0].cands[0].kind == 'decay'
    assert programs[0].cands[0].resolve()[1] == 1              # the glob-escaped name finds the file


def test_vote_log_derives_verdicts_old_and_new():
    from types import SimpleNamespace
    from kobi.swipe.deck import App
    votes = [dict(card='main:0', program=0, cid=None, verdict='dislike', t=1),       # the first deck's votes ...
             dict(card='alt:0:aaa', program=0, cid='aaa', verdict='dislike', t=2),
             dict(card='alt:0:bbb', program=0, cid='bbb', verdict='like', t=3, octave=1),
             dict(card='main:1', program=1, cid=None, verdict='like', t=4),
             dict(card='main:2', program=2, cid=None, verdict='dislike', t=5),       # disliked, nothing picked
             dict(card='prog:3', program=3, cid='ccc', verdict='pick', t=6, octave=-1),  # ... and this deck's
             dict(card='prog:4', program=4, cid=None, verdict='none', t=7)]
    fake = SimpleNamespace(state=dict(votes=list(votes)))
    d = App.derive(fake)
    assert d[0]['decision'] == 'pick' and d[0]['pick'] == 'bbb' and d[0]['octave'] == 1 and d[0]['passed'] == ['bank', 'aaa']
    assert d[1]['decision'] == 'keep' and d[1]['pick'] is None
    assert d[2]['decision'] is None and d[2]['passed'] == ['bank']              # comes back as an open card
    assert d[3]['decision'] == 'pick' and d[3]['pick'] == 'ccc' and d[3]['octave'] == -1
    assert d[4]['decision'] == 'none' and d[5]['decision'] is None
    fake.state['votes'].append(dict(card='reopen:0', program=0, cid=None, verdict='reopen', t=8))
    d = App.derive(fake)
    assert d[0]['decision'] is None and d[0]['pick'] is None and 'aaa' in d[0]['passed']
    fake.state['votes'] = votes[:5]                                               # back, twice
    assert App.derive(fake)[3]['decision'] is None


def test_pick_of_a_gm_fallback_keeps_its_octave_and_adds_the_apps():
    loc = dict(source='VCSL', path='Chordophones/Zithers/Grand Piano, Kawai', sub='Sustains', kind='decay', standin=False,
               note='', octave=1, tags=[])
    c = gm_map._pick_cand(dict(shape='gm', loc=loc, octave=-1, lib_title='VCSL', license='CC0 1.0'), 'decay')
    assert c.octave == 0 and c.kind == 'decay' and c.sub == 'Sustains'



def test_notes_are_kept_per_version_and_beside_the_votes():
    import threading
    from types import SimpleNamespace
    from kobi.swipe.deck import App
    fake = SimpleNamespace(lock=threading.RLock(), state=dict(votes=[], notes={}), _save=lambda: None, write_picks=lambda: None)
    App.note(fake, 0, 'bank', '  thin in the low end  ')
    App.note(fake, 0, 'abc123', 'warmer, noisy attack')
    assert fake.state['notes'] == {'0': {'bank': 'thin in the low end', 'abc123': 'warmer, noisy attack'}}
    assert App._note(fake, 0, None) == 'thin in the low end' and App._note(fake, 0, 'abc123') == 'warmer, noisy attack'
    App.note(fake, 0, 'bank', '')                                  # empty text takes the note away
    assert fake.state['notes'] == {'0': {'abc123': 'warmer, noisy attack'}} and fake.state['votes'] == []


def test_a_layered_pick_becomes_a_stack(tmp_path, monkeypatch):
    for lib in ('A', 'B'):
        d = tmp_path / 'Extra' / lib
        d.mkdir(parents=True)
        sf.write(str(d / 'c4.wav'), np.zeros(100), 44100)
        (d / 'x.sfz').write_text('<region> sample=c4.wav key=60\n')
    monkeypatch.setattr(gm_map, 'ROOT', str(tmp_path))
    programs = [gm_map.Program(0, 'Crystal', [gm_map.Cand('VCSL', 'nowhere', None, 'sustain')])]
    layer = lambda lib, g: dict(shape='sfz', loc=dict(rel='x.sfz'), root=f'Extra/{lib}', octave=0, gain=g, pan=0.0)
    pick = dict(shape='derived', loc=dict(make='stack'), complete=True, layers=[layer('A', 0.0), layer('B', -5.0)])
    path = tmp_path / 'SWIPE_PICKS.json'
    path.write_text(json.dumps({'0': dict(verdict='replace', pick=pick)}))
    layers = {}
    assert len(gm_map.apply_picks(programs, str(path), layers)) == 1
    assert [(c.path, g) for c, g, *_ in layers[0]] == [('A', 0.0), ('B', -5.0)] and programs[0].cands[0].path == 'A'


def test_a_covering_layer_reaches_every_key_of_the_first():
    from kobi.ingest import cover_keys
    regs = [Region(sample='a', lokey=48, hikey=57, pitch_keycenter=57, lovel=1, hivel=110),
            Region(sample='b', lokey=67, hikey=74, pitch_keycenter=67, lovel=1, hivel=110),
            Region(sample='c', lokey=48, hikey=74, pitch_keycenter=60, lovel=111, hivel=127)]
    cover_keys(regs, 55, 94)                                     # the recorder's range
    assert [(r.lokey, r.hikey) for r in regs] == [(48, 57), (67, 94), (48, 94)]


def test_a_single_pick_replaces_a_layered_program(tmp_path, monkeypatch):
    d = tmp_path / 'Extra' / 'Brass'
    d.mkdir(parents=True)
    sf.write(str(d / 'c4.wav'), np.zeros(100), 44100)
    (d / 'x.sfz').write_text('<region> sample=c4.wav key=60\n')
    monkeypatch.setattr(gm_map, 'ROOT', str(tmp_path))
    programs = [gm_map.Program(0, 'Brass Section', [gm_map.Cand('Iowa', 'Trumpet', None, 'sustain')])]
    layers = {0: [(gm_map.Cand('Iowa', 'Trumpet', None, 'sustain'), 0.0, 0.0)]}
    pick = dict(shape='sfz', loc=dict(rel='x.sfz'), root='Extra/Brass', complete=True, octave=0)
    path = tmp_path / 'SWIPE_PICKS.json'
    path.write_text(json.dumps({'0': dict(verdict='replace', pick=pick)}))
    gm_map.apply_picks(programs, str(path), layers)
    assert 0 not in layers and programs[0].cands[0].path == 'Brass'

