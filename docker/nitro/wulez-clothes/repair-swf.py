#!/usr/bin/env python3
"""Repair the two kinds of broken SWF in the Wulez clothing pack.

Usage:
    python3 docker/nitro/wulez-clothes/repair-swf.py <in.swf> <out.swf>

1. Six SWFs lost their zlib trailer (the Adler-32 checksum): the body is all
   there - it inflates to exactly the length the header declares - but the
   stream never ends, so nitro-converter fails with "unexpected end of file".
2. Twelve (shirt_M_long* and shirt_M_chemisehbt) were renamed without their
   document class: the SymbolClass entry for id 0 still says
   shirt_M_longamerics, with its terminating NUL missing. The converter strips
   that name off every sprite, gets nothing back, and writes an empty bundle.

Both come out fixed by re-reading every tag and writing the SWF back with the
document class set to the file's own name and a fresh zlib stream.
"""
import os
import struct
import sys
import zlib


def repair(src, dst):
    library = os.path.splitext(os.path.basename(src))[0]
    raw = open(src, 'rb').read()
    if raw[:3] != b'CWS':
        raise SystemExit('%s: not a zlib SWF' % src)
    body = zlib.decompressobj().decompress(raw[8:])
    nbits = body[0] >> 3
    i = (5 + nbits * 4 + 7) // 8 + 4                 # frame rect, rate, count
    out = bytearray(body[:i])
    while i < len(body):
        header = struct.unpack('<H', body[i:i + 2])[0]
        j = i + 2
        code, length = header >> 6, header & 0x3f
        if length == 0x3f:
            length = struct.unpack('<I', body[j:j + 4])[0]
            j += 4
        data = body[j:j + length]
        i = j + length
        if code == 76:                                # SymbolClass
            count = struct.unpack('<H', data[:2])[0]
            k, entries = 2, []
            for _ in range(count):
                cid = struct.unpack('<H', data[k:k + 2])[0]
                k += 2
                end = data.find(b'\0', k)
                end = len(data) if end < 0 else end
                entries.append((cid, library.encode() if cid == 0 else data[k:end]))
                k = end + 1
            data = struct.pack('<H', len(entries)) + b''.join(
                struct.pack('<H', cid) + name + b'\0' for cid, name in entries)
        out += struct.pack('<HI', (code << 6) | 0x3f, len(data)) + data
        if code == 0:
            break
    with open(dst, 'wb') as fh:
        fh.write(b'CWS' + raw[3:4] + struct.pack('<I', len(out) + 8) + zlib.compress(bytes(out), 9))


if __name__ == '__main__':
    repair(sys.argv[1], sys.argv[2])
