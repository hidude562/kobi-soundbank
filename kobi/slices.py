"""kobi.slices — a byte-range index so a browser can fetch one note out of a packed Ogg.

A packed program is one Ogg Vorbis file (kobi/packing.py); its SFZ addresses each note with
``offset`` / ``end`` in samples.  Ogg is a sequence of self-delimiting pages, each stamped with the
absolute sample count completed by its end (the granule position), so a note lives in a known run
of pages.  Prepend the file's header pages to that run and the result is a small, valid Ogg that
any decoder can open — the browser's ``decodeAudioData`` included — without downloading the rest of
the program.

Vorbis is a lapped transform, so the decoder needs one packet of warm-up before it produces
output, and a run must start on a page that begins a fresh packet.  The index therefore starts a
note's run one page early, and because Vorbis decoding is deterministic the decoded PCM is
bit-identical to the full file's from the second packet on; a client anchors the slice by its *end*
(the last page's granule) which has no such ambiguity.  ``--verify`` proves both claims with ffmpeg.

Written as ``<program folder>/slices.json``:

    {"pack.ogg": {"header": 3542, "rate": 44100, "channels": 2,
                  "notes": {"<offset>": [byte_start, byte_end, granule_end, granule_start], ...}}}

    python3 -m kobi.slices kobi_slim kobi_ultra_hifi_pf --verify
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import random
import re
import struct
import subprocess
import sys

import numpy as np
from . import paths

_OP = re.compile(r'(?<!\S)([\w]+)=(\S+)')


def ogg_pages(data: bytes) -> list[dict]:
    """[{pos, size, granule, seq, flags, headers}] for every page; headers is True for the pages
    that carry the identification, comment and setup packets (the ones a slice must be prefixed
    with)."""
    pages, i, n = [], 0, len(data)
    while i + 27 <= n:
        if data[i:i + 4] != b'OggS':
            raise ValueError(f'lost Ogg sync at byte {i}')
        flags = data[i + 5]
        granule, = struct.unpack_from('<q', data, i + 6)
        seq, = struct.unpack_from('<I', data, i + 18)
        nseg = data[i + 26]
        segs = data[i + 27:i + 27 + nseg]
        body = i + 27 + nseg
        size = 27 + nseg + sum(segs)
        first = data[body:body + 7]
        pages.append(dict(pos=i, size=size, granule=granule, seq=seq, flags=flags,
                          headers=first in (b'\x01vorbis', b'\x03vorbis', b'\x05vorbis') or granule == 0 and not pages))
        i += size
    return pages


def slice_range(pages: list[dict], start: int, end: int, warmup: int = 1) -> tuple[int, int, int]:
    """(byte_start, byte_end, granule_end) covering samples [start, end] with ``warmup`` extra pages
    before the first page that holds ``start``.  A page holds the samples in (prev_granule, granule]."""
    audio = [p for p in pages if not p['headers']]
    first = next(k for k, p in enumerate(audio) if p['granule'] >= start)
    last = next(k for k, p in enumerate(audio) if p['granule'] >= end)
    first = max(0, first - warmup)
    a, b = audio[first], audio[last]
    # the 4th value is where decoding of the run begins (granule of the page before it), so a client
    # knows the decoded length — and its memory cost — before decoding
    g_start = audio[first - 1]['granule'] if first > 0 else 0
    return a['pos'], b['pos'] + b['size'], b['granule'], g_start


def index_program(folder: str, sfz_path: str) -> dict:
    text = open(sfz_path).read()
    by_file: dict = {}
    for line in text.split('\n'):
        if not line.startswith('<region>'):
            continue
        o = dict(_OP.findall(line))
        if 'offset' not in o or 'end' not in o:
            continue
        by_file.setdefault(o['sample'], set()).add((int(o['offset']), int(o['end'])))
    out = {}
    for name, notes in by_file.items():
        data = open(os.path.join(folder, name), 'rb').read()
        pages = ogg_pages(data)
        header_end = max(p['pos'] + p['size'] for p in pages if p['headers'])
        rate = struct.unpack_from('<I', data, pages[0]['pos'] + 27 + pages[0]['size'] - 27 - (pages[0]['size'] - 27 - data[pages[0]['pos'] + 26]) + 12)[0] \
            if False else _ident(data, pages[0])
        entry = dict(header=header_end, rate=rate[0], channels=rate[1], notes={})
        for start, end in sorted(notes):
            entry['notes'][str(start)] = list(slice_range(pages, start, end))
        out[name] = entry
    return out


def _ident(data: bytes, page0: dict) -> tuple[int, int]:
    body = page0['pos'] + 27 + data[page0['pos'] + 26]
    assert data[body:body + 7] == b'\x01vorbis'
    return struct.unpack_from('<I', data, body + 12)[0], data[body + 11]


def splice(data: bytes, header_end: int, b0: int, b1: int) -> bytes:
    """Header pages + the run of pages, exactly as the browser client assembles them (sequence
    numbers renumbered, EOS set on the last page, CRCs recomputed)."""
    from kobi.oggcrc import renumber
    return renumber(data[:header_end], data[b0:b1])


def _decode(ogg: bytes) -> np.ndarray:
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', 'pipe:0', '-f', 'f32le', '-acodec', 'pcm_f32le', 'pipe:1'],
                       input=ogg, capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


def verify(folder: str, index: dict, sample: float = 0.05, seed: int = 1) -> tuple[int, int, float]:
    """Decode a random subset of slices with ffmpeg and compare with the full decode.  Returns
    (checked, exact, mean overhead) — exact counts slices whose note span is bit-identical."""
    rng = random.Random(seed)
    checked = exact = 0
    overhead = []
    for name, entry in index.items():
        data = open(os.path.join(folder, name), 'rb').read()
        full = _decode(data).reshape(-1, entry['channels'])
        items = list(entry['notes'].items())
        pick = items if sample >= 1 else rng.sample(items, max(1, int(len(items) * sample)))
        for start, (b0, b1, g_end, _g0) in pick:
            start = int(start)
            piece = _decode(splice(data, entry['header'], b0, b1)).reshape(-1, entry['channels'])
            n = len(piece)
            # granule = samples completed, so the last decoded sample is g_end - 1; a slice that begins at
            # the file's first audio page is a real stream start and begins at 0 (decoders may trim its end)
            first_abs = 0 if b0 == entry['header'] else g_end - n
            end = next(e for s, e in _note_spans(folder, name) if s == start)
            ok = first_abs <= start and g_end >= end and np.array_equal(piece[start - first_abs: end - first_abs + 1], full[start:end + 1])
            checked += 1; exact += ok
            overhead.append((b1 - b0) / max(1, _note_bytes_estimate(entry, start, end)))
            if not ok:
                print(f'   MISMATCH {name} offset {start}: slice covers [{first_abs}, {g_end}], note [{start}, {end}]')
    return checked, exact, float(np.mean(overhead)) if overhead else 0.0


_spans_cache: dict = {}


def _note_spans(folder: str, name: str):
    key = (folder, name)
    if key not in _spans_cache:
        spans = set()
        for sfz in glob.glob(os.path.join(os.path.dirname(folder.rstrip('/')), 'GM', '*.sfz')):
            text = open(sfz).read()
            m = re.search(r'default_path=(\S+)', text)
            if not m or os.path.normpath(os.path.join(os.path.dirname(sfz), m.group(1))) != os.path.normpath(folder):
                continue
            for line in text.split('\n'):
                if line.startswith('<region>'):
                    o = dict(_OP.findall(line))
                    if o.get('sample') == name and 'offset' in o:
                        spans.add((int(o['offset']), int(o['end'])))
        _spans_cache[key] = sorted(spans)
    return _spans_cache[key]


def _note_bytes_estimate(entry: dict, start: int, end: int) -> float:
    """Bytes the note itself occupies, pro rata over the file's audio pages — the overhead baseline."""
    total = entry.get('_audio_bytes')
    span = entry.get('_span')
    if total is None or span is None:
        return 1.0
    return total * (end - start + 1) / span


def build(bank: str, do_verify: bool = False, sample: float = 0.05) -> dict:
    gm = os.path.join(bank, 'GM')
    stats = dict(programs=0, notes=0, checked=0, exact=0, overhead=[])
    for sfz in sorted(glob.glob(os.path.join(gm, '*.sfz'))):
        text = open(sfz).read()
        m = re.search(r'default_path=(\S+)', text)
        if not m or 'offset=' not in text:
            continue
        folder = os.path.normpath(os.path.join(gm, m.group(1)))
        index = index_program(folder, sfz)
        for name, entry in index.items():
            size = os.path.getsize(os.path.join(folder, name))
            spans = _note_spans(folder, name)
            entry['_audio_bytes'] = size - entry['header']
            entry['_span'] = max(e for _, e in spans) - min(s for s, _ in spans) + 1 if spans else 1
        if do_verify:
            c, e, oh = verify(folder, index, sample)
            stats['checked'] += c; stats['exact'] += e; stats['overhead'].append(oh)
        for entry in index.values():
            entry.pop('_audio_bytes', None); entry.pop('_span', None)
        with open(os.path.join(folder, 'slices.json'), 'w') as fh:
            json.dump(index, fh, separators=(',', ':'))
        stats['programs'] += 1
        stats['notes'] += sum(len(e['notes']) for e in index.values())
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('banks', nargs='+')
    ap.add_argument('--verify', action='store_true', help='decode a sample of slices with ffmpeg and compare with the full file')
    ap.add_argument('--sample', type=float, default=0.05, help='fraction of notes to verify (1 = all)')
    a = ap.parse_args(argv)
    for bank in a.banks:
        bank = paths.bank(bank)
        s = build(bank, a.verify, a.sample)
        line = f'{os.path.basename(bank):20s} {s["programs"]:3d} programs, {s["notes"]:5d} note slices indexed'
        if a.verify:
            line += f'; verified {s["exact"]}/{s["checked"]} bit-exact, slice bytes {np.mean(s["overhead"]):.2f}x the note itself'
        print(line, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
