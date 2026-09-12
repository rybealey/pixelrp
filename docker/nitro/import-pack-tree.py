#!/usr/bin/env python3
"""Import a Habba Customs pack tree into a new Builders category.

One download, one new category page: the download's root IS the category, its
top-level folders are the pages under it, and their subfolders are pages under
those - at whatever depth the download goes to. Two packs use this:

    construction   ~/Downloads/Habba Customs/Building        -> Builders > Construction
    customs        ~/Downloads/Habba Customs/Custom Furnis   -> Builders > Customs

    python3 docker/nitro/import-pack-tree.py construction [root]
    python3 docker/nitro/import-pack-tree.py customs      [root]

The bundle machinery is shared with import-designer-furni.py through
furni_bundle.py; that import keeps its own script because it hangs a page per
designer off an EXISTING parent and carries the Kasja exception.

Emits, per pack:
  emulator/Resources/SQLs/Updates/<n>_<Name>.sql
  nitro/overrides/bundled/furniture/<classname>.nitro   (re-encoded, zlib)
  nitro/overrides/dcr/hof_furni/icons/<classname>_icon.png
  nitro/overrides/gamedata-merge/{FurnitureData,ExternalTexts}.json
  docker/nitro/<pack>-furni/furnidata-entries.json

Subcategories come out alphabetically, because the folders are walked sorted.
Furni whose bundle carries no icon frame are left for
synthesize-furni-icons.py, which draws one from the sprite.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furni_bundle as fb

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def repo(*parts):
    return os.path.join(REPO, *parts)


# `prologue` is the only substantial difference between the two: it creates the
# category page and settles where it sits among its siblings.
CONSTRUCTION_PROLOGUE = """\
SET @builders := COALESCE(
    (SELECT `id` FROM `catalog_pages` WHERE `parent_id` = -1 AND `caption` = 'Builders' LIMIT 1),
    912362);
SET @designer := COALESCE(
    (SELECT `id` FROM `catalog_pages` WHERE `id` = 941000 LIMIT 1),
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
"""

CUSTOMS_PROLOGUE = """\
SET @builders := COALESCE(
    (SELECT `id` FROM `catalog_pages` WHERE `parent_id` = -1 AND `caption` = 'Builders' LIMIT 1),
    912362);
SET @designer := COALESCE(
    (SELECT `id` FROM `catalog_pages` WHERE `id` = 941000 LIMIT 1),
    (SELECT `id` FROM `catalog_pages` WHERE `caption` IN ('Designer Furni', 'Designer')
        ORDER BY `id` LIMIT 1));
SET @construction := COALESCE(
    (SELECT `id` FROM `catalog_pages` WHERE `id` = 943000 LIMIT 1),
    (SELECT `id` FROM `catalog_pages` WHERE `caption` = 'Construction' ORDER BY `id` LIMIT 1));

-- The three custom categories read Construction, Customs, Designer, in that
-- order, anchored to wherever Designer already sat so the groups above them
-- (Cartier, Club and their dividers) are untouched.
SET @base := COALESCE((SELECT `order_num` FROM `catalog_pages` WHERE `id` = @designer), 1004);
UPDATE `catalog_pages` SET `order_num` = @base WHERE `id` = @construction;
UPDATE `catalog_pages` SET `order_num` = @base + 2 WHERE `id` = @designer;
UPDATE `catalog_pages` SET `order_num` = @base + 3
    WHERE `parent_id` = @builders AND `caption` = 'Habba Creators';
"""

BSSTONINO_PROLOGUE = """\
SET @builders := COALESCE(
    (SELECT `id` FROM `catalog_pages` WHERE `parent_id` = -1 AND `caption` = 'Builders' LIMIT 1),
    912362);
SET @customs := COALESCE(
    (SELECT `id` FROM `catalog_pages` WHERE `id` = 944000 LIMIT 1),
    (SELECT `id` FROM `catalog_pages` WHERE `caption` = 'Customs' AND `parent_id` = @builders
        ORDER BY `id` LIMIT 1));
"""

BSSTONINO_EPILOGUE = """\
-- Every set under Customs renumbered alphabetically, which is both how
-- 95_CatalogAlphabetical left this tab and the only way to slot a new one in
-- without drifting. An earlier draft nudged the siblings after Bsstonino down
-- by one, which is correct exactly once: a second run nudges them again.
-- Assigning absolute positions from the captions that are there lands the same
-- way however many times it runs.
SET @n := 0;
UPDATE `catalog_pages` SET `order_num` = (@n := @n + 1)
    WHERE `parent_id` = @customs
    ORDER BY `caption`;
"""

PACKS = {
    'construction': {
        'root': '~/Downloads/Habba Customs/Building',
        'caption': 'Construction',
        'sql': repo('emulator/Resources/SQLs/Updates/93_ConstructionFurni.sql'),
        'record_dir': repo('docker/nitro/construction-furni'),
        'furni_base': 104297,      # 92_DesignerFurni ended at 104296
        'page_base': 943000,       # 942xxx is the designer import's
        'category': 'construction',
        'furniline': 'construction',
        'prologue': CONSTRUCTION_PROLOGUE,
        'order_sql': '@designer_order + 1',
        'idempotence': 'The rename is written\n-- as an id-first update so a re-run after it has happened is a no-op.',
        'title': 'the Habba Customs building sets, in Builders > Construction',
        'blurb': """\
-- %(count)d building pieces - alphabets, blocks, figures and tiles - under a new
-- Construction category, laid out as the download folder is: its top level
-- becomes the pages under Construction, and a folder's own subfolders are
-- pages under that (Alphabet > Letter A). Generated by
-- docker/nitro/import-pack-tree.py; the machinery it shares with the
-- designer import lives in docker/nitro/furni_bundle.py.
--
-- Designer Furni is renamed Designer here and Construction sits directly below
-- it, so the tab reads as two plain categories rather than one long name and
-- one short one.""",
    },
    'bsstonino': {
        'root': '~/Documents/Codex/2026-09-08/bu/outputs/Habba Customs/Miscellaneous Furni/Bsstonino',
        'caption': 'Bsstonino',
        'sql': repo('emulator/Resources/SQLs/Updates/122_BsstoninoFurni.sql'),
        'record_dir': repo('docker/nitro/bsstonino-furni'),
        'furni_base': 108000,      # 115_BankTellerBot took the highest before this, 107500
        'page_base': 945000,       # 944xxx is the Customs import's
        'category': 'customs',
        'furniline': 'customs',
        'prologue': BSSTONINO_PROLOGUE,
        'parent_sql': '@customs',
        'order_sql': '1',     # the epilogue's renumber is what actually places it
        'epilogue': BSSTONINO_EPILOGUE,
        'idempotence': "The sets under Customs are\n-- renumbered alphabetically at the end, which lands the same way every run.",
        'title': "Bsstonino's furni, in Builders > Customs",
        'blurb': """\
-- %(count)d pieces across eleven sub-packs, hung under the EXISTING Customs
-- category rather than making a twelfth top-level one - it is one creator's
-- work, not a theme. Generated by docker/nitro/import-pack-tree.py.
--
-- The pack's own manifests carry no real names: every item's `name` is its
-- classname and its description is that plus _desc, so the titles below are
-- derived from the classnames and read 'Furni 2429'. That is what the download
-- contains; inventing nicer ones would be inventing, not importing.""",
    },
    'customs': {
        'root': '~/Downloads/Habba Customs/Custom Furnis',
        'caption': 'Customs',
        'sql': repo('emulator/Resources/SQLs/Updates/94_CustomsFurni.sql'),
        'record_dir': repo('docker/nitro/customs-furni'),
        'furni_base': 104530,      # 93_ConstructionFurni ended at 104529
        'page_base': 944000,       # 943xxx is Construction's
        'category': 'customs',
        'furniline': 'customs',
        'prologue': CUSTOMS_PROLOGUE,
        'order_sql': '@base + 1',
        'idempotence': 'The ordering is written as\n-- absolute updates off Designer\'s slot, so a re-run lands the same way.',
        'title': 'the Habba Customs themed sets, in Builders > Customs',
        'blurb': """\
-- %(count)d themed custom furni - fifty-odd sets, from Animal Crossing to a fuel
-- station - under a new Customs category, laid out as the download folder is:
-- its top level becomes the pages under Customs, and a set's own subfolders are
-- pages under that. Generated by docker/nitro/import-pack-tree.py.
--
-- Customs sits between Construction and Designer, so the three custom
-- categories read Construction, Customs, Designer.""",
    },
}

MERGE_FURNI = repo('nitro/overrides/gamedata-merge/FurnitureData.json')
MERGE_TEXTS = repo('nitro/overrides/gamedata-merge/ExternalTexts.json')
BUNDLE_OUT = repo('nitro/overrides/bundled/furniture')
ICON_OUT = repo('nitro/overrides/dcr/hof_furni/icons')
SQL_SOURCES = [
    repo('emulator/Resources/SQLs/Original Database.sql'),
    repo('emulator/Resources/SQLs/Updates/31_FullFurniLibrary.sql'),
    repo('emulator/Resources/SQLs/Updates/84_KasjaFurniture.sql'),
    repo('emulator/Resources/SQLs/Updates/85_HabboFurniSync.sql'),
    repo('emulator/Resources/SQLs/Updates/92_DesignerFurni.sql'),
    repo('emulator/Resources/SQLs/Updates/93_ConstructionFurni.sql'),
    repo('emulator/Resources/SQLs/Updates/94_CustomsFurni.sql'),
    repo('emulator/Resources/SQLs/Updates/115_BankTellerBot.sql'),
]
ROWS_PER_INSERT = 400

if len(sys.argv) < 2 or sys.argv[1] not in PACKS:
    raise SystemExit('usage: import-pack-tree.py {%s} [root]' % '|'.join(sorted(PACKS)))
PACK = PACKS[sys.argv[1]]
ROOT = os.path.expanduser(sys.argv[2] if len(sys.argv) > 2 else PACK['root'])
SQL_OUT = PACK['sql']
RECORD_OUT = os.path.join(PACK['record_dir'], 'furnidata-entries.json')
FURNI_BASE = PACK['furni_base']
PAGE_BASE = PACK['page_base']
CATEGORY_PAGE = PAGE_BASE
# A pack never sees the migration that imports it, only the ones before it.
SQL_SOURCES = [p for p in SQL_SOURCES if os.path.basename(p) != os.path.basename(SQL_OUT)]


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
        # A pack whose manifest has no real text writes the classname into both
        # fields - name "bsstonino_furni2429", description the same plus _desc.
        # Prettifying that placeholder yields "Furni 2429 Desc", which reads as
        # a bug rather than as a description; falling back to the name is what
        # the no-description branch already does.
        raw_desc = source.get('description') or ''
        desc = fb.pretty(raw_desc, prefix) if raw_desc and raw_desc != '%s_desc' % classname else name
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

# The download's root IS the category page, so its own loose files sell there
# and its top-level folders are the pages under it.
for item in tree['items']:
    rows.append(dict(item, id=fid, page=CATEGORY_PAGE))
    fid += 1
for n, child in enumerate(tree['children']):
    emit(child, CATEGORY_PAGE, n + 1)


# ---- gamedata ---------------------------------------------------------------

furnitype = [{
    'id': r['id'], 'classname': r['classname'], 'revision': 0,
    'category': PACK['category'], 'defaultdir': 0, 'xdim': r['x'], 'ydim': r['y'],
    'partcolors': {'color': []}, 'name': r['name'], 'description': r['desc'],
    'adurl': '', 'offerid': -1, 'buyout': False, 'rentofferid': -1,
    'rentbuyout': False, 'bc': False, 'excludeddynamic': False, 'customparams': '',
    'specialtype': 1, 'canstandon': r['walk'], 'cansiton': r['sit'], 'canlayon': False,
    'furniline': PACK['furniline'],
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
-- PixelRP: %(title)s.
--
%(blurb)s
--
-- The rendering half is the .nitro bundles, the icons and the FurnitureData
-- entries under nitro/overrides/; the rows below are inert without them.
--
-- Everything is free - the catalog has been since 90_FreeCatalog.
--
-- Idempotent: fixed id ranges, cleared before insert. %(idempotence)s

%(prologue)s
DELETE FROM `catalog_items` WHERE `item_id` BETWEEN %(first)d AND %(last)d;
DELETE FROM `catalog_pages` WHERE `id` BETWEEN %(page_first)d AND %(page_last)d;
DELETE FROM `furniture` WHERE `id` BETWEEN %(first)d AND %(last)d;

INSERT INTO `catalog_pages`
    (`id`,`parent_id`,`caption`,`icon_image`,`min_rank`,`min_vip`,`order_num`,`page_link`,
     `page_layout`,`page_strings_1`,`page_strings_2`,`visible`,`enabled`)
VALUES
    (%(page)d, %(parent)s, '%(caption)s', 193, 2, 0, %(order)s, '', 'default_3x3', '', '', b'1', b'1');

""" % {
        'title': PACK['title'],
        'blurb': PACK['blurb'] % {'count': len(rows)},
        'idempotence': PACK['idempotence'],
        'prologue': PACK['prologue'],
        'first': FURNI_BASE, 'last': last_fid,
        'page_first': PAGE_BASE, 'page_last': PAGE_BASE + 999,
        'page': CATEGORY_PAGE, 'caption': PACK['caption'], 'order': PACK['order_sql'],
        # A pack normally creates a category directly under the Builders tab.
        # One that extends an existing category names its parent instead.
        'parent': PACK.get('parent_sql', '@builders'),
    })

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

    # Anything that has to run once the pages exist - a pack extending an
    # existing category re-sorts its siblings here.
    if PACK.get('epilogue'):
        o.write('\n' + PACK['epilogue'])

print('pages: %d   furni: %d   ids %d-%d   pages %d-%d'
      % (len(pages) + 1, len(rows), FURNI_BASE, last_fid, PAGE_BASE, pid - 1))
print('skipped (already in furniture, or a duplicate in the download): %d' % len(skipped_existing))
print('no dimensions in bundle (defaulted 1x1, z 1.0): %d' % len(no_dims))
print('no icon frame - synthesize-furni-icons.py draws these: %d' % len(no_icon))
print('inferred can_sit: %d   is_walkable: %d' % (len(guessed['sit']), len(guessed['walk'])))
json.dump({'no_dims': no_dims, 'no_icon': no_icon, 'skipped': skipped_existing,
           'sit': guessed['sit'], 'walk': guessed['walk']},
          open(os.path.join(os.path.dirname(RECORD_OUT), 'import-report.json'), 'w'), indent=1)
