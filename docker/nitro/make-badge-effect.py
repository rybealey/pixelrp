#!/usr/bin/env python3
"""make-badge-effect.py - build a Nitro avatar-effect bundle whose only art is
a badge image, and point an EffectMap entry at it.

Used for the City Government on-duty enable (effect 102): instead of the stock
"Staff" pentagram, the corporation's badge floats above the head. Pure
Python (no Pillow on the dev Mac): a GIF badge is converted with macOS `sips`;
the badge PNG becomes the bundle's spritesheet as-is, every animation frame
referencing the whole image, centred where the stock glyph sat.

Why a NEW library name rather than overwriting Staff.nitro: bundles are served
with a week-long max-age and their URL carries no version, so a rewritten
Staff.nitro would stay stale in every browser that has it cached. EffectMap.json
is served no-store, so retargeting id 102 at a fresh library name takes effect
on the next client load.

Usage:
  python3 docker/nitro/make-badge-effect.py --badge badge.gif --lib GovtBadge \
      --effect-id 102 --effectmap EffectMap.json --out nitro/overrides
"""
import argparse, json, pathlib, shutil, struct, subprocess, sys, tempfile, zlib

# ---- minimal PNG reader (8-bit, non-interlaced) -----------------------------
def read_png_size(path: pathlib.Path):
    data = path.read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        sys.exit(f"error: {path} is not a PNG")
    w, h, depth, ctype, _, _, interlace = struct.unpack('>IIBBBBB', data[16:29])
    if depth != 8 or interlace != 0:
        sys.exit("error: badge PNG must be 8-bit and non-interlaced (sips output is)")
    return w, h

def to_png(src: pathlib.Path, tmpdir: pathlib.Path) -> pathlib.Path:
    if src.suffix.lower() == '.png':
        return src
    out = tmpdir / (src.stem + '.png')
    if shutil.which('sips'):
        subprocess.run(['sips', '-s', 'format', 'png', str(src), '--out', str(out)], check=True, capture_output=True)
        return out
    sys.exit("error: badge is not a PNG and no converter (sips) is available - convert it to PNG first")

# ---- bundle -----------------------------------------------------------------
def build_bundle(lib: str, effect_id: int, png_bytes: bytes, w: int, h: int, frames: int, glyph_center=(32.5, -100)):
    # The stock Staff glyph's visible centre in avatar coordinates (measured):
    # x 32.5 (the avatar's midline), y -100 (just above the head). Asset x/y are
    # the registration offsets: the image draws at (-x, -y) from the anchor, so
    # centring a w*h badge there means x = w/2 - cx, y = h/2 - cy.
    cx, cy = glyph_center
    ox, oy = round(w / 2 - cx), round(h / 2 - cy)
    sprite_id = f"fx{effect_id}_1"
    member = f"std_{sprite_id}_1"
    frame_json = {"frame": {"x": 0, "y": 0, "w": w, "h": h}, "rotated": False, "trimmed": False,
                  "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h}, "sourceSize": {"w": w, "h": h}, "pivot": {"x": 0.5, "y": 0.5}}
    assets, sheet_frames, anim_frames = {}, {}, []
    for i in range(frames):
        asset = f"h_{member}_0_{i}"
        assets[asset] = {"x": ox, "y": oy}
        sheet_frames[f"{lib}_{asset}"] = dict(frame_json)
        anim_frames.append({"repeats": 1, "fxs": [{"id": sprite_id, "frame": i, "action": "Default"}]})
    doc = {
        "assets": assets,
        "animations": {lib: {
            "name": f"fx.{effect_id}", "desc": lib,
            # ink 0 = normal blending. The stock Staff layer used 33 (additive),
            # which glows and washes a badge toward white over light floors.
            "sprites": [{"id": sprite_id, "member": member, "ink": 0, "staticY": 1,
                         "directionList": [{"id": d, "dz": 0} for d in range(8)]}],
            "frames": anim_frames}},
        "name": lib,
        "spritesheet": {"frames": sheet_frames, "meta": {"image": f"{lib}.png", "format": "RGBA8888", "size": {"w": w, "h": h}, "scale": 1}}
    }
    entries = [(f"{lib}.json", json.dumps(doc, separators=(',', ':')).encode()), (f"{lib}.png", png_bytes)]
    out = struct.pack('>h', len(entries))
    for name, raw in entries:
        blob = zlib.compress(raw, 9)
        out += struct.pack('>h', len(name)) + name.encode() + struct.pack('>i', len(blob)) + blob
    return out

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--badge', type=pathlib.Path, required=True, help='badge image (png or gif)')
    p.add_argument('--lib', required=True, help='new effect library name, e.g. GovtBadge')
    p.add_argument('--effect-id', type=int, required=True)
    p.add_argument('--effectmap', type=pathlib.Path, required=True, help='current EffectMap.json (copied and retargeted)')
    p.add_argument('--out', type=pathlib.Path, required=True, help='overrides root (gets bundled/effect/<lib>.nitro and gamedata/EffectMap.json)')
    p.add_argument('--frames', type=int, default=1)
    args = p.parse_args()

    with tempfile.TemporaryDirectory() as td:
        png_path = to_png(args.badge, pathlib.Path(td))
        w, h = read_png_size(png_path)
        png_bytes = png_path.read_bytes()
        bundle = build_bundle(args.lib, args.effect_id, png_bytes, w, h, args.frames)

    effect_dir = args.out / 'bundled' / 'effect'
    effect_dir.mkdir(parents=True, exist_ok=True)
    (effect_dir / f"{args.lib}.nitro").write_bytes(bundle)

    effectmap = json.loads(args.effectmap.read_text())
    effects = effectmap['effects'] if isinstance(effectmap, dict) else effectmap
    hit = [e for e in effects if str(e.get('id')) == str(args.effect_id)]
    if not hit:
        sys.exit(f"error: effect id {args.effect_id} not in {args.effectmap}")
    hit[0]['lib'] = args.lib
    hit[0]['revision'] = int(hit[0].get('revision', 0)) + 1
    gamedata_dir = args.out / 'gamedata'
    gamedata_dir.mkdir(parents=True, exist_ok=True)
    (gamedata_dir / 'EffectMap.json').write_text(json.dumps(effectmap, separators=(',', ':')))
    print(f"wrote {effect_dir / (args.lib + '.nitro')} ({len(bundle)} bytes, badge {w}x{h}) and {gamedata_dir / 'EffectMap.json'} (id {args.effect_id} -> {args.lib})")

if __name__ == '__main__':
    main()
