#!/usr/bin/env python3
"""Re-encode gzip-compressed entries inside .nitro bundles as zlib.

nitro-renderer 1.6.6's NitroBundle parser uses pako.inflate (zlib only).
Some community asset packs ship bundle entries gzip-compressed, which that
parser cannot read — the bundle silently fails and, for mandatory room
libraries, leaves the client stuck at 80% on the loading screen.

Usage:
    python3 fix-bundle-compression.py <assets-dir> [--dry-run]

Rewrites affected .nitro files in place (atomic replace). Idempotent.
"""
import struct
import sys
import zlib
from pathlib import Path

GZIP_MAGIC = b"\x1f\x8b"


def convert_bundle(path: Path, dry_run: bool) -> bool:
    data = path.read_bytes()
    out = bytearray()
    off = 0
    (count,) = struct.unpack_from(">h", data, off)
    off += 2
    out += data[:2]
    changed = False
    for _ in range(count):
        (name_len,) = struct.unpack_from(">h", data, off)
        off += 2
        name = data[off : off + name_len]
        off += name_len
        (blob_len,) = struct.unpack_from(">i", data, off)
        off += 4
        blob = data[off : off + blob_len]
        off += blob_len
        if blob[:2] == GZIP_MAGIC:
            blob = zlib.compress(zlib.decompress(blob, 31), 9)
            changed = True
        out += struct.pack(">h", name_len) + name + struct.pack(">i", len(blob)) + blob
    if changed and not dry_run:
        tmp = path.with_suffix(".nitro.tmp")
        tmp.write_bytes(bytes(out))
        tmp.replace(path)
    return changed


def main() -> None:
    root = Path(sys.argv[1])
    dry_run = "--dry-run" in sys.argv
    scanned = fixed = failed = 0
    for path in root.rglob("*.nitro"):
        scanned += 1
        try:
            if convert_bundle(path, dry_run):
                fixed += 1
        except Exception as exc:  # noqa: BLE001 - report and continue
            failed += 1
            print(f"UNPARSEABLE {path}: {exc}", file=sys.stderr)
    verb = "would fix" if dry_run else "fixed"
    print(f"scanned={scanned} {verb}={fixed} unparseable={failed}")


if __name__ == "__main__":
    main()
