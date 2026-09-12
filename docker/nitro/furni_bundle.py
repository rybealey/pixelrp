#!/usr/bin/env python3
"""Shared machinery for importing a folder of .nitro furniture packs.

Both import-designer-furni.py and import-building-furni.py take a download
whose folder tree IS the catalog tree and turn it into furniture rows, catalog
pages, bundles, icons and gamedata entries. Everything that is the same for
either pack lives here; each importer keeps only what makes it different - its
target page, its id ranges, and any pack-specific exception.

Nothing in this module writes SQL or decides page structure. It reads a bundle,
re-encodes it, crops its icon and turns a classname into a display name.
"""
import glob
import gzip
import io
import json
import os
import re
import struct
import zipfile
import zlib


SEAT = re.compile(r'chair|sofa|bench|stool|puf|pouf|seat|couch|armchair|beanbag|throne'
                  r'|chaise|canape|fauteuil|tabouret|banc|siege')
GROUND = re.compile(r'floor|tile|grass|dirt|water|path|road|sand|snow|rug|carpet|mat\b'
                    r'|lawn|bridge|stair|pavement|stone(?!wall)|platform|deck'
                    r'|tapis|sol\b|dalle|herbe|eau\b|chemin|sable|neige|plancher'
                    r'|carrelage|moquette|pelouse|parquet')


def bundle_entries(path):
    """{name: blob} for one .nitro (big-endian: count, then len/name/len/blob).

    A handful of bundles in the wild are ZIP archives of the same two files
    instead - one in the Building download is - so PK is read as a zip and its
    members come back already plain. `inflate` copes with either.
    """
    raw = open(path, 'rb').read()
    if raw[:2] == b'PK':
        with zipfile.ZipFile(path) as archive:
            return {name: archive.read(name) for name in archive.namelist()}
    count = struct.unpack('>H', raw[:2])[0]
    i, out = 2, {}
    for _ in range(count):
        ln = struct.unpack('>H', raw[i:i + 2])[0]
        i += 2
        name = raw[i:i + ln].decode('utf-8')
        i += ln
        dl = struct.unpack('>I', raw[i:i + 4])[0]
        i += 4
        out[name] = raw[i:i + dl]
        i += dl
    return out


def inflate(blob):
    """gzip, zlib, or already plain (a zip member) - all three occur."""
    if blob[:2] == b'\x1f\x8b':
        return gzip.decompress(blob)
    try:
        return zlib.decompress(blob)
    except zlib.error:
        return blob


def write_bundle(path, entries):
    """Same layout back out, every entry zlib.

    bundle_entries hands back the blobs STILL COMPRESSED, so they are inflated
    before being re-compressed - packing them as-is produces a bundle whose
    entries are compressed twice, which the client silently fails to read.
    """
    with open(path, 'wb') as fh:
        fh.write(struct.pack('>H', len(entries)))
        for name, data in entries.items():
            packed = zlib.compress(inflate(data), 9)
            encoded = name.encode('utf-8')
            fh.write(struct.pack('>H', len(encoded)) + encoded)
            fh.write(struct.pack('>I', len(packed)) + packed)


def existing_classnames(sql_sources):
    """Every furniture classname the hotel already defines, so it is never re-added."""
    names = set()
    for path in sql_sources:
        text = open(path, encoding='utf-8', errors='replace').read()
        # every quoted first-or-second value of a furniture tuple; over-matching
        # here only ever means skipping something we should have imported, and
        # the counts at the end would show that
        names.update(re.findall(r"\('([a-zA-Z0-9_*]+)',", text))
        names.update(re.findall(r"\([0-9]+,'([a-zA-Z0-9_*]+)',", text))
        names.update(re.findall(r"VALUES \('[0-9]+', '([a-zA-Z0-9_*]+)'", text))
    return names


def load_items_json(root):
    """classname -> the source hotel's catalog entry, from every _items.json."""
    items = {}
    for path in glob.glob(os.path.join(root, '**', '_items.json'), recursive=True):
        for item in json.load(open(path, encoding='utf-8')):
            key = item.get('classname') or item.get('asset_name')
            if key and key not in items:
                items[key] = item
    return items


def pretty(raw, prefix):
    name = raw[len(prefix):] if prefix and raw.startswith(prefix) else raw
    name = re.sub(r'^(habbox|hbx|custom)_', '', name)
    name = re.sub(r'(?<=[a-z])(?=\d)', ' ', name)         # plant3 -> plant 3
    words = [w for w in name.replace('_', ' ').replace('-', ' ').split() if w]
    return ' '.join(w.capitalize() for w in words) or raw


def common_prefix(classnames):
    prefix = os.path.commonprefix(classnames)
    return prefix[:prefix.rindex('_') + 1] if '_' in prefix else ''


def read_furni(path):
    entries = bundle_entries(path)
    json_name = next(k for k in entries if k.endswith('.json'))
    png_name = next((k for k in entries if k.endswith('.png')), None)
    data = json.loads(inflate(entries[json_name]))
    model = (data.get('logic') or {}).get('model') or {}
    dims = model.get('dimensions') or {}
    vis64 = next((v for v in data.get('visualizations') or [] if v.get('size') == 64), {})
    frames = (data.get('spritesheet') or {}).get('frames') or {}
    icon = next((k for k in frames if k.endswith('_icon_a')), None) \
        or next((k for k in frames if '_icon_' in k), None)
    return {
        'entries': entries,
        'png': png_name,
        'x': int(float(dims.get('x', 1) or 1)),
        'y': int(float(dims.get('y', 1) or 1)),
        'z': float(dims.get('z', 1.0) if dims.get('z') is not None else 1.0),
        'has_dims': bool(dims),
        'modes': max(1, len(vis64.get('animations') or {})),
        'icon_frame': frames.get(icon) if icon else None,
    }


def crop_icon(entries, png_name, frame, out_path):
    # Pillow is imported HERE rather than at the top because it is needed by
    # exactly this function. Importing it on the module made every consumer of
    # the bundle reader depend on an image library - which is how
    # show-furni-directions.py, whose whole job is to unzip a JSON blob and
    # print a list, died on a server that has no Pillow installed.
    from PIL import Image

    rect = frame.get('frame') or {}
    if not png_name or not rect:
        return False
    image = Image.open(io.BytesIO(inflate(entries[png_name])))
    icon = image.crop((rect['x'], rect['y'], rect['x'] + rect['w'], rect['y'] + rect['h']))
    if frame.get('rotated'):
        icon = icon.rotate(90, expand=True)
    icon.save(out_path, 'PNG')
    return True


# ---- walk -------------------------------------------------------------------

