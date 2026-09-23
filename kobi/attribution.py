"""kobi.attribution — who made the sounds in the banks, and on what terms.

The banks are aggregates: every program (and every kit piece) keeps the licence of the library it was
built from.  This reads the mapping a bank is built from (kobi.gm_map with the swipe picks applied,
stacks and resampled versions resolved to their sources, the kit from demo/GM/Drums.sfz) and writes
ATTRIBUTION.md: what needs a decision before a bank is published, the credits each licence asks for,
and a program-by-program table.  With bank folders as arguments, a copy goes into each.

    python3 -m kobi.attribution [kobi_ogg kobi_slim ...]
"""
from __future__ import annotations

import argparse
import json
import os
import re

from . import paths

CHANGES = ('trimmed, looped, re-encoded as Ogg Vorbis, levelled, pitch-corrected where a note was off, and mapped '
           'to General MIDI keys by kobi_soundbank; soundfont presets were rendered through sfizz first')

# library -> title, by, licence (+ url, note).  ``need`` is what the licence asks of a redistributor.
CREDITS = {
    'VCSL': dict(title='Versilian Community Sample Library (VCSL)', by='Versilian Studios (Sam Gossner) and contributors',
                 licence='CC0 1.0', url='https://github.com/sgossner/VCSL'),
    'VSCO2': dict(title='VSCO 2 Community Edition', by='Versilian Studios (Sam Gossner, Simon Dalzell)', licence='CC0 1.0',
                  url='https://github.com/sgossner/VSCO-2-CE'),
    'FreePats': dict(title='FreePats', by='the FreePats project', licence='CC0 1.0', url='https://freepats.zenvoid.org'),
    'FreePats-FSS': dict(title='FSS Steel String Guitar (FreePats)', by='the FreePats project', licence='GNU GPL',
                         url='https://freepats.zenvoid.org', need='copyleft: distribute under the GPL, with the source samples on request'),
    'Karoryfer': dict(title='Karoryfer Samples free instruments', by='Karoryfer Samples', licence='CC0 1.0', url='https://karoryfer.com'),
    'Iowa': dict(title='University of Iowa Musical Instrument Samples', by='University of Iowa Electronic Music Studios',
                 licence='free for any project, without restriction', url='https://theremin.music.uiowa.edu/MIS.html'),
    'SSO-CC0': dict(title='Sonatina Symphonic Orchestra (the CC0 celeste in the SSO fork)', by='Mattias Westlund and contributors',
                    licence='CC0 1.0', url='https://github.com/peastman/sso'),
    'SSO': dict(title='Sonatina Symphonic Orchestra', by='Mattias Westlund', licence='CC Sampling Plus 1.0',
                url='https://github.com/peastman/sso', need='attribution; the set contains Philharmonia and unknown-provenance '
                'recordings, so check each instrument before a public release'),
    'Discord-GM': dict(title='Discord SFZ GM Bank', by='per instrument (below)', licence='CC0 1.0 (every instrument used here)',
                       url='https://github.com/sfzinstruments/Discord-SFZ-GM-Bank'),
    'GregSullivan-EPianos': dict(title="Greg Sullivan's E-Pianos (Wurlitzer EP200)", by='Greg Sullivan (http://www.sullivang.net/); SFZ by kinwie',
                                 licence='CC BY 3.0', url='https://github.com/sfzinstruments/GregSullivan.E-Pianos', need='attribution'),
    'MTG-SoloSax': dict(title='MTG Solo Saxophones', by='MTG, Music Technology Group, Universitat Pompeu Fabra (freesound.org packs '
                        '20239, 20247, 20251, 20253); SFZ by kinwie', licence='CC BY 4.0',
                        url='https://github.com/sfzinstruments/MTG.SoloSax', need='attribution'),
    'JLearman-SteelDrum': dict(title='jSteelDrum', by='Jeff Learman', licence='Unlicense (public domain)',
                               url='https://github.com/sfzinstruments/jlearman.SteelDrum'),
    'GTownChurch': dict(title='G-Town Church Sampling Project', by='Tobias Marberger; SFZ by S. Christian Collins',
                        licence='CC Sampling Plus 1.0', url='https://github.com/sfzinstruments/GTownChurchSamplingProject',
                        need='attribution; transformed samples may be used commercially, verbatim copies of the whole set only '
                        'non-commercially, and the work may not be used to advertise anything but itself'),
    'SamsSonor': dict(title="Sam's Sonor drum kit (Sonor Force 3001)", by='Sam Greene; SFZ by kinwie', licence='CC BY-SA 4.0',
                      url='https://github.com/sfzinstruments/SamsSonor', need='attribution, and share-alike: the kit as built '
                      'here is CC BY-SA 4.0 too'),
    'HungarianZither': dict(title='Hungarian Zither', by='sfzinstruments', licence='CC0 1.0', url='https://github.com/sfzinstruments/hungarian_zither'),
    'CitharaBarbarica': dict(title='Cithara Barbarica (medieval lyre)', by='sfzinstruments', licence='CC0 1.0',
                             url='https://github.com/sfzinstruments/cithara-barbarica'),
    'FluidR3-GM': dict(title='Fluid R3 GM soundfont', by='Frank Wen (2000-2002, 2008), Toby Smithe (2008)', licence='MIT',
                       url='https://packages.debian.org/fluid-soundfont-gm', need='keep the copyright and MIT notice'),
    'MS-Basic': dict(title='MuseScore_General_HQ v0.2 (MuseScore "MS Basic")', by='Frank Wen (2000-02), Michael Cowgill (2014-17), '
                     'S. Christian Collins (2018-20)', licence='MIT', url='https://musescore.org', need='keep the copyright and MIT notice'),
    'A320U': dict(title='Airfont 320 update (A320U.sf2)', by='Milton Paredes (2005)', licence='GNU GPL 2.0 or later',
                  url='https://musix.es', need='copyleft: distribute under the GPL, with the soundfont on request'),
    'ClassicalAcousticGuitar': dict(title='"Classical Acoustic Guitar" SFZ (downloaded 2026-09-22)', by='unknown', licence='unknown',
                                    url='', need='no author or licence found: find its source or replace it before publishing'),
}
_ATTN = ('unknown', 'SSO', 'GPL', 'BY-SA')


def _root_lib(cand) -> str:
    """The CREDITS key for a gm_map candidate."""
    if cand.source == 'Extra':
        lib = cand.path
        if lib == 'Derived':
            sub = cand.sub or ''
            return next((k for pre, k in (('FluidR3', 'FluidR3-GM'), ('MS_Basic', 'MS-Basic'), ('A320U', 'A320U'), ('Iowa', 'Iowa'))
                         if sub.startswith(pre)), 'Derived')
        return lib
    if cand.source == 'Sonatina Symphonic Orchestra':
        return 'SSO'
    if cand.source == 'SSO':
        return 'SSO-CC0' if 'Celeste' in cand.path else 'SSO'
    if cand.source == 'FreePats' and 'FSS-SteelStringGuitar' in f'{cand.path} {cand.sub or ""}':
        return 'FreePats-FSS'
    if cand.source == 'Iowa' or cand.source.startswith('Iowa'):
        return 'Iowa'
    return cand.source


def _discord_credit(cand) -> str:
    """The Author/License lines a Discord GM instrument states in its own SFZ."""
    try:
        path, _ = cand.resolve()
        text = open(path).read(3000)
    except Exception:
        return ''
    lines = [l.strip('/ ').strip() for l in text.split('\n')[:12] if l.startswith('//')]
    keep = [l for l in lines if re.match(r'(Author|License|From|A custom mix|Source)', l)]
    return '; '.join(keep)


def programs() -> list:
    """[(program number, name, [(credits key, detail)])] for the 128 programs and the kit."""
    from . import gm_map
    rows = []
    for p in gm_map.PROGRAMS:
        if p.num in gm_map.LAYERS:
            cands = [c for c, *_ in gm_map.LAYERS[p.num]]
        else:
            cands = [next((c for c in p.cands if c.resolve()[1]), p.cands[0])]
        parts = []
        for c in cands:
            key = _root_lib(c)
            detail = f'{c.path} {c.sub or ""}'.strip() if c.source != 'Extra' else (c.sub or '').split('/')[-1].replace('.sfz', '')
            if key == 'Discord-GM':
                detail += f' ({_discord_credit(c)})'
            parts.append((key, detail))
        rows.append((p.num, p.name, parts))
    rows.append(('kit', 'GM drum kit', _kit()))
    return rows


def _kit() -> list:
    src = os.path.join(paths.ROOT, 'demo', 'GM', 'Drums.sfz')
    picks = os.path.join(paths.ROOT, 'SWIPE_PICKS.json')
    pick_lib = ''
    if os.path.exists(picks):
        pick_lib = ((json.load(open(picks)).get('128') or {}).get('pick') or {}).get('lib', '')
    used = {}
    if os.path.exists(src):
        for l in open(src).read().split('\n'):
            m = re.match(r'^// (\d+) ([^:]+): (\S+)', l)
            if m:
                lib = {'Pick': pick_lib or 'Pick', 'BigRusty': 'Karoryfer', 'Muldjord': 'FreePats-Muldjord'}.get(m.group(3), m.group(3))
                used.setdefault(lib, []).append(m.group(1))
    return [(lib, 'keys ' + ', '.join(keys)) for lib, keys in used.items()]


def write(out: str) -> str:
    rows = programs()
    by_lib: dict = {}
    for num, name, parts in rows:
        label = f'{num:03d} {name}' if isinstance(num, int) else name
        for key, _ in parts:
            if label not in by_lib.setdefault(key, []):
                by_lib[key].append(label)
    attn = [k for k in by_lib if any(w in CREDITS.get(k, {}).get('licence', 'unknown') for w in _ATTN) or k == 'SSO']
    md = ['# Attribution', '',
          'The kobi_soundbank banks are collections of independently licensed instruments: each program and each drum-kit '
          'piece keeps the licence of the library it was built from, listed below.  In every case the samples were '
          f'{CHANGES}.  The code that builds them is MIT ([LICENSE](LICENSE)).  Generated by `python3 -m kobi.attribution` from '
          'the mapping the banks are built from (gm_map with the swipe picks in SWIPE_PICKS.json).', '']
    if attn:
        md += ['## Before publishing a bank', '']
        for k in attn:
            c = CREDITS.get(k, dict(title=k, licence='unknown'))
            md.append(f"- **{c['title']}** ({c['licence']}): {c.get('need', 'check the licence')}.  Used by: {', '.join(by_lib[k])}.")
        md.append('')
    md += ['## Credits', '', 'Libraries whose licence asks for attribution or a notice, then the public-domain and CC0 ones '
           '(no attribution required; credited with thanks).', '']
    order = sorted(by_lib, key=lambda k: ('CC0' in CREDITS.get(k, {}).get('licence', '') or 'Unlicense' in CREDITS.get(k, {}).get('licence', '')
                                            or 'without restriction' in CREDITS.get(k, {}).get('licence', ''), k))
    for k in order:
        c = CREDITS.get(k, dict(title=k, by='?', licence='unknown', url=''))
        url = f" <{c['url']}>" if c.get('url') else ''
        md.append(f"- **{c['title']}** by {c['by']} — {c['licence']}.{url}  ({len(by_lib[k])} program{'s' if len(by_lib[k]) != 1 else ''})")
    md += ['', '## Program by program', '', '| program | library | licence | instrument |', '|---|---|---|---|']
    for num, name, parts in rows:
        label = f'{num:03d} {name}' if isinstance(num, int) else name
        for i, (key, detail) in enumerate(parts):
            c = CREDITS.get(key, dict(title=key, licence='unknown'))
            md.append(f"| {label if i == 0 else ''} | {c['title']} | {c['licence']} | {detail.replace('|', '/')} |")
    md += ['', '## MIT notice (Fluid R3 GM, MuseScore_General_HQ)', '',
           'Copyright (c) 2000-2002, 2008 Frank Wen; 2008 Toby Smithe; 2014-2017 Michael Cowgill; 2018-2020 S. Christian Collins.',
           '', 'Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated '
           'documentation files (the "Software"), to deal in the Software without restriction, including without limitation the '
           'rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit '
           'persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and '
           'this permission notice shall be included in all copies or substantial portions of the Software.', '',
           'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE '
           'WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE AUTHORS OR '
           'COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR '
           'OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.']
    text = '\n'.join(md) + '\n'
    with open(out, 'w') as fh:
        fh.write(text)
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('banks', nargs='*', help='built banks to put a copy into')
    a = ap.parse_args(argv)
    text = write(os.path.join(paths.ROOT, 'ATTRIBUTION.md'))
    for b in a.banks:
        b = paths.bank(b)
        if os.path.isdir(b):
            with open(os.path.join(b, 'ATTRIBUTION.md'), 'w') as fh:
                fh.write(text.replace('[LICENSE](LICENSE)', 'the repository\'s LICENSE'))
    print(text.split('## Credits')[0])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
