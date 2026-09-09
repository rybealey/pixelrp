#!/usr/bin/env python3
"""Import the Habba Customs "Building" packs into Builders > Construction.

The same process as import-designer-furni.py, sharing its machinery through
furni_bundle.py; only the shape of the target differs.

Where the designer import hung a page per designer off an existing parent, this
one CREATES its parent - Builders > Construction - and the download's own top
level becomes its children:

    Building/Alphabet/Letter A/*.nitro  -> Construction > Alphabet > Letter A
    Building/Custom Alphabets/*.nitro   -> Construction > Custom Alphabets

It also renames Designer Furni to Designer and puts Construction directly below
it, so the tab reads as two plain categories.

Emits, exactly as the designer import does:
  emulator/Resources/SQLs/Updates/93_ConstructionFurni.sql
  nitro/overrides/bundled/furniture/<classname>.nitro   (re-encoded, zlib)
  nitro/overrides/dcr/hof_furni/icons/<classname>_icon.png
  nitro/overrides/gamedata-merge/{FurnitureData,ExternalTexts}.json
  docker/nitro/construction-furni/furnidata-entries.json

Furni whose bundle carries no icon frame are left for
synthesize-furni-icons.py, which draws one from the sprite.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furni_bundle as fb

ROOT = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1
                          else '~/Downloads/Habba Customs/Building')
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SQL_OUT = os.path.join(REPO, 'emulator/Resources/SQLs/Updates/93_ConstructionFurni.sql')
RECORD_OUT = os.path.join(REPO, 'docker/nitro/construction-furni/furnidata-entries.json')
MERGE_FURNI = os.path.join(REPO, 'nitro/overrides/gamedata-merge/FurnitureData.json')
MERGE_TEXTS = os.path.join(REPO, 'nitro/overrides/gamedata-merge/ExternalTexts.json')
BUNDLE_OUT = os.path.join(REPO, 'nitro/overrides/bundled/furniture')
ICON_OUT = os.path.join(REPO, 'nitro/overrides/dcr/hof_furni/icons')
SQL_SOURCES = [
    os.path.join(REPO, 'emulator/Resources/SQLs/Original Database.sql'),
    os.path.join(REPO, 'emulator/Resources/SQLs/Updates/31_FullFurniLibrary.sql'),
    os.path.join(REPO, 'emulator/Resources/SQLs/Updates/84_KasjaFurniture.sql'),
    os.path.join(REPO, 'emulator/Resources/SQLs/Updates/85_HabboFurniSync.sql'),
    os.path.join(REPO, 'emulator/Resources/SQLs/Updates/92_DesignerFurni.sql'),
]

FURNI_BASE = 104297        # 92_DesignerFurni ended at 104296
PAGE_BASE = 943000         # 942xxx is the designer import's
CONSTRUCTION_PAGE = 943000
DESIGNER_FURNI_PAGE = 941000
ROWS_PER_INSERT = 400


def is_dir_entry(name):
    return not name.startswith('.') and not name.startswith('_')


def subfolders(folder):
    return sorted(d for d in os.listdir(folder)
                  if is_dir_entry(d) and os.path.isdir(os.path.join(folder, d)))


existing = fb.existing_classnames(SQL_SOURCES)
source_items = fb.load_items_json(ROOT)

rows, pages = [], []
seen, skipped_existing, no_dims, no_icon = set(), [], [], []
guessed = {'sit': [], 'walk': []}
os.makedirs(BUNDLE_OUT, exist_ok=True)
os.makedirs(ICON_OUT, exist_ok=True)


def read_folder(folder):
    """New bundles sitting directly in `folder`, parsed, re-encoded, icon cropped."""
    files = sorted(f for f in os.listdir(folder) if f.endswith('.nitro'))
    classnames = [f[:-6] for f in files]
    prefix = fb.common_prefix(classnames) if len(classnames) > 1 else ''
    found = []
    for fn in files:
        classname = fn[:-6]
        if classname in existing or classname in seen:
            skipped_existing.append(classname)
            continue
        seen.add(classname)
        furni = fb.read_furni(os.path.join(folder, fn))
        if not furni['has_dims']:
            no_dims.append(classname)
        source = source_items.get(classname) or {}
        name = fb.pretty(source.get('name') or classname, prefix)
        desc = fb.pretty(source['description'], prefix) if source.get('description') else name
        sit = bool(fb.SEAT.search(classname))
        walk = furni['z'] <= 0.05 and bool(fb.GROUND.search(classname))
        if sit:
            guessed['sit'].append(classname)
        if walk:
            guessed['walk'].append(classname)
        fb.write_bundle(os.path.join(BUNDLE_OUT, fn), furni['entries'])
        if not (furni['icon_frame'] and fb.crop_icon(
                furni['entries'], furni['png'], furni['icon_frame'],
                os.path.join(ICON_OUT, '%s_icon.png' % classname))):
            no_icon.append(classname)
        found.append({
            'classname': classname, 'name': name, 'desc': desc,
            'x': furni['x'], 'y': furni['y'], 'z': furni['z'],
            'sit': sit, 'walk': walk, 'modes': furni['modes'],
        })
    return found


def survey(folder):
    """The folder tree, depth-first; a folder with nothing new returns None."""
    items = read_folder(folder)
    children = [c for c in (survey(os.path.join(folder, sub)) for sub in subfolders(folder)) if c]
    if not items and not children:
        return None
    return {'name': os.path.basename(folder), 'items': items, 'children': children}


fid, pid = FURNI_BASE, PAGE_BASE + 1     # PAGE_BASE itself is Construction


def emit(tree, parent, order):
    global fid, pid
    page = pid
    pid += 1
    pages.append((page, parent, tree['name'], order))
    for item in tree['items']:
        rows.append(dict(item, id=fid, page=page))
        fid += 1
    for n, child in enumerate(tree['children']):
        emit(child, page, n + 1)


tree = survey(ROOT)
if tree is None:
    raise SystemExit('nothing new in %s' % ROOT)

# The download's root IS Construction, so its own loose files sell on that page
# and its top-level folders are the categories under it.
for item in tree['items']:
    rows.append(dict(item, id=fid, page=CONSTRUCTION_PAGE))
    fid += 1
for n, child in enumerate(tree['children']):
    emit(child, CONSTRUCTION_PAGE, n + 1)


# ---- gamedata ---------------------------------------------------------------

furnitype = [{
    'id': r['id'], 'classname': r['classname'], 'revision': 0,
    'category': 'construction', 'defaultdir': 0, 'xdim': r['x'], 'ydim': r['y'],
    'partcolors': {'color': []}, 'name': r['name'], 'description': r['desc'],
    'adurl': '', 'offerid': -1, 'buyout': False, 'rentofferid': -1,
    'rentbuyout': False, 'bc': False, 'excludeddynamic': False, 'customparams': '',
    'specialtype': 1, 'canstandon': r['walk'], 'cansiton': r['sit'], 'canlayon': False,
    'furniline': 'construction',
} for r in rows]
texts = {}
for r in rows:
    texts['%s_name' % r['classname']] = r['name']
    texts['%s_desc' % r['classname']] = r['desc']

os.makedirs(os.path.dirname(RECORD_OUT), exist_ok=True)
json.dump({'furnitype': furnitype, 'externaltexts': texts}, open(RECORD_OUT, 'w'), indent=1)

merged = json.load(open(MERGE_FURNI, encoding='utf-8'))
have = {e['classname'] for e in merged['roomitemtypes']['furnitype']}
merged['roomitemtypes']['furnitype'].extend(e for e in furnitype if e['classname'] not in have)
json.dump(merged, open(MERGE_FURNI, 'w', encoding='utf-8'))

merged_texts = json.load(open(MERGE_TEXTS, encoding='utf-8'))
for key, value in texts.items():
    merged_texts.setdefault(key, value)
json.dump(merged_texts, open(MERGE_TEXTS, 'w', encoding='utf-8'), indent=1)


# ---- SQL --------------------------------------------------------------------

def esc(value):
    return "'%s'" % str(value).replace('\\', '\\\\').replace("'", "\\'")


def chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


last_fid = FURNI_BASE + len(rows) - 1
with open(SQL_OUT, 'w', encoding='utf-8') as o:
    o.write("""\
-- PixelRP: the Habba Customs building sets, in Builders > Construction.
--
-- %d building pieces - alphabets, blocks, figures and tiles - under a new
-- Construction category, laid out as the download folder is: its top level
-- becomes the pages under Construction, and a folder's own subfolders are
-- pages under that (Alphabet > Letter A). Generated by
-- docker/nitro/import-building-furni.py; the machinery it shares with the
-- designer import lives in docker/nitro/furni_bundle.py.
--
-- Designer Furni is renamed Designer here and Construction sits directly below
-- it, so the tab reads as two plain categories rather than one long name and
-- one short one.
--
-- The rendering half is the .nitro bundles, the icons and the FurnitureData
-- entries under nitro/overrides/; the rows below are inert without them.
--
-- Everything is free - the catalog has been since 90_FreeCatalog.
--
-- Idempotent: fixed id ranges, cleared before insert. The rename is written
-- as an id-first update so a re-run after it has happened is a no-op.

SET @builders := COALESCE(
    (SELECT `id` FROM `catalog_pages` WHERE `parent_id` = -1 AND `caption` = 'Builders' LIMIT 1),
    912362);
SET @designer := COALESCE(
    (SELECT `id` FROM `catalog_pages` WHERE `id` = %d LIMIT 1),
    (SELECT `id` FROM `catalog_pages` WHERE `caption` IN ('Designer Furni', 'Designer')
        ORDER BY `id` LIMIT 1));

-- Designer Furni -> Designer. Resolved above by id, so this still finds the
-- page after it has already been renamed.
UPDATE `catalog_pages` SET `caption` = 'Designer' WHERE `id` = @designer;

-- Construction goes directly below Designer; Habba Creators (89, still dark)
-- moves down one so nothing shares an order_num with it.
SET @designer_order := COALESCE((SELECT `order_num` FROM `catalog_pages` WHERE `id` = @designer), 1004);
UPDATE `catalog_pages` SET `order_num` = @designer_order + 2
    WHERE `parent_id` = @builders AND `caption` = 'Habba Creators';

DELETE FROM `catalog_items` WHERE `item_id` BETWEEN %d AND %d;
DELETE FROM `catalog_pages` WHERE `id` BETWEEN %d AND %d;
DELETE FROM `furniture` WHERE `id` BETWEEN %d AND %d;

INSERT INTO `catalog_pages`
    (`id`,`parent_id`,`caption`,`icon_image`,`min_rank`,`min_vip`,`order_num`,`page_link`,
     `page_layout`,`page_strings_1`,`page_strings_2`,`visible`,`enabled`)
VALUES
    (%d, @builders, 'Construction', 193, 2, 0, @designer_order + 1, '', 'default_3x3', '', '', b'1', b'1');

""" % (len(rows), DESIGNER_FURNI_PAGE, FURNI_BASE, last_fid, PAGE_BASE, PAGE_BASE + 999,
       FURNI_BASE, last_fid, CONSTRUCTION_PAGE))

    o.write('INSERT INTO `catalog_pages` (`id`,`parent_id`,`caption`,`icon_image`,`min_rank`,'
            '`min_vip`,`order_num`,`page_link`,`page_layout`,`page_strings_1`,`page_strings_2`,'
            '`visible`,`enabled`) VALUES\n')
    o.write(',\n'.join(
        "    (%d,%d,%s,193,2,0,%d,'','default_3x3','','',b'1',b'1')"
        % (page, parent, esc(caption), order) for page, parent, caption, order in pages) + ';\n')

    o.write('\n-- Furniture. id == sprite_id, the convention every custom line here follows;\n'
            "-- interaction_modes_count is the bundle's own animation count.\n")
    for batch in chunks(rows, ROWS_PER_INSERT):
        o.write('INSERT INTO `furniture` (`id`,`item_name`,`public_name`,`type`,`width`,`length`,'
                '`stack_height`,`can_stack`,`can_sit`,`is_walkable`,`sprite_id`,`allow_recycle`,'
                '`allow_trade`,`allow_marketplace_sell`,`allow_gift`,`allow_inventory_stack`,'
                '`interaction_type`,`behaviour_data`,`interaction_modes_count`,`is_rare`) VALUES\n')
        o.write(',\n'.join(
            "    (%d,%s,%s,'s',%d,%d,%s,'1','%d','%d',%d,'0','1','0','1','1','default',0,%d,'0')"
            % (r['id'], esc(r['classname']), esc(r['name']), r['x'], r['y'], r['z'],
               r['sit'], r['walk'], r['id'], r['modes'])
            for r in batch) + ';\n')

    o.write('\n')
    for batch in chunks(rows, ROWS_PER_INSERT):
        o.write('INSERT INTO `catalog_items` (`page_id`,`item_id`,`catalog_name`,`cost_credits`,'
                '`cost_pixels`,`cost_diamonds`,`amount`,`limited_sells`,`limited_stack`,'
                '`offer_active`,`extradata`,`badge`,`offer_id`) VALUES\n')
        o.write(',\n'.join(
            "    (%d,'%d',%s,0,0,0,1,0,0,'1','','',-1)" % (r['page'], r['id'], esc(r['name']))
            for r in batch) + ';\n')

print('pages: %d   furni: %d   ids %d-%d   pages %d-%d'
      % (len(pages) + 1, len(rows), FURNI_BASE, last_fid, PAGE_BASE, pid - 1))
print('skipped (already in furniture, or a duplicate in the download): %d' % len(skipped_existing))
print('no dimensions in bundle (defaulted 1x1, z 1.0): %d' % len(no_dims))
print('no icon frame - synthesize-furni-icons.py draws these: %d' % len(no_icon))
print('inferred can_sit: %d   is_walkable: %d' % (len(guessed['sit']), len(guessed['walk'])))
json.dump({'no_dims': no_dims, 'no_icon': no_icon, 'skipped': skipped_existing,
           'sit': guessed['sit'], 'walk': guessed['walk']},
          open(os.path.join(os.path.dirname(RECORD_OUT), 'import-report.json'), 'w'), indent=1)
