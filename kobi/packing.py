"""kobi.packing — one Ogg per program instead of one per note.

An Ogg Vorbis file carries about 3.4 KB of headers: a 30-byte identification header, a small
comment header, and ~3.2 KB of setup (the codebooks).  The setup depends only on the encoder
settings, not on the audio, so a whole kobi bank contains just four distinct setup headers — one
per (sample rate, channel count).  Repeated once per note they cost about a quarter of a slim bank.

Packing concatenates a program's notes into one Ogg separated by a short guard of silence, and
addresses each note with the standard SFZ ``offset`` / ``end`` opcodes, its loop points shifted by
the note's start.  Files stay ordinary Ogg and the SFZ stays ordinary SFZ, so sfizz and any other
host still play the bank.  The guard matters because Vorbis is a lapped transform: without it the
tail of one note would bleed into the head of the next.

Notes are grouped by (rate, channels) — packing cannot mix formats, and resampling to force one
would alter the audio — so a program is one file unless its sources really differ.
"""
from __future__ import annotations

import os
import subprocess
import sys

import numpy as np
import soundfile as sf

from .paths import use_dctjoin
use_dctjoin()                                   # dctjoin: encode_ogg, pad_after_loop

GUARD_S = 0.05
# Padding of loop continuation written after loop_end, so the codec's block that spans the seam has
# real audio to overlap with rather than the guard silence.  Measured on this bank: 0 ms degrades the
# worst seam to 3.6x the loop's own step, 50 ms reaches 1.96x and 100 and 250 ms are bit-identical to
# it.  dctjoin's 250 ms default dates from one file per note, where the seam was the file's end.
PAD_S = 0.05
# Ogg page duration.  A browser fetching one note by byte range (kobi.slices) has to take whole
# pages plus one page of decoder warm-up, so short pages keep that overhead small: 0.1 s pages cost
# about 2.4% of the file and make a typical note fetch ~1.3x its own size instead of ~3x.
PAGE_S = 0.1


def audio_format(path: str) -> tuple[int, int]:
    i = sf.info(path)
    return int(i.samplerate), int(i.channels)


def group_by_format(entries: list) -> dict:
    """{(rate, channels): [entry, ...]} keeping the given order within each group."""
    groups: dict = {}
    for e in entries:
        groups.setdefault(audio_format(e['path']), []).append(e)
    return groups


def pack_notes(entries: list, dst_ogg: str, quality: float = 1.0, guard_s: float = GUARD_S, mono: bool = False,
               rate_div: int = 1) -> dict:
    """Concatenate ``entries`` — [{'stem', 'path', 'loop': (start, end) | None}], all of one format —
    into ``dst_ogg`` in one encode.  Returns {stem: {'start', 'length', 'loop'}} in samples of the
    packed file.  A looped note is padded after its loop first (the codec's block boundary must not
    fall on the seam), exactly as the one-file-per-note path does."""
    from dctjoin.unaltered import encode_ogg, pad_after_loop
    chunks, index, pos = [], {}, 0
    rate = ch = None
    for e in entries:
        x, fs = sf.read(e['path'], dtype='float32', always_2d=True)
        if mono and x.shape[1] > 1:                   # an ultra-light bank: stereo costs about 60% more
            x = x.mean(axis=1, keepdims=True)
        loop = e.get('loop')
        if rate_div > 1:
            # halving the rate halves the data.  A loop stays exactly periodic because dctloop's loop
            # length is even, so the resampled loop is still one whole period; its bounds just move.
            from scipy.signal import resample_poly
            x = resample_poly(x, 1, rate_div, axis=0).astype(np.float32)
            fs //= rate_div
            if loop:
                ls = int(round(loop[0] / rate_div))
                loop = (ls, ls + (loop[1] - loop[0] + 1) // rate_div - 1)
        if rate is None:
            rate, ch = fs, x.shape[1]
        elif (fs, x.shape[1]) != (rate, ch):
            raise ValueError(f"{e['path']}: {fs} Hz {x.shape[1]}ch in a {rate} Hz {ch}ch pack")
        max_s = e.get('max_s')
        if max_s and len(x) > int(max_s * fs):        # a truncated one-shot (kobi.slim)
            x = x[:int(max_s * fs)].copy()
            f = min(len(x), int(0.08 * fs))
            x[-f:] *= np.linspace(1, 0, f)[:, None]
        if loop:
            x = pad_after_loop(x, loop[0], loop[1], fs, seconds=PAD_S)
        index[e['stem']] = dict(start=pos, length=len(x),
                                loop=[pos + loop[0], pos + loop[1]] if loop else None)
        chunks.append(x)
        chunks.append(np.zeros((int(round(guard_s * fs)), ch), dtype=np.float32))
        pos += len(x) + int(round(guard_s * fs))
    if not chunks:
        return {}
    packed = np.concatenate(chunks)
    peak = float(np.max(np.abs(packed)))
    if peak > 0.999:                      # the notes are already scaled individually; this is a guard
        packed *= 0.999 / peak
    tmp = dst_ogg[:-4] + '.tmp.wav'
    os.makedirs(os.path.dirname(dst_ogg) or '.', exist_ok=True)
    sf.write(tmp, packed, rate, subtype='PCM_16')
    encode_ogg(tmp, dst_ogg, quality, page_s=PAGE_S)
    os.remove(tmp)
    for v in index.values():
        v['rate'], v['channels'] = rate, ch
    return index


def slice_packed(src_ogg: str, start: int, length: int, dst: str) -> None:
    """Write samples [start, start+length) of a packed Ogg to ``dst`` (lossless).  Used only when a
    bank has to be re-packed without its lossless build cache — it costs a second lossy generation."""
    x, fs = sf.read(src_ogg, dtype='float32', always_2d=True)
    sf.write(dst, x[start:start + length], fs, subtype='PCM_16')


def ogg_header_bytes(path: str) -> int:
    """Size of the Ogg pages before the first audio page — what packing removes per note."""
    d = open(path, 'rb').read(65536)
    i, total = 0, 0
    while i + 27 <= len(d) and d[i:i + 4] == b'OggS':
        nseg = d[i + 26]
        size = 27 + nseg + sum(d[i + 27:i + 27 + nseg])
        body = d[i + 27 + nseg:i + size]
        if body[:7] not in (b'\x01vorbis', b'\x03vorbis', b'\x05vorbis') and total:
            break
        total += size
        i += size
    return total


def ffprobe_duration(path: str) -> float:
    try:
        return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                                    capture_output=True, text=True, check=True).stdout.strip())
    except Exception:
        return 0.0
