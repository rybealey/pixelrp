#!/usr/bin/env python3
"""Import the Kasja custom furniture packs into Builders > Kasja.

Reads the pack folders (default ~/Downloads/Kasja), pulls each furni's own
metadata straight out of its SWF, and emits:

  emulator/Resources/SQLs/Updates/84_KasjaFurniture.sql
      furniture rows, the Builders divider + Kasja pages, and one catalog row
      per furni.
  docker/nitro/kasja/furnidata-entries.json
      the FurnitureData.json furnitype entries and ExternalTexts name/desc keys
      for the same set, merged into the (git-ignored) asset tree on deploy by
      apply-gamedata-fragments.py.
  nitro/overrides/dcr/hof_furni/icons/<classname>_icon.png
      the pack's own catalog icons. The client does NOT read the icon out of
      the .nitro bundle even though it is in there: renderer-config's
      furni.asset.icon.url points at ${hof.furni.url}/icons/%libname%_icon.png,
      a plain static PNG. Ship the bundle without these and every icon in the
      shop is blank, which is exactly what happened on the first import.

A Habbo furni SWF carries its own definition as DefineBinaryData tags: the
logic XML gives <dimensions x y z>, the object XML gives the logic and
visualization class. That is every field the furniture table needs except two
the format simply does not record, which are inferred and listed at the end of
a run so they can be corrected by hand:

  can_sit      classname looks like a seat (chair/sofa/bench/stool/puf/seat)
  is_walkable  z <= 0.05 AND the classname reads like ground (tile, grass,
               water, path, rug, bridge, stair ...) - flat alone is not enough,
               since the packs model fences and archways flat as well

Clothing is skipped, and that means both of Valentine's clothing folders:
"Clothing" (the garment SWFs) and "Clothing (Furniture)" - the latter is furni
whose whole purpose is to sell a garment, which is the sellable clothing this
shop does not carry.

NOT done here: converting the SWFs to .nitro bundles. That needs
billsonnn/nitro-converter (Node), and without those bundles the client has
nothing to draw - the catalog rows are inert until they land in
nitro/overrides/bundled/furniture/.
"""
import json
import os
import shutil
import re
import struct
import sys
import zlib

ROOT = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else '~/Downloads/Kasja')
SQL_OUT = 'emulator/Resources/SQLs/Updates/84_KasjaFurniture.sql'
JSON_OUT = 'docker/nitro/kasja/furnidata-entries.json'
ICON_OUT = 'nitro/overrides/dcr/hof_furni/icons'

FURNI_BASE = 100035     # 100001-100005 navigation, 100010-100034 Cartier
PAGE_BASE = 940000      # clear of the catalog restore's 930000 range
SEAT = re.compile(r'chair|sofa|bench|stool|puf|seat|couch')
# Flat is not the same as walkable: these packs model fences and archways at
# z=0.01 too, and a fence you can walk through is a bug. Ground words as well
# as a flat z, and stonewall is not stone.
GROUND = re.compile(r'floor|tile|grass|dirt|water|path|road|sand|snow|rug|carpet'
                    r'|mat\b|lawn|bridge|stair|pavement|stone(?!wall)')
# pack folder -> the prefix its classnames carry, stripped for the display name
PACK_ORDER = ['Modern Cabin', 'Autumn', 'Beach House', 'Christmas', 'Garden',
              'Ghibli', "Valentine's Day"]


def swf_binary(path):
    """DefineBinaryData (tag 87) payloads: 2-byte id + 4 reserved, then XML."""
    raw = open(path, 'rb').read()
    if raw[:3] == b'CWS':
        body = zlib.decompress(raw[8:])
    elif raw[:3] == b'FWS':
        body = raw[8:]
    else:
        raise ValueError('unsupported SWF signature %r' % raw[:3])
    i = ((5 + 4 * (body[0] >> 3) + 7) // 8) + 4      # frame rect, rate, count
    out = []
    while i + 2 <= len(body):
        header = struct.unpack_from('<H', body, i)[0]
        i += 2
        code, length = header >> 6, header & 0x3f
        if length == 0x3f:
            length = struct.unpack_from('<I', body, i)[0]
            i += 4
        if code == 87:
            out.append(body[i + 6:i + length].decode('utf-8', 'replace'))
        i += length
    return out


def pretty(classname, prefix):
    name = classname[len(prefix):] if classname.startswith(prefix) else classname
    name = re.sub(r'^kasja_', '', name)
    name = re.sub(r'(?<=[a-z])(?=\d)', ' ', name)     # bridge2 -> bridge 2
    return ' '.join(w.capitalize() for w in name.replace('_', ' ').split()) or classname


def collect():
    packs = {}
    for dirpath, _dirs, files in os.walk(ROOT):
        for fn in sorted(files):
            if not fn.lower().endswith('.swf'):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
            parts = rel.split(os.sep)
            # Both "Clothing" and "Clothing (Furniture)": the second is furni
            # that sells a garment, which is still sellable clothing.
            if any(p.lower().startswith('clothing') for p in parts):
                continue
            pack = parts[0]
            # A pack's own subfolders are its categories, minus the folder that
            # merely holds the SWFs ("swf's", "SWF", "Furniture").
            sub = [p for p in parts[1:-1]
                   if p.lower().replace("'", '') not in ('swf', 'swfs', 'furniture')]
            blobs = swf_binary(os.path.join(dirpath, fn))
            logic = next((b for b in blobs if '<objectData' in b), '')
            d = re.search(r'<dimensions x="([\d.]+)" y="([\d.]+)" z="(-?[\d.]+)"', logic)
            if not d:
                raise SystemExit('no dimensions in %s' % rel)
            packs.setdefault((pack, tuple(sub)), []).append({
                'classname': fn[:-4],
                'x': int(float(d.group(1))), 'y': int(float(d.group(2))),
                'z': float(d.group(3)),
            })
    return packs


packs = collect()
# Longest shared classname prefix per pack, so kasja_sghibli_pig reads "Pig".
prefixes = {}
for (pack, _sub), items in packs.items():
    names = [i['classname'] for i in items]
    prefix = os.path.commonprefix(names)
    prefix = prefix[:prefix.rindex('_') + 1] if '_' in prefix else ''
    prefixes.setdefault(pack, []).append(prefix)
prefix_for = {p: min(v, key=len) for p, v in prefixes.items()}

rows, pages, fid, pid = [], [], FURNI_BASE, PAGE_BASE + 3
guessed = {'sit': [], 'walk': []}
for pack in PACK_ORDER:
    subs = sorted(k for k in packs if k[0] == pack)
    if not subs:
        raise SystemExit('pack folder missing: %s' % pack)
    parent = pid
    pages.append((pid, 'KASJA', pack, len(subs) > 1 or not subs[0][1]))
    pid += 1
    for key in subs:
        items = sorted(packs[key], key=lambda i: i['classname'])
        if key[1]:                                    # Christmas > Standard / Danish
            page, label = pid, key[1][-1]
            pages.append((pid, parent, label, True))
            pid += 1
        else:
            page = parent
        for it in items:
            sit = bool(SEAT.search(it['classname']))
            walk = it['z'] <= 0.05 and bool(GROUND.search(it['classname']))
            if sit:
                guessed['sit'].append(it['classname'])
            if walk:
                guessed['walk'].append(it['classname'])
            rows.append({
                'id': fid, 'page': page, 'pack': pack,
                'classname': it['classname'],
                'name': pretty(it['classname'], prefix_for[pack]),
                'x': it['x'], 'y': it['y'], 'z': it['z'],
                'sit': sit, 'walk': walk,
                'price': 3 if it['x'] * it['y'] <= 1 else 5,
            })
            fid += 1

# ---- FurnitureData.json + ExternalTexts.json fragments ----------------------
json.dump({
    'furnitype': [{
        'id': r['id'], 'classname': r['classname'], 'revision': 0,
        'category': 'kasja', 'defaultdir': 0, 'xdim': r['x'], 'ydim': r['y'],
        'partcolors': {'color': []}, 'name': r['name'],
        'description': r['name'], 'adurl': '', 'offerid': -1,
        'buyout': False, 'rentofferid': -1, 'rentbuyout': False,
        'bc': False, 'excludeddynamic': False, 'customparams': '',
        'specialtype': 1, 'canstandon': r['walk'], 'cansiton': r['sit'],
        'canlayon': False, 'furniline': 'kasja',
    } for r in rows],
    'externaltexts': {k: v for r in rows for k, v in (
        ('%s_name' % r['classname'], r['name']),
        ('%s_desc' % r['classname'], r['name']),
    )},
}, open(JSON_OUT, 'w'), indent=1)


# ---- catalog icons ---------------------------------------------------------
os.makedirs(ICON_OUT, exist_ok=True)
wanted = {r['classname'] for r in rows}
found = {}
for dirpath, _dirs, files in os.walk(ROOT):
    if any(p.lower().startswith('clothing')
           for p in os.path.relpath(dirpath, ROOT).split(os.sep)):
        continue
    for fn in files:
        if fn.lower().endswith('_icon.png') and fn[:-9] in wanted:
            found[fn[:-9]] = os.path.join(dirpath, fn)
for classname, src in found.items():
    shutil.copy2(src, os.path.join(ICON_OUT, '%s_icon.png' % classname))
missing_icons = sorted(wanted - set(found))


def esc(v):
    return "'%s'" % str(v).replace('\\', '\\\\').replace("'", "\\'")


with open(SQL_OUT, 'w') as o:
    o.write("""\
-- PixelRP: the Kasja furniture packs, in Builders > Kasja.
--
-- 215 custom furni from the seven Kasja packs, laid out as the download folder
-- is: a page per pack, and Christmas keeps its Standard / Danish split. A
-- divider sits above Kasja the way one sits above Cartier, so the tab reads as
-- three groups. Generated by docker/nitro/import-kasja.py, which reads each
-- SWF's own logic XML for its dimensions - see that file for the two fields
-- (can_sit, is_walkable) the format does not record and that are inferred.
--
-- The rendering half of this import is the .nitro bundles and the
-- FurnitureData.json entries (docker/nitro/kasja/furnidata-entries.json); the
-- rows below are inert until those are in the asset tree.
--
-- Idempotent: fixed id ranges, cleared before insert.

SET @builders := COALESCE(
    (SELECT `id` FROM `catalog_pages` WHERE `parent_id` = -1 AND `caption` = 'Builders' LIMIT 1),
    912362);
SET @club_order := (SELECT `order_num` FROM `catalog_pages`
                    WHERE `parent_id` = @builders AND `caption` = 'Club' LIMIT 1);
SET @divider := COALESCE(@club_order, 1002) + 1;

DELETE FROM `catalog_items` WHERE `item_id` BETWEEN %d AND %d;
DELETE FROM `catalog_pages` WHERE `id` BETWEEN %d AND %d;
DELETE FROM `furniture` WHERE `id` BETWEEN %d AND %d;

-- The divider is the same non-clickable sentinel Cartier's uses: the client
-- keys on page_link = 'divider', and enabled = 0 keeps it from opening.
INSERT INTO `catalog_pages`
    (`id`,`parent_id`,`caption`,`icon_image`,`min_rank`,`min_vip`,`order_num`,`page_link`,
     `page_layout`,`page_strings_1`,`page_strings_2`,`visible`,`enabled`)
VALUES
    (%d, @builders, '-', 0, 2, 0, @divider, 'divider', 'default_3x3', '', '', b'1', b'0'),
    (%d, @builders, 'Kasja', 193, 2, 0, @divider + 1, '', 'default_3x3', '', '', b'1', b'1');
""" % (FURNI_BASE, FURNI_BASE + len(rows) - 1, PAGE_BASE, PAGE_BASE + 999,
       FURNI_BASE, FURNI_BASE + len(rows) - 1, PAGE_BASE + 1, PAGE_BASE + 2))

    o.write('\nINSERT INTO `catalog_pages` (`id`,`parent_id`,`caption`,`icon_image`,`min_rank`,'
            '`min_vip`,`order_num`,`page_link`,`page_layout`,`page_strings_1`,`page_strings_2`,'
            '`visible`,`enabled`) VALUES\n')
    lines = []
    for n, (page, parent, caption, _leaf) in enumerate(pages):
        par = str(PAGE_BASE + 2) if parent == 'KASJA' else str(parent)
        lines.append("    (%d,%s,%s,193,2,0,%d,'','default_3x3','','',b'1',b'1')"
                     % (page, par, esc(caption), n + 1))
    o.write(',\n'.join(lines) + ';\n')

    o.write('\n-- Furniture. id == sprite_id, the convention every custom line here follows.\n')
    o.write('INSERT INTO `furniture` (`id`,`item_name`,`public_name`,`type`,`width`,`length`,'
            '`stack_height`,`can_stack`,`can_sit`,`is_walkable`,`sprite_id`,`allow_recycle`,'
            '`allow_trade`,`allow_marketplace_sell`,`allow_gift`,`allow_inventory_stack`,'
            '`interaction_type`,`behaviour_data`,`interaction_modes_count`,`is_rare`) VALUES\n')
    o.write(',\n'.join(
        "    (%d,%s,%s,'s',%d,%d,%s,'1','%d','%d',%d,'0','1','0','1','1','default',0,1,'0')"
        % (r['id'], esc(r['classname']), esc(r['name']), r['x'], r['y'], r['z'],
           r['sit'], r['walk'], r['id'])
        for r in rows) + ';\n')

    o.write('\nINSERT INTO `catalog_items` (`page_id`,`item_id`,`catalog_name`,`cost_credits`,'
            '`cost_pixels`,`cost_diamonds`,`amount`,`limited_sells`,`limited_stack`,'
            '`offer_active`,`extradata`,`badge`,`offer_id`) VALUES\n')
    o.write(',\n'.join(
        "    (%d,'%d',%s,%d,0,0,1,0,0,'1','','',-1)"
        % (r['page'], r['id'], esc(r['name']), r['price'])
        for r in rows) + ';\n')

print('packs: %d   pages: %d   furni: %d   ids %d-%d'
      % (len({p for p, _ in packs}), len(pages) + 2, len(rows),
         FURNI_BASE, FURNI_BASE + len(rows) - 1))
print('icons: %d copied to %s%s'
      % (len(found), ICON_OUT,
         '' if not missing_icons else '   MISSING: ' + ', '.join(missing_icons)))
print('inferred can_sit (%d): %s' % (len(guessed['sit']), ', '.join(guessed['sit'][:8])))
print('inferred is_walkable (%d): %s' % (len(guessed['walk']), ', '.join(guessed['walk'][:8])))
