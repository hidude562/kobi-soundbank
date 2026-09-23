"""The network drops while the scheduler is fetching a song's notes, then comes back: nothing may be
given up for good, and every note must arrive once the connection is back.

    python3 kobi_web/test/dropout_browser.py [port] [bank]
"""
import os, subprocess, sys, time, urllib.request
from playwright.sync_api import sync_playwright

ROOT = os.environ.get('KOBI_ROOT') or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MIDI = os.environ.get('KOBI_DROPOUT_MIDI', '../../midi/nena/01%20CANDY.MID')
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8774
bank = sys.argv[2] if len(sys.argv) > 2 else 'kobi_slim'
server = subprocess.Popen([sys.executable, 'kobi_web/test/rangeserver.py', str(port), ROOT], cwd=ROOT,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
S = 'window.kobiSched && window.kobiSched.engine && window.kobiSched.engine.loader.summary'
try:
    for _ in range(50):
        try: urllib.request.urlopen(f'http://127.0.0.1:{port}/kobi_web/sched/', timeout=1); break
        except Exception: time.sleep(0.1)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(f'http://127.0.0.1:{port}/kobi_web/sched/?bank=../../{bank}/&midi={MIDI}')
        page.wait_for_function(f'{S} && {S}.fetched > 15', timeout=60000)
        before = page.evaluate(S)
        ctx.set_offline(True)                                     # fetch rejects; the browser fires 'offline'
        time.sleep(4)
        off = page.evaluate(S)
        ctx.set_offline(False)                                    # ... and 'online', which resumes the loader
        page.wait_for_function(f'{S}.idle === 0 && {S}.fetching === 0', timeout=90000)
        after = page.evaluate(S)
        pick = lambda s: {k: s.get(k) for k in ('slices', 'idle', 'fetching', 'fetched', 'ready', 'failed', 'retries', 'requests', 'paused')}
        print('online      ', pick(before)); print('offline 4 s ', pick(off)); print('back online ', pick(after))
        ok = (off['failed'] == 0 and off['retries'] > 0 and off['paused'] and off['requests'] - before['requests'] < 40
              and after['failed'] == 0 and after['idle'] == 0)
        print('DROPOUT', 'PASS' if ok else 'FAIL')
        browser.close()
    sys.exit(0 if ok else 1)
finally:
    server.terminate()
