#!/usr/bin/env python3
"""Draw the Spaces page's floor and wallpaper thumbnails from room.nitro.

The catalog's Spaces page shows every floor and wallpaper as a tile whose image
is c_images/catalogue/th_floor_<id>.png or th_wall_<id>.png. Sulake never put
those on images.habbo.com (it 404s for all but a handful), and the server's
asset tree never had them, so every tile was blank. Landscapes are different -
their th_landscape_*_001.png do exist upstream and were mirrored as they are.

What room.nitro does have is the patterns themselves: every floor and wall
plane is ONE layer, a texture from the spritesheet tinted by a colour (plane
-> material -> texture -> bitmap). That is exactly what the room preview draws,
so the thumbnail is drawn from it too, at the texture's own scale so the pixel
art stays crisp:

  floor   a 32x16 isometric tile, centred in 32x32. Floor textures are already
          drawn in screen space (the room tiles them unprojected), so the tile
          is simply cut out of the tinted texture repeated.
  wall    the corner Habbo's own th_wall thumbnails show: two 16px-wide planes
          rising to a peak in the middle, the right one shaded darker the way
          the room shades its right-hand wall. Wall textures are 32px-wide
          strips repeated down the wall and skewed with it.

Run from the repo root with a copy of room.nitro (the server's, from
nitro/assets/bundled/generic/room.nitro - it is not in the repo):
    python3 docker/nitro/synthesize-spaces-thumbs.py path/to/room.nitro
Writes into nitro/overrides/c_images/catalogue/, overwriting what is there.
The '99999' test wall and each 'default' plane are skipped.
"""
import io
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furni_bundle as fb  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(REPO, 'nitro/overrides/c_images/catalogue')
SIZE = 32
# The room draws its right-hand wall darker than its left.
RIGHT_WALL_SHADE = 0.8
SKIP = {'default', '99999'}


def load(path):
    entries = fb.bundle_entries(path)
    data = json.loads(fb.inflate(entries['room.json']))
    sheet = Image.open(io.BytesIO(fb.inflate(entries['room.png']))).convert('RGBA')
    return data, sheet


def texture_for(section, plane, frames, sheet):
    """The plane's tinted texture, or None when any link in the chain is missing."""
    vis = next((v for v in plane.get('visualizations') or [] if v.get('size') == 64), None)
    layer = ((vis or {}).get('allLayers') or [None])[0]
    if not layer:
        return None
    material = next((m for m in section['materials'] if m['id'] == layer.get('materialId')), None)
    try:
        texture_id = material['matrices'][0]['columns'][0]['cells'][0]['textureId']
    except (TypeError, KeyError, IndexError):
        return None
    texture = next((t for t in section['textures'] if t['id'] == texture_id), None)
    if not texture or not texture.get('bitmaps'):
        return None
    frame = (frames.get('room_' + texture['bitmaps'][0]['assetName']) or {}).get('frame')
    if not frame:
        return None
    image = sheet.crop((frame['x'], frame['y'], frame['x'] + frame['w'], frame['y'] + frame['h']))
    return tint(image, layer.get('color', 0xFFFFFF))


def tint(image, color, shade=1.0):
    r, g, b = ((color >> 16) & 255) * shade, ((color >> 8) & 255) * shade, (color & 255) * shade
    out = image.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            pr, pg, pb, pa = px[x, y]
            px[x, y] = (int(pr * r / 255), int(pg * g / 255), int(pb * b / 255), pa)
    return out


def floor_thumb(texture):
    out = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    src, dst = texture.load(), out.load()
    # diamond: top (16,8), right (31,16), bottom (16,24), left (0,16)
    for y in range(8, 24):
        half = (y - 8) * 2 if y < 16 else (24 - y) * 2
        for x in range(16 - half, 16 + half):
            dst[x, y] = src[x % texture.width, y % texture.height]
    return out


def wall_thumb(texture):
    out = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    left, right = texture.load(), tint(texture, 0xFFFFFF, RIGHT_WALL_SHADE).load()
    for x in range(SIZE):
        # the top edge rises 1px per 2 to the peak in the middle, then falls
        top = (8 - x // 2) if x < 16 else ((x - 16) // 2)
        src = left if x < 16 else right
        for y in range(top, min(SIZE, top + 24)):
            out.load()[x, y] = src[x % texture.width, (y - top) % texture.height]
    return out


def main():
    if len(sys.argv) != 2:
        sys.exit('usage: synthesize-spaces-thumbs.py path/to/room.nitro')
    data, sheet = load(sys.argv[1])
    frames = data['spritesheet']['frames']
    rv = data['roomVisualization']
    os.makedirs(OUT_DIR, exist_ok=True)
    written, failed = 0, []
    for key, prefix, draw in (('floorData', 'th_floor', floor_thumb), ('wallData', 'th_wall', wall_thumb)):
        section = rv[key]
        for plane in section['planes']:
            plane_id = str(plane['id'])
            if plane_id in SKIP:
                continue
            texture = texture_for(section, plane, frames, sheet)
            if texture is None:
                failed.append('%s_%s' % (prefix, plane_id))
                continue
            draw(texture).save(os.path.join(OUT_DIR, '%s_%s.png' % (prefix, plane_id)))
            written += 1
    print('wrote %d   could not draw %d %s' % (written, len(failed), failed[:10]))


if __name__ == '__main__':
    main()
