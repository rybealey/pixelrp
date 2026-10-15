#!/usr/bin/env python3
"""Turn the ATM Machine into a plain cash machine: no green glow, no 'ATM' sign.

The glow is its own visualization layer (layer 2, ink ADD, sprite `c`), so it
comes off cleanly - the layer, its assets and its frame all go, and layerCount
drops to 2.

The sign is not a layer. It is painted into the body sprite, across two
surfaces, and has to be repainted out:

  * The isometric top face is symmetric about its vertex, so the clean left
    half mirrors onto the right and brings the outline and the edge bevel with
    it. Its ridges are NOT symmetric, though - they sit at fixed columns - so
    the mirror is used only for the 4px bevel band and the interior is redrawn
    from the ridge columns instead. Where both halves are under the sign (the
    wedge above the face's bottom vertex) the ridge columns are all there is.
  * The right panel above the poster band is flat, so it is repainted from the
    column palette its clean rows below the sign show.

The catalog icon carries the same sign and gets the same treatment, with its
own (smaller, shifted) geometry.

Run it against the converted bundle, once:

    python3 docker/nitro/atm-strip-sign.py nitro/overrides/bundled/furniture/atm_moneymachine.nitro

Idempotent: a bundle with no glow layer left is reported and skipped.
"""
import io
import json
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furni_bundle as fb

from PIL import Image

CLASS = 'atm_moneymachine'
GLOW_LAYER = '2'

BLACK = (0, 0, 0, 255)
CLEAR = (0, 0, 0, 0)
BASE = (134, 134, 134, 255)          # the top face
RIDGE = (199, 199, 199, 255)         # its vertical ridges
LEFT = (112, 112, 112, 255)          # the left panel
PANEL_FILL = (197, 197, 197, 255)    # the right panel above the poster band

GREEN = {(124, 254, 132, 255), (52, 134, 36, 255), (127, 191, 91, 255), (51, 86, 32, 255),
         (4, 2, 4, 255)}
# The letters also carry pure black shading, a white specular, and the (173)
# highlight along the sign plate's lower edge. All three occur on the machine
# too, so they join the mask only by touching it, never on colour alone. A leak
# into the machine's own outline or right edge is harmless: the model repaints
# those as what they already were.
INK = {(4, 2, 4, 255), BLACK, (222, 222, 222, 255), (173, 173, 173, 255)}

# (rows the sign covers, mirror axis, first row below the face's bottom vertex,
#  ridge columns, right-panel columns that are not the flat fill)
BODY = dict(rows=range(8, 34), axis=49, vertex=26, ridges={9, 10, 15, 22, 23, 29, 34, 35},
            panel={24: RIDGE, 25: BASE, 26: (94, 94, 94, 255), 27: (179, 179, 179, 255),
                   46: (222, 222, 222, 255), 47: (94, 94, 94, 255), 48: BASE, 49: BLACK},
            post=24)
ICON = dict(rows=range(4, 18), axis=25, vertex=13, ridges={5, 11, 17},
            panel={12: RIDGE, 13: (94, 94, 94, 255), 24: BASE, 25: BLACK}, post=12)


def repaint(sprite, spec):
    """Return a copy of `sprite` with the sign painted out."""
    width, height = sprite.size
    px = sprite.load()
    rows, axis = spec['rows'], spec['axis']

    mask = {(x, y) for y in rows for x in range(width) if px[x, y] in GREEN}
    while True:
        grew = {(x, y) for (mx, my) in mask
                for x, y in ((mx + 1, my), (mx - 1, my), (mx, my + 1), (mx, my - 1))
                if 0 <= x < width and y in rows and (x, y) not in mask and px[x, y] in INK}
        if not grew:
            break
        mask |= grew

    def face_limit(y):
        """The face's rightmost column: its left boundary, mirrored.

        Below the left panel's top that boundary is where the panel ends;
        above it, where the sprite starts being drawn at all.
        """
        x = 1
        if px[1, y] == LEFT:
            while x < width and px[x, y] == LEFT:
                x += 1
        else:
            x = 0
            while x < width and px[x, y][3] == 0:
                x += 1
        return axis - x

    out = sprite.copy()
    op = out.load()
    for (x, y) in sorted(mask):
        mx, limit = axis - x, face_limit(y)
        if mx < 0 or px[mx, y][3] == 0:
            op[x, y] = CLEAR                    # the sign overhangs the machine here
        elif y >= spec['vertex'] or x > limit:
            op[x, y] = spec['panel'].get(x, LEFT if x < spec['post'] else PANEL_FILL)
        elif x > limit - 4 and (mx, y) not in mask:
            op[x, y] = px[mx, y]                # outline and edge bevel, mirrored
        else:
            op[x, y] = RIDGE if x in spec['ridges'] else BASE
    return out, len(mask)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else \
        'nitro/overrides/bundled/furniture/%s.nitro' % CLASS
    entries = fb.bundle_entries(path)
    data = json.loads(fb.inflate(entries['%s.json' % CLASS]))
    sheet = Image.open(io.BytesIO(fb.inflate(entries['%s.png' % CLASS]))).convert('RGBA')
    frames = data['spritesheet']['frames']

    vis = next(v for v in data['visualizations'] if v['size'] == 64)
    if GLOW_LAYER not in (vis.get('layers') or {}):
        print('%s: glow layer already gone - nothing to do' % path)
        return

    # 1. the sign, out of the body sprite and out of the icon
    for key, spec in ((CLASS + '_' + CLASS + '_64_b_2_0', BODY),
                      (CLASS + '_' + CLASS + '_icon_a', ICON)):
        rect = frames[key]['frame']
        box = (rect['x'], rect['y'], rect['x'] + rect['w'], rect['y'] + rect['h'])
        cleaned, painted = repaint(sheet.crop(box), spec)
        sheet.paste(cleaned, box[:2])
        print('%s: repainted %d pixels' % (key.rsplit('_', 3)[-1] or key, painted))

    # 2. the glow layer, out of the visualization, the assets and the sheet
    vis['layerCount'] -= 1
    vis['layers'].pop(GLOW_LAYER)
    for animation in vis.get('animations', {}).values():
        (animation.get('layers') or {}).pop(GLOW_LAYER, None)
    for name in [n for n in data['assets'] if '_c_' in n]:
        data['assets'].pop(name)
    for name in [n for n in frames if '_c_' in n]:
        frames.pop(name)

    entries['%s.json' % CLASS] = zlib.compress(json.dumps(data).encode('utf-8'), 9)
    buf = io.BytesIO()
    sheet.save(buf, 'PNG')
    entries['%s.png' % CLASS] = zlib.compress(buf.getvalue(), 9)
    fb.write_bundle(path, entries)
    print('%s: layerCount now %d, layers %s' % (path, vis['layerCount'], sorted(vis['layers'])))


if __name__ == '__main__':
    main()
