"""kobi.manifest — write GM/manifest.json for a bank folder (what the web player reads).

    python3 -m kobi.manifest kobi_slim kobi_ogg ...
"""
import glob
import json
import os
import re
import sys

from .paths import use_dctjoin
use_dctjoin()
from dctjoin.gm import GM_PROGRAMS  # noqa: E402


def _entry(gm_dir: str, sfz: str) -> tuple[int, int]:
    text = open(os.path.join(gm_dir, sfz)).read()
    m = re.search(r'default_path=(\S+)', text)
    files = set(re.findall(r'sample=(\S+)', text))
    folder = os.path.normpath(os.path.join(gm_dir, m.group(1))) if m else gm_dir
    return sum(os.path.getsize(os.path.join(folder, f)) for f in files if os.path.exists(os.path.join(folder, f))) + len(text), len(files)


def write_manifest(bank: str, name: str | None = None) -> dict:
    gm = os.path.join(bank, 'GM')
    man = dict(name=name or os.path.basename(bank.rstrip('/')), format='sfz+ogg', drums=None, programs={}, total_bytes=0)
    oggs = glob.glob(os.path.join(bank, '*', '*.ogg'))
    if oggs:                                              # the rate the audio was written at: a player that runs its
        import soundfile as sf                            # context at this rate never resamples a loop
        man['rate'] = int(sf.info(oggs[0]).samplerate)
    for n in range(128):
        f = f'{n:03d} {GM_PROGRAMS[n][0]}.sfz'
        if os.path.exists(os.path.join(gm, f)):
            b, nf = _entry(gm, f)
            man['programs'][str(n)] = dict(file=f, name=GM_PROGRAMS[n][0], bytes=b, files=nf)
            man['total_bytes'] += b
    if os.path.exists(os.path.join(gm, 'Drums.sfz')):
        b, nf = _entry(gm, 'Drums.sfz')
        man['drums'] = dict(file='Drums.sfz', name='Drums', bytes=b, files=nf)
        man['total_bytes'] += b
    with open(os.path.join(gm, 'manifest.json'), 'w') as fh:
        json.dump(man, fh, indent=1)
    return man


if __name__ == '__main__':
    for bank in sys.argv[1:]:
        m = write_manifest(bank)
        print(f'{bank}: {len(m["programs"])} programs{" + drums" if m["drums"] else ""}, {m["total_bytes"] / 1e6:.1f} MB')
