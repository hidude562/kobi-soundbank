"""kobi.swipe.deck — the vote log, which instrument and which version to show, and the picks.

One card per GM program.  Its options are the bank's current sound and every alternative the
catalogue ranks for the program (other banks and libraries of the same instrument); the viewer
cycles through them and gives the program one verdict: keep (the bank's own), pick (one of the
alternatives), none (nothing on offer is good) or skip.

State is an append-only list of votes (back pops the last one) plus a cursor into the programs.
Everything else is derived from the log, so a restart or a back can never leave it inconsistent.
Votes written by the first version of the deck (a verdict on the bank's sound, then one per
alternative) are read too: a disliked program with no pick comes back as an open card.

Only what is near the viewer is prepared: the option on screen and the ``BUFFER`` after it.  Before
the viewer starts cycling a card, look-ahead stays on disk (no downloads for a card that may be kept).
"""
from __future__ import annotations

import json
import multiprocessing
import os
import threading
import time
from concurrent.futures import ProcessPoolExecutor

from .. import gm_map, paths
from .catalog import Catalog, current_cand
from .fetch import Fetcher
from .gm_words import DRUMS, family
from .jobs import Jobs
from .libraries import ALL
from .prep import Prep

BUFFER = 2
AUTO_FULL = 100e6          # a pick whose whole instrument is bigger waits for a click in the list
PROGRAMS = list(range(128)) + [DRUMS]
NAMES = {p.num: p.name for p in gm_map.PROGRAMS}
NAMES[DRUMS] = 'Drum kit'


class Ctx:
    def __init__(self, fetcher, cache):
        self.fetcher, self.cache = fetcher, cache


class App:
    def __init__(self, store: str, max_rate: float = 5e6, max_bytes: int = 40 << 20, workers: int = 2, log=print,
                 picks: str | None = None):
        self.store, self.log = store, log
        self.picks = picks or os.path.join(paths.ROOT, 'SWIPE_PICKS.json')
        os.makedirs(store, exist_ok=True)
        self.fetcher = Fetcher(max_rate)
        self.catalog = Catalog(Ctx(self.fetcher, os.path.join(store, 'index')))
        self.pool = ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'))
        self.prep = Prep(self.catalog, self.fetcher, store, self.pool, max_bytes)
        self.jobs = Jobs({'cpu': workers, 'net': 2}, log)
        self.lock = threading.RLock()
        self.path = os.path.join(store, 'state.json')
        self.state = dict(votes=[], cursor=0, failed={}, complete={}, confirmed={}, notes={}, review={})
        if os.path.exists(self.path):
            with open(self.path) as fh:
                self.state.update(json.load(fh))
        t = time.time()
        self.catalog.scan_local()
        log(f'local libraries: {len(self.catalog.alts)} instruments ({time.time() - t:.1f} s)')
        threading.Thread(target=self.catalog.index_all_remote, kwargs=dict(log=log), daemon=True).start()
        for d in self.derive().values():                  # picks whose full fetch did not finish last time
            if d['pick'] and d['pick'] not in self.state['complete'] and \
                    (d['pick'] in self.state['confirmed'] or (d.get('full_bytes') or 0) <= AUTO_FULL):
                self._full_job(d['pick'])

    # ------------------------------------------------------------------ state
    def _save(self) -> None:
        tmp = self.path + '.tmp'
        with open(tmp, 'w') as fh:
            json.dump(self.state, fh, indent=1)
        os.replace(tmp, self.path)

    def derive(self) -> dict:
        """{program: {'decision': None|'keep'|'pick'|'none'|'skip', 'pick', 'octave', 'full_bytes', 'since',
        'passed': option ids turned down in the first deck}}"""
        out = {p: dict(decision=None, pick=None, octave=0, full_bytes=None, since=None, passed=[], last=0.0) for p in PROGRAMS}
        for v in self.state['votes']:
            d = out[v['program']]
            kind = v['card'].split(':', 1)[0]
            if kind in ('prog', 'main', 'alt', 'reviewed'):
                d['last'] = v['t']
            if kind == 'prog':                           # one verdict per program
                d['decision'], d['since'] = v['verdict'], v['t']
                d['pick'] = v.get('cid') if v['verdict'] == 'pick' else None
                d['octave'], d['full_bytes'] = v.get('octave', 0), v.get('full_bytes')
            elif kind == 'main':                         # first deck: a verdict on the bank's sound ...
                d['since'] = v['t']
                if v['verdict'] == 'dislike':
                    d['decision'], d['pick'] = None, None
                    d['passed'].append('bank')
                else:
                    d['decision'], d['pick'] = {'like': 'keep', 'skip': 'skip'}.get(v['verdict'], v['verdict']), None
            elif kind == 'alt':                          # ... then one per alternative
                if v['verdict'] == 'like':
                    d['decision'], d['pick'], d['since'] = 'pick', v['cid'], v['t']
                    d['octave'], d['full_bytes'] = v.get('octave', 0), v.get('full_bytes')
                elif v['cid'] not in d['passed']:
                    d['passed'].append(v['cid'])
            elif kind == 'reopen':
                d['decision'], d['pick'] = None, None
        for key, rv in self.state.get('review', {}).items():   # asked to look again, not answered since
            d = out.get(int(key))
            if d is not None:
                d['review'] = rv if rv['t'] > d['last'] and d['decision'] is not None else None
        return out

    def vote(self, program: int, verdict: str, option: str | None = None) -> dict:
        """``verdict``: 'pick' the option playing (the bank's own is a keep), 'none' of them, or 'skip'."""
        if program not in PROGRAMS or verdict not in ('pick', 'none', 'skip'):
            raise ValueError(f'no verdict {verdict!r} for program {program!r}')
        v = dict(card=f'prog:{program}', program=program, cid=None, verdict=verdict, t=time.time())
        if verdict == 'skip' and self.derive()[program].get('review'):
            v = dict(card=f'reviewed:{program}', program=program, cid=None, verdict='reviewed', t=time.time())
        elif verdict == 'pick' and option not in (None, 'bank'):
            job = self.jobs.get(('alt', program, option))
            res = job.result if job is not None and job.status == 'done' else (self.prep.cached_alt(option, program) or {})
            v.update(cid=option, octave=int(res.get('octave', 0)), full_bytes=res.get('full_bytes'))
        elif verdict == 'pick':
            v['verdict'] = 'keep'
        with self.lock:
            self.state['votes'].append(v)
            if self.state.get('front') == program:
                self.state['front'] = None
            self._save()
        if v['cid'] and (v.get('full_bytes') or 0) <= AUTO_FULL:
            self._full_job(v['cid'])
        self.write_picks()
        return dict(ok=True)

    def _full_job(self, cid: str):
        def run(job):
            res = self.prep.full_fetch(cid, job)
            with self.lock:
                self.state['complete'][cid] = res
                self._save()
            self.write_picks()
            return res
        return self.jobs.submit(('full', cid), run, 5, 'net')

    def back(self) -> dict:
        """Take back the last verdict and show its program again, on the option that was chosen."""
        with self.lock:
            v = self.state['votes'].pop() if self.state['votes'] else None
            if v is not None:
                self.state['front'] = v['program']
            self._save()
        self.write_picks()
        if v is None:
            return dict(ok=True, program=None, focus=None)
        return dict(ok=True, program=v['program'], focus=v.get('cid') or 'bank')

    def review(self, programs: list, reasons: dict | None = None) -> dict:
        """Ask for another look at ``programs``: they come back as cards after the unrated ones, keep
        their verdict until a new one is given, and start on the versions added since."""
        now = time.time()
        with self.lock:
            for p in programs:
                if int(p) in PROGRAMS:
                    self.state.setdefault('review', {})[str(int(p))] = dict(t=now, reason=(reasons or {}).get(str(p), ''))
            self._save()
        return dict(ok=True, review=len(programs))

    def reopen(self, program: int) -> dict:
        with self.lock:
            self.state['votes'].append(dict(card=f'reopen:{program}', program=program, cid=None, verdict='reopen', t=time.time()))
            self.state['front'] = program
            self._save()
        self.write_picks()
        return dict(ok=True)

    def note(self, program: int, option: str, text: str) -> dict:
        """The viewer's note on one version of a program ('bank' or an alternative); empty text removes it.
        Notes live beside the vote log, not in it, so going back never takes one away."""
        if program not in PROGRAMS or not option:
            raise ValueError(f'no version {option!r} of program {program!r}')
        text = (text or '').strip()[:2000]
        with self.lock:
            notes = self.state['notes'].setdefault(str(program), {})
            if text:
                notes[option] = text
            else:
                notes.pop(option, None)
            self._save()
        self.write_picks()
        return dict(ok=True, note=text)

    def _note(self, program: int, option: str | None) -> str:
        return self.state['notes'].get(str(program), {}).get(option or 'bank', '')

    def fetch_full(self, cid: str) -> dict:
        """The go-ahead for a big pick's whole instrument."""
        with self.lock:
            self.state['confirmed'][cid] = time.time()
            self._save()
        self._full_job(cid)
        return dict(ok=True)

    def set_cursor(self, program: int) -> dict:
        with self.lock:
            self.state['cursor'] = PROGRAMS.index(program)
            self.state['front'] = program
            self._save()
        return dict(ok=True)

    def _failed(self, program: int, cid: str, why: str) -> None:
        with self.lock:
            self.state['failed'].setdefault(str(program), {})[cid] = why
            self._save()

    # ------------------------------------------------------------------ jobs
    def _bank_job(self, bank: str, program: int, prio: int):
        return self.jobs.submit(('bank', bank, program), lambda job: self.prep.bank_preview(bank, program, job), prio)

    def _source_job(self, program: int, prio: int):
        return self.jobs.submit(('source', program), lambda job: self.prep.source_preview(program, job), prio)

    def _alt_job(self, program: int, cid: str, prio: int):
        alt = self.catalog.get(cid)
        lib = ALL.get(alt.lib) if alt else None
        lane = 'net' if lib is not None and lib.remote else 'cpu'
        return self.jobs.submit(('alt', program, cid), lambda job: self.prep.alt_preview(cid, program, job), prio, lane)

    @staticmethod
    def _audio(job) -> dict:
        if job is None or job.status != 'done':
            return dict(status=job.status if job else 'queued', error=job.error if job else None,
                        progress=job.progress if job else '')
        r = job.result
        return dict(status='done', key=r['key'], wave=r.get('wave'), secs=r.get('secs'), shift=r.get('shift', 0),
                    octave=r.get('octave', 0), fetched=r.get('fetched', 0), source=r.get('source', ''), regions=r.get('regions'),
                    full_bytes=r.get('full_bytes'))

    # ------------------------------------------------------------------ the deck
    def deck(self, focus: str | None = None) -> dict:
        """{'card': the program on screen with all its options, 'next': the programs after it}."""
        with self.lock:
            derived = self.derive()
            cursor, front = self.state['cursor'], self.state.get('front')
        order = PROGRAMS[cursor:] + PROGRAMS[:cursor]
        open_ = [p for p in order if derived[p]['decision'] is None]
        open_ += [p for p in PROGRAMS if derived[p].get('review')]     # then another look, in program order
        on = front is not None and (derived[front]['decision'] is None or derived[front].get('review'))
        p = front if on else (open_[0] if open_ else None)
        if p is None:
            return dict(card=None, next=[])
        card = self._card(p, derived[p], focus)
        ahead = [q for q in open_ if q != p][:2]
        for i, q in enumerate(ahead):                    # the next cards' bank sound, rendered from disk
            self._bank_job('slim', q, 2 + i)
        return dict(card=card, next=[dict(program=q, bank=self._audio(self.jobs.get(('bank', 'slim', q)))) for q in ahead])

    def _card(self, p: int, d: dict, focus: str | None) -> dict:
        failed = self.state['failed'].get(str(p), {})
        alts = self.catalog.ranked(p, exclude=set(failed))
        rv = d.get('review')
        if rv:                                           # another look: what was added since comes first
            alts = [a for a in alts if a.to_json()['new']] + [a for a in alts if not a.to_json()['new']]
        ids = ['bank'] + [a.cid for a in alts]
        if focus not in ids:                             # a fresh card: start on the first version not turned down
            fresh = [a.cid for a in alts if a.to_json()['new']] if rv else []
            focus = fresh[0] if fresh else next((i for i in ids if i not in d['passed']), 'bank')
        f = ids.index(focus)
        slim = self._bank_job('slim', p, 0 if f == 0 else 1)
        micro = self._bank_job('micro', p, 4)
        src = self._source_job(p, 4) if p != DRUMS else None
        for i in range(max(1, f), min(len(ids), f + BUFFER + 1)):
            lib = ALL.get(alts[i - 1].lib)
            if f == 0 and i > f and lib is not None and lib.remote:
                continue                                 # not cycling yet: no downloads ahead
            job = self._alt_job(p, ids[i], 0 if i == f else i - f)
            if job.status == 'failed':
                self._failed(p, ids[i], job.error or 'failed')
        c = current_cand(p)
        cur = (_label(c.path) + (f' / {c.sub}' if c.sub and c.source not in ('FreePats', 'Karoryfer') else '')
               + f' · {c.source}') if c else 'kobi.drums GM kit · Big Rusty + VCSL percussion'
        options = [dict(id='bank', type='bank', title='Now in the bank', lib_title=cur, license='', remote=False,
                        listed=False, passed='bank' in d['passed'], note=self._note(p, 'bank'), audio=self._audio(slim),
                        compare=dict(micro=self._audio(micro), source=self._audio(src) if src else None))]
        for a in alts:
            options.append(dict(a.to_json(), id=a.cid, type='alt', passed=a.cid in d['passed'], note=self._note(p, a.cid),
                                audio=self._audio(self.jobs.get(('alt', p, a.cid)))))
        review = None
        if rv:
            pick = self.catalog.get(d['pick']) if d['pick'] else None
            review = dict(decision=d['decision'], pick=pick.title if pick else None, pick_lib=ALL[pick.lib].title if pick else None,
                          reason=rv.get('reason') or self._note(p, d['pick']), new=sum(1 for o in options if o.get('new')))
        return dict(program=p, name=NAMES[p], family=family(p), current=cur, standin=bool(c and c.standin),
                    options=options, focus=focus, review=review)

    # ------------------------------------------------------------------ overview
    def overview(self) -> dict:
        with self.lock:
            derived = self.derive()
        rows = []
        for p in PROGRAMS:
            d = derived[p]
            alt = self.catalog.get(d['pick']) if d['pick'] else None
            full = self.jobs.get(('full', d['pick'])) if d['pick'] else None
            # rated programs have their previews on disk: asking again costs a cache read, and brings
            # the play buttons back after a restart
            bank = self._bank_job('slim', p, 4) if d['decision'] else self.jobs.get(('bank', 'slim', p))
            pj = self._alt_job(p, d['pick'], 4) if alt else None
            rows.append(dict(program=p, name=NAMES[p], family=family(p), decision=d['decision'],
                             pick=alt.to_json() if alt else None,
                             pick_audio=self._audio(pj) if pj else None, bank_audio=self._audio(bank) if bank else None,
                             full=('done' if d['pick'] in self.state['complete'] else full.status if full else
                                   'confirm' if d['pick'] else None),
                             full_bytes=d.get('full_bytes'), full_progress=(full.progress if full else ''),
                             note_on=d['pick'] or 'bank', note=self._note(p, d['pick']), review=bool(d.get('review')),
                             notes=len(self.state['notes'].get(str(p), {}))))
        return dict(rows=rows, cursor=PROGRAMS[self.state['cursor']])

    def status(self) -> dict:
        with self.lock:
            derived = self.derive()
        voted = sum(1 for d in derived.values() if d['decision'] is not None)
        picks = sum(1 for d in derived.values() if d['decision'] == 'pick')
        none = sum(1 for d in derived.values() if d['decision'] == 'none')
        review = sum(1 for d in derived.values() if d.get('review'))
        return dict(voted=voted, total=len(PROGRAMS), picks=picks, none=none, review=review, back=len(self.state['votes']),
                    fetch=self.fetcher.status(), jobs=self.jobs.summary(), catalog=self.catalog.counts())

    # ------------------------------------------------------------------ what it adds up to
    def write_picks(self) -> None:
        """SWIPE_PICKS.json / .md in the repository: per program keep / replace-with / still searching."""
        with self.lock:                                  # a vote and a finished full fetch may both write
            self._write_picks()

    def _write_picks(self) -> None:
        derived = self.derive()
        out, lines = {}, ['# Swipe picks', '',
                          'Written by `python3 -m kobi.swipe` on every vote.  `keep`: the bank\'s current sound was chosen; '
                          '`replace`: another version was picked (gm_map puts it first once its full fetch is complete); '
                          '`none`: nothing on offer was good; `skipped`: undecided.', '',
                          '| # | program | verdict | pick | library | licence | on disk | note |', '|---|---|---|---|---|---|---|---|']
        for p in PROGRAMS:
            d = derived[p]
            notes = self.state['notes'].get(str(p), {})
            if d['decision'] is None and not notes:
                continue
            row = dict(program=p, name=NAMES[p], verdict={'keep': 'keep', 'skip': 'skipped', 'none': 'none', None: 'open'}.get(
                       d['decision'], 'replace'), passed=d['passed'], note=self._note(p, d['pick']))
            if notes:
                row['notes'] = dict(notes)                   # every version noted, by option id ('bank' or a candidate)
            alt = self.catalog.get(d['pick']) if d['pick'] else None
            if alt is not None:
                lib = ALL.get(alt.lib)
                row.update(verdict='replace', pick=dict(alt.to_json(), loc=alt.loc,
                                                       root=os.path.relpath(_root(lib, alt), paths.SOURCES) if lib else None,
                                                       complete=bool(not (lib and lib.remote) or alt.cid in self.state['complete']),
                                                       octave=d.get('octave', 0), note=self._note(p, d['pick'])))
                if alt.shape == 'derived' and alt.loc.get('make') == 'stack':
                    row['pick']['layers'] = self._layers(p, alt)
                    row['pick']['complete'] = alt.cid in self.state['complete'] or \
                        all(not ALL[self.catalog.get(L['cid']).lib].remote for L in alt.loc['layers'] if self.catalog.get(L['cid']))
            out[str(p)] = row
            pk = row.get('pick')
            waiting = pk and not pk['complete'] and alt.cid not in self.state['confirmed'] and (d.get('full_bytes') or 0) > AUTO_FULL
            on_disk = '' if not pk else 'yes' if pk['complete'] else \
                f"waiting for OK ({(d.get('full_bytes') or 0) / 1e6:.0f} MB)" if waiting else 'fetching'
            note = ' '.join(row['note'].split()).replace('|', '/')
            lines.append(f"| {p} | {NAMES[p]} | {row['verdict']} | {pk['title'] if pk else ''} | {pk['lib_title'] if pk else ''} | "
                         f"{pk['license'] if pk else ''} | {on_disk} | {note} |")
        tmp = self.picks + '.tmp'
        with open(tmp, 'w') as fh:
            json.dump(out, fh, indent=1)
        os.replace(tmp, self.picks)
        with open(os.path.splitext(self.picks)[0] + '.md', 'w') as fh:
            fh.write('\n'.join(lines) + '\n')


def _layer_pick(self, p: int, cid: str, gain: float, pan: float, cover: bool = False) -> dict | None:
    la = self.catalog.get(cid)
    if la is None:
        return None
    lib = ALL.get(la.lib)
    res = self.prep.cached_alt(cid, p) or {}
    return dict(la.to_json(), loc=la.loc, root=os.path.relpath(_root(lib, la), paths.SOURCES) if lib else None,
                octave=int(res.get('octave', 0)), gain=gain, pan=pan, cover=cover)


def _layers(self, p: int, alt) -> list:
    """A picked stack's layers as gm_map needs them (each its own pick, with a gain and a pan)."""
    return [x for x in (_layer_pick(self, p, L['cid'], L.get('gain', 0.0), L.get('pan', 0.0), bool(L.get('cover')))
                        for L in alt.loc['layers']) if x]


App._layers = _layers


def _label(path: str) -> str:
    """An instrument folder's name, with its parent when that says something (TX81Z / Piano 1)."""
    parts = path.rstrip('/').split('/')
    if len(parts) > 1 and not parts[-2].endswith(('phones', 'Zithers', 'Strings', 'Brass', 'Woodwinds', 'Keys', 'Percussion')) \
            and len(parts[-1]) < 12:
        return f'{parts[-2]} / {parts[-1]}'
    return parts[-1]


def _root(lib, alt):
    from .catalog import lib_root
    return lib_root(lib, alt)
