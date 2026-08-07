#!/usr/bin/env python3
"""
extract-furni-icons.py

Extracts furniture catalog/inventory grid icons (`<classname>_icon.png`) from
our own bundled `.nitro` furniture packages, instead of scraping them from
Sulake's CDN. This fixes the missing
  nitro/assets/dcr/hof_furni/icons/<classname>_icon.png
requests the Nitro client renderer makes (see `furni.asset.icon.url` =
`${hof.furni.url}/icons/%libname%%param%_icon.png` in
nitro/renderer-config*.json).

Bundle format (per `.nitro` file, big-endian):
    int16   fileCount
    repeat fileCount times:
        int16   nameLen
        bytes   name (utf-8, nameLen bytes)
        int32   blobLen
        bytes   blob (zlib-compressed; decompress to get raw file contents)

Each furniture bundle contains (at least) a `<lib>.json` (pixi spritesheet
description with `spritesheet.frames`) and a `<lib>.png` (the actual sprite
sheet). Icon frames are keyed like `<lib>_<lib>_icon_a` (the base/default
icon) and sometimes additional suffixes such `_icon_b` (alternate state,
e.g. toggled furni). We crop every icon frame found and write it out as:
    <classname>_icon.png              for the "_a" (default) icon frame
    <classname>_<suffix>_icon.png     for any other icon frame suffix

This intentionally does NOT attempt to synthesize per-color icon variants
(`<classname>_<N>_icon.png`) for furni whose color variants are expressed as
separate `classname*N` catalog entries — colored icons for those items are
tinted client-side at render time from the single base icon layer data, not
fetched as separate static images, so a single base icon is sufficient for
every `*N` variant of a given library.

Usage:
    python3 docker/nitro/extract-furni-icons.py

Requires Pillow (`pip3 install pillow`).
"""

import json
import struct
import sys
import zlib
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Pillow is required: pip3 install pillow", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_DIR = REPO_ROOT / "nitro" / "assets" / "bundled" / "furniture"
OUT_DIR = REPO_ROOT / "nitro" / "assets" / "dcr" / "hof_furni" / "icons"
FURNITURE_DATA = REPO_ROOT / "nitro" / "assets" / "gamedata" / "FurnitureData.json"


def read_nitro_bundle(path: Path) -> dict:
    """Parse a .nitro bundle into {filename: raw_bytes (decompressed)}."""
    data = path.read_bytes()
    pos = 0
    (count,) = struct.unpack_from(">h", data, pos)
    pos += 2

    files = {}
    for _ in range(count):
        (name_len,) = struct.unpack_from(">h", data, pos)
        pos += 2
        name = data[pos : pos + name_len].decode("utf-8")
        pos += name_len
        (blob_len,) = struct.unpack_from(">i", data, pos)
        pos += 4
        blob = data[pos : pos + blob_len]
        pos += blob_len
        files[name] = blob

    return files


def decompress_maybe(blob: bytes) -> bytes:
    """Bundle entries are zlib-compressed; be defensive in case one isn't."""
    try:
        return zlib.decompress(blob)
    except zlib.error:
        return blob


def extract_icons_from_bundle(bundle_path: Path) -> list[tuple[str, "Image.Image"]]:
    """Return a list of (output_filename, PIL.Image) for every icon frame."""
    raw_files = read_nitro_bundle(bundle_path)

    json_name = next((n for n in raw_files if n.endswith(".json")), None)
    png_name = next((n for n in raw_files if n.endswith(".png")), None)
    if not json_name or not png_name:
        raise ValueError(f"missing .json or .png entry in {bundle_path.name}")

    meta = json.loads(decompress_maybe(raw_files[json_name]))
    sheet_bytes = decompress_maybe(raw_files[png_name])

    frames = meta.get("spritesheet", {}).get("frames", {})
    icon_frames = {k: v for k, v in frames.items() if "_icon_" in k or k.endswith("_icon")}
    if not icon_frames:
        raise ValueError(f"no icon frames in {bundle_path.name}")

    lib_name = bundle_path.stem  # classname, e.g. "table_plasto_4leg"

    sheet_io = __import__("io").BytesIO(sheet_bytes)
    sheet = Image.open(sheet_io)
    sheet.load()

    results = []
    for frame_key, frame_info in icon_frames.items():
        # frame_key looks like "<lib>_<lib>_icon_a" -> suffix "a"
        suffix = frame_key.rsplit("_icon_", 1)[-1] if "_icon_" in frame_key else ""

        rect = frame_info["frame"]
        x, y, w, h = rect["x"], rect["y"], rect["w"], rect["h"]
        crop = sheet.crop((x, y, x + w, y + h))

        if suffix in ("", "a"):
            out_name = f"{lib_name}_icon.png"
        else:
            out_name = f"{lib_name}_{suffix}_icon.png"

        results.append((out_name, crop))

    return results


def load_classnames() -> set[str]:
    """Base (non-color-variant) classnames referenced in FurnitureData.json."""
    data = json.loads(FURNITURE_DATA.read_text())
    names = set()
    for section in ("roomitemtypes", "wallitemtypes"):
        for item in data.get(section, {}).get("furnitype", []):
            classname = item["classname"]
            base = classname.split("*", 1)[0]
            names.add(base)
    return names


def main() -> None:
    if not BUNDLE_DIR.is_dir():
        print(f"bundle dir not found: {BUNDLE_DIR}", file=sys.stderr)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    bundles = sorted(BUNDLE_DIR.glob("*.nitro"))
    print(f"found {len(bundles)} furniture bundles")

    written = 0
    ok_bundles = 0
    failed_bundles = []
    written_libs = set()

    for bundle_path in bundles:
        try:
            icons = extract_icons_from_bundle(bundle_path)
        except Exception as exc:  # noqa: BLE001 - we want to skip & count, not crash
            failed_bundles.append((bundle_path.name, str(exc)))
            continue

        for out_name, image in icons:
            out_path = OUT_DIR / out_name
            image.save(out_path)
            written += 1

        written_libs.add(bundle_path.stem)
        ok_bundles += 1

    print(f"processed ok: {ok_bundles} bundles, {written} icon files written")
    print(f"failed/skipped: {len(failed_bundles)} bundles")
    if failed_bundles:
        sample = failed_bundles[:15]
        for name, reason in sample:
            print(f"  SKIP {name}: {reason}")
        if len(failed_bundles) > len(sample):
            print(f"  ... and {len(failed_bundles) - len(sample)} more")

    # Coverage against FurnitureData.json classnames
    try:
        classnames = load_classnames()
        base_names = {c.split("*", 1)[0] for c in classnames}
        covered = base_names & written_libs
        missing = base_names - written_libs
        pct = (len(covered) / len(base_names) * 100) if base_names else 0.0
        print(
            f"coverage: {len(covered)}/{len(base_names)} base classnames "
            f"({pct:.1f}%) have an icon bundle"
        )
        if missing:
            sample_missing = sorted(missing)[:20]
            print(f"  sample misses ({len(missing)} total): {sample_missing}")
    except Exception as exc:  # noqa: BLE001
        print(f"could not compute coverage against FurnitureData.json: {exc}")


if __name__ == "__main__":
    main()
