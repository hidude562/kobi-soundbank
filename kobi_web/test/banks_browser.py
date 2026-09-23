"""Play every bank in the browser and check the sounds the post-filter changed actually sound.

    python3 kobi_web/test/banks_browser.py [port]
"""
import os
import subprocess, sys, time, urllib.request
from playwright.sync_api import sync_playwright

ROOT = os.environ.get('KOBI_ROOT') or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8791
BANKS = ['kobi_slim', 'kobi_slim_lite', 'kobi_ultra', 'kobi_ultra_hifi', 'kobi_ultra_hifi_pf']
server = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/kobi_web/', timeout=1); break
        except Exception:
            time.sleep(0.1)
    errors, rows = [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        page = browser.new_page()
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(f'http://127.0.0.1:{port}/kobi_web/')
        page.wait_for_function('window.kobiDemo', timeout=30000)
        for bank in BANKS:
            r = page.evaluate('''async (bank) => {
                const { KobiBank } = await import('./kobi-player.js');
                const off = new OfflineAudioContext(2, 44100 * 6, 44100);
                const b = new KobiBank('../' + bank + '/', { context: off });
                const man = await b.manifest();
                await Promise.all([b.load(0), b.load('drums'), b.load(119), b.load(56)]);
                b.noteOn(0, 60, 100, { when: 0.1 });                    // piano
                b.noteOn('drums', 49, 110, { when: 1.2 });               // crash: looped by the post-filter
                b.noteOn('drums', 38, 110, { when: 2.2 });               // snare
                b.noteOn(119, 36, 100, { when: 3.0 });                   // reverse cymbal on a key that used to be silent
                const h = b.noteOn(56, 67, 100, { when: 4.2 }); if (h) b.noteOff(h, 67, 5.2);
                const buf = await off.startRendering();
                const L = buf.getChannelData(0), R = buf.getChannelData(1);
                const rms = (a, c) => { let s = 0, n = 0; for (let i = a*44100; i < c*44100; i++) { s += (L[i]*L[i]+R[i]*R[i])/2; n++; } return 20*Math.log10(Math.sqrt(s/n)+1e-12); };
                let peak = 0; for (let i = 0; i < L.length; i++) peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i]));
                return { total: man.total_bytes, bytes: b.bytes, piano: rms(0.15, 1.0), crash: rms(1.25, 2.1),
                         snare: rms(2.25, 2.9), sfx: rms(3.05, 4.1), trumpet: rms(4.3, 5.1), peak: 20*Math.log10(peak) };
            }''', bank)
            rows.append((bank, r))
            print(f"{bank:20s} manifest {r['total']/1e6:5.1f} MB  piano {r['piano']:6.1f}  crash {r['crash']:6.1f}  "
                  f"snare {r['snare']:6.1f}  sfx(key36) {r['sfx']:6.1f}  trumpet {r['trumpet']:6.1f} dB  peak {r['peak']:5.1f}")
        browser.close()
    ok = all(all(r[k] > -72 for k in ('piano', 'crash', 'snare', 'sfx', 'trumpet')) and r['peak'] < 0 for _, r in rows) and not errors   # master at -24 dB
    print('console errors:', errors[:4])
    print('BANKS', 'PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)
finally:
    server.terminate()
