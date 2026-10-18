#!/usr/bin/env python3
"""make-police-beacon.py - build the police beacon avatar effect and point an
EffectMap entry at it.

The blue beacon an on-duty officer wears on the way to a 911 call or a backup
request (emulator PoliceBeacon; design: the "Police siren duty badge" canvas,
2026-10-19). The art is drawn here rather than kept as a PNG, so a change is a
change to the numbers below and a rebuild:

  - the beacon: a 19x18 UK-style blue lens on a chrome collar and base, a bright
    band sweeping round the lens over 6 frames (sides held two steps, the front
    one - about 0.74 s a turn at the avatar's ~82 ms animation step);
  - the glow: a blue halo behind it, drawn additively (ink 33, like the bot
    badge's ring), always on and brightest while the light faces the viewer.

Placed like the staff (102) and bot (187) badges: the artwork's bottom 82 px
above the feet, centred on the avatar. Pure Python (no Pillow on the dev Mac).

Use a NEW library name for every rebuild (PoliceBeacon2, ...): bundles are
cached for a week and their URL carries no version; EffectMap.json is no-store.

Usage:
  python3 docker/nitro/make-police-beacon.py --lib PoliceBeacon1
"""
import argparse, json, math, pathlib, struct, sys, zlib

REPO = pathlib.Path(__file__).resolve().parents[2]
EFFECT_ID = 639

# ---- the beacon --------------------------------------------------------------
# Drawn on the staff badge's 40x32 canvas (centre column 19), then cropped.
W, H = 40, 32
CX, BY, RX, RY = 19.5, 24, 6, 11          # lens: superellipse on row BY
CAP = (17, 12, 21, 12)
COLLAR = (11, 24, 27, 25)
BASE = (13, 27, 25, 28)
PHASES = [-0.9, -0.45, 0.0, 0.45, 0.9, 1.6]   # where the bright band is (-1 left .. 1 right, 1.6 = facing away)
REPEATS = [2, 1, 1, 1, 2, 2]                  # avatar animation steps per frame

PALETTE = {
    'k': (0, 0, 0), 'W': (255, 255, 255),
    'c': (0xe1, 0xe7, 0xec), 'g': (0xa7, 0xb2, 0xbb), 'G': (0x6b, 0x75, 0x7e), 'h': (0x3a, 0x41, 0x48),
    '2': (0xef, 0xfa, 0xff), 'B': (0x8f, 0xd8, 0xff), 'b': (0x2b, 0x97, 0xf5), 'n': (0x1a, 0x5d, 0xc8), 'N': (0x0c, 0x2f, 0x73),
}

def put(g, x, y, ch):
    if 0 <= x < W and 0 <= y < H:
        g[y][x] = ch

def box(g, x0, y0, x1, y1, rows):
    """Rows y0..y1 between x0..x1, each row (first, middle, last) characters."""
    mask = set()
    for y in range(y0, y1 + 1):
        a, m, z = rows[y - y0]
        for x in range(x0, x1 + 1):
            put(g, x, y, a if x == x0 else z if x == x1 else m)
            mask.add((x, y))
    return mask

def outline(g, mask):
    for y in range(H):
        for x in range(W):
            if (x, y) not in mask and any((x + dx, y + dy) in mask for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                put(g, x, y, 'k')

def beacon(phase):
    g = [['.'] * W for _ in range(H)]
    lens = set()
    for y in range(H):
        for x in range(W):
            nx, ny = (x + 0.5 - CX) / RX, (y + 0.5 - BY) / RY
            if y + 0.5 <= BY and abs(nx) ** 2.6 + abs(ny) ** 2.6 <= 1.0:
                lens.add((x, y))
    for (x, y) in lens:
        nx, ny = (x + 0.5 - CX) / RX, (y + 0.5 - BY) / RY
        d = abs(nx - phase)
        lv = 0 if d < 0.14 else 1 if d < 0.38 else 2 if d < 0.62 else 3 if d < 0.95 else 4
        if ny < -0.82 and lv > 1:
            lv -= 1                                    # the top catches light
        if (x - 11) % 4 == 0 and lv in (1, 2, 3) and y > BY - RY * 0.85:
            lv += 1                                    # lens ribs
        put(g, x, y, '2BbnN'[lv])
    box(g, *CAP, [('W', 'c', 'g')])
    collar = box(g, *COLLAR, [('W', 'c', 'g'), ('c', 'g', 'G')])
    base = box(g, *BASE, [('g', 'G', 'h'), ('G', 'h', 'h')])
    outline(g, lens | collar)
    outline(g, base)
    return g

# ---- the glow ----------------------------------------------------------------
GLOW_W, GLOW_H = 37, 31
GLOW_CX, GLOW_CY = 18.5, 15.5                 # the lens centre, in the glow image
GLOW_COLOUR = (60, 165, 255)
GLOW_RINGS = ((17, 0.26), (14, 0.30), (11, 0.36), (8, 0.46), (6, 0.30))   # radius, added strength
LENS_Y = 18.5                                 # lens centre row on the 40x32 canvas

def glow_strength(phase):
    return 0.7 + 0.3 * max(0.0, 1.0 - abs(phase))

def glow(strength):
    """Additive layer: the colour scaled by alpha is what gets added (ink 33)."""
    rows = []
    for y in range(GLOW_H):
        row = bytearray()
        for x in range(GLOW_W):
            dd = math.hypot(x + 0.5 - GLOW_CX, (y + 0.5 - GLOW_CY) * 1.15)
            a = sum(s for r, s in GLOW_RINGS if dd <= r) * strength
            add = [min(255, int(c * a)) for c in GLOW_COLOUR]
            alpha = max(add)
            row += bytes([round(c * 255 / alpha) for c in add] + [alpha]) if alpha else b'\0\0\0\0'
        rows.append(bytes(row))
    return rows

# ---- png / bundle ------------------------------------------------------------
def png(w, h, rows):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    raw = b''.join(b'\0' + r for r in rows)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))

def to_rows(grid, box_):
    x0, y0, x1, y1 = box_
    rows = []
    for y in range(y0, y1):
        row = bytearray()
        for x in range(x0, x1):
            ch = grid[y][x]
            row += bytes(PALETTE[ch] + (255,)) if ch != '.' else b'\0\0\0\0'
        rows.append(bytes(row))
    return rows

def build(lib):
    grids = [beacon(p) for p in PHASES]
    pts = [(x, y) for g in grids for y in range(H) for x in range(W) if g[y][x] != '.']
    art = (min(x for x, _ in pts), min(y for _, y in pts), max(x for x, _ in pts) + 1, max(y for _, y in pts) + 1)
    aw, ah = art[2] - art[0], art[3] - art[1]
    # Effect coordinates: an image draws at (-x, -y) from the avatar's origin,
    # whose midline is x 32; y counts up from the feet. The 40x32 canvas sits
    # where the staff badge's does (x 12), its art bottom 82 above the feet.
    beacon_xy = (-(12 + art[0]), 82 + ah)
    lens_x, lens_up = 12 + CX, 82 + (art[3] - LENS_Y)
    glow_xy = (-round(lens_x - GLOW_CX), round(lens_up + GLOW_CY))

    glow_id, beacon_id = f"fx{EFFECT_ID}_1", f"fx{EFFECT_ID}_2"
    glow_member, beacon_member = f"std_{glow_id}_1", f"std_{beacon_id}_1"
    sheet_rows, sheet_w, top = [], max(GLOW_W, aw), 0
    assets, frames = {}, {}

    def add(asset, rows, w, h, xy):
        nonlocal top
        assets[asset] = {"x": xy[0], "y": xy[1]}
        frames[f"{lib}_{asset}"] = {"frame": {"x": 0, "y": top, "w": w, "h": h}, "rotated": False, "trimmed": False,
                                    "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h}, "sourceSize": {"w": w, "h": h},
                                    "pivot": {"x": 0.5, "y": 0.5}}
        sheet_rows.extend(r + b'\0' * 4 * (sheet_w - w) for r in rows)
        top += h

    for i, p in enumerate(PHASES):
        add(f"h_{glow_member}_0_{i}", glow(glow_strength(p)), GLOW_W, GLOW_H, glow_xy)
    for i, g in enumerate(grids):
        add(f"h_{beacon_member}_0_{i}", to_rows(g, art), aw, ah, beacon_xy)

    def sprite(sid, member, ink, dz):
        # staticY 0: it drops with a sitting or lying wearer, as the badges do
        return {"id": sid, "member": member, "ink": ink, "staticY": 0, "directionList": [{"id": d, "dz": dz} for d in range(8)]}

    doc = {
        "assets": assets,
        "animations": {lib: {
            "name": f"fx.{EFFECT_ID}", "desc": lib,
            # ink 33 = additive: the glow brightens what is behind it; the
            # beacon draws normally (0) on top (dz 1)
            "sprites": [sprite(glow_id, glow_member, 33, 0), sprite(beacon_id, beacon_member, 0, 1)],
            "frames": [{"repeats": REPEATS[i], "fxs": [{"id": glow_id, "frame": i, "action": "Default"},
                                                       {"id": beacon_id, "frame": i, "action": "Default"}]}
                       for i in range(len(PHASES))]}},
        "name": lib,
        "spritesheet": {"frames": frames, "meta": {"image": f"{lib}.png", "format": "RGBA8888", "size": {"w": sheet_w, "h": top}, "scale": 1}},
    }
    entries = [(f"{lib}.json", json.dumps(doc, separators=(',', ':')).encode()), (f"{lib}.png", png(sheet_w, top, sheet_rows))]
    out = struct.pack('>h', len(entries))
    for name, raw in entries:
        blob = zlib.compress(raw, 9)
        out += struct.pack('>h', len(name)) + name.encode() + struct.pack('>i', len(blob)) + blob
    return out, (aw, ah), beacon_xy, glow_xy

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--lib', required=True, help='new effect library name, e.g. PoliceBeacon1')
    p.add_argument('--out', type=pathlib.Path, default=REPO / 'nitro' / 'overrides',
                   help='overrides root (gets bundled/effect/<lib>.nitro; its gamedata/EffectMap.json is updated)')
    args = p.parse_args()

    bundle, size, beacon_xy, glow_xy = build(args.lib)
    effect_dir = args.out / 'bundled' / 'effect'
    effect_dir.mkdir(parents=True, exist_ok=True)
    (effect_dir / f"{args.lib}.nitro").write_bytes(bundle)

    map_path = args.out / 'gamedata' / 'EffectMap.json'
    effectmap = json.loads(map_path.read_text())
    effects = effectmap['effects'] if isinstance(effectmap, dict) else effectmap
    hit = [e for e in effects if str(e.get('id')) == str(EFFECT_ID)]
    if hit:
        hit[0]['lib'] = args.lib
        hit[0]['revision'] = int(hit[0].get('revision', 0)) + 1
    else:
        effects.append({"id": str(EFFECT_ID), "lib": args.lib, "type": "fx", "revision": 1})
    map_path.write_text(json.dumps(effectmap, separators=(',', ':')))
    print(f"wrote {effect_dir / (args.lib + '.nitro')} ({len(bundle)} bytes; beacon {size[0]}x{size[1]} at {beacon_xy}, "
          f"glow {GLOW_W}x{GLOW_H} at {glow_xy}) and {map_path} (id {EFFECT_ID} -> {args.lib})")

if __name__ == '__main__':
    sys.exit(main())
