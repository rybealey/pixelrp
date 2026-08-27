#!/usr/bin/env python3
"""Merge new official furni into the local, customized gamedata.

Appends every furnitype entry present in the official furnidata
(/tmp/fd.json) but absent from the local FurnitureData.json, and adds the
matching <classname>_name / <classname>_desc keys to ExternalTexts.json.
Idempotent: entries already present are skipped, so a re-run is a no-op.
Never rewrites existing entries, so the PixelRP rebrand and in-place fixes
are preserved. Run rename-habbo-to-pixelrp.py afterwards to rebrand the
freshly added text.
"""
import json

OFF = json.load(open('/tmp/fd.json'))
FD_PATH = 'nitro/assets/gamedata/FurnitureData.json'
ET_PATH = 'nitro/assets/gamedata/ExternalTexts.json'
fd = json.load(open(FD_PATH))
et = json.load(open(ET_PATH))


def merge(kind):
    local = fd[kind]['furnitype']
    have = {f['classname'] for f in local}
    added = 0
    for f in OFF[kind]['furnitype']:
        if f['classname'] not in have:
            local.append(f)
            nk, dk = f"{f['classname']}_name", f"{f['classname']}_desc"
            if nk not in et:
                et[nk] = f.get('name', f['classname'])
            if dk not in et:
                et[dk] = f.get('description', '')
            added += 1
    return added


a = merge('roomitemtypes')
b = merge('wallitemtypes')
json.dump(fd, open(FD_PATH, 'w'), ensure_ascii=False, separators=(',', ':'))
json.dump(et, open(ET_PATH, 'w'), ensure_ascii=False, separators=(',', ':'))
print(f"added floor={a} wall={b} new furnitype entries")
