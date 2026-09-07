"""Where things are.  Everything is relative to the repository unless an environment variable says
otherwise, so a fresh clone works without editing code:

    KOBI_ROOT     the repository (default: the parent of this package)
    KOBI_SOURCES  the pulled sample libraries (default: <root>/uncompressed, see SOURCES.md)
    KOBI_SSO      Sonatina Symphonic Orchestra's Samples folder, for the one CC0 piece taken from it
                  (default: <sources>/Sonatina Symphonic Orchestra/Samples)
    KOBI_DCTJOIN  the sfz_compressor checkout that provides dctloop / dctjoin (default: the vendor/
                  submodule, else a sibling checkout)
    KOBI_MIDIS    a folder of demo MIDI files (default: <root>/midi/nena)
"""
from __future__ import annotations

import os
import sys

ROOT = os.environ.get('KOBI_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = os.environ.get('KOBI_SOURCES') or os.path.join(ROOT, 'uncompressed')
SSO = os.environ.get('KOBI_SSO') or os.path.join(SOURCES, 'Sonatina Symphonic Orchestra', 'Samples')
MIDIS = os.environ.get('KOBI_MIDIS') or os.path.join(ROOT, 'midi', 'nena')


def bank(name: str) -> str:
    """A bank folder given by name (kobi_slim) or by path."""
    return name if os.path.isabs(name) else os.path.join(ROOT, name)


def dctjoin_dir() -> str:
    for c in (os.environ.get('KOBI_DCTJOIN'), os.path.join(ROOT, 'vendor', 'sfz_compressor'),
              os.path.join(os.path.dirname(ROOT), 'sfz_compressor')):
        if c and os.path.isdir(os.path.join(c, 'dctjoin')):
            return c
    raise RuntimeError('dctjoin not found: run `git submodule update --init` or set KOBI_DCTJOIN')


def use_dctjoin() -> None:
    """Make dctloop / dctjoin importable."""
    try:
        import dctjoin  # noqa: F401
    except ImportError:
        sys.path.insert(0, dctjoin_dir())
