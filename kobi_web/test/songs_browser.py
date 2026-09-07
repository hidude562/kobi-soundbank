"""Play a run of songs through one engine: every song must reach full readiness.

A player page is used for a whole sitting, not one file, so the loader has to hand back the decoded
audio of the songs before this one.  This walks several MIDI files through a single KobiEngine with a
small decoded-RAM budget and fails if any song cannot get its opening decoded within the preroll.

    python3 kobi_web/test/songs_browser.py [bank] [budget MB] [n songs]
"""
import glob
import os
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = os.environ.get('KOBI_ROOT') or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MIDIS = os.environ.get('KOBI_MIDIS') or os.path.join(ROOT, 'midi', 'nena')
bank = sys.argv[1] if len(sys.argv) > 1 else 'kobi_slim'
budget = float(sys.argv[2]) if len(sys.argv) > 2 else 32
n = int(sys.argv[3]) if len(sys.argv) > 3 else 8
port = 8831

files = sorted(glob.glob(os.path.join(MIDIS, '*.[mM][iI][dD]*')))[:n]
if not files:
    print(f'no MIDI files in {MIDIS} (set KOBI_MIDIS)')
    sys.exit(0)
songs = [{'name': os.path.basename(f), 'bytes': list(open(f, 'rb').read())} for f in files]
server = subprocess.Popen([sys.executable, os.path.join(ROOT, 'kobi_web/test/rangeserver.py'), str(port), ROOT], cwd=ROOT)
try:
    for _ in range(50):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/kobi_web/', timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(f'http://127.0.0.1:{port}/kobi_web/sched/')
        page.wait_for_function('window.kobiSched')
        rows = page.evaluate('''async ([songs, bank, budget]) => {
            const { KobiEngine } = await import('./kobi-engine.js');
            const engine = await KobiEngine.open(`../../${bank}/`, { maxDecodedBytes: budget * 1e6 });
            const out = [];
            for (const s of songs) {                       // one engine for the whole sitting
                const info = await engine.load(new Uint8Array(s.bytes).buffer);
                const t0 = performance.now();
                const r = await engine.loader.whenReady(0, engine.preroll, 8000);
                const st = engine.loader.summary;
                out.push({ name: s.name, need: r.need, ready: r.ready, ms: Math.round(performance.now() - t0),
                           decodedMB: +(st.decodedBytes / 1e6).toFixed(1), evicted: st.evicted, failed: st.failed,
                           fetchedMB: +(st.bytes / 1e6).toFixed(1) });
            }
            return out;
        }''', [songs, bank, budget])
        browser.close()
    print(f'{bank}, {budget:g} MB decoded budget, {len(rows)} songs through one engine:')
    print(f'  {"song":26s} {"ready":>9} {"ms":>6} {"decoded":>8} {"evicted":>8} {"failed":>7}')
    ok = not errors
    for r in rows:
        good = r['ready'] == r['need'] and r['failed'] == 0
        ok &= good
        print(f'  {r["name"][:26]:26s} {r["ready"]:4d}/{r["need"]:<4d} {r["ms"]:6d} {r["decodedMB"]:7.1f}M {r["evicted"]:8d} {r["failed"]:7d}'
              + ('' if good else '   <-- INCOMPLETE'))
    if errors:
        print('  page errors:', errors[:3])
    print('SONGS', 'PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)
finally:
    server.terminate()
