"""kobi.swipe.fetch — pull only the bytes a preview needs.

Remote libraries come in three shapes, and none of them is downloaded whole to hear one card:

* GitHub repositories (the sfzinstruments organisation): the tree listing names every file, and
  files come one at a time from raw.githubusercontent.com — the SFZ text first, then only the
  samples the preview phrase plays.
* Zip archives on a server that honours ``Range`` (GitHub releases, Iowa MIS, Versilian): the
  central directory is read from the end of the file, then single members are fetched and
  inflated.  A 400 MB archive costs its directory plus the few notes a card needs.
* Iowa MIS pages: an HTML page per instrument naming its zips (each zip then read as above).

Every byte goes through one ``Fetcher``: one stream at a time, rate-capped, in 256 KB chunks,
resumable through ``.part`` files, so the app never floods the network or the disk.
"""
from __future__ import annotations

import json
import os
import struct
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import zlib

UA = 'kobi-soundbank-swipe/1 (+https://github.com/hidude562/kobi-soundbank)'
CHUNK = 1 << 18


def _github_token() -> str | None:
    tok = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if tok:
        return tok
    try:
        out = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


class Fetcher:
    """One download stream at a time, at most ``max_rate`` bytes/s."""

    def __init__(self, max_rate: float = 5e6):
        self.max_rate = max_rate
        self.lock = threading.Lock()
        self.total = 0                   # bytes pulled this session
        self.current: dict | None = None  # {'label', 'done', 'size'} of the stream in flight
        self._token = _github_token()
        self._small = threading.BoundedSemaphore(6)

    # ------------------------------------------------------------------ plumbing
    def _open(self, url: str, headers: dict | None = None, timeout: float = 60):
        h = {'User-Agent': UA}
        if self._token and urllib.parse.urlparse(url).netloc == 'api.github.com':
            h['Authorization'] = f'Bearer {self._token}'
        h.update(headers or {})
        return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)

    def _pump(self, resp, sink, label: str, size: int | None, start: int = 0) -> int:
        """Copy ``resp`` into ``sink`` in chunks, throttled.  Returns bytes copied."""
        n, t0 = 0, time.monotonic()
        self.current = dict(label=label, done=start, size=size)
        while True:
            buf = resp.read(CHUNK)
            if not buf:
                break
            sink(buf)
            n += len(buf)
            self.total += len(buf)
            self.current['done'] = start + n
            if self.max_rate:
                ahead = n / self.max_rate - (time.monotonic() - t0)
                if ahead > 0:
                    time.sleep(ahead)
        return n

    # ------------------------------------------------------------------ requests
    def json(self, url: str) -> dict | list:
        with self.lock, self._open(url) as r:
            return json.loads(r.read().decode('utf-8'))

    def text(self, url: str) -> str:
        with self.lock, self._open(url) as r:
            return r.read().decode('utf-8', 'replace')

    def range(self, url: str, start: int, end: int, label: str = '') -> tuple[bytes, int]:
        """(bytes ``start``..``end`` inclusive, total file size).  ``start < 0``: the last
        ``-start`` bytes."""
        spec = f'bytes={start}' if start < 0 else f'bytes={start}-{end}'
        out = bytearray()
        with self.lock, self._open(url, {'Range': spec}) as r:
            if r.status != 206:
                raise IOError(f'{url}: server ignored Range (HTTP {r.status})')
            self._pump(r, out.extend, label or os.path.basename(url), None if start < 0 else end - start + 1)
            total = int(r.headers.get('Content-Range', '/0').rsplit('/', 1)[-1] or 0)
        return bytes(out), total

    def download(self, url: str, dst: str, label: str = '') -> int:
        """Stream ``url`` to ``dst`` (resuming a ``.part``).  Returns the file size."""
        if os.path.exists(dst):
            return os.path.getsize(dst)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        part = dst + '.part'
        have = os.path.getsize(part) if os.path.exists(part) else 0
        with self.lock, self._open(url, {'Range': f'bytes={have}-'} if have else None) as r:
            if have and r.status != 206:
                have = 0                                   # no resume: start over
            size = r.headers.get('Content-Length')
            size = int(size) + have if size else None
            with open(part, 'ab' if have else 'wb') as fh:
                self._pump(r, fh.write, label or os.path.basename(dst), size, have)
        os.replace(part, dst)
        return os.path.getsize(dst)

    def small(self, url: str, dst: str) -> int:
        """A text file (SFZ, include, licence): fetched outside the one-stream lock, a few at a time —
        hundreds of 2 KB requests in a row cost latency, not bandwidth."""
        if os.path.exists(dst):
            return os.path.getsize(dst)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with self._small, self._open(url) as r:
            data = r.read()
        self.total += len(data)
        with open(dst + '.part', 'wb') as fh:
            fh.write(data)
        os.replace(dst + '.part', dst)
        return len(data)

    def status(self) -> dict:
        return dict(total=self.total, current=self.current if self.lock.locked() else None, max_rate=self.max_rate)


# ---------------------------------------------------------------------- GitHub repositories

AUDIO = ('.wav', '.flac', '.ogg', '.aif', '.aiff', '.mp3', '.wv')
TEXTLIKE = ('.sfz', '.sfzh', '.txt', '.inc', '.h', '.md', '.xml', '.cfg', '')


class GitHubRepo:
    """A repository mirrored file by file into ``root``."""

    def __init__(self, fetcher: Fetcher, repo: str, root: str, cache: str):
        self.f, self.repo, self.root = fetcher, repo, root
        self.cache = os.path.join(cache, 'github', repo.replace('/', '__') + '.json')
        self._tree = None

    def tree(self) -> dict:
        """{'branch', 'files': {path: size}} — cached on disk after the first two API calls."""
        if self._tree is None:
            if os.path.exists(self.cache):
                with open(self.cache) as fh:
                    self._tree = json.load(fh)
            else:
                meta = self.f.json(f'https://api.github.com/repos/{self.repo}')
                branch = meta['default_branch']
                t = self.f.json(f'https://api.github.com/repos/{self.repo}/git/trees/{branch}?recursive=1')
                files = {e['path']: e.get('size', 0) for e in t['tree'] if e['type'] == 'blob'}
                self._tree = dict(branch=branch, files=files, truncated=t.get('truncated', False))
                os.makedirs(os.path.dirname(self.cache), exist_ok=True)
                with open(self.cache, 'w') as fh:
                    json.dump(self._tree, fh)
        return self._tree

    def lookup(self, rel: str) -> str | None:
        """The repository path for ``rel``, matching case-insensitively (SFZ files are written on
        Windows as often as not)."""
        files = self.tree()['files']
        if rel in files:
            return rel
        low = rel.replace('\\', '/').lower()
        for p in files:
            if p.lower() == low:
                return p
        return None

    def local(self, path: str) -> str:
        return os.path.join(self.root, path)

    def fetch(self, path: str) -> str:
        dst = self.local(path)
        if not os.path.exists(dst):
            q = urllib.parse.quote(path)
            url = f'https://raw.githubusercontent.com/{self.repo}/{self.tree()["branch"]}/{q}'
            if os.path.splitext(path)[1].lower() in TEXTLIKE and self.size_of(path) <= 512 * 1024:
                self.f.small(url, dst)
            else:
                self.f.download(url, dst, f'{self.repo.split("/")[-1]}: {os.path.basename(path)}')
            with open(dst, 'rb') as fh:
                head = fh.read(64)
            if head.startswith(b'version https://git-lfs'):          # an LFS pointer: the media host has the bytes
                os.remove(dst)
                self.f.download(f'https://media.githubusercontent.com/media/{self.repo}/{self.tree()["branch"]}/{q}', dst,
                                f'{self.repo.split("/")[-1]}: {os.path.basename(path)}')
        return dst

    def sfz_files(self) -> list:
        return [p for p in self.tree()['files'] if p.lower().endswith('.sfz')]

    def fetch_text(self, limit: int = 512 * 1024) -> None:
        """Every small non-audio file (SFZ, includes, licence, readme) — what parsing needs."""
        for p, size in self.tree()['files'].items():
            ext = os.path.splitext(p)[1].lower()
            if ext in TEXTLIKE and size <= limit:
                self.fetch(p)

    def size_of(self, path: str) -> int:
        return self.tree()['files'].get(path, 0)


# ---------------------------------------------------------------------- remote zip archives

class RemoteZip:
    """A zip archive read over HTTP Range: the directory once, then members one by one."""

    def __init__(self, fetcher: Fetcher, url: str, cache: str):
        self.f, self.url = fetcher, url
        key = urllib.parse.quote(url, safe='')[-180:]
        self.cache = os.path.join(cache, 'zip', key + '.json')
        self._members = None

    def members(self) -> dict:
        """{name: {'offset', 'csize', 'size', 'method', 'crc'}}"""
        if self._members is None:
            if os.path.exists(self.cache):
                with open(self.cache) as fh:
                    self._members = json.load(fh)
            else:
                self._members = self._read_directory()
                os.makedirs(os.path.dirname(self.cache), exist_ok=True)
                with open(self.cache, 'w') as fh:
                    json.dump(self._members, fh)
        return self._members

    def _read_directory(self) -> dict:
        tail, total = self.f.range(self.url, -(1 << 16), 0, 'zip directory')
        base = total - len(tail)
        i = tail.rfind(b'PK\x05\x06')
        if i < 0:
            raise IOError(f'{self.url}: no end-of-central-directory record in the last 64 KB')
        _, _, _, _, count, cd_size, cd_off, _ = struct.unpack('<IHHHHIIH', tail[i:i + 22])
        j = tail.rfind(b'PK\x06\x06')                    # zip64 end record
        if j >= 0:
            count, cd_size, cd_off = struct.unpack('<QQQ', tail[j + 32:j + 56])
        cd = tail[cd_off - base: cd_off - base + cd_size] if cd_off >= base else \
            self.f.range(self.url, cd_off, cd_off + cd_size - 1, 'zip directory')[0]
        out, p = {}, 0
        while p + 46 <= len(cd) and cd[p:p + 4] == b'PK\x01\x02':
            (_, _, _, flags, method, _, _, crc, csize, size, nlen, xlen, clen, _, _, _, off) = \
                struct.unpack('<IHHHHHHIIIHHHHHII', cd[p:p + 46])
            name = cd[p + 46:p + 46 + nlen].decode('utf-8' if flags & 0x800 else 'cp437', 'replace')
            extra = cd[p + 46 + nlen:p + 46 + nlen + xlen]
            if 0xFFFFFFFF in (csize, size, off):              # zip64 sizes / offset in the extra field
                q = 0
                while q + 4 <= len(extra):
                    hid, hlen = struct.unpack('<HH', extra[q:q + 4])
                    if hid == 1:
                        vals, r = [], q + 4
                        for present in (size == 0xFFFFFFFF, csize == 0xFFFFFFFF, off == 0xFFFFFFFF):
                            if present:
                                vals.append(struct.unpack('<Q', extra[r:r + 8])[0]); r += 8
                            else:
                                vals.append(None)
                        size = vals[0] if vals[0] is not None else size
                        csize = vals[1] if vals[1] is not None else csize
                        off = vals[2] if vals[2] is not None else off
                    q += 4 + hlen
            if not name.endswith('/'):
                out[name] = dict(offset=off, csize=csize, size=size, method=method, crc=crc)
            p += 46 + nlen + xlen + clen
        return out

    def extract(self, name: str, dst: str) -> str:
        if os.path.exists(dst):
            return dst
        m = self.members()[name]
        head = self.f.range(self.url, m['offset'], m['offset'] + 29, 'zip header')[0]
        nlen, xlen = struct.unpack('<HH', head[26:30])
        start = m['offset'] + 30 + nlen + xlen
        data = self.f.range(self.url, start, start + m['csize'] - 1, os.path.basename(name))[0] if m['csize'] else b''
        if m['method'] == 8:
            data = zlib.decompressobj(-15).decompress(data)
        elif m['method'] != 0:
            raise IOError(f'{name}: zip method {m["method"]} not supported')
        if zlib.crc32(data) & 0xFFFFFFFF != m['crc']:
            raise IOError(f'{name}: CRC mismatch')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst + '.part', 'wb') as fh:
            fh.write(data)
        os.replace(dst + '.part', dst)
        return dst


def iowa_zips(fetcher: Fetcher, page: str, cache: str) -> list:
    """Zip URLs named on an Iowa MIS 2012 instrument page (cached)."""
    import re
    path = os.path.join(cache, 'iowa', os.path.basename(page) + '.json')
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    html = fetcher.text('https://theremin.music.uiowa.edu/MIS-Pitches-2012/' + page)
    zips = ['https://theremin.music.uiowa.edu/' + urllib.parse.quote(z.replace('../', ''))
            for z in re.findall(r'href="([^"]*\.zip)"', html)]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as fh:
        json.dump(zips, fh)
    return zips
