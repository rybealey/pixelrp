#!/usr/bin/env python3
"""Import a Habbo Unity-client clothing bundle (UnityFS) as a Nitro figure bundle.

Usage:
    python3 docker/nitro/import-unity-figure.py <unity-bundle-file>

Extracts the sprites and the AvatarPartBundleXml manifest (offsets, aliases)
via UnityPy, packs a spritesheet, and writes
nitro/assets/bundled/figure/<library>.nitro in the exact container format
nitro-renderer parses (int16-BE entry count; per entry: int16-BE name length,
name, int32-BE blob length, zlib blob).

Registration checklist (the script reports, but does not invent, game data):
  - FigureMap.json must map the library to its part ids (the script adds the
    entry if missing, deriving parts from the sprite names).
  - FigureData.json must contain a selectable set referencing those parts —
    official items usually already have one; custom items need a hand-written
    set modeled on a same-type sibling.
  - After any FigureData change: python3 docker/nitro/figuredata-json-to-xml.py
    and restart the emulator, or saves strip the new set.

Requires: pip3 install UnityPy pillow
"""
import json
import os
import re
import struct
import sys
import zlib

import UnityPy
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIGURE_DIR = os.path.join(REPO, 'nitro/assets/bundled/figure')
FIGUREMAP = os.path.join(REPO, 'nitro/assets/gamedata/FigureMap.json')

def main(bundle_path):
    env = UnityPy.load(bundle_path)
    images = {}
    manifest = None
    library = None
    for obj in env.objects:
        if obj.type.name == 'Texture2D':
            d = obj.read()
            images[d.m_Name] = d.image
        elif obj.type.name == 'MonoBehaviour':
            tree = obj.read_typetree()
            asset = (tree.get('xmlAsset') or {}).get('avatarPartAsset')
            if asset:
                manifest = asset
                library = asset['name']
    if not manifest or not library:
        sys.exit('no AvatarPartBundleXml manifest found in bundle')

    # assets: manifest parts carry "x,y" offsets; aliases point at other assets
    assets = {}
    for part in manifest['parts']:
        x, y = (int(v) for v in part['param']['value'].split(','))
        assets[part['name']] = { 'x': x, 'y': y }
    for alias in (manifest.get('assetAliases') or []):
        target = dict(assets.get(alias['link']) or {})
        target['source'] = alias['link']
        if alias.get('flipH'): target['flipH'] = True
        if alias.get('flipV'): target['flipV'] = True
        assets[alias['name']] = target

    # vertical-strip spritesheet (matches converter output shape)
    names = [n for n in assets if 'source' not in assets[n] and n in images]
    sheet_w = max(images[n].width for n in names)
    sheet_h = sum(images[n].height for n in names)
    sheet = Image.new('RGBA', (sheet_w, sheet_h))
    frames = {}
    cursor = 0
    for n in names:
        img = images[n]
        sheet.paste(img, (0, cursor))
        frames[f'{library}_{n}'] = {
            'frame': { 'x': 0, 'y': cursor, 'w': img.width, 'h': img.height },
            'rotated': False, 'trimmed': False,
            'spriteSourceSize': { 'x': 0, 'y': 0, 'w': img.width, 'h': img.height },
            'sourceSize': { 'w': img.width, 'h': img.height },
            'pivot': { 'x': 0.5, 'y': 0.5 },
        }
        cursor += img.height

    import io
    png = io.BytesIO()
    sheet.save(png, format='PNG')
    doc = {
        'assets': assets,
        'name': library,
        'spritesheet': {
            'frames': frames,
            'meta': { 'image': f'{library}.png', 'format': 'RGBA8888',
                      'size': { 'w': sheet_w, 'h': sheet_h }, 'scale': 1 },
        },
    }

    entries = [
        (f'{library}.json', zlib.compress(json.dumps(doc, separators=(',', ':')).encode(), 9)),
        (f'{library}.png', zlib.compress(png.getvalue(), 9)),
    ]
    out = bytearray()
    out += struct.pack('>h', len(entries))
    for name, blob in entries:
        out += struct.pack('>h', len(name)) + name.encode()
        out += struct.pack('>i', len(blob)) + blob
    dest = os.path.join(FIGURE_DIR, f'{library}.nitro')
    open(dest, 'wb').write(bytes(out))
    print(f'wrote {dest} ({len(out)} bytes, {len(assets)} assets, {len(frames)} frames)')

    # FigureMap: add the library if absent
    fm = json.load(open(FIGUREMAP))
    if not any(l['id'] == library for l in fm['libraries']):
        parts = sorted({ (int(m.group(2)), m.group(1))
                         for n in assets
                         for m in [re.match(r'h_\w+?_(\w{2})_(\d+)_', n)] if m })
        fm['libraries'].append({ 'id': library, 'revision': 0,
                                 'parts': [ { 'id': i, 'type': t } for i, t in parts ] })
        json.dump(fm, open(FIGUREMAP, 'w'), ensure_ascii=False, separators=(',', ':'))
        print(f'FigureMap: added {library} with parts {parts}')
        print('NOTE: FigureData needs a selectable set for these parts if none exists,')
        print('then: python3 docker/nitro/figuredata-json-to-xml.py && restart emulator')
    else:
        print(f'FigureMap: {library} already registered')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
