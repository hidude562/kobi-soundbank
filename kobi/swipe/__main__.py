"""Swipe through the bank's sounds; a left swipe pulls up alternatives.

    python3 -m kobi.swipe                          # http://127.0.0.1:8791
    python3 -m kobi.swipe --host 0.0.0.0           # reachable from a phone (tailscale / LAN)
    python3 -m kobi.swipe --max-rate 2 --max-preview-mb 20

Downloads land in uncompressed/Extra/<library>/ (Iowa instruments in uncompressed/Iowa/), app state
and rendered previews in uncompressed/_swipe/.  Votes and picks survive restarts; picks are
written to SWIPE_PICKS.json / SWIPE_PICKS.md in the repository.
"""
from __future__ import annotations

import argparse
import os
import sys
import time


def main(argv=None) -> int:
    from .. import paths
    ap = argparse.ArgumentParser(prog='python3 -m kobi.swipe', description=__doc__.split('\n\n')[0])
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=8791)
    ap.add_argument('--store', default=os.path.join(paths.SOURCES, '_swipe'), help='state, index cache and previews')
    ap.add_argument('--max-rate', type=float, default=5.0, help='download cap, MB/s (one stream at a time)')
    ap.add_argument('--max-preview-mb', type=float, default=40.0, help='skip an alternative whose preview needs more samples than this')
    ap.add_argument('--workers', type=int, default=2, help='render processes')
    ap.add_argument('--picks', default=None, help='where picks are written (default: SWIPE_PICKS.json in the repository, which gm_map reads)')
    a = ap.parse_args(argv)

    def log(msg):
        print(time.strftime('%H:%M:%S'), msg, flush=True)

    from .deck import App
    from .server import serve
    log(f'samples: {os.path.realpath(paths.SOURCES)}')
    app = App(a.store, max_rate=a.max_rate * 1e6, max_bytes=int(a.max_preview_mb * 1e6), workers=a.workers, log=log, picks=a.picks)
    httpd = serve(app, a.host, a.port)
    shown = 'localhost' if a.host in ('127.0.0.1', '0.0.0.0') else a.host
    log(f'swipe away: http://{shown}:{a.port}/')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.pool.shutdown(wait=False, cancel_futures=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
