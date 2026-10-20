#!/usr/bin/env python3
"""make-white-brick-cube.py - build the White Brick Cube furni bundle and icon.

A 1x1, one-high cube in the brick of Bsstonino's White Brick Block
(bsstonino_furni706, 2x1), made to stack and to sit side by side with no seam
in any direction (design: the "White Brick Cube" canvas, 2026-10-20). Two
states, as the 2x1: 0 white, 1 grey, switched by clicking.

How the joins disappear:

  - Every pixel is painted from WORLD coordinates (tile centres on integers, a
    tile spans -0.5..0.5, one height unit is T px). Two cubes that touch paint
    the same spot the same way, so brick rows and the stagger run straight
    across the join. Exactly 1.0 high, 2 courses per cube (an even count, so
    the stagger carries on), no bevel or highlight on any edge.
  - The black outline is its own layer, z -1010: drawn 0.714 behind, past the
    0.707 between neighbouring tiles, so a touching cube paints over it and
    only the outline round the whole build is left.
  - The 2 outline pixels above the top corner land on the DIAGONAL cube behind
    (1.414 away), so they are a third layer, z -2100 (1.484). Habbo's builder
    block (bc_block_redbrick) does the same.

Both rotations are the same picture, never mirrored: a mirror would swap the
light and dark sides and a turned cube would show in a wall. The light side is
the left, as the 2x1 turned to run down-right (how it stood on the cubes in the
first test), and the bricks are its bricks: two a tile, half a brick on each
row, the light line on the right of each joint.

Pure Python (no Pillow on the dev Mac).

Usage:
  python3 docker/nitro/make-white-brick-cube.py          # writes the bundle + icon
  python3 docker/nitro/make-white-brick-cube.py --test   # blocks of cubes == one big box
"""
import argparse, json, math, pathlib, struct, sys, zlib

REPO = pathlib.Path(__file__).resolve().parents[2]
NAME = 'white_brick_cube'
SIZE = 64            # T = SIZE // 2 px per tile edge and per height unit
ICON_T = 16          # the shop icon is the same cube drawn at T 16 (34x34; at 12 the bricks blur)

# Greys from bsstonino_furni706 as it stands turned (its long side running
# down-right): top, its highlight and mortar; left side (light); right side
# (dark). State 0 white, state 1 grey.
PALETTE = {
    0: dict(top=233, top_hi=246, top_mo=177, L=219, L_hi=244, L_mo=180, R=190, R_hi=219, R_mo=161),
    1: dict(top=181, top_hi=224, top_mo=71, L=158, L_hi=219, L_mo=73, R=121, R_hi=158, R_mo=58),
}
OUTLINE = (0, 0, 0, 255)
LAYERS = [('outline', -1010), ('fill', None), ('tip', -2100)]   # layer id = index = a, b, c


# ---- the brick ---------------------------------------------------------------
def grey(v):
    return (v, v, v, 255)


def colour(face, wx, wy, wz, state, T):
    """A face pixel's colour, from where it is in the room - never from the cube."""
    p = PALETTE[state]
    brick = T // 2                               # brick length along a side, and row height
    if face == 'top':
        # the 2x1's top: narrow strips of short bricks running along x, each
        # strip half a brick on from the next, a light line past each joint.
        # A and B step 1 per screen column, 2T a tile.
        A = math.floor((wx + 0.5) * 2 * T)
        B = math.floor((wy + 0.5) * 2 * T)
        strip = T // 2                           # 4 strips a tile
        if B % strip in (0, 1):
            return grey(p['top_mo'])
        # joints line up with the left side's top row where the two meet
        at = (A - T // 4 - (T // 2) * ((B // strip) % 2)) % T
        if at in (0, 1):
            return grey(p['top_mo'])
        return grey(p['top_hi'] if at in (2, 3) else p['top'])
    h = math.floor(wz * T)                       # height in px, 0 at the bottom
    row = (h // brick) % 2                       # 2 rows a cube - an even count, so the stagger carries on
    if face == 'L':                              # faces +y, runs along x
        col = math.floor((wx + 0.5) * T) % T
    else:                                        # faces +x, runs along y; col grows with screen x
        col = (T - 1 - math.floor((wy + 0.5) * T)) % T
    # joints every brick, half a brick on each row; the same on both sides, so
    # at the front corner each row's brick wraps round from one side to the other
    at = (col - T // 8 - (T // 4) * row) % brick
    if h % brick == 0 or at == 0:
        return grey(p[face + '_mo'])
    if at == 1 or (at == 2 and h % brick == 1):  # the 2x1's light line right of a joint, a step wider at its foot
        return grey(p[face + '_hi'])
    return grey(p[face])


def hit(sx, sy, box, T):
    """The visible face of box (x0, x1, y0, y1, z0, z1) under screen point sx, sy."""
    x0, x1, y0, y1, z0, z1 = box
    d, s = sx / T, (sy + z1 * T) / (T / 2)
    wx, wy = (s + d) / 2, (s - d) / 2
    if x0 < wx < x1 and y0 < wy < y1:
        return 'top', wx, wy, z1
    wx = sx / T + y1
    wz = ((wx + y1) * (T / 2) - sy) / T
    if x0 < wx < x1 and z0 < wz < z1:
        return 'L', wx, y1, wz
    wy = x1 - sx / T
    wz = ((x1 + wy) * (T / 2) - sy) / T
    if y0 < wy < y1 and z0 < wz < z1:
        return 'R', x1, wy, wz
    return None


def draw_box(box, state, T):
    """{(x, y): rgba} of a box's faces, sampled at pixel centres, and its outline ring."""
    x0, x1, y0, y1, z0, z1 = box
    fill = {}
    for py in range(math.floor((x0 + y0) * T / 2 - z1 * T) - 2, math.ceil((x1 + y1) * T / 2 - z0 * T) + 2):
        for px in range(math.floor((x0 - y1) * T) - 2, math.ceil((x1 - y0) * T) + 2):
            face = hit(px + 0.5, py + 0.5, box, T)
            if face:
                fill[(px, py)] = colour(face[0], face[1], face[2], face[3], state, T)
    ring = {}
    for (px, py) in fill:
        for q in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
            if q not in fill:
                ring[q] = OUTLINE
    return fill, ring


def cube_layers(state, T):
    """The three layers of one cube on tile (0, 0, 0), relative to the tile centre."""
    fill, ring = draw_box((-0.5, 0.5, -0.5, 0.5, 0, 1), state, T)
    top = min(y for _, y in fill)
    tip = {k: v for k, v in ring.items() if k[1] == top - 1}
    return {'outline': {k: v for k, v in ring.items() if k not in tip}, 'fill': fill, 'tip': tip}


# ---- png / bundle ------------------------------------------------------------
def png(w, h, rows):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    raw = b''.join(b'\0' + r for r in rows)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def crop(px):
    """Pixels -> (rows, w, h, asset x, asset y): the image draws at (-x, -y) from the tile centre."""
    x0, y0 = min(x for x, _ in px), min(y for _, y in px)
    w, h = max(x for x, _ in px) - x0 + 1, max(y for _, y in px) - y0 + 1
    rows = [b''.join(bytes(px.get((x0 + i, y0 + j), (0, 0, 0, 0))) for i in range(w)) for j in range(h)]
    return rows, w, h, -x0, -y0


def build():
    T = SIZE // 2
    layers = {st: cube_layers(st, T) for st in (0, 1)}
    images = {                      # asset -> pixels; a and c are the same in both states
        f'{NAME}_{SIZE}_a_2_0': layers[0]['outline'],
        f'{NAME}_{SIZE}_b_2_0': layers[0]['fill'],
        f'{NAME}_{SIZE}_b_2_1': layers[1]['fill'],
        f'{NAME}_{SIZE}_c_2_0': layers[0]['tip'],
    }
    small = cube_layers(0, ICON_T)
    icon = {**small['outline'], **small['tip'], **small['fill']}

    assets, frames, sheet, top = {}, {}, [], 0
    crops = {k: crop(v) for k, v in images.items()}
    icon_rows, icon_w, icon_h, _, _ = crop(icon)
    sheet_w = max([c[1] for c in crops.values()] + [icon_w])

    def add(asset, rows, w, h):
        nonlocal top
        frames[f'{NAME}_{asset}'] = {"frame": {"x": 0, "y": top, "w": w, "h": h}, "rotated": False, "trimmed": False,
                                      "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h}, "sourceSize": {"w": w, "h": h},
                                      "pivot": {"x": 0.5, "y": 0.5}}
        sheet.extend(r + b'\0' * 4 * (sheet_w - w) for r in rows)
        top += h

    for asset, (rows, w, h, x, y) in crops.items():
        add(asset, rows, w, h)
    add(f'{NAME}_icon_a', icon_rows, icon_w, icon_h)

    # every layer x direction x state; the ones not drawn above point at one that is.
    # Direction 4 is direction 2 as it is - no flipH, so the light side stays right.
    for code in 'abc':
        for d in (2, 4):
            for st in (0, 1):
                asset = f'{NAME}_{SIZE}_{code}_{d}_{st}'
                own = f'{NAME}_{SIZE}_{code}_2_{st if code == "b" else 0}'
                x, y = crops[own][3], crops[own][4]
                assets[asset] = {"x": x, "y": y} if asset == own else {"source": own, "x": x, "y": y}
    assets[f'{NAME}_icon_a'] = {"x": 0, "y": 0}

    def state(i):
        return {"layers": {str(n): {"frameSequences": {"0": {"frames": {"0": {"id": i}}}}} for n in range(len(LAYERS))}}

    doc = {
        "type": "furniture", "name": NAME,
        "logicType": "furniture_multistate", "visualizationType": "furniture_animated",
        "assets": assets,
        "logic": {"model": {"dimensions": {"x": 1, "y": 1, "z": 1}, "directions": [90, 180]}},
        "visualizations": [
            {"angle": 45, "layerCount": len(LAYERS), "size": SIZE,
             "layers": {str(n): ({"z": z} if z is not None else {}) for n, (_, z) in enumerate(LAYERS)},
             "directions": {"2": {}, "4": {}},
             "animations": {"0": state(0), "1": state(1)}},
            {"angle": 360, "layerCount": 1, "size": 1},
        ],
        "spritesheet": {"frames": frames, "meta": {"image": f"{NAME}.png", "format": "RGBA8888",
                                                   "size": {"w": sheet_w, "h": top}, "scale": 1}},
    }
    entries = [(f"{NAME}.json", json.dumps(doc, separators=(',', ':')).encode()), (f"{NAME}.png", png(sheet_w, top, sheet))]
    out = struct.pack('>H', len(entries))
    for name, raw in entries:
        blob = zlib.compress(raw, 9)
        out += struct.pack('>H', len(name)) + name.encode() + struct.pack('>I', len(blob)) + blob
    return out, png(icon_w, icon_h, icon_rows), (icon_w, icon_h)


# ---- the seam test -----------------------------------------------------------
# Nitro's order (RoomSpriteCanvas): depth = -0.70708(x + y) - 0.007125z, plus
# per layer (z / -1000 - layerId * 0.001) * sqrt(.5); the larger draws first.
DEPTH_XY = math.cos(math.radians(-135)) * math.cos(math.radians(0.5))
DEPTH_Z = -math.sin(math.radians(0.5)) * (math.sqrt(0.5) / math.sqrt(0.75))


def scene(cubes, T):
    sprites = {st: cube_layers(st, T) for st in (0, 1)}
    items = []
    for (tx, ty, tz, st) in cubes:
        for lid, (name, z) in enumerate(LAYERS):
            rel = (((z or 0) / -1000) - lid * 0.001) * math.sqrt(0.5)
            items.append((DEPTH_XY * (tx + ty) + DEPTH_Z * tz + rel, (tx - ty) * T, (tx + ty) * (T // 2) - tz * T, sprites[st][name]))
    out = {}
    for _, ox, oy, px in sorted(items, key=lambda t: -t[0]):
        for (x, y), c in px.items():
            out[(x + ox, y + oy)] = c
    return out


def test():
    T, bad = SIZE // 2, 0
    for (nx, ny, nz) in [(3, 1, 1), (1, 3, 1), (2, 2, 1), (1, 1, 3), (3, 3, 3), (2, 3, 2)]:
        for st in (0, 1):
            got = scene([(x, y, z, st) for x in range(nx) for y in range(ny) for z in range(nz)], T)
            fill, ring = draw_box((-0.5, nx - 0.5, -0.5, ny - 0.5, 0, nz), st, T)
            want = dict(ring); want.update(fill)
            diff = sum(1 for k in set(got) | set(want) if got.get(k) != want.get(k))
            bad += diff
            print(f"{nx}x{ny}, {nz} high, state {st}: {diff} pixels differ from one big box")
    return 1 if bad else 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', type=pathlib.Path, default=REPO / 'nitro' / 'overrides',
                   help='overrides root (gets bundled/furniture/<name>.nitro and dcr/hof_furni/icons/<name>_icon.png)')
    p.add_argument('--test', action='store_true', help='check that blocks of cubes draw as one solid box, write nothing')
    args = p.parse_args()
    if args.test:
        return test()
    bundle, icon, icon_size = build()
    furni = args.out / 'bundled' / 'furniture' / f'{NAME}.nitro'
    icon_path = args.out / 'dcr' / 'hof_furni' / 'icons' / f'{NAME}_icon.png'
    furni.write_bytes(bundle)
    icon_path.write_bytes(icon)
    print(f"wrote {furni} ({len(bundle)} bytes) and {icon_path} ({icon_size[0]}x{icon_size[1]})")


if __name__ == '__main__':
    sys.exit(main())
