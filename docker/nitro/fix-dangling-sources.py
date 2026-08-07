#!/usr/bin/env python3
"""Repair dangling `source` aliases inside .nitro figure/furni bundles.

The nitro-converter sometimes emits asset entries whose `source` names a
sprite that was dropped from the bundle (seen with NFT part dedup, e.g. the
standard face `h_std_fc_1_*` aliasing deleted `*_fc_6221/6222_*` images —
result: avatars render with no nose/mouth). A dangling alias renders as
nothing, silently.

Two repairs, in priority order, for every asset carrying a `source`:

1. If the asset has its own sprite in the spritesheet, the alias is dropped
   entirely — GraphicAssetCollection falls back to the asset's own name when
   `source` is absent. This is the common case for the human figure parts:
   the sprite was always there, only the alias was junk. (Aliasing such an
   asset to a *different* action is how the idle face came to borrow the
   open-mouthed speaking sprite.)
2. Otherwise, if `source` resolves to no other asset in the bundle, it is
   rewritten to the closest existing sprite with the same size prefix, part
   type, part id, and direction, preferring actions in the order std, spk,
   sml, sad, agr, wlk, then anything, at frame 0.

Usage:
    python3 fix-dangling-sources.py <assets-dir> [--dry-run]

Asset key format: <size>_<action>_<part>_<partId>_<direction>_<frame>
Idempotent; rewrites files in place via atomic replace.
"""
import struct
import sys
import zlib
from pathlib import Path

ACTION_PRIORITY = ["std", "spk", "sml", "sad", "agr", "wlk"]


def parse_key(key: str):
    bits = key.split("_")
    if len(bits) < 6:
        return None
    # size prefix may itself contain no underscore; format is fixed-width from the right
    return {
        "size": "_".join(bits[:-5]),
        "action": bits[-5],
        "part": bits[-4],
        "part_id": bits[-3],
        "direction": bits[-2],
        "frame": bits[-1],
    }


def best_substitute(key: str, assets: dict):
    want = parse_key(key)
    if not want:
        return None
    candidates = []
    for other, meta in assets.items():
        if isinstance(meta, dict) and meta.get("source"):
            continue  # only alias to real sprites
        got = parse_key(other)
        if not got:
            continue
        if (
            got["size"] == want["size"]
            and got["part"] == want["part"]
            and got["part_id"] == want["part_id"]
            and got["direction"] == want["direction"]
        ):
            try:
                prio = ACTION_PRIORITY.index(got["action"])
            except ValueError:
                prio = len(ACTION_PRIORITY)
            candidates.append((prio, int(got["frame"] or 0), other))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][2]


def process(path: Path, dry_run: bool):
    data = path.read_bytes()
    off = 0
    (count,) = struct.unpack_from(">h", data, off)
    off += 2
    entries = []
    json_index = None
    for i in range(count):
        (name_len,) = struct.unpack_from(">h", data, off)
        off += 2
        name = data[off : off + name_len]
        off += name_len
        (blob_len,) = struct.unpack_from(">i", data, off)
        off += 4
        blob = data[off : off + blob_len]
        off += blob_len
        entries.append([name, blob])
        if name.decode(errors="replace").endswith(".json"):
            json_index = i
    if json_index is None:
        return 0, 0, 0
    import json as jsonlib

    j = jsonlib.loads(zlib.decompress(entries[json_index][1]))
    assets = j.get("assets") or {}
    lib = j.get("name", "")
    frames = set((j.get("spritesheet") or {}).get("frames", {}).keys())
    unaliased = remapped = unresolved = 0
    for key, meta in assets.items():
        if not (isinstance(meta, dict) and meta.get("source")):
            continue
        # An asset that has its own sprite in the sheet needs no alias at all:
        # GraphicAssetCollection falls back to the asset's own name when
        # `source` is absent. Aliasing such an asset to a different action is
        # how the idle face ended up borrowing the open-mouthed speaking
        # sprite. flipH only takes effect alongside a source, so mirrored
        # aliases are left intact.
        if f"{lib}_{key}" in frames and not meta.get("flipH"):
            del meta["source"]
            unaliased += 1
            continue
        if meta["source"] in assets:
            continue
        sub = best_substitute(meta["source"], assets) or best_substitute(key, assets)
        if sub:
            meta["source"] = sub
            remapped += 1
        else:
            unresolved += 1
    if (remapped or unaliased) and not dry_run:
        entries[json_index][1] = zlib.compress(
            jsonlib.dumps(j, separators=(",", ":")).encode(), 9
        )
        out = bytearray(struct.pack(">h", count))
        for name, blob in entries:
            out += struct.pack(">h", len(name)) + name + struct.pack(">i", len(blob)) + blob
        tmp = path.with_suffix(".nitro.tmp")
        tmp.write_bytes(bytes(out))
        tmp.replace(path)
    return unaliased, remapped, unresolved


def main() -> None:
    root = Path(sys.argv[1])
    dry_run = "--dry-run" in sys.argv
    total_unaliased = total_remapped = total_unresolved = touched = 0
    for path in root.rglob("*.nitro"):
        try:
            unaliased, remapped, unresolved = process(path, dry_run)
        except Exception as exc:  # noqa: BLE001
            print(f"SKIP {path}: {exc}", file=sys.stderr)
            continue
        if unaliased or remapped or unresolved:
            touched += 1
            print(f"{path.name}: unaliased={unaliased} remapped={remapped} unresolved={unresolved}")
        total_unaliased += unaliased
        total_remapped += remapped
        total_unresolved += unresolved
    verb = "would fix" if dry_run else "fixed"
    print(f"bundles touched={touched} {verb}: unaliased={total_unaliased} "
          f"remapped={total_remapped} unresolved={total_unresolved}")


if __name__ == "__main__":
    main()
