#!/usr/bin/env python3
"""Backfill missing per-color-variant furni icons (bc_tile*1 -> bc_tile_1_icon.png).

nitro-renderer requests `{base}_{param}_icon.png` for any classname registered
with an indexed color (`base*param` in FurnitureData) — see
RoomContentLoader.getAssetUrls, which appends `_param` whenever the full
`base*param` classname exists in FurnitureData. extract-furni-icons.py only
produces one icon per .nitro bundle (the base icon), so every color-variant
icon 404'd — most visibly in the Builders Club catalog tree, where every
single item is a `*N` variant.

For each missing variant icon this script:
  1. downloads the official one from images.habbo.com/dcr/hof_furni/{revision}/
  2. falls back to copying the local base icon when the CDN has no variant

Idempotent: re-running skips icons that already exist. Run from the repo root
after any FurnitureData / icon-tree regeneration:

    python3 docker/nitro/fetch-variant-icons.py
"""
import json, os, shutil
from concurrent.futures import ThreadPoolExecutor
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICONS = os.path.join(REPO, 'nitro/assets/dcr/hof_furni/icons')
FD = os.path.join(REPO, 'nitro/assets/gamedata/FurnitureData.json')
CDN = 'https://images.habbo.com/dcr/hof_furni'

d = json.load(open(FD))
existing = set(os.listdir(ICONS))
work = []
for section in ('roomitemtypes', 'wallitemtypes'):
    for t in d[section]['furnitype']:
        cn = t['classname']
        if '*' not in cn:
            continue
        base, param = cn.split('*', 1)
        fn = f'{base}_{param}_icon.png'
        if fn not in existing:
            work.append((base, param, t.get('revision'), fn))
            existing.add(fn)  # dedupe repeated classnames

print(f'missing variant icons: {len(work)}', flush=True)

stats = {'cdn': 0, 'copied': 0, 'nobase': 0}

def fetch(job):
    base, param, rev, fn = job
    url = f'{CDN}/{rev}/{fn}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'pixelrp-asset-repair'})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            open(os.path.join(ICONS, fn), 'wb').write(data)
            return 'cdn'
    except Exception:
        pass
    src = os.path.join(ICONS, f'{base}_icon.png')
    if os.path.exists(src):
        shutil.copyfile(src, os.path.join(ICONS, fn))
        return 'copied'
    return 'nobase'

with ThreadPoolExecutor(max_workers=8) as ex:
    for i, res in enumerate(ex.map(fetch, work), 1):
        stats[res] += 1
        if i % 500 == 0:
            print(f'{i}/{len(work)} {stats}', flush=True)

print('DONE', stats)
