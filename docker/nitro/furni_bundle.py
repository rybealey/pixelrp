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


# Logic types whose double click is a plain state change. The rest - clothing,
# crackable eggs, sound blocks, dice - do something else on a click, and
# furniture_multiheight changes height per state, which a count alone does not
# give it: avatars would stand on the taller table at the old height.
SWITCHED_BY_CLICK = ('furniture_multistate', 'furniture_basic')


def click_modes(data, classname):
    """interaction_modes_count for a plain ('default') furni, from its bundle:
    state 0, then every state from 1 up until the first gap.

    State 0 needs no animation of its own - with none, every layer simply draws
    frame 0 - so a bundle whose only animation is 1 still has two states, and
    counting its animations (1) left a furni that could not be clicked at all.
    Counting stops at the first gap because the server cycles 0, 1, 2 ... in
    order; ids past a gap (100, 101, 1234 - states the server sets itself, like
    a toilet's flush) would put blank clicks in the cycle. Transitions are not
    states. Wired boxes (wf_*) are not switched by hand.
    """
    if classname.startswith('wf_') or data.get('logicType') not in SWITCHED_BY_CLICK:
        return 1
    vis64 = next((v for v in data.get('visualizations') or [] if v.get('size') == 64), {})
    ids = set()
    for key, animation in (vis64.get('animations') or {}).items():
        if 'transitionTo' not in animation and 'transitionFrom' not in animation and key.isdigit():
            ids.add(int(key))
    n = 1
    while n in ids:
        n += 1
    return n


LAYER_LETTERS = 'abcdefghijklmnopqrstuvwxyz'


def click_states(entries, classname, count=None):
    """The states a click should go through, from the art: of 0 .. count - 1
    (count defaults to click_modes), the ones that show something new.

    A look is not always a click state. Two kinds of state are dropped:
    - one that draws exactly what the state before it draws, still - the same
      pictures in the same places the same way round, in every direction - so
      the click to it shows nothing; often a count running past the end of
      the art, where a state falls back to frame 0. The last state goes too if
      it looks like state 0. A look that comes round again later stays (a pipe
      that grows, then shrinks back);
    - the Washing Machine's: a furni of three looks - one moving, the same
      stopped on its first frame, and one other still - clicks between the
      moving one and the other, never the stopped copy. A stopped look is left
      everywhere else: a speaker's or a wind chime's only 'off', a lamp's
      steady colours beside its flashing one.
    Fewer than two states left means nothing is dropped.
    """
    import hashlib

    import numpy as np
    from PIL import Image

    data = json.loads(inflate(entries[next(k for k in entries if k.endswith('.json'))]))
    top = count if count else click_modes(data, classname)
    every = list(range(top))
    vis = next((v for v in data.get('visualizations') or [] if v.get('size') == 64), None)
    png = next((k for k in entries if k.endswith('.png')), None)
    if top < 2 or data.get('logicType') != 'furniture_multistate' or not vis or not png:
        return every
    sheet = Image.open(io.BytesIO(inflate(entries[png]))).convert('RGBA')
    frames = {(k[:-4] if k.endswith('.png') else k): v
              for k, v in ((data.get('spritesheet') or {}).get('frames') or {}).items()}
    assets = data.get('assets') or {}
    dirs = sorted(int(d) for d in (vis.get('directions') or {'2': {}}))
    layers = int(vis.get('layerCount') or 1)
    anims = vis.get('animations') or {}
    hashes = {}

    def picture(name):
        # an asset can borrow another's picture and still sit elsewhere or flipped
        own = assets.get(name) or {}
        src, hops = name, 0
        while (assets.get(src) or {}).get('source') and hops < 5:
            src, hops = assets[src]['source'], hops + 1
        frame = frames.get(classname + '_' + src) or frames.get(src)
        digest = None
        if frame:
            r = frame.get('frame') or {}
            key = (r.get('x'), r.get('y'), r.get('w'), r.get('h'))
            if key not in hashes:
                pixels = np.array(sheet.crop((r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h'])))
                pixels[pixels[..., 3] == 0] = 0          # what a clear pixel holds is not seen
                hashes[key] = hashlib.blake2b(pixels.tobytes() + bytes(str(pixels.shape), 'ascii'),
                                              digest_size=8).hexdigest()
            digest = hashes[key]
        return digest, bool(own.get('flipH')), int(own.get('x', 0) or 0), int(own.get('y', 0) or 0)

    def look(state):
        """Per layer: every look the state's animation shows, and the one it starts on."""
        layer_anims = (anims.get(str(state)) or {}).get('layers') or {}
        out = []
        for layer in range(layers):
            seq = []
            for sequence in ((layer_anims.get(str(layer)) or {}).get('frameSequences') or {}).values():
                for f in (sequence.get('frames') or {}).values():
                    seq.append((int(f.get('id', 0)), int(f.get('x', 0) or 0), int(f.get('y', 0) or 0)))
            shown = [(tuple(picture('%s_64_%s_%d_%d' % (classname, LAYER_LETTERS[layer], d, f))
                            for d in dirs), x, y) for f, x, y in (seq or [(0, 0, 0)])]
            out.append((frozenset(shown), shown[0]))
        return out

    looks = [look(s) for s in every]
    moving = {s for s in every if any(len(shown) > 1 for shown, _ in looks[s])}
    first = [[start for _, start in looks[s]] for s in every]

    def alike(s, t):
        return s not in moving and t not in moving and first[s] == first[t]

    # a click to a state that looks just like the one before it shows nothing;
    # a look coming round again later is fine (a pipe that grows, then shrinks)
    keep = []
    for s in every:
        if not keep or not alike(s, keep[-1]):
            keep.append(s)
    while len(keep) > 1 and alike(keep[-1], 0):
        keep.pop()                                # the last click back to 0 shows nothing
    stopped = [s for s in keep if s and s not in moving and any(t in moving and first[t] == first[s] for t in keep)]
    if len(keep) == 3 and len([s for s in keep if s in moving]) == 1 and len(stopped) == 1:
        keep.remove(stopped[0])
    return keep if len(keep) >= 2 else every


def read_furni(path):
    entries = bundle_entries(path)
    json_name = next(k for k in entries if k.endswith('.json'))
    png_name = next((k for k in entries if k.endswith('.png')), None)
    data = json.loads(inflate(entries[json_name]))
    model = (data.get('logic') or {}).get('model') or {}
    dims = model.get('dimensions') or {}
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
        'modes': click_modes(data, os.path.basename(path)[:-len('.nitro')]),
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

