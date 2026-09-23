"""kobi.swipe.jobs — a small priority queue of background work.

Priorities: 0 the card on screen, 1 the next cards, 2 the alternatives buffer of disliked programs,
3 look-ahead on the main deck, 5 full fetches after a pick.  Asking for a job again with a better
priority moves it up; a finished job is never run twice.

Two lanes with their own threads: 'cpu' (renders of what is on disk) and 'net' (anything that may
download), so a slow remote library never holds up the card on screen.
"""
from __future__ import annotations

import heapq
import itertools
import threading
import time
import traceback


class Job:
    __slots__ = ('key', 'fn', 'prio', 'status', 'result', 'error', 'progress', 't0', 't1')

    def __init__(self, key, fn, prio):
        self.key, self.fn, self.prio = key, fn, prio
        self.status, self.result, self.error, self.progress = 'queued', None, None, ''
        self.t0 = self.t1 = None


class Jobs:
    def __init__(self, lanes: dict | None = None, log=print):
        lanes = lanes or {'cpu': 2, 'net': 2}
        self.cv = threading.Condition()
        self.heaps: dict = {lane: [] for lane in lanes}
        self.jobs: dict = {}
        self.seq = itertools.count()
        self.log = log
        for lane, n in lanes.items():
            for i in range(n):
                threading.Thread(target=self._run, args=(lane,), name=f'swipe-{lane}-{i}', daemon=True).start()

    def submit(self, key, fn, prio: int, lane: str = 'cpu') -> Job:
        with self.cv:
            job = self.jobs.get(key)
            if job is None:
                job = self.jobs[key] = Job(key, fn, prio)
            elif job.status != 'queued' or prio >= job.prio:
                return job
            job.prio = prio
            heapq.heappush(self.heaps[lane], (prio, next(self.seq), key))
            self.cv.notify_all()
            return job

    def get(self, key) -> Job | None:
        return self.jobs.get(key)

    def retry(self, key) -> None:
        with self.cv:
            self.jobs.pop(key, None)

    def _run(self, lane: str) -> None:
        heap = self.heaps[lane]
        while True:
            with self.cv:
                while True:
                    while heap:
                        prio, _, key = heapq.heappop(heap)
                        job = self.jobs.get(key)
                        if job is not None and job.status == 'queued' and job.prio == prio:
                            break
                    else:
                        self.cv.wait()
                        continue
                    break
                job.status, job.t0 = 'running', time.time()
            try:
                job.result = job.fn(job)
                job.status = 'done'
            except Exception as e:                      # Skip and real errors alike end the job
                job.error = f'{type(e).__name__}: {e}' if type(e).__name__ != 'Skip' else str(e)
                job.status = 'failed'
                if type(e).__name__ != 'Skip':
                    self.log(f'job {job.key} failed:\n' + traceback.format_exc(limit=6))
            job.t1 = time.time()
            job.progress = ''

    def summary(self) -> dict:
        with self.cv:
            st = {}
            for j in self.jobs.values():
                st[j.status] = st.get(j.status, 0) + 1
            running = [dict(key=str(j.key), progress=j.progress) for j in self.jobs.values() if j.status == 'running']
            return dict(counts=st, running=running)
