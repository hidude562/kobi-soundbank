"""A static file server that honours HTTP Range requests (python -m http.server does not), for the
browser tests and for trying the scheduler demo locally.

    python3 kobi_web/test/rangeserver.py [port] [root]
"""
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class RangeHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def send_head(self):
        rng = self.headers.get('Range')
        path = self.translate_path(self.path)
        if not rng or not rng.startswith('bytes=') or not os.path.isfile(path):
            return super().send_head()
        size = os.path.getsize(path)
        a, _, b = rng[6:].partition('-')
        start = int(a) if a else max(0, size - int(b))
        end = min(int(b) if b and a else size - 1, size - 1)
        if start > end or start >= size:
            self.send_response(416)
            self.send_header('Content-Range', f'bytes */{size}')
            self.end_headers()
            return None
        f = open(path, 'rb')
        f.seek(start)
        self.send_response(206)
        self.send_header('Content-Type', self.guess_type(path))
        self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length', str(end - start + 1))
        self.end_headers()
        self._range_len = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        n = getattr(self, '_range_len', None)
        if n is None:
            return super().copyfile(source, outputfile)
        while n > 0:
            chunk = source.read(min(65536, n))
            if not chunk:
                break
            outputfile.write(chunk)
            n -= len(chunk)

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    os.chdir(sys.argv[2] if len(sys.argv) > 2 else (os.environ.get('KOBI_ROOT') or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    ThreadingHTTPServer(('127.0.0.1', port), RangeHandler).serve_forever()
