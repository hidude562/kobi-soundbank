"""Headless-browser smoke test: serve the repo, open the demo, load two programs on demand, play.

    python3 kobi_web/test/smoke_browser.py [port]
"""
import os
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = os.environ.get('KOBI_ROOT') or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
server = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/kobi_web/', timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        page = browser.new_page()
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(f'http://127.0.0.1:{port}/kobi_web/')
        page.wait_for_function('window.kobiDemo && document.querySelectorAll("#programs button").length > 100')
        n_buttons = page.evaluate('document.querySelectorAll("#programs button").length')
        page.wait_for_function('window.kobiDemo.bank.isLoaded(0)', timeout=30000)
        r = page.evaluate('''async () => {
            const { bank } = window.kobiDemo;
            const t0 = performance.now();
            const before = bank.bytes;
            const trumpet = await bank.load(56);
            const drums = await bank.load('drums');
            const ms = performance.now() - t0;
            const h = bank.noteOn(56, 67, 100);
            const d = bank.noteOn('drums', 38, 110);
            const piano = bank.noteOn(0, 60, 100);
            const voices = bank.voices.size;
            bank.noteOff(h); bank.noteOff(piano);
            await new Promise(r => setTimeout(r, 300));
            return { buttons: document.querySelectorAll('#programs button').length, loaded: bank.stats.programs,
                     bytes: bank.bytes, fetchedForTwo: bank.bytes - before, ms, trumpetRegions: trumpet.regions.length,
                     drumRegions: drums.regions.length, voices, trumpetLoop: trumpet.regions[0].loop !== null,
                     trumpetRate: trumpet.regions[0].rate, trumpetHandle: h ? h.voices.length : 0, drumHandle: d ? d.voices.length : 0,
                     pianoHandle: piano ? piano.voices.length : 0, ctxState: bank.ctx.state };
        }''')
        browser.close()
    print(r)
    ok = (r['buttons'] == 129 and r['loaded'] == 3 and r['trumpetRegions'] > 5 and r['drumRegions'] > 40 and r['trumpetHandle'] >= 1
          and r['drumHandle'] >= 1 and r['pianoHandle'] >= 2 and r['trumpetLoop'] and r['trumpetRate'] in (44100, 48000) and not errors)
    print('console errors:', errors[:5])
    print('SMOKE', 'PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)
finally:
    server.terminate()
