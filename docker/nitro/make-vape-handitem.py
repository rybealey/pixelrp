#!/usr/bin/env python3
"""make-vape-handitem.py - put the vape in the avatar's hand.

The vape (emulator RpVape, Twist 2026-10-20) is held whenever it is in the
backpack and raised to the mouth for a hit. Its hand item is 1129 - over 999,
so the client never raises it on its own every ten seconds the way it does a
drink (AvatarLogic: only ids up to MAX_HAND_USE_ID are "used"); the hit raises
it on purpose. 1129 draws part 405 of hh_human_item, both carried (crr) and
raised (drk).

The art follows the Ice Lolly (part 231) - a bar held upright in the fist and
raised with one end at the lips - so it sits where a hand item should in every
direction. From each lolly picture only its line is taken: from the body pixel
nearest the stick (the fist) to the one farthest from it (the lips). Along that
line a slim pen is drawn as BC2 from the Vape Icon canvas: orange body, a cream
band, a silver ring and a black mouthpiece at the far end, lit from the top
left, with a black outline. Seen end-on (raised, facing the viewer) only its
orange base shows. The lolly's own fat, foreshortened shape is not kept.

Adds or replaces part 405 in nitro/overrides/bundled/figure/hh_human_item.nitro
(appended as a strip under the sheet; every other picture is untouched), and
the three gamedata-merge fragments that make 1129 mean it: FigureMap (ri 405),
HabboAvatarActions (CarryItem and UseItem 1129 -> 405) and ExternalTexts
(handitem1129 "Vape"). The beta deploy renews the figure bundles' ?v=, so
nobody keeps a cached library without it.

Usage:
  python3 docker/nitro/make-vape-handitem.py
"""
import io, json, math, pathlib, re, struct, sys, zlib

from PIL import Image

REPO = pathlib.Path(__file__).resolve().parents[2]
BUNDLE = REPO / 'nitro' / 'overrides' / 'bundled' / 'figure' / 'hh_human_item.nitro'
MERGE = REPO / 'nitro' / 'overrides' / 'gamedata-merge'

HAND_ITEM = 1129
PART = 405
SOURCE_PART = 231          # the Ice Lolly
NAME = 'Vape'

def hx(s):
    return (int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16), 255)

# The lolly's four pinks and its stick: where its body and its stick are.
PINKS = [(0xf4, 0x77, 0xae), (0xe2, 0x4e, 0x8f), (0xcd, 0x3b, 0x7b), (0xac, 0x28, 0x62)]
STICK = [(0xcf, 0x9b, 0x59), (0x88, 0x5a, 0x1e)]
OUTLINE = (0, 0, 0)

# Each zone in four shades across the pen: lit edge, light, face, shadow.
ORANGE = [hx('#ffc679'), hx('#fdab4f'), hx('#f59436'), hx('#cf5a24')]
BLACK = [hx('#6a6a6a'), hx('#4a4a4a'), hx('#333333'), hx('#1f1f1f')]
SILVER = [hx('#ffffff'), hx('#e4e4e4'), hx('#b8b8b8'), hx('#8c8c8c')]
CREAM = [hx('#fff8e6'), hx('#fff1c9'), hx('#ffe2a6'), hx('#e0a868')]

RADIUS = 1.45              # half the pen's width inside its outline: 3 px across
TIP_RADIUS = 1.25          # the mouthpiece a little narrower, blunt at the end
# Raised, the lolly's top end sits higher than a mouth: at its line the pen
# touched the nose (Twist, 2026-10-20). Lowered this many pixels it is on the lips.
RAISED_DROP = 2
# Held, the lolly's body sits on top of the fist with only its stick inside, so
# the pen stood on the hand - and the bit of fist under it looked like a thin,
# pinching hand (Twist, 2026-10-20). Lowered this many pixels it runs through
# the fist the way Habbo's own pencil (part 230) and paintbrush (142) do: the
# fist behind its lower half, a little of it showing below.
HELD_DROP = 7

# Zones along the vape, 0 at the hand and 1 at the mouthpiece.
def zone(u):
    if u > 0.76:
        return BLACK                # mouthpiece
    if u > 0.64:
        return SILVER               # ring
    if 0.22 < u <= 0.36:
        return CREAM                # band
    return ORANGE

def axis(img):
    """The lolly's line from fist to lips: the body pixel nearest its stick, and the one farthest away."""
    px = img.load()
    w, h = img.size
    body = [(x, y) for y in range(h) for x in range(w) if px[x, y][3] and px[x, y][:3] in PINKS]
    stick = [(x, y) for y in range(h) for x in range(w) if px[x, y][3] and px[x, y][:3] in STICK]
    if not body or not stick:
        return None
    sx = sum(x for x, _ in stick) / len(stick)
    sy = sum(y for _, y in stick) / len(stick)
    near = min(body, key=lambda p: (p[0] - sx) ** 2 + (p[1] - sy) ** 2)
    far = max(body, key=lambda p: (p[0] - sx) ** 2 + (p[1] - sy) ** 2)
    return (near[0] + 0.5, near[1] + 0.5), (far[0] + 0.5, far[1] + 0.5)

def upright(img):
    """Held: straight up the middle of the lolly's body, bottom (the fist) to top - the lolly
    leans a little with its stick, and a pen leaning that way looked wonky (Twist, 2026-10-20)."""
    px = img.load()
    body = [(x, y) for y in range(img.height) for x in range(img.width) if px[x, y][3] and px[x, y][:3] in PINKS]
    if not body:
        return None
    cx = math.floor((min(x for x, _ in body) + max(x for x, _ in body) + 1) / 2) + 0.5
    return (cx, max(y for _, y in body) + 0.5), (cx, min(y for _, y in body) + 0.5)

# Directions a 3 px pen draws as an even pixel stair: flat, 2:1, 1:1, 1:2 and
# upright, either way. A line between them steps unevenly and looks bent.
CLEAN_ANGLES = [math.atan2(sy * a, sx * b) for a, b in ((0, 1), (1, 2), (1, 1), (2, 1), (1, 0)) for sx in (1, -1) for sy in (1, -1)]

def snapped(line):
    """Raised: the lolly's line turned to the nearest clean angle about its mouth end, which stays on the lips."""
    (ax, ay), (bx, by) = line
    bx, by = math.floor(bx) + 0.5, math.floor(by) + 0.5
    angle = math.atan2(by - ay, bx - ax)
    best = min(CLEAN_ANGLES, key=lambda c: abs(math.atan2(math.sin(angle - c), math.cos(angle - c))))
    length = math.hypot(bx - ax, by - ay)
    return (bx - length * math.cos(best), by - length * math.sin(best)), (bx, by)

def pen(img, held):
    """The vape as a slim pen, on a canvas padded by 3 px a side: upright when held, along the
    lolly's line (squared to a clean angle) when raised. Seen end-on (raised, facing the viewer)
    only its orange base shows, at the lips."""
    line = upright(img) if held else axis(img)
    if not line:
        return img.copy(), 0
    if not held and math.dist(*line) >= 4:
        line = snapped(line)
    pad = 3
    w, h = img.width + 2 * pad, img.height + 2 * pad
    (ax, ay), (bx, by) = line
    ax, ay, bx, by = ax + pad, ay + pad, bx + pad, by + pad
    dx, dy = bx - ax, by - ay
    length = (dx * dx + dy * dy) ** 0.5
    inside = {}
    if length < 4:
        cx, cy = (ax + bx) / 2, (ay + by) / 2
        for y in range(h):
            for x in range(w):
                nx, ny = x + 0.5 - cx, y + 0.5 - cy
                if abs(nx) + abs(ny) <= 2.6 and abs(nx) <= 2.0 and abs(ny) <= 2.0:
                    light = -nx - ny
                    inside[(x, y)] = ORANGE[0 if light > 1.5 else 1 if light > 0 else 2 if light > -1.5 else 3]
    else:
        ux, uy = dx / length, dy / length
        px_, py_ = -uy, ux
        if px_ + py_ > 0:              # the side facing the light (up and left)
            px_, py_ = -px_, -py_
        # pull the ends in so the rounded caps finish where the lolly did
        ax, ay = ax + ux * 0.8, ay + uy * 0.8
        bx, by = bx - ux * 0.8, by - uy * 0.8
        span = length - 1.6
        for y in range(h):
            for x in range(w):
                cx, cy = x + 0.5 - ax, y + 0.5 - ay
                t = max(0.0, min(span, cx * ux + cy * uy))
                n = cx * px_ + cy * py_
                r = TIP_RADIUS if t / span > 0.82 else RADIUS
                if (cx * ux + cy * uy - t) ** 2 + n * n > r * r:
                    continue
                u = t / span
                side = n / r                  # +1 on the lit side, -1 in shadow
                shade = 0 if side > 0.55 else 1 if side > 0.0 else 2 if side > -0.6 else 3
                inside[(x, y)] = zone(u)[shade]
        # a lone pixel sticking out of an end reads as a bent tip: drop it
        for _ in range(2):
            lone = [p for p in inside if sum((p[0] + ex, p[1] + ey) in inside for ex, ey in ((1, 0), (-1, 0), (0, 1), (0, -1))) < 2]
            for p in lone:
                del inside[p]
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    o = out.load()
    for p, c in inside.items():
        o[p] = c
    for y in range(h):
        for x in range(w):
            if (x, y) not in inside and any((x + ex, y + ey) in inside for ex, ey in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                o[x, y] = OUTLINE + (255,)
    return out, pad

# ---- bundle ------------------------------------------------------------------
def read_bundle(path):
    f = io.BytesIO(path.read_bytes())
    count, = struct.unpack('>h', f.read(2))
    entries = []
    for _ in range(count):
        n, = struct.unpack('>h', f.read(2))
        name = f.read(n).decode()
        size, = struct.unpack('>i', f.read(4))
        entries.append((name, zlib.decompress(f.read(size))))
    return entries

def write_bundle(path, entries):
    out = struct.pack('>h', len(entries))
    for name, raw in entries:
        blob = zlib.compress(raw, 9)
        out += struct.pack('>h', len(name)) + name.encode() + struct.pack('>i', len(blob)) + blob
    path.write_bytes(out)

def build_library():
    entries = read_bundle(BUNDLE)
    jname = next(n for n, _ in entries if n.endswith('.json'))
    doc = json.loads(dict(entries)[jname])
    pname = doc['spritesheet']['meta']['image']
    sheet = Image.open(io.BytesIO(dict(entries)[pname])).convert('RGBA')
    lib, assets, frames = doc['name'], doc['assets'], doc['spritesheet']['frames']

    def picture(asset):
        a = assets[asset]
        fr = frames[f"{lib}_{a.get('source', asset)}"]['frame']
        img = sheet.crop((fr['x'], fr['y'], fr['x'] + fr['w'], fr['y'] + fr['h']))
        return img.transpose(Image.FLIP_LEFT_RIGHT) if a.get('flipH') else img

    mine = re.compile(rf'^h_(crr|drk)_ri_{PART}_\d_\d+$')
    old = []
    for key in [k for k in assets if mine.match(k)]:
        del assets[key]
        fr = frames.pop(f'{lib}_{key}', None)
        if fr:
            old.append(fr['frame'])
    # A rebuild: the last build's strip is the bottom of the sheet - cut it off
    # rather than leave it there under a new one.
    if old:
        strip_top = min(f['y'] for f in old)
        if all(f['frame']['y'] + f['frame']['h'] <= strip_top for f in frames.values()):
            sheet = sheet.crop((0, 0, sheet.width, strip_top))

    new = []
    for action in ('crr', 'drk'):
        for d in range(8):
            src = f'h_{action}_ri_{SOURCE_PART}_{d}_0'
            dst = f'h_{action}_ri_{PART}_{d}_0'
            a = dict(assets[src])
            if 'source' in a and not mine.match(a['source']) and f'_ri_{SOURCE_PART}_' not in a['source']:
                assets[dst] = a                    # a blank shared with other items (hand out of sight)
                continue
            a.pop('source', None)
            a.pop('flipH', None)
            img, pad = pen(picture(src), held=(action == 'crr'))
            bbox = img.getbbox()
            img = img.crop(bbox)
            # an asset draws its top-left at (-x, y above the feet): padding and cropping move it
            a['x'] -= bbox[0] - pad
            a['y'] -= bbox[1] - pad
            a['y'] -= RAISED_DROP if action == 'drk' else HELD_DROP
            new.append((dst, a, img))

    strip_w = sum(img.width for _, _, img in new)
    strip_h = max(img.height for _, _, img in new)
    grown = Image.new('RGBA', (max(sheet.width, strip_w), sheet.height + strip_h), (0, 0, 0, 0))
    grown.paste(sheet, (0, 0))
    x = 0
    for dst, a, img in new:
        grown.paste(img, (x, sheet.height))
        assets[dst] = a
        frames[f'{lib}_{dst}'] = {"frame": {"x": x, "y": sheet.height, "w": img.width, "h": img.height}, "rotated": False,
                                  "trimmed": False, "spriteSourceSize": {"x": 0, "y": 0, "w": img.width, "h": img.height},
                                  "sourceSize": {"w": img.width, "h": img.height}, "pivot": {"x": 0.5, "y": 0.5}}
        x += img.width
    doc['spritesheet']['meta']['size'] = {"w": grown.width, "h": grown.height}

    png = io.BytesIO()
    grown.save(png, 'PNG', optimize=True)
    out = []
    for name, raw in entries:
        if name == jname:
            raw = json.dumps(doc, separators=(',', ':')).encode()
        elif name == pname:
            raw = png.getvalue()
        out.append((name, raw))
    write_bundle(BUNDLE, out)
    return len(new)

# ---- gamedata-merge fragments ------------------------------------------------
def edit_fragment(name, change):
    path = MERGE / name
    raw = path.read_bytes()
    crlf = b'\r\n' in raw
    data = json.loads(raw.replace(b'\r\n', b'\n'))
    change(data)
    text = json.dumps(data, indent=1, ensure_ascii=True)
    path.write_bytes(text.replace('\n', '\r\n').encode() if crlf else text.encode())

def figuremap(data):
    lib = next(l for l in data['libraries'] if l['id'] == 'hh_human_item')
    if not any(str(p.get('id')) == str(PART) and p.get('type') == 'ri' for p in lib['parts']):
        lib['parts'].append({"id": PART, "type": "ri"})
        lib['parts'].sort(key=lambda p: int(p['id']))

def actions(data):
    for action in data['actions']:
        if action['id'] in ('CarryItem', 'UseItem'):
            params = [p for p in action['params'] if p['id'] != str(HAND_ITEM)]
            params.append({"id": str(HAND_ITEM), "value": str(PART)})
            action['params'] = params

def texts(data):
    data[f'handitem{HAND_ITEM}'] = NAME

def main():
    count = build_library()
    edit_fragment('FigureMap.json', figuremap)
    edit_fragment('HabboAvatarActions.json', actions)
    edit_fragment('ExternalTexts.json', texts)
    print(f"hh_human_item: part {PART} = {count} pictures drawn along part {SOURCE_PART}'s; "
          f"handitem {HAND_ITEM} '{NAME}' -> ri {PART} in FigureMap, HabboAvatarActions and ExternalTexts")

if __name__ == '__main__':
    sys.exit(main())
