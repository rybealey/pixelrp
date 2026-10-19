#!/usr/bin/env python3
"""make-vape-smoke.py - build the vape's smoke puff avatar effect and point an
EffectMap entry at it.

The puff a player breathes out after a hit from their vape (emulator RpVape,
Twist 2026-10-20). For the first second nothing is drawn - the vape is at the
mouth then (the client raises it when this effect goes on) - and then a small
cloud leaves the mouth, grows as it drifts the way the avatar faces and rises,
then thins out and is gone - about 2.2 s more. It plays ONCE: the animation
resets when the effect goes on (resetOnToggle) and ends on a long empty frame,
and the emulator takes the effect off before that runs out.

The art is drawn here rather than kept as PNGs, so a change is a change to the
numbers below and a rebuild. One set of frames per direction (directions 1, as
Giant Mouth, effect 80, does), each starting at that direction's mouth -
measured from hh_human_face's mouth pixels (h_std_fc_1_<dir>_0); the mirrored
directions 4-6 sit around x 33, as Giant Mouth's do. In front of the head
except facing away (7), where it rises from behind it.

Effect coordinates, as for the badges: x across the 64 px avatar (midline 32),
y up from the feet. Pure Python (no Pillow on the dev Mac).

Use a NEW library name for every rebuild (VapeSmoke2, ...): bundles are cached
for a week and their URL carries no version; EffectMap.json is no-store.

Usage:
  python3 docker/nitro/make-vape-smoke.py --lib VapeSmoke3
"""
import argparse, json, math, pathlib, struct, sys, zlib

REPO = pathlib.Path(__file__).resolve().parents[2]
EFFECT_ID = 640

# Mouth per direction (x, height above the feet) and which way the puff drifts
# (x per step forward, extra rise). 0-3 measured; 4-6 mirror 2-0 around x 33.
MOUTH = {0: (45, 54), 1: (46, 53), 2: (41, 49), 3: (32.5, 47), 4: (25, 49), 5: (20, 53), 6: (21, 54), 7: (33, 58)}
DRIFT = {0: (0.55, 1.2), 1: (1.0, 0.55), 2: (0.75, 0.6), 3: (0.95, 0.6), 4: (-0.75, 0.6), 5: (-1.0, 0.55), 6: (-0.55, 1.2), 7: (0.0, 1.5)}
BEHIND = {7}

# The puff over time: distance out, rise, size and opacity. Frame 0 is the
# first burst at the lips; from the middle on its lobes drift apart as it fades.
DIST = [0.5, 2.6, 5.4, 8.4, 11.2, 13.6, 15.8, 17.6, 19.2, 20.6]
RISE = [0.0, 1.0, 2.6, 4.8, 7.4, 10.2, 13.2, 16.2, 19.2, 22.2]
SIZE = [1.6, 3.6, 5.6, 7.4, 8.8, 9.9, 10.8, 11.4, 11.9, 12.2]   # big clouds, wider than the head at the end (Twist, 2026-10-20)
SPREAD = [1.0, 1.0, 1.0, 1.0, 1.05, 1.12, 1.22, 1.34, 1.48, 1.64]
ALPHA = [140, 155, 160, 158, 150, 138, 120, 98, 72, 45]   # see-through: the room shows through it (Twist)
LEAD_REPEATS = 12                         # nothing for ~1 s first: the vape is at the mouth (the client raises it)
REPEATS = [2, 2, 2, 3, 3, 3, 3, 3, 3, 3]   # avatar animation steps (~82 ms) per frame: ~2.2 s
TAIL_REPEATS = 60                         # then nothing, ~5 s - the emulator takes it off long before

# Light from the top left: white, two greys, and a darker rim low and right so
# it still reads on a pale floor.
SHADES = [(255, 255, 255), (236, 237, 243), (214, 215, 224), (191, 192, 204)]
RIM = (163, 165, 180)

# The cloud as overlapping lobes (dx, dy up, radius), in units of its size:
# a big middle, two shoulders, two smaller lobes on top and a billow out each side.
LOBES = [(0.0, 0.0, 1.0), (-0.85, -0.2, 0.72), (0.85, -0.15, 0.75), (-0.35, 0.62, 0.68), (0.42, 0.58, 0.64),
         (-1.4, 0.1, 0.5), (1.35, 0.3, 0.52)]

def puff(direction, frame):
    """One frame for one direction: (left, top-above-feet, rows) or None when empty."""
    mx, my = MOUTH[direction]
    fx, up = DRIFT[direction]
    sign = (fx > 0) - (fx < 0)
    cx = mx + fx * DIST[frame] + sign * 1.0
    cy = my + RISE[frame] * max(1.0, up / 0.6) ** 0.6
    r, s = SIZE[frame], SPREAD[frame]
    parts = [(cx + ox * r * s, cy + oy * r * s, rr * r) for ox, oy, rr in (LOBES if frame >= 2 else LOBES[:1])]
    x0, x1 = math.floor(cx - 3 * r) - 1, math.ceil(cx + 3 * r) + 1
    y0, y1 = math.floor(cy - 3 * r) - 1, math.ceil(cy + 3 * r) + 1
    inside = {}
    for ya in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            px, py = x + 0.5, ya - 0.5           # pixel centre; ya counts up, row ya spans ya-1..ya
            best = None
            for bx, by, br in parts:
                d = math.hypot(px - bx, py - by) / br
                if d <= 1.0 and (best is None or d < best[0]):
                    best = (d, (px - bx) / br, (py - by) / br)
            if best:
                inside[(x, ya)] = best
    if not inside:
        return None
    pix = {}
    for (x, ya), (d, nx, ny) in inside.items():
        light = -0.6 * nx + 0.8 * ny
        shade = 0 if light > 0.35 else 1 if light > -0.25 else 2 if light > -0.65 else 3
        if frame <= 1:
            shade = min(shade, 1)
        rim = frame >= 2 and ((x + 1, ya) not in inside or (x, ya - 1) not in inside) and light < 0
        pix[(x, ya)] = RIM if rim else SHADES[shade]
    left, right = min(x for x, _ in pix), max(x for x, _ in pix)
    top, bottom = max(y for _, y in pix), min(y for _, y in pix)
    a = ALPHA[frame]
    rows = []
    for ya in range(top, bottom - 1, -1):
        row = bytearray()
        for x in range(left, right + 1):
            c = pix.get((x, ya))
            row += bytes(c + (a,)) if c else b'\0\0\0\0'
        rows.append(bytes(row))
    return left, top, rows

# ---- png / bundle ------------------------------------------------------------
def png(w, h, rows):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    raw = b''.join(b'\0' + r for r in rows)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))

def build(lib):
    sid = f"fx{EFFECT_ID}_1"
    member = f"std_{sid}_1"
    images = []
    for direction in range(8):
        for frame in range(len(DIST)):
            got = puff(direction, frame)
            if got:
                images.append((f"h_{member}_{direction}_{frame}", *got))
    sheet_w = max(len(rows[0]) // 4 for *_, rows in images)
    sheet_rows, assets, frames, top = [], {}, {}, 0
    for asset, left, top_above, rows in images:
        w, h = len(rows[0]) // 4, len(rows)
        assets[asset] = {"x": -left, "y": top_above}
        frames[f"{lib}_{asset}"] = {"frame": {"x": 0, "y": top, "w": w, "h": h}, "rotated": False, "trimmed": False,
                                    "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h}, "sourceSize": {"w": w, "h": h},
                                    "pivot": {"x": 0.5, "y": 0.5}}
        sheet_rows.extend(r + b'\0' * 4 * (sheet_w - w) for r in rows)
        top += h

    doc = {
        "assets": assets,
        "animations": {lib: {
            "name": f"fx.{EFFECT_ID}", "desc": lib,
            # back to frame 0 whenever the effect goes on, so every hit starts at the lips
            "resetOnToggle": True,
            # staticY 0: it drops with a sitting wearer, as the mouth does
            "sprites": [{"id": sid, "member": member, "directions": 1, "ink": 0, "staticY": 0,
                         "directionList": [{"id": d, "dz": -1 if d in BEHIND else 1} for d in range(8)]}],
            # the first and last frames name a picture that does not exist: nothing
            # is drawn (a frame with no fx at all would draw picture 0)
            "frames": [{"repeats": LEAD_REPEATS, "fxs": [{"id": sid, "frame": 99, "action": "Default"}]}]
                      + [{"repeats": REPEATS[i], "fxs": [{"id": sid, "frame": i, "action": "Default"}]} for i in range(len(DIST))]
                      + [{"repeats": TAIL_REPEATS, "fxs": [{"id": sid, "frame": 99, "action": "Default"}]}]}},
        "name": lib,
        "spritesheet": {"frames": frames, "meta": {"image": f"{lib}.png", "format": "RGBA8888", "size": {"w": sheet_w, "h": top}, "scale": 1}},
    }
    entries = [(f"{lib}.json", json.dumps(doc, separators=(',', ':')).encode()), (f"{lib}.png", png(sheet_w, top, sheet_rows))]
    out = struct.pack('>h', len(entries))
    for name, raw in entries:
        blob = zlib.compress(raw, 9)
        out += struct.pack('>h', len(name)) + name.encode() + struct.pack('>i', len(blob)) + blob
    return out, len(images)

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--lib', required=True, help='new effect library name, e.g. VapeSmoke1')
    p.add_argument('--out', type=pathlib.Path, default=REPO / 'nitro' / 'overrides',
                   help='overrides root (gets bundled/effect/<lib>.nitro; its gamedata/EffectMap.json is updated)')
    args = p.parse_args()

    bundle, count = build(args.lib)
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
    print(f"wrote {effect_dir / (args.lib + '.nitro')} ({len(bundle)} bytes, {count} pictures) and {map_path} (id {EFFECT_ID} -> {args.lib})")

if __name__ == '__main__':
    sys.exit(main())
