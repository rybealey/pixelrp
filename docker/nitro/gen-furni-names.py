#!/usr/bin/env python3
"""Resolve a display name for every furni and emit a public_name UPDATE.

Name resolution per furni (source: official /tmp/fd.json):
  1. the .com furnidata `name` if it is real (not the `"<classname> name"`
     placeholder and non-empty) - covers the ~11k established items with proper
     English names.
  2. otherwise a prettified classname (strip a leading line/season token,
     split on _/*/camelCase, Title Case) - clean deterministic English for the
     newest/unreleased items that have no real name anywhere yet.

Writes /tmp/furni_names.json (classname -> name, consumed by gen-catalog.py)
and emulator/Resources/SQLs/Updates/32_FurniNames.sql (idempotent UPDATE of
furniture.public_name, staged + joined on item_name).
"""
import json
import re

OFF = json.load(open('/tmp/fd.json'))

# Season/line tokens worth KEEPING (mapped to a readable word, kept as a prefix
# so a placeholder still reads as themed, e.g. "Halloween Bookshelf").
_SEASON = {
    'hween': 'Halloween', 'habboween': 'Halloween', 'xmas': 'Christmas',
    'christmas': 'Christmas', 'valentine': 'Valentine', 'valentines': 'Valentine',
    'easter': 'Easter', 'summer': 'Summer', 'spring': 'Spring', 'autumn': 'Autumn',
    'ranch': 'Ranch', 'diamond': 'Diamond', 'duckets': 'Ducket', 'ducket': 'Ducket',
}
# Leading tokens to DROP (internal line codes, not part of a human name).
_DROP = re.compile(r'^(nft\w*|ltd\d*|bonus\w*|hc|pcnc|wl|r\d{2}|clothing)_', re.I)
_DATE = re.compile(r'^c?\d{2,4}$', re.I)   # season/date token like c26, 2024


def prettify(cn):
    base = re.sub(r'\*\d+$', '', cn)              # drop color-variant suffix
    base = _DROP.sub('', base)                    # drop internal line-code prefix
    parts = base.replace('.', '_').replace('*', '_').split('_')
    out = []
    for i, p in enumerate(parts):
        low = p.lower()
        if i < 2 and low in _SEASON:              # keep season word, readable
            out.append(_SEASON[low]); continue
        if _DATE.match(p) and i < 3:              # drop the date token (c26, 2024)
            continue
        out.append(p)
    text = ' '.join(out)
    text = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text)   # split camelCase
    text = re.sub(r'(?<=[A-Za-z])(?=\d)', ' ', text)   # split letters/digits
    pretty = ' '.join(w.capitalize() for w in text.split())
    return pretty or cn


names = {}
for kind in ('roomitemtypes', 'wallitemtypes'):
    for f in OFF[kind]['furnitype']:
        cn = f['classname']
        nm = str(f.get('name', '')).strip()
        names[cn] = nm if (nm and nm != f"{cn} name") else prettify(cn)

json.dump(names, open('/tmp/furni_names.json', 'w'), ensure_ascii=False)


def esc(s):
    return "'" + str(s).replace("\\", "\\\\").replace("'", "\\'") + "'"


rows = [f"({esc(cn)},{esc(nm[:56])})" for cn, nm in names.items()]
OUT = 'emulator/Resources/SQLs/Updates/32_FurniNames.sql'
with open(OUT, 'w') as o:
    o.write("-- Resolve furniture.public_name for the full library.\n")
    o.write("-- Idempotent: staged names joined on item_name.\n")
    o.write("DROP TEMPORARY TABLE IF EXISTS _name_stage;\n")
    o.write("CREATE TEMPORARY TABLE _name_stage (item_name VARCHAR(70), nm VARCHAR(56));\n")
    for i in range(0, len(rows), 500):
        o.write("INSERT INTO _name_stage (item_name,nm) VALUES\n"
                + ",\n".join(rows[i:i + 500]) + ";\n")
    o.write("UPDATE furniture f JOIN _name_stage s ON f.item_name=s.item_name "
            "SET f.public_name=s.nm;\n")
    o.write("DROP TEMPORARY TABLE _name_stage;\n")

print(f"names: {len(names)}; sql rows: {len(rows)} -> {OUT}")
