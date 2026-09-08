#!/usr/bin/env python3
"""Import furni Habbo has that we do not, and file it in the catalog.

Our library was synced in full on 2026-08-27; this picks up what Habbo has
added since. Run the diff by comparing classnames in the live furnidata (fetch
it with `habbo-downloader -c gamedata`; www.habbo.com blocks a plain curl but
the tool's client works) against nitro/assets/gamedata/FurnitureData.json.

Unlike the Kasja packs, nothing here is guessed: Habbo's furnidata carries id,
xdim/ydim, cansiton, canstandon and the real name, so the furniture rows are
exact. Stack height still comes from the SWF's own logic XML, which is what the
client actually renders against.

Emits, for the set in import_set.json:
  emulator/Resources/SQLs/Updates/85_HabboFurniSync.sql
      furniture rows (ids from FURNI_BASE) and catalog rows.
  nitro/overrides/gamedata-merge/{FurnitureData,ExternalTexts}.json
      MERGED into the existing fragments, not replacing them - the Kasja
      entries live in the same files.
  nitro/overrides/bundled/furniture/*.nitro, dcr/hof_furni/icons/*_icon.png
      copied from the converter output and the habbo-downloader icon set.

Where things land, from the classname:
  nft_*   Staff > NFT           collectibles, never public
  wf_fx_*  Staff > Wired > Effects
  wf_xtra_* Staff > Wired > Add-Ons
  hween*  Furni By Holiday > Halloween > <year>
Every target except NFT already exists from the catalog restore, so the SQL
resolves them by caption rather than by id.

Clothing is excluded, as everywhere else.
"""
import json
import os
import re
import shutil
import struct
import sys
import zlib

SCRATCH = sys.argv[1] if len(sys.argv) > 1 else '.'
CONVERTED = os.path.expanduser('~/Documents/Personal/Projects/Games/nitro-converter/assets/bundled/furniture')
ICONS_SRC = os.path.join(SCRATCH, 'hdl/resource/dcr/hof_furni')
SWF_DIR = os.path.join(SCRATCH, 'newswf')
SQL_OUT = 'emulator/Resources/SQLs/Updates/85_HabboFurniSync.sql'
BUNDLE_DST = 'nitro/overrides/bundled/furniture'
ICON_DST = 'nitro/overrides/dcr/hof_furni/icons'
MERGE_DIR = 'nitro/overrides/gamedata-merge'

FURNI_BASE = 100250     # Kasja ends at 100249
PAGE_BASE = 950000      # clear of the restore (930000) and Kasja (940000)


def swf_stack_height(classname):
    """The z of <dimensions> in the SWF's logic XML - what the client renders."""
    path = os.path.join(SWF_DIR, classname.split('*')[0] + '.swf')
    if not os.path.exists(path):
        return None
    raw = open(path, 'rb').read()
    if raw[:3] == b'CWS':
        body = zlib.decompress(raw[8:])
    elif raw[:3] == b'FWS':
        body = raw[8:]
    else:
        return None
    i = ((5 + 4 * (body[0] >> 3) + 7) // 8) + 4
    while i + 2 <= len(body):
        header = struct.unpack_from('<H', body, i)[0]
        i += 2
        code, length = header >> 6, header & 0x3f
        if length == 0x3f:
            length = struct.unpack_from('<I', body, i)[0]
            i += 4
        if code == 87:
            blob = body[i + 6:i + length].decode('utf-8', 'replace')
            m = re.search(r'<dimensions x="[\d.]+" y="[\d.]+" z="(-?[\d.]+)"', blob)
            if m:
                return float(m.group(1))
        i += length
    return None


def pretty(classname, name):
    """Habbo ships '<classname> name' for items it has not named yet."""
    if name and not name.endswith(' name'):
        return name
    base = re.sub(r'^(nft|wf|hween\d*)_', '', classname.split('*')[0])
    base = re.sub(r'^(xtra|fx|nt)_', '', base)
    return ' '.join(w.capitalize() for w in base.replace('_', ' ').split()) or classname


def target(classname, furniline):
    if classname.startswith('nft'):
        return 'nft', 50000
    if classname.startswith('wf_fx'):
        return 'wired_effects', 3
    if classname.startswith('wf_'):
        return 'wired_addons', 3
    year = re.search(r'hween(\d{2})', classname)
    if year:
        return 'halloween:20' + year.group(1), 5
    return 'misc', 5


items = json.load(open(os.path.join(SCRATCH, 'import_set.json')))
live = json.load(open(os.path.join(SCRATCH, 'hdl/resource/gamedata/furnidata.json')))
by_class = {}
for kind in ('roomitemtypes', 'wallitemtypes'):
    for f in live.get(kind, {}).get('furnitype', []) or []:
        by_class[f['classname']] = (kind, f)
# variants share a base SWF and are listed individually in furnidata
wanted = [i['classname'] for i in items]
wanted += [c for c in by_class if c.startswith('nft_bonusrare16_3*')]

rows, bundles = [], set()
for n, classname in enumerate(sorted(set(wanted))):
    kind, f = by_class[classname]
    z = swf_stack_height(classname)
    rows.append({
        'id': FURNI_BASE + n,
        'sprite': int(f['id']),                      # the client resolves by furnidata id
        'classname': classname,
        'name': pretty(classname, f.get('name')),
        'type': 'i' if kind == 'wallitemtypes' else 's',
        'x': int(f.get('xdim') or 1), 'y': int(f.get('ydim') or 1),
        'z': z if z is not None else 0.0,
        'sit': bool(f.get('cansiton')), 'walk': bool(f.get('canstandon')),
        'rare': bool(f.get('rare')),
        'desc': f.get('description') or f.get('name') or classname,
        'furnidata': f, 'kind': kind,
    })
    bundles.add(classname.split('*')[0])

for r in rows:
    r['where'], r['price'] = target(r['classname'], r['furnidata'].get('furniline'))

# ---- assets ---------------------------------------------------------------
os.makedirs(BUNDLE_DST, exist_ok=True)
os.makedirs(ICON_DST, exist_ok=True)
copied_b = copied_i = missing_i = 0
for base in sorted(bundles):
    src = os.path.join(CONVERTED, base + '.nitro')
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(BUNDLE_DST, base + '.nitro'))
        copied_b += 1
for r in rows:
    icon = r['classname'].replace('*', '_') + '_icon.png'
    src = os.path.join(ICONS_SRC, icon)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(ICON_DST, icon))
        copied_i += 1
    else:
        missing_i += 1

# ---- gamedata fragments (merged into what is already there) ---------------
fd_path = os.path.join(MERGE_DIR, 'FurnitureData.json')
frag = json.load(open(fd_path)) if os.path.exists(fd_path) else {}
for kind in ('roomitemtypes', 'wallitemtypes'):
    frag.setdefault(kind, {}).setdefault('furnitype', [])
have = {e['classname'] for k in ('roomitemtypes', 'wallitemtypes')
        for e in frag[k]['furnitype']}
added_fd = 0
for r in rows:
    if r['classname'] in have:
        continue
    frag[r['kind']]['furnitype'].append(r['furnidata'])   # verbatim, it is official
    added_fd += 1
json.dump(frag, open(fd_path, 'w'), indent=1)

et_path = os.path.join(MERGE_DIR, 'ExternalTexts.json')
texts = json.load(open(et_path)) if os.path.exists(et_path) else {}
added_et = 0
for r in rows:
    for key, val in (('%s_name' % r['classname'], r['name']),
                     ('%s_desc' % r['classname'], r['desc'])):
        if key not in texts:
            texts[key] = val
            added_et += 1
json.dump(texts, open(et_path, 'w'), indent=1)


def esc(v):
    return "'%s'" % str(v).replace('\\', '\\\\').replace("'", "\\'")


groups = {}
for r in rows:
    groups.setdefault(r['where'], []).append(r)

with open(SQL_OUT, 'w') as o:
    o.write("""\
-- PixelRP: furni Habbo has added since our library sync, and where it lives.
--
-- %d items over %d bundles. Generated by docker/nitro/import-habbo-sync.py -
-- see that file for how the set was diffed and what each rule files where.
-- Every field comes from Habbo's own furnidata (id, dimensions, cansiton,
-- canstandon, name) except stack height, which is read from the SWF's logic
-- XML because that is what the client renders against.
--
-- Clothing is excluded, as everywhere else: Habbo also added
-- clothing_nft26_nftwitchcape and hween_cloth_c26_checkerskirt, which this
-- shop does not sell.
--
-- Idempotent: fixed id ranges, cleared before insert. Targets are resolved by
-- caption because the catalog restore hands out fresh page ids each run.

DELETE FROM `catalog_items` WHERE `item_id` BETWEEN %d AND %d;
DELETE FROM `catalog_pages` WHERE `id` BETWEEN %d AND %d;
DELETE FROM `furniture` WHERE `id` BETWEEN %d AND %d;

SET @staff   := (SELECT `id` FROM `catalog_pages` WHERE `parent_id` = -1 AND `caption` = 'Staff' LIMIT 1);
SET @wired   := (SELECT `id` FROM `catalog_pages` WHERE `parent_id` = @staff AND `caption` = 'Wired' LIMIT 1);
SET @waddons := (SELECT `id` FROM `catalog_pages` WHERE `parent_id` = @wired AND `caption` = 'Add-Ons' LIMIT 1);
SET @wfx     := (SELECT `id` FROM `catalog_pages` WHERE `parent_id` = @wired AND `caption` = 'Effects' LIMIT 1);
SET @hol     := (SELECT p.`id` FROM `catalog_pages` p JOIN `catalog_pages` s ON s.`id` = p.`parent_id`
                 WHERE p.`caption` = 'Halloween' AND s.`caption` = 'Furni By Holiday' LIMIT 1);

-- Staff > NFT is new; Halloween > 2026 is the first item of its year.
INSERT INTO `catalog_pages`
    (`id`,`parent_id`,`caption`,`icon_image`,`min_rank`,`min_vip`,`order_num`,`page_link`,
     `page_layout`,`page_strings_1`,`page_strings_2`,`visible`,`enabled`)
SELECT %d, @staff, 'NFT', 92, 5, 0, 20, '', 'default_3x3', '', '', b'1', b'1'
FROM DUAL WHERE @staff IS NOT NULL;
INSERT INTO `catalog_pages`
    (`id`,`parent_id`,`caption`,`icon_image`,`min_rank`,`min_vip`,`order_num`,`page_link`,
     `page_layout`,`page_strings_1`,`page_strings_2`,`visible`,`enabled`)
SELECT %d, @hol, '2026', 34, 1, 0, 2026, '', 'default_3x3', '', '', b'1', b'1'
FROM DUAL WHERE @hol IS NOT NULL;
SET @nft  := %d;
SET @h26  := %d;

-- Furniture. sprite_id is the furnidata id, which is how the client resolves
-- the asset; furniture.id is ours and only the catalog refers to it.
""" % (len(rows), len(bundles),
       FURNI_BASE, FURNI_BASE + len(rows) - 1, PAGE_BASE, PAGE_BASE + 99,
       FURNI_BASE, FURNI_BASE + len(rows) - 1, PAGE_BASE, PAGE_BASE + 1,
       PAGE_BASE, PAGE_BASE + 1))
    o.write('INSERT INTO `furniture` (`id`,`item_name`,`public_name`,`type`,`width`,`length`,'
            '`stack_height`,`can_stack`,`can_sit`,`is_walkable`,`sprite_id`,`allow_recycle`,'
            '`allow_trade`,`allow_marketplace_sell`,`allow_gift`,`allow_inventory_stack`,'
            '`interaction_type`,`behaviour_data`,`interaction_modes_count`,`is_rare`) VALUES\n')
    o.write(',\n'.join(
        "    (%d,%s,%s,'%s',%d,%d,%s,'1','%d','%d',%d,'0','1','0','1','1','default',0,1,'%d')"
        % (r['id'], esc(r['classname']), esc(r['name']), r['type'], r['x'], r['y'], r['z'],
           r['sit'], r['walk'], r['sprite'], r['rare'])
        for r in rows) + ';\n\n')

    page_expr = {'nft': '@nft', 'wired_addons': '@waddons', 'wired_effects': '@wfx',
                 'halloween:2026': '@h26'}
    for where, group in sorted(groups.items()):
        expr = page_expr.get(where)
        if expr is None:
            print('no target for %s (%d items) - skipped' % (where, len(group)))
            continue
        o.write('-- %s (%d)\n' % (where, len(group)))
        o.write('INSERT INTO `catalog_items` (`page_id`,`item_id`,`catalog_name`,`cost_credits`,'
                '`cost_pixels`,`cost_diamonds`,`amount`,`limited_sells`,`limited_stack`,'
                '`offer_active`,`extradata`,`badge`,`offer_id`)\n')
        # UNION ALL, not commas: these are SELECT statements, not VALUES rows.
        # The WHERE guard means a missing target page skips its items rather
        # than inserting them onto page 0.
        o.write('\nUNION ALL\n'.join(
            "SELECT %s, '%d', %s, %d, 0, 0, 1, 0, 0, '1', '', '', -1 FROM DUAL WHERE %s IS NOT NULL"
            % (expr, r['id'], esc(r['name']), r['price'], expr) for r in group))
        o.write(';\n\n')

print('items: %d over %d bundles (ids %d-%d)' % (len(rows), len(bundles), FURNI_BASE, FURNI_BASE + len(rows) - 1))
print('bundles copied: %d | icons copied: %d (missing %d)' % (copied_b, copied_i, missing_i))
print('gamedata fragment: +%d furnitype, +%d texts' % (added_fd, added_et))
for where, group in sorted(groups.items()):
    print('   %-16s %d  e.g. %s' % (where, len(group), group[0]['name']))
