#!/usr/bin/env python3
"""make-chat-bubble.py - convert oversized AI-generated chat bubble art into
native-resolution 9-slice assets for the Nitro client.

Input: one PNG on a transparent background containing the bubble BODY on top
and the POINTER (tail) below it, separated by at least one fully transparent
row (see docs/chat-bubble-art.md).

Output: bubble_<id>.png + bubble_<id>_pointer.png in the client's chatbubbles
asset dir (or --out), downscaled with nearest-neighbor and alpha-hardened,
plus a ready-to-paste SCSS block on stdout.

Usage:
  python3 docker/nitro/make-chat-bubble.py input.png --id 40
"""
import argparse
import pathlib
import sys

from PIL import Image

DEFAULT_OUT = pathlib.Path(__file__).resolve().parents[2] / "client/src/assets/images/chat/chatbubbles"
ALPHA_THRESHOLD = 64


def opaque_rows(img):
    alpha = img.getchannel("A")
    w, h = img.size
    data = alpha.getdata()
    return [any(data[y * w + x] >= ALPHA_THRESHOLD for x in range(w)) for y in range(h)]


def split_regions(img):
    """Split into (body, pointer) at the widest fully-transparent row band."""
    rows = opaque_rows(img)
    bands = []  # (start, length) of transparent bands strictly between opaque content
    y = 0
    while y < len(rows):
        if not rows[y]:
            start = y
            while y < len(rows) and not rows[y]:
                y += 1
            if start > 0 and y < len(rows):  # interior band only
                bands.append((start, y - start))
        else:
            y += 1
    if not bands:
        sys.exit("error: no transparent band between body and pointer - input must contain two shapes (see docs/chat-bubble-art.md)")
    split_at = max(bands, key=lambda b: b[1])[0]
    return img.crop((0, 0, img.width, split_at)), img.crop((0, split_at, img.width, img.height))


def crop_to_alpha(img):
    bbox = img.getchannel("A").point(lambda a: 255 if a >= ALPHA_THRESHOLD else 0).getbbox()
    if bbox is None:
        sys.exit("error: region is fully transparent")
    return img.crop(bbox)


def harden_alpha(img):
    r, g, b, a = img.split()
    return Image.merge("RGBA", (r, g, b, a.point(lambda v: 255 if v >= 128 else 0)))


def downscale(img, target_height):
    scale = target_height / img.height
    width = max(1, round(img.width * scale))
    return img.resize((width, target_height), Image.NEAREST)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=pathlib.Path)
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--height", type=int, default=32, help="native body height (px)")
    p.add_argument("--pointer-height", type=int, default=7, help="native pointer height (px)")
    p.add_argument("--border", type=int, default=12, help="9-slice border (px) for the SCSS block")
    p.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = p.parse_args()

    img = Image.open(args.input).convert("RGBA")
    body_raw, pointer_raw = split_regions(img)
    body = harden_alpha(downscale(crop_to_alpha(body_raw), args.height))
    pointer = harden_alpha(downscale(crop_to_alpha(pointer_raw), args.pointer_height))

    if body.width < 2 * args.border + 4:
        sys.exit(f"error: body too narrow ({body.width}px) for a {args.border}px 9-slice border")

    args.out.mkdir(parents=True, exist_ok=True)
    body_path = args.out / f"bubble_{args.id}.png"
    pointer_path = args.out / f"bubble_{args.id}_pointer.png"
    body.save(body_path)
    pointer.save(pointer_path)

    b = args.border
    print(f"wrote {body_path} ({body.width}x{body.height})")
    print(f"wrote {pointer_path} ({pointer.width}x{pointer.height})")
    print(f"""
SCSS block for ChatWidgetView.scss (inside `.bubble-container .chat-bubble`,
after the last stock `&.bubble-38` block):

        &.bubble-{args.id} {{
            border-image-source: url('@/assets/images/chat/chatbubbles/bubble_{args.id}.png');

            border-image-slice: {b} {b} {b} {b} fill;
            border-image-width: {b}px {b}px {b}px {b}px;
            border-image-outset: 0px 0px 0px 0px;

            .chat-content {{
                margin-left: 20px;
            }}

            .pointer {{
                background: url('@/assets/images/chat/chatbubbles/bubble_{args.id}_pointer.png');
                width: {pointer.width}px;
                height: {pointer.height}px;
                bottom: -{pointer.height - 1}px;
            }}
        }}
""")


if __name__ == "__main__":
    main()
