#!/usr/bin/env python3
"""Draw a catalog icon for furni whose bundle does not carry one.

The client fetches every catalog tile from dcr/hof_furni/icons/<classname>
_icon.png, a static PNG that has nothing to do with the bundle at render time.
Most bundles ship the artist's own icon as an `_icon_a` frame in their
spritesheet, which import-designer-furni.py crops out. 176 of the Habba Customs
bundles have no such frame, so their tiles are blank in the shop.

A real icon is drawn by hand - it is NOT the furni sprite scaled down, and
comparing the two shows it: same-size only where the artist happened to reuse
the sprite, different aspect ratios everywhere else. So this cannot recover the
missing artwork. What it can do is render the furni itself, small: composite the
64-size sprite's layers the way the room renderer would, trim it, and scale it
into the 35x35 box the real icons occupy (their p95 is 36 and their median 29).
The result reads as the item rather than as a blank square, which is the whole
point of the tile.

Which state gets drawn: animation 0, the state a freshly placed furni is in.
Except when that state is nearly empty - a multistate "objects" furni whose
first state is a 34x5 sliver would make a thumbnail of a smudge - in which case
the fullest state is used instead, since the tile's job is to show what the
thing is.

Run from the repo root, after the import:
    python3 docker/nitro/synthesize-furni-icons.py
Idempotent: only ever writes an icon that is not already on disk.
"""
import glob
import gzip
import io
import json
import os
import struct
import sys
import zlib

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUNDLE_DIR = os.path.join(REPO, 'nitro/overrides/bundled/furniture')
ICON_DIR = os.path.join(REPO, 'nitro/overrides/dcr/hof_furni/icons')

# The box the shipped icons sit in: 95% are 36px or under on both axes.
ICON_BOX = 35
# Below this share of the fullest state's opaque pixels, state 0 is not
# showing the furni and the fullest state is drawn instead.
EMPTY_STATE_RATIO = 0.5
# The room renderer's default facing; every one of these bundles has it.
DIRECTION = '2'


def bundle_entries(path):
    raw = open(path, 'rb').read()
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
    return gzip.decompress(blob) if blob[:2] == b'\x1f\x8b' else zlib.decompress(blob)


def load(path):
    entries = bundle_entries(path)
    json_name = next(k for k in entries if k.endswith('.json'))
    png_name = next((k for k in entries if k.endswith('.png')), None)
    data = json.loads(inflate(entries[json_name]))
    sheet = Image.open(io.BytesIO(inflate(entries[png_name]))).convert('RGBA') if png_name else None
    return data, sheet


def cut(sheet, frames, key):
    frame = frames.get(key)
    if not frame:
        return None
    r = frame['frame']
    out = sheet.crop((r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h']))
    return out.rotate(90, expand=True) if frame.get('rotated') else out


def compose(data, sheet, animation):
    """One state of the 64-size sprite, layers stacked by z the way a room draws it.

    An asset entry can be an alias of another (`source`, usually the mirrored
    direction), and it carries the registration offset the sprite is drawn at -
    negated, exactly as the renderer does it, so the layers line up.
    """
    lib = data['name']
    frames = (data.get('spritesheet') or {}).get('frames') or {}
    assets = data.get('assets') or {}
    vis = next((v for v in data.get('visualizations') or [] if v.get('size') == 64), None)
    if not vis or not sheet:
        return None
    layers = vis.get('layers') or {}
    placed = []
    for index in range(vis.get('layerCount') or 1):
        frame_id = 0
        layer_anim = ((animation or {}).get('layers') or {}).get(str(index))
        if layer_anim:
            sequences = layer_anim.get('frameSequences') or {}
            if sequences:
                sequence = sequences.get('0') or list(sequences.values())[0]
                entries = sequence.get('frames') or {}
                if entries:
                    frame_id = (entries.get('0') or list(entries.values())[0]).get('id', 0)
        name = '%s_64_%s_%s_%d' % (lib, chr(97 + index), DIRECTION, frame_id)
        asset = assets.get(name)
        if asset is None:
            continue
        image = cut(sheet, frames, '%s_%s' % (lib, asset.get('source', name)))
        if image is None:
            continue
        if asset.get('flipH'):
            image = image.transpose(Image.FLIP_LEFT_RIGHT)
        placed.append(((layers.get(str(index)) or {}).get('z', 0), index,
                       -int(asset.get('x', 0)), -int(asset.get('y', 0)), image))
    if not placed:
        return None
    left = min(p[2] for p in placed)
    top = min(p[3] for p in placed)
    canvas = Image.new('RGBA', (max(p[2] + p[4].width for p in placed) - left,
                                max(p[3] + p[4].height for p in placed) - top), (0, 0, 0, 0))
    for _z, _i, x, y, image in sorted(placed, key=lambda p: (p[0], p[1])):
        canvas.alpha_composite(image, (x - left, y - top))
    return canvas


def opaque_pixels(image):
    return sum(1 for a in image.getchannel('A').getdata() if a > 8)


def thumbnail(data, sheet):
    vis = next((v for v in data.get('visualizations') or [] if v.get('size') == 64), None)
    animations = (vis or {}).get('animations') or {}
    keys = sorted(animations, key=lambda k: int(k)) if animations else [None]
    default = compose(data, sheet, animations.get('0') if '0' in animations else
                      (animations.get(keys[0]) if keys[0] is not None else None))
    if default is None:
        return None
    best, best_weight = default, opaque_pixels(default)
    for key in keys:
        if key is None or key == '0':
            continue
        other = compose(data, sheet, animations.get(key))
        if other is None:
            continue
        weight = opaque_pixels(other)
        if weight > best_weight:
            best, best_weight = other, weight
    chosen = default if opaque_pixels(default) >= best_weight * EMPTY_STATE_RATIO else best
    box = chosen.getbbox()
    if not box:
        return None
    chosen = chosen.crop(box)
    if max(chosen.size) > ICON_BOX:
        scale = ICON_BOX / max(chosen.size)
        chosen = chosen.resize((max(1, round(chosen.width * scale)),
                                max(1, round(chosen.height * scale))), Image.LANCZOS)
    return chosen


written, skipped, failed = 0, 0, []
for path in sorted(glob.glob(os.path.join(BUNDLE_DIR, '*.nitro'))):
    classname = os.path.basename(path)[:-6]
    out = os.path.join(ICON_DIR, '%s_icon.png' % classname)
    if os.path.exists(out):
        skipped += 1
        continue
    try:
        data, sheet = load(path)
        icon = thumbnail(data, sheet)
    except Exception as error:                      # a bundle we cannot read is not fatal
        failed.append((classname, repr(error)[:60]))
        continue
    if icon is None:
        failed.append((classname, 'nothing to draw'))
        continue
    icon.save(out, 'PNG')
    written += 1

print('synthesised %d   already had one %d   still blank %d' % (written, skipped, len(failed)))
for classname, why in failed[:10]:
    print('   %s: %s' % (classname, why))
if failed:
    json.dump([c for c, _ in failed],
              open(os.path.join(REPO, 'docker/nitro/designer-furni/still-blank.json'), 'w'), indent=1)
sys.exit(0)
