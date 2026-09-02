#!/usr/bin/env python3
"""make-tile-cursor.py - rebuild tile_cursor.nitro with a different stroke
thickness for the floor hover diamond.

The hover square is the `tile_cursor` mandatory room library: a 512x64
spritesheet plus a JSON manifest inside a .nitro bundle. Only frame
`tile_cursor_tile_cursor_64_a_0_0.png` is drawn on a normal floor hover
(state 0 in TileCursorLogic); the yellow/red/green/blue frames beside it are
unused alternates and the small blue disc is the layer-1 height marker.

The diamond is a stepped isometric ring, one step = 2px across / 1px down:

    d(x, y) = |x - 32.5| / 2 + |y - 16|          outer edge at d <= 16.5

  * white band  = `steps` steps inward from the outer edge
  * drop shadow = that band translated down by exactly `steps` rows, which is
    what makes it abut the stroke seamlessly - translating by any other amount
    opens a transparent gap on the top edges. Thickness and offset therefore
    move together; they are not independent knobs.
  * blue rim    = the one step of visible shadow adjacent to the white

Regenerating at the shipped thickness (3) reproduces the original frame to
within 14 translucent shadow pixels at the left, right and bottom tips, where
the original rasterizer was irregular.

Only frame a_0_0 is touched - the manifest and every other frame are copied
through byte-for-byte. Entries are zlib-deflated, never gzip, because
nitro-renderer 1.6.6 parses them with pako.inflate (see
fix-bundle-compression.py).

Usage:
  python3 docker/nitro/make-tile-cursor.py tile_cursor.nitro --steps 2 -o out.nitro

Deploy by copying the result over
  <checkout>/nitro/assets/bundled/generic/tile_cursor.nitro
on the VPS. nitro/assets/ is gitignored and no workflow rsyncs it, so this is
a manual step. The path is served with max-age=604800 and no cache-buster on
`generic.asset.url`, so purge Cloudflare or bump that URL afterwards, and test
on beta first: a malformed mandatory library hangs the client at 80%.
"""
import argparse
import io
import pathlib
import struct
import sys
import zlib

from PIL import Image

WHITE = (255, 255, 255, 255)
RIM = (169, 211, 227, 255)
SHADOW = (0, 0, 0, 77)

FRAME_BOX = (2, 23, 68, 59)  # a_0_0 within the spritesheet
FRAME_SIZE = (66, 36)
CX, CY, OUTER = 32.5, 16, 16.5


def iso(x, y):
    return abs(x - CX) / 2 + abs(y - CY)


def draw_diamond(steps):
    """The hover diamond at a stroke thickness of `steps` isometric steps."""
    w, h = FRAME_SIZE
    white = {(x, y) for y in range(h) for x in range(w)
             if OUTER - steps < iso(x, y) <= OUTER}
    shadow = {(x, y + steps) for (x, y) in white} - white
    shadow = {(x, y) for (x, y) in shadow if 0 <= y < h}

    img = Image.new("RGBA", FRAME_SIZE, (0, 0, 0, 0))
    px = img.load()
    for (x, y) in shadow:
        rim = any((x + dx, y) in white for dx in (-2, -1, 1, 2))
        px[x, y] = RIM if rim else SHADOW
    for (x, y) in white:
        px[x, y] = WHITE
    return img


def read_bundle(path):
    data = path.read_bytes()
    (count,) = struct.unpack_from(">h", data, 0)
    off = 2
    entries = []
    for _ in range(count):
        (name_len,) = struct.unpack_from(">h", data, off)
        off += 2
        name = data[off:off + name_len]
        off += name_len
        (blob_len,) = struct.unpack_from(">i", data, off)
        off += 4
        entries.append((name, zlib.decompress(data[off:off + blob_len])))
        off += blob_len
    return entries


def write_bundle(path, entries):
    out = bytearray(struct.pack(">h", len(entries)))
    for name, raw in entries:
        blob = zlib.compress(raw, 9)
        out += struct.pack(">h", len(name)) + name
        out += struct.pack(">i", len(blob)) + blob
    path.write_bytes(bytes(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", type=pathlib.Path, help="source tile_cursor.nitro")
    ap.add_argument("--steps", type=int, default=2,
                    help="stroke thickness in isometric steps (shipped art is 3)")
    ap.add_argument("-o", "--out", type=pathlib.Path, required=True)
    args = ap.parse_args()

    if not 1 <= args.steps <= 6:
        sys.exit("--steps must be between 1 and 6")

    entries = read_bundle(args.bundle)
    rebuilt = []
    for name, raw in entries:
        if not name.endswith(b".png"):
            rebuilt.append((name, raw))
            continue
        sheet = Image.open(io.BytesIO(raw)).convert("RGBA")
        sheet.paste(draw_diamond(args.steps), FRAME_BOX[:2])
        buf = io.BytesIO()
        sheet.save(buf, format="PNG", optimize=True, compress_level=9)
        rebuilt.append((name, buf.getvalue()))
        print(f"  {name.decode()}: frame a_0_0 redrawn at {args.steps} steps")

    write_bundle(args.out, rebuilt)
    print(f"wrote {args.out} ({args.out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
