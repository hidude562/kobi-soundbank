"""Does the browser decode a byte-range slice of a packed Ogg bit-identically to the whole file?

Serves the repo with Range support, then in Chromium: fetch header + one note's pages via Range,
splice with kobi-ogg.js, decodeAudioData both the slice and the full file at the file's own rate,
and compare the note's span sample for sample.

    python3 kobi_web/test/splice_browser.py [bank] [program folder]
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = os.environ.get('KOBI_ROOT') or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
bank = sys.argv[1] if len(sys.argv) > 1 else 'kobi_slim'
prog = sys.argv[2] if len(sys.argv) > 2 else '000_Acoustic_Grand_Piano'
port = 8767
server = subprocess.Popen([sys.executable, 'kobi_web/test/rangeserver.py', str(port), ROOT], cwd=ROOT)
try:
    for _ in range(50):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/kobi_web/', timeout=1); break
        except Exception:
            time.sleep(0.1)
    index = json.load(open(f'{ROOT}/{bank}/{prog}/slices.json'))
    name, entry = next(iter(index.items()))
    notes = list(entry['notes'].items())
    picks = [notes[0], notes[len(notes) // 3], notes[2 * len(notes) // 3], notes[-1]]
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(f'http://127.0.0.1:{port}/kobi_web/sched/')
        r = page.evaluate('''async ([url, header, rate, picks]) => {
            const { spliceOgg, lastGranule } = await import('./kobi-ogg.js');
            const ctx = new OfflineAudioContext(1, 1, rate);
            const fullBytes = await (await fetch(url)).arrayBuffer();
            const full = await ctx.decodeAudioData(fullBytes.slice(0));
            const h = await fetch(url, { headers: { Range: `bytes=0-${header - 1}` } });
            const hdr = new Uint8Array(await h.arrayBuffer());
            const out = [];
            for (const [start, [b0, b1, g]] of picks) {
                const t0 = performance.now();
                const res = await fetch(url, { headers: { Range: `bytes=${b0}-${b1 - 1}` } });
                const run = new Uint8Array(await res.arrayBuffer());
                const ogg = spliceOgg(hdr, run);
                const buf = await ctx.decodeAudioData(ogg.buffer.slice(0));
                const n = buf.length;
                const firstAbs = b0 === header ? 0 : lastGranule(run) - n;
                const s = Number(start);
                const a = full.getChannelData(0), b = buf.getChannelData(0);
                let maxd = 0, cmp = Math.min(20000, n - (s - firstAbs));
                for (let i = 0; i < cmp; i++) maxd = Math.max(maxd, Math.abs(a[s + i] - b[s - firstAbs + i]));
                out.push({ start: s, status: res.status, bytes: run.length, decoded: n, firstAbs, granule: lastGranule(run),
                           ms: Math.round(performance.now() - t0), maxDiff: maxd, compared: cmp, covers: firstAbs <= s });
            }
            return { fullRate: full.sampleRate, fullLen: full.length, fullBytes: fullBytes.byteLength, out };
        }''', [f'/{bank}/{prog}/{name}', entry['header'], entry['rate'], picks])
        browser.close()
    print(f'{bank}/{prog}/{name}: full file {r["fullBytes"]} bytes -> {r["fullLen"]} samples at {r["fullRate"]} Hz')
    ok = not errors
    for o in r['out']:
        good = o['status'] == 206 and o['covers'] and o['maxDiff'] == 0
        ok &= good
        print(f'  note @{o["start"]:>8}: HTTP {o["status"]}, {o["bytes"]:6d} bytes -> {o["decoded"]:6d} samples, first abs {o["firstAbs"]:>8}, '
              f'max diff {o["maxDiff"]:.1e} over {o["compared"]} samples, {o["ms"]} ms {"OK" if good else "<-- FAIL"}')
    if errors: print('page errors:', errors)
    print('SPLICE', 'PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)
finally:
    server.terminate()
