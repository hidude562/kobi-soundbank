"""Headroom test: a velocity-110 piano chord, drum hits and a brass triad through the player's output
chain in an OfflineAudioContext must stay below full scale (floats above 1.0 there are what the live
destination would clip).

    python3 kobi_web/test/peaks_browser.py [port]
"""
import os
import subprocess, sys, time, urllib.request
from playwright.sync_api import sync_playwright
ROOT = os.environ.get('KOBI_ROOT') or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
server = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try: urllib.request.urlopen(f'http://127.0.0.1:{port}/kobi_web/', timeout=1); break
        except Exception: time.sleep(0.1)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        page = browser.new_page()
        page.goto(f'http://127.0.0.1:{port}/kobi_web/')
        page.wait_for_function('window.kobiDemo && window.kobiDemo.bank.isLoaded(0)', timeout=30000)
        r = page.evaluate('''async () => {
            const { KobiBank } = await import('./kobi-player.js');
            const off = new OfflineAudioContext(2, 44100 * 4, 44100);
            const bank = new KobiBank('../kobi_slim/', { context: off });
            await bank.load(0); await bank.load('drums'); await bank.load(56);
            const chord = [60, 64, 67, 72];
            chord.forEach(k => { const h = bank.noteOn(0, k, 110, { when: 0.1 }); bank.noteOff(h, k, 1.6); });
            [[36, 1.9], [38, 2.1], [49, 2.1], [42, 2.3]].forEach(([k, t]) => bank.noteOn('drums', k, 120, { when: t }));
            [67, 71, 74].forEach(k => { const h = bank.noteOn(56, k, 110, { when: 2.8 }); bank.noteOff(h, k, 3.6); });
            const buf = await off.startRendering();
            const L = buf.getChannelData(0), R = buf.getChannelData(1);
            let peak = 0, over = 0, sumsq = 0;
            for (let i = 0; i < L.length; i++) { const a = Math.max(Math.abs(L[i]), Math.abs(R[i])); if (a > peak) peak = a; if (a > 1) over++; sumsq += (L[i]*L[i] + R[i]*R[i]) / 2; }
            const seg = (a, b) => { let s = 0, n = 0; for (let i = a * 44100; i < b * 44100; i++) { s += (L[i]*L[i] + R[i]*R[i]) / 2; n++; } return 20 * Math.log10(Math.sqrt(s / n) + 1e-9); };
            return { peakDb: 20 * Math.log10(peak), samplesOver: over, rmsDb: 20 * Math.log10(Math.sqrt(sumsq / L.length)),
                     chordRms: seg(0.2, 0.6), drumsRms: seg(1.9, 2.4), brassRms: seg(2.9, 3.5), master: bank.master.gain.value };
        }''')
        browser.close()
    print(r)
    ok = r['samplesOver'] == 0 and r['peakDb'] < -3 and -42 < r['chordRms'] < -20   # master at -24 dB: 3 dB of headroom
    print('PEAKS', 'PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)
finally:
    server.terminate()
