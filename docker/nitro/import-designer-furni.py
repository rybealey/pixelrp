#!/usr/bin/env python3
"""Import the Habba Customs "Designer Furni" packs into Builders > Designer Furni.

Reads the download (default "~/Downloads/Habba Customs/Designer Furni"), whose
folder tree IS the catalog tree:

    <Designer>/                 -> a page under Builders > Designer Furni
    <Designer>/<Pack>/          -> a page under that designer
    <Designer>/*.nitro          -> sold on the designer's own page (loose files)

and emits everything the hotel needs to sell and draw them:

  emulator/Resources/SQLs/Updates/92_DesignerFurni.sql
      furniture rows, the designer and pack pages, one catalog row per furni.
  nitro/overrides/bundled/furniture/<classname>.nitro
      the bundles, re-encoded. The download mixes two compressions (about half
      the entries are gzip, the rest zlib); the client's inflater takes both,
      but every bundle we ship is zlib and a mixed tree is a debugging trap, so
      they are normalised on the way in.
  nitro/overrides/dcr/hof_furni/icons/<classname>_icon.png
      cropped out of each bundle's spritesheet (the `_icon_a` frame). The
      client reads the icon from this static path, never from the bundle - see
      import-kasja.py for how that was learned. Bundles with no icon frame are
      listed at the end of a run; those tiles are blank in the shop.
  nitro/overrides/gamedata-merge/{FurnitureData,ExternalTexts}.json
      the entries the client needs to recognise the classnames, appended to the
      shipped fragment (apply-gamedata-fragments.py merges it on the server).
      docker/nitro/designer-furni/furnidata-entries.json keeps this import's
      own entries as a record, the way kasja/ does.

Unlike the Kasja SWFs these are already .nitro bundles, so the furni's own
definition is read from the bundle JSON: logic.model.dimensions for x/y/z, the
64-size visualization's animation count for interaction_modes_count. Alongside
each folder the download carries an _items.json - the source hotel's catalog
export - which supplies the display name and description where it has one.

Two fields nothing records and that are inferred, exactly as for Kasja:
can_sit from seat words in the classname (English and French - "habbox_" is a
French hotel's prefix), is_walkable from a flat z AND a ground word.

Skipped, and counted: a classname the hotel already has (the Kasja packs
overlap 84_KasjaFurniture by 175 items - only Kasja's genuinely new packs are
added, under the existing Kasja page), and a bundle that appears in two folders
(kept where it is first met, walking designers then packs alphabetically).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furni_bundle as fb

ROOT = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1
                          else '~/Downloads/Habba Customs/Designer Furni')
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SQL_OUT = os.path.join(REPO, 'emulator/Resources/SQLs/Updates/92_DesignerFurni.sql')
RECORD_OUT = os.path.join(REPO, 'docker/nitro/designer-furni/furnidata-entries.json')
MERGE_FURNI = os.path.join(REPO, 'nitro/overrides/gamedata-merge/FurnitureData.json')
MERGE_TEXTS = os.path.join(REPO, 'nitro/overrides/gamedata-merge/ExternalTexts.json')
BUNDLE_OUT = os.path.join(REPO, 'nitro/overrides/bundled/furniture')
ICON_OUT = os.path.join(REPO, 'nitro/overrides/dcr/hof_furni/icons')
SQL_SOURCES = [
    os.path.join(REPO, 'emulator/Resources/SQLs/Original Database.sql'),
    os.path.join(REPO, 'emulator/Resources/SQLs/Updates/31_FullFurniLibrary.sql'),
    os.path.join(REPO, 'emulator/Resources/SQLs/Updates/84_KasjaFurniture.sql'),
    os.path.join(REPO, 'emulator/Resources/SQLs/Updates/85_HabboFurniSync.sql'),
]

FURNI_BASE = 100277        # 85_HabboFurniSync ended at 100276
PAGE_BASE = 942000         # 940xxx is Kasja's, 941000/941001 are 89's
DESIGNER_FURNI_PAGE = 941000
KASJA_PAGE = 940002
KASJA_FIRST_FREE_ORDER = 10   # 84 laid Kasja's packs out at 1-9
ROWS_PER_INSERT = 400



def is_dir_entry(name):
    return not name.startswith('.') and not name.startswith('_')


def subfolders(folder):
    return sorted(d for d in os.listdir(folder)
                  if is_dir_entry(d) and os.path.isdir(os.path.join(folder, d)))


existing = fb.existing_classnames(SQL_SOURCES)
source_items = fb.load_items_json(ROOT)

rows, pages = [], []
seen, skipped_existing, skipped_dupe, no_dims, no_icon = set(), [], [], [], []
guessed = {'sit': [], 'walk': []}
os.makedirs(BUNDLE_OUT, exist_ok=True)
os.makedirs(ICON_OUT, exist_ok=True)


def read_folder(folder):
    """New bundles sitting directly in `folder`, in classname order.

    Everything expensive happens here - the bundle is parsed, re-encoded and
    its icon cropped - so it runs exactly once per file, during the survey.
    Which page the furni ends up on is decided afterwards.
    """
    files = sorted(f for f in os.listdir(folder) if f.endswith('.nitro'))
    classnames = [f[:-6] for f in files]
    prefix = fb.common_prefix(classnames) if len(classnames) > 1 else ''
    found = []
    for fn in files:
        classname = fn[:-6]
        if classname in existing:
            skipped_existing.append(classname)
            continue
        if classname in seen:
            skipped_dupe.append(classname)
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
        if not (furni['icon_frame'] and fb.crop_icon(furni['entries'], furni['png'],
                                                  furni['icon_frame'],
                                                  os.path.join(ICON_OUT, '%s_icon.png' % classname))):
            no_icon.append(classname)
        found.append({
            'classname': classname, 'name': name, 'desc': desc,
            'x': furni['x'], 'y': furni['y'], 'z': furni['z'],
            'sit': sit, 'walk': walk, 'modes': furni['modes'],
        })
    return found


def survey(folder):
    """The folder tree as a tree of {name, items, children}, depth-first.

    A folder with nothing new anywhere beneath it comes back as None and so
    never becomes a page - which is what keeps the Kasja packs 84 already
    imported from reappearing as empty categories.
    """
    items = read_folder(folder)
    children = [c for c in (survey(os.path.join(folder, sub)) for sub in subfolders(folder)) if c]
    if not items and not children:
        return None
    return {'name': os.path.basename(folder), 'items': items, 'children': children}


# The download's tree IS the catalog tree, at any depth: Mathias nests
# Plants > Plants I / Plants II, and that third level is a page too.
designers = [(d, survey(os.path.join(ROOT, d)))
             for d in sorted(x for x in os.listdir(ROOT)
                             if is_dir_entry(x) and os.path.isdir(os.path.join(ROOT, x)))]
designers = [(name, tree) for name, tree in designers if tree]

fid, pid = FURNI_BASE, PAGE_BASE


def emit(tree, parent, designer, order):
    """Give this folder a page, its items rows, then the same to its children."""
    global fid, pid
    page = pid
    pid += 1
    pages.append((page, parent, tree['name'], order))
    for item in tree['items']:
        rows.append(dict(item, id=fid, page=page, designer=designer))
        fid += 1
    for n, child in enumerate(tree['children']):
        emit(child, page, designer, n + 1)


designer_order = 2                 # Kasja is 1 (89_BuildersDesignerFurni)
for name, tree in designers:
    if name == 'Kasja':
        # 84 built Kasja's page and its packs. Only the packs it does not have
        # get a page here, hung off the existing Kasja page and continuing its
        # order - the designer folder itself is not a second Kasja page.
        for n, child in enumerate(tree['children']):
            emit(child, 'KASJA', name, KASJA_FIRST_FREE_ORDER + n)
        if tree['items']:
            for item in tree['items']:
                rows.append(dict(item, id=fid, page='KASJA_PAGE', designer=name))
                fid += 1
        continue
    emit(tree, 'DESIGNER', name, designer_order)
    designer_order += 1


# ---- gamedata ---------------------------------------------------------------

def slug(text):
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')


furnitype = [{
    'id': r['id'], 'classname': r['classname'], 'revision': 0,
    'category': 'designer', 'defaultdir': 0, 'xdim': r['x'], 'ydim': r['y'],
    'partcolors': {'color': []}, 'name': r['name'], 'description': r['desc'],
    'adurl': '', 'offerid': -1, 'buyout': False, 'rentofferid': -1,
    'rentbuyout': False, 'bc': False, 'excludeddynamic': False, 'customparams': '',
    'specialtype': 1, 'canstandon': r['walk'], 'cansiton': r['sit'], 'canlayon': False,
    'furniline': 'designer_%s' % slug(r['designer']),
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
-- PixelRP: the Habba Customs Designer Furni packs, in Builders > Designer Furni.
--
-- %d custom furni from %d designers, laid out exactly as the download folder
-- is: a page per designer under Designer Furni (the parent 89 created), a page
-- per pack under its designer, and a designer's loose files sold on the
-- designer's own page. Kasja's three packs 84 did not have (CF, Farm, Teddy
-- Bears) join the existing Kasja page; its other packs were already imported
-- and are skipped. Generated by docker/nitro/import-designer-furni.py, which
-- reads each bundle's own model for its dimensions and state count - see that
-- file for the two fields (can_sit, is_walkable) that are inferred.
--
-- The rendering half is the .nitro bundles, the icons and the FurnitureData
-- entries, all under nitro/overrides/; the rows below are inert without them.
--
-- Everything is free - the catalog has been since 90_FreeCatalog.
--
-- Idempotent: fixed id ranges, cleared before insert. Resolved by id first and
-- caption second, the way 89 resolves Kasja, so a re-run after the pages have
-- been renamed still finds them.

SET @designer := COALESCE(
    (SELECT `id` FROM `catalog_pages` WHERE `id` = %d AND `caption` = 'Designer Furni' LIMIT 1),
    (SELECT `id` FROM `catalog_pages` WHERE `caption` = 'Designer Furni' ORDER BY `id` LIMIT 1),
    %d);
SET @kasja := COALESCE(
    (SELECT `id` FROM `catalog_pages` WHERE `id` = %d AND `caption` = 'Kasja' LIMIT 1),
    (SELECT `id` FROM `catalog_pages` WHERE `caption` = 'Kasja' ORDER BY `id` LIMIT 1),
    @designer);

DELETE FROM `catalog_items` WHERE `item_id` BETWEEN %d AND %d;
DELETE FROM `catalog_pages` WHERE `id` BETWEEN %d AND %d;
DELETE FROM `furniture` WHERE `id` BETWEEN %d AND %d;

""" % (len(rows), len({r['designer'] for r in rows}),
       DESIGNER_FURNI_PAGE, DESIGNER_FURNI_PAGE, KASJA_PAGE,
       FURNI_BASE, last_fid, PAGE_BASE, PAGE_BASE + 999, FURNI_BASE, last_fid))

    o.write('INSERT INTO `catalog_pages` (`id`,`parent_id`,`caption`,`icon_image`,`min_rank`,'
            '`min_vip`,`order_num`,`page_link`,`page_layout`,`page_strings_1`,`page_strings_2`,'
            '`visible`,`enabled`) VALUES\n')
    lines = []
    for page, parent, caption, order in pages:
        par = {'DESIGNER': '@designer', 'KASJA': '@kasja'}.get(parent, str(parent))
        lines.append("    (%d,%s,%s,193,2,0,%d,'','default_3x3','','',b'1',b'1')"
                     % (page, par, esc(caption), order))
    o.write(',\n'.join(lines) + ';\n')

    o.write('\n-- Furniture. id == sprite_id, the convention every custom line here follows;\n'
            '-- interaction_modes_count is the bundle\'s own animation count, so a furni\n'
            '-- with states cycles through them on double-click.\n')
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
            "    (%s,'%d',%s,0,0,0,1,0,0,'1','','',-1)"
            % (('@kasja' if r['page'] == 'KASJA_PAGE' else r['page']), r['id'], esc(r['name']))
            for r in batch) + ';\n')

print('designers: %d   pages: %d   furni: %d   ids %d-%d   pages %d-%d'
      % (len({r['designer'] for r in rows}), len(pages), len(rows), FURNI_BASE, last_fid,
         PAGE_BASE, pid - 1))
print('skipped: %d already in furniture, %d duplicates within the download'
      % (len(skipped_existing), len(skipped_dupe)))
print('no dimensions in bundle (defaulted 1x1, z 1.0): %d  %s'
      % (len(no_dims), ' '.join(no_dims[:6])))
print('no icon frame (blank tile in the shop): %d  %s' % (len(no_icon), ' '.join(no_icon[:6])))
print('inferred can_sit: %d   is_walkable: %d' % (len(guessed['sit']), len(guessed['walk'])))
json.dump({'no_dims': no_dims, 'no_icon': no_icon, 'skipped_dupe': skipped_dupe,
           'sit': guessed['sit'], 'walk': guessed['walk']},
          open(os.path.join(os.path.dirname(RECORD_OUT), 'import-report.json'), 'w'), indent=1)
