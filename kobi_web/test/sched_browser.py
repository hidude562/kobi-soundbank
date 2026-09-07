"""The scheduler in a real browser against a Range-capable server.

1. Real time: load a demo MIDI, play the first N seconds; the loader must fetch a small fraction of
   the programs' bytes, stay under its decoded-PCM budget, and the notes must mostly be exact
   (fallbacks are allowed while the queue catches up, misses are not).
2. Offline: render the first seconds with every slice loaded and compare the loudness envelope with
   sfizz's render of the same file from the same bank.

    python3 kobi_web/test/sched_browser.py [midi] [bank] [seconds]
"""
import glob
import json
import os
import subprocess
import sys
import time
import urllib.request

import numpy as np
import soundfile as sf
from playwright.sync_api import sync_playwright

ROOT = os.environ.get('KOBI_ROOT') or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MIDIS = os.environ.get('KOBI_MIDIS') or os.path.join(ROOT, 'midi', 'nena')
midi = sys.argv[1] if len(sys.argv) > 1 else '07COUNT'
bank = sys.argv[2] if len(sys.argv) > 2 else 'kobi_slim'
seconds = float(sys.argv[3]) if len(sys.argv) > 3 else 20
port = 8768
midi_path = glob.glob(f'{MIDIS}/{midi}.*')[0]
server = subprocess.Popen([sys.executable, 'kobi_web/test/rangeserver.py', str(port), ROOT], cwd=ROOT)
try:
    for _ in range(50):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/kobi_web/', timeout=1); break
        except Exception:
            time.sleep(0.1)
    rel = os.path.relpath(midi_path, ROOT) if midi_path.startswith(ROOT) else None
    # the MIDI is outside the served root: hand its bytes to the page
    midi_bytes = list(open(midi_path, 'rb').read())
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        page = browser.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.goto(f'http://127.0.0.1:{port}/kobi_web/sched/')
        page.wait_for_function('window.kobiSched')
        rt = page.evaluate('''async ([bytes, bank, seconds]) => {
            const { KobiEngine } = await import('./kobi-engine.js');
            const engine = new KobiEngine(`../../${bank}/`, { maxDecodedBytes: 24e6, decodeAhead: 6, preroll: 3, prerollTimeout: 6000 });
            const t0 = performance.now();
            const info = await engine.load(new Uint8Array(bytes).buffer);
            const compiled = performance.now() - t0;
            const man = await engine.loader.manifest();
            const programBytes = info.programs.reduce((a, p) => a + (p === 'drums' ? man.drums.bytes : man.programs[p].bytes), 0);
            const t1 = performance.now();
            await engine.play();
            const startLatency = performance.now() - t1;
            const samples = [];
            while (engine.position < seconds) {
                await new Promise(r => setTimeout(r, 1000));
                const s = engine.status;
                samples.push({ t: +s.position.toFixed(1), ready: s.ready, fetched: s.fetched, pcmMB: +(s.decodedBytes / 1e6).toFixed(1), pinMB: +(s.pinnedBytes / 1e6).toFixed(1), voices: s.voices,
                               started: s.started, fallbacks: s.fallbacks, missed: s.missed, evicted: s.evicted, reqs: s.requests, kb: Math.round(s.bytes / 1024) });
            }
            const s = engine.status;
            engine.stop();
            return { info, compiled, programBytes, startLatency, samples, final: s, ctxRate: engine.ctx.sampleRate, missedLog: engine.missedLog, budget: engine.loader.maxDecodedBytes };
        }''', [midi_bytes, bank, seconds])
        off = page.evaluate('''async ([bytes, bank, seconds]) => {
            const { KobiEngine } = await import('./kobi-engine.js');
            const t0 = performance.now();
            const r = await KobiEngine.renderOffline(`../../${bank}/`, new Uint8Array(bytes).buffer, { seconds, sampleRate: 44100 });
            const L = r.buffer.getChannelData(0), R = r.buffer.getChannelData(1);
            const step = 4410, out = [];              // loudness every 100 ms
            for (let i = 0; i + step <= L.length; i += step) { let s = 0; for (let k = i; k < i + step; k++) s += (L[k]*L[k] + R[k]*R[k]) / 2; out.push(10 * Math.log10(s / step + 1e-12)); }
            let peak = 0; for (let i = 0; i < L.length; i++) peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i]));
            return { env: out, peak, stats: r.stats, loader: r.loader, ms: performance.now() - t0 };
        }''', [midi_bytes, bank, seconds])
        browser.close()
    info = rt['info']
    print(f'{midi} on {bank}: {info["notes"]} notes, {len(info["programs"])} programs -> {info["slices"]} slices, {info["bytes"]/1e3:.0f} KB of slices vs {rt["programBytes"]/1e3:.0f} KB for the whole programs; compiled in {rt["compiled"]:.0f} ms, play() returned after {rt["startLatency"]:.0f} ms')
    print(f'  {"t":>5} {"ready":>5} {"fetched":>7} {"PCM MB":>6} {"pinned":>6} {"voices":>6} {"started":>7} {"fallb":>5} {"missed":>6} {"evict":>5} {"reqs":>5} {"KB":>6}')
    for s in rt['samples']:
        print(f'  {s["t"]:5.1f} {s["ready"]:5d} {s["fetched"]:7d} {s["pcmMB"]:6.1f} {s["pinMB"]:6.1f} {s["voices"]:6d} {s["started"]:7d} {s["fallbacks"]:5d} {s["missed"]:6d} {s["evicted"]:5d} {s["reqs"]:5d} {s["kb"]:6d}')
    if rt['missedLog']: print('  missed:', rt['missedLog'][:5])
    ahead = max(s['pcmMB'] - s['pinMB'] for s in rt['samples'])
    print(f'  decoded ahead of playback peaked at {ahead:.1f} MB against a {rt["budget"]/1e6:.0f} MB budget; pinned by sounding voices up to {max(s["pinMB"] for s in rt["samples"]):.1f} MB')
    f = rt['final']
    frac_bytes = f['bytes'] / rt['programBytes']
    # offline vs sfizz
    ref_path = f'{ROOT}/renders_slim/{os.path.splitext(os.path.basename(midi_path))[0]}.wav' if bank == 'kobi_slim' else None
    corr = None
    if ref_path and os.path.exists(ref_path):
        x, fs = sf.read(ref_path, always_2d=True)
        n = int(seconds * fs); m = x[:n].mean(axis=1)
        step = fs // 10
        ref = np.array([10 * np.log10((m[i:i+step] ** 2).mean() + 1e-12) for i in range(0, len(m) - step + 1, step)])
        web = np.array(off['env'])[:len(ref)]; ref = ref[:len(web)]
        keep = (ref > -60) & (web > -60)
        corr = float(np.corrcoef(ref[keep], web[keep])[0, 1]) if keep.sum() > 10 else 0.0
        print(f'  offline render ({off["ms"]:.0f} ms, {off["loader"]["ready"]} slices, peak {20*np.log10(off["peak"]+1e-9):.1f} dBFS, {off["stats"]["fallbacks"]} fallbacks, {off["stats"]["missed"]} missed): loudness-envelope correlation with sfizz render {corr:.3f}, level offset {np.mean(web[keep]-ref[keep]):+.1f} dB')
    print(f'  final: {f["started"]} notes started, {f["fallbacks"]} fallbacks, {f["missed"]} missed, {f["unmapped"]} unmapped by the bank, {f["stolen"]} stolen, {f["evicted"]} evictions; fetched {f["bytes"]/1e3:.0f} KB = {frac_bytes*100:.0f}% of the programs, PCM peak {max(s["pcmMB"] for s in rt["samples"]):.1f} MB, range {f["rangeSupported"]}')
    late = [s for s in rt['samples'] if s['t'] >= 5]
    ok = (not errors and f['missed'] == 0 and f['rangeSupported'] is True and ahead <= rt['budget'] / 1e6 * 1.15
          # fetched bytes: the song's slices (plus page rounding) and never the whole programs
          and f['bytes'] <= 1.6 * info['bytes'] and f['bytes'] < rt['programBytes'] and f['started'] > 20
          and (corr is None or corr > 0.6) and off['stats']['missed'] == 0)
    if errors: print('  page errors:', errors[:5])
    print('SCHED', 'PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)
finally:
    server.terminate()
