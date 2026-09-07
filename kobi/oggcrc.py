"""Ogg page CRC and renumbering — the Python twin of kobi_web/sched/kobi-ogg.js, used to verify
that what the browser assembles is a valid stream."""
from __future__ import annotations

import struct

_TABLE = []
for _i in range(256):
    _r = _i << 24
    for _ in range(8):
        _r = ((_r << 1) ^ 0x04C11DB7) if _r & 0x80000000 else (_r << 1)
    _TABLE.append(_r & 0xFFFFFFFF)


def crc(page: bytes) -> int:
    """Ogg's CRC-32: polynomial 0x04c11db7, no reflection, zero init, zero final xor, computed with
    the CRC field itself zeroed."""
    r = 0
    for k, b in enumerate(page):
        if 22 <= k < 26:
            b = 0
        r = ((r << 8) & 0xFFFFFFFF) ^ _TABLE[((r >> 24) & 0xFF) ^ b]
    return r


def renumber(header_pages: bytes, run: bytes) -> bytes:
    """Concatenate header pages and a run of audio pages into one stream: sequence numbers made
    contiguous, EOS flagged on the last page, every touched page's CRC recomputed."""
    out = bytearray(header_pages)
    seq = 0
    i = 0
    while i + 27 <= len(out):
        nseg = out[i + 26]
        size = 27 + nseg + sum(out[i + 27:i + 27 + nseg])
        seq = struct.unpack_from('<I', out, i + 18)[0] + 1
        i += size
    j = 0
    pages = []
    while j + 27 <= len(run):
        nseg = run[j + 26]
        size = 27 + nseg + sum(run[j + 27:j + 27 + nseg])
        pages.append(bytearray(run[j:j + size]))
        j += size
    for k, p in enumerate(pages):
        struct.pack_into('<I', p, 18, seq + k)
        if k == len(pages) - 1:
            p[5] |= 0x04
        struct.pack_into('<I', p, 22, crc(p))
        out += p
    return bytes(out)
