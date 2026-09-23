"""kobi.swipe.server — the HTTP face of the app (stdlib only).

    GET  /                      the swipe page
    GET  /api/deck?focus=<id>   the program on screen with all its versions (preparing <id> and the next ones)
    GET  /api/status            progress, downloads, background work
    GET  /api/overview          every program: verdict, pick, full-fetch state
    POST /api/vote              {"program": n, "verdict": "pick" | "none" | "skip", "option": id}
    POST /api/back | /api/reopen {"program"} | /api/cursor {"program"} | /api/fetch {"cid"} (a big pick's go-ahead)
    POST /api/note              {"program": n, "option": id, "text": "..."} (empty text removes the note)
    POST /api/review            {"programs": [n, ...], "reasons": {n: "..."}} (another look, new versions first)
    GET  /media/<key>.mp3|.flac a rendered preview (content-keyed, cached forever)
"""
from __future__ import annotations

import json
import os
import re
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
         '.mp3': 'audio/mpeg', '.flac': 'audio/flac', '.svg': 'image/svg+xml'}
_MEDIA = re.compile(r'^/media/([0-9a-f]{16})\.(mp3|flac)$')


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'kobi-swipe/1'

        def log_message(self, fmt, *args):             # quiet: the console is for downloads and errors
            pass

        def _send(self, code: int, body: bytes, ctype: str, cache: str = 'no-store') -> None:
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', cache)
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj).encode(), 'application/json')

        def _file(self, path: str, cache: str) -> None:
            if not os.path.isfile(path):
                return self._send(404, b'not found', 'text/plain')
            with open(path, 'rb') as fh:
                self._send(200, fh.read(), TYPES.get(os.path.splitext(path)[1], 'application/octet-stream'), cache)

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            try:
                u = urlparse(self.path)
                q = parse_qs(u.query)
                if u.path in ('/', '/index.html'):
                    return self._file(os.path.join(STATIC, 'index.html'), 'no-cache')
                if u.path in ('/app.js', '/app.css', '/icon.svg'):
                    return self._file(os.path.join(STATIC, u.path[1:]), 'no-cache')
                m = _MEDIA.match(u.path)
                if m:
                    return self._file(os.path.join(app.prep.out, f'{m.group(1)}.{m.group(2)}'), 'public, max-age=31536000, immutable')
                if u.path == '/api/deck':
                    return self._json(dict(app.deck(q.get('focus', [None])[0]), status=app.status()))
                if u.path == '/api/status':
                    return self._json(app.status())
                if u.path == '/api/overview':
                    return self._json(app.overview())
                return self._send(404, b'not found', 'text/plain')
            except Exception:
                app.log(traceback.format_exc())
                return self._json(dict(error='server error'), 500)

        def do_POST(self):
            try:
                n = int(self.headers.get('Content-Length') or 0)
                body = json.loads(self.rfile.read(n) or b'{}')
                u = urlparse(self.path)
                if u.path == '/api/vote':
                    return self._json(app.vote(int(body['program']), str(body['verdict']), body.get('option')))
                if u.path == '/api/back':
                    return self._json(app.back())
                if u.path == '/api/reopen':
                    return self._json(app.reopen(int(body['program'])))
                if u.path == '/api/cursor':
                    return self._json(app.set_cursor(int(body['program'])))
                if u.path == '/api/fetch':
                    return self._json(app.fetch_full(str(body['cid'])))
                if u.path == '/api/review':
                    return self._json(app.review([int(x) for x in body['programs']], body.get('reasons')))
                if u.path == '/api/note':
                    return self._json(app.note(int(body['program']), str(body['option']), str(body.get('text') or '')))
                return self._send(404, b'not found', 'text/plain')
            except (KeyError, ValueError) as e:
                return self._json(dict(error=f'bad request: {e}'), 400)
            except Exception:
                app.log(traceback.format_exc())
                return self._json(dict(error='server error'), 500)

    return Handler


def serve(app, host: str, port: int) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), make_handler(app))
    httpd.daemon_threads = True
    return httpd
