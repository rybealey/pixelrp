#!/usr/bin/env python3
"""Import the furni Zipto sells in its shop, sorted into PixelRP's shop.

    python3 docker/nitro/import-zipto-shop.py [~/Desktop/Zipto Import] [--polar <beta carpet_polar.nitro>]

The input is the `Zipto Import` folder: Zipto's download (scripts/
nitro-asset-downloader) cross-referenced with beta and cut down to the furni
beta does not have - by name, or by picture (the same 64-size sprites in the
same colour). Its `_import.json` lists each furni with the Zipto shop page it
sat on; ROUTES below says where that page goes in PixelRP's shop:

  - into a page we already have, when we already sell the rest of that set
    there (Elven Easter -> Seasonal > Easter > Easter 2026)
  - a new Customs set for another hotel's set (Cokemusic, Christmas Charm...)
  - a new Themes page, or a whole tree of them, for Habbo's own (Habbo Origins
    and its 17 pages, the public rooms we lacked)
  - Staff > Wired > Accessories for the wired tiles, switches and gates
  - nowhere, for Zipto's own wired boxes: our server cannot run them

Only Zipto's SHOP is imported here. The ~25,000 furni Zipto has but does not
sell are left for a set-by-set pick.

Emits:
  emulator/Resources/SQLs/Updates/<n>_ZiptoShopFurni.sql
  nitro/overrides/bundled/furniture/<lib>.nitro          (re-encoded, zlib)
  nitro/overrides/dcr/hof_furni/icons/<classname>_icon.png
  nitro/overrides/c_images/catalogue/icon_<page id>.png  (Zipto's page icons)
  nitro/overrides/gamedata-merge/{FurnitureData,ExternalTexts}.json
  docker/nitro/zipto-furni/{furnidata-entries,import-report}.json

Ids: furni 112000-113999 (id == sprite_id), pages 964000-964999, and a new
page's icon is icon_<its page id>.png.
"""
import collections
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furni_bundle as fb
import zipto_names as zn

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def repo(*parts):
    return os.path.join(REPO, *parts)


SQL_OUT = repo('emulator/Resources/SQLs/Updates/293_ZiptoShopFurni.sql')
RECORD_DIR = repo('docker/nitro/zipto-furni')
MERGE_FURNI = repo('nitro/overrides/gamedata-merge/FurnitureData.json')
MERGE_TEXTS = repo('nitro/overrides/gamedata-merge/ExternalTexts.json')
BUNDLE_OUT = repo('nitro/overrides/bundled/furniture')
ICON_OUT = repo('nitro/overrides/dcr/hof_furni/icons')
PAGE_ICON_OUT = repo('nitro/overrides/c_images/catalogue')
FURNI_FIRST, FURNI_LAST = 112000, 113999
PAGE_FIRST, PAGE_LAST = 964000, 964999
ROWS_PER_INSERT = 400

args = [a for a in sys.argv[1:]]
POLAR_BASE = None
if '--polar' in args:
    i = args.index('--polar')
    POLAR_BASE = os.path.expanduser(args[i + 1])
    del args[i:i + 2]
SRC = os.path.expanduser(args[0] if args else '~/Desktop/Zipto Import')

# Pages that already exist, as (variable, id on beta, caption, parent variable).
# Resolved by id AND caption first, then by caption under the parent, then the
# parent itself - so a database whose ids differ still lands the furni in the
# right set, and one that lacks a page puts them a level up rather than
# failing the deploy on a NULL page_id.
EXISTING = [
    ('builders', 912362, 'Builders', None),
    ('furni', 930209, 'Furni', None),
    ('staff', 930210, 'Staff', None),
    ('seasonal', 2000003, 'Seasonal', 'builders'),
    ('themes', 2000002, 'Themes', 'builders'),
    ('customs', 944000, 'Customs', 'builders'),
    ('easter', 2000098, 'Easter', 'seasonal'),
    ('easter2026', 2000112, 'Easter 2026', 'easter'),
    ('halloween', 2000080, 'Halloween', 'seasonal'),
    ('hween2017', 2000088, 'Halloween 2017', 'halloween'),
    ('hween2023', 2000094, 'Halloween 2023', 'halloween'),
    ('christmas', 2000062, 'Christmas', 'seasonal'),
    ('xmas2011', 2000065, 'Christmas 2011', 'christmas'),
    ('xmas2014', 2000068, 'Christmas 2014', 'christmas'),
    ('valentines', 2000113, "Valentine's", 'seasonal'),
    ('val2013', 2000116, "Valentine's 2013", 'valentines'),
    ('autumn', 2000143, 'Autumn', 'seasonal'),
    ('recycler', 2000258, 'Recycler', 'themes'),
    ('trophies', 2000284, 'Trophies', 'themes'),
    ('windows', 2000294, 'Windows', 'themes'),
    ('habbo_history', 2000208, 'Habbo History', 'themes'),
    ('asian', 2000155, 'Asian', 'themes'),
    ('country', 2000176, 'Country', 'themes'),
    ('habbowood', 2000213, 'Habbowood', 'themes'),
    ('virus', 2000289, 'Virus', 'themes'),
    ('japan', 2000221, 'Japan', 'themes'),
    ('household', 2000217, 'Household', 'themes'),
    ('new_york', 2000241, 'New York', 'themes'),
    ('scifi', 2000263, 'Scifi', 'themes'),
    ('habbopalooza', 2000211, 'Habbopalooza', 'themes'),
    ('rainbow', 2000255, 'Rainbow', 'themes'),
    ('rainyday', 2000256, 'Rainyday', 'themes'),
    ('sanrio', 2000261, 'Sanrio', 'themes'),
    ('tokyo', 2000282, 'Tokyo', 'themes'),
    ('vikings', 2000288, 'Vikings', 'themes'),
    ('anniversary25', 2000147, '25th Anniversary', 'themes'),
    ('welcome_lounge', 2000292, 'Welcome Lounge', 'themes'),
    ('the_lido', 2000278, 'The Lido', 'themes'),
    ('club_gifts', 2000170, 'Club Gifts', 'themes'),
    ('promotional', 953200, 'Promotional', 'customs'),
    ('kindergarten', 944057, 'Kindergarten', 'customs'),
    ('lines', 2000001, 'Lines', 'furni'),
    ('classics', 2000006, 'Classics', 'lines'),
    ('club', 930225, 'Club', 'lines'),
    ('sound', 2000013, 'Sound', 'staff'),
    ('wired', 2000011, 'Wired', 'staff'),
    ('games', 2000004, 'Games', 'staff'),
    ('snow_storm', 2000019, 'Snow Storm', 'games'),
    ('rares', 2000008, 'Rares', 'staff'),
    ('bonus', 2000304, 'Bonus Rares', 'rares'),
    ('nft_tab', 2000009, 'NFT', 'staff'),
    ('nft', 2000298, 'NFT', 'nft_tab'),
    ('nft2025', 2000301, 'NFT 2025', 'nft_tab'),
    ('gangnam_duck', 949405, 'Gangnam Duck', 'nft'),
    ('key_stool', 949423, 'Key Stool', 'nft'),
]

# Zipto shop folder (under Classic/) -> where it goes. The longest matching
# prefix wins, so a folder's sub-folders follow it unless listed themselves.
#   ('page', var)                   an existing page
#   ('new', parent var, caption)    a new page holding just this folder
#   ('tree', parent var, caption)   a new page, and a page under it per sub-folder
#   None                            not imported
ROUTES = {
    'New Furniture/2026- Elven Easter': ('page', 'easter2026'),
    'New Furniture/Blue Classic': ('new', 'customs', 'Blue Classic'),
    'New Furniture/Bonus Items/2016': ('new', 'bonus', 'Recoloured Plant'),
    'New Furniture/Neopets': ('new', 'customs', 'Neopets'),
    'New Furniture/Cokemusic': ('new', 'customs', 'Cokemusic'),
    'New Furniture/Christmas Charm': ('new', 'customs', 'Christmas Charm'),
    'New Furniture/Feerique': ('new', 'customs', 'Feerique'),
    'New Furniture/Hanami': ('new', 'customs', 'Hanami'),
    'New Furniture/Ice Age': ('new', 'customs', 'Ice Age'),
    'New Furniture/Icy Blue': ('new', 'customs', 'Icy Blue'),
    'New Furniture/Rylai Japan': ('new', 'customs', 'Rylai Japan'),
    'New Furniture/White Christmas': ('new', 'customs', 'White Christmas'),
    'New Furniture/Mini Items': ('new', 'customs', 'Mini Items'),
    'New Furniture/Regazza': ('new', 'customs', 'Regazza'),
    'Classic Furniture/Music Shop': ('page', 'sound'),
    'Classic Furniture/Recycler': ('page', 'recycler'),
    'Classic Furniture/Trophies': ('page', 'trophies'),
    'Classic Furniture/Windows': ('page', 'windows'),
    'Modern Furniture/AD Furniture': ('page', 'promotional'),
    'Modern Furniture/Animals': ('new', 'customs', 'Animals'),
    'Modern Furniture/Area 2024': ('page', 'habbo_history'),
    'Modern Furniture/Asian': ('page', 'asian'),
    'Modern Furniture/Autumn': ('page', 'autumn'),
    'Modern Furniture/Mini Trophies': ('page', 'trophies'),
    'Modern Furniture/Country': ('page', 'country'),
    'Modern Furniture/Garage': ('new', 'customs', 'Garage'),
    'Modern Furniture/Habbo History': ('page', 'habbo_history'),
    'Modern Furniture/Habbowood': ('page', 'habbowood'),
    'Modern Furniture/Hospital': ('page', 'virus'),
    'Modern Furniture/Japan': ('page', 'japan'),
    'Modern Furniture/Laundry': ('page', 'household'),
    'Modern Furniture/New York': ('page', 'new_york'),
    'Modern Furniture/Outerspace': ('page', 'scifi'),
    'Modern Furniture/Palooza': ('page', 'habbopalooza'),
    'Modern Furniture/Rainbow': ('page', 'rainbow'),
    'Modern Furniture/Rainy Day': ('page', 'rainyday'),
    'Modern Furniture/Sanrio': ('page', 'sanrio'),
    'Modern Furniture/Scifi': ('page', 'scifi'),
    'Modern Furniture/Tokyo': ('page', 'tokyo'),
    'Modern Furniture/Vikings': ('page', 'vikings'),
    'Seasonal Furniture/Christmas/2011 - Winter Cabin': ('page', 'xmas2011'),
    'Seasonal Furniture/Christmas/2014 - Tropical': ('page', 'xmas2014'),
    'Seasonal Furniture/Valentines Day/2013 - Love Locks': ('page', 'val2013'),
    'Seasonal Furniture/Halloween/2017 - Cursed Caves': ('page', 'hween2017'),
    'Seasonal Furniture/Halloween/2017 - Spooky': ('page', 'hween2017'),
    'Seasonal Furniture/Halloween/2023 - Egyptian': ('page', 'hween2023'),
    'Seasonal Furniture/Summer/2025 - Summer': ('page', 'anniversary25'),
    'Habbo Origins': ('tree', 'themes', 'Habbo Origins'),
    'Public Furniture/Basement Lobby': ('new', 'themes', 'Basement Lobby'),
    'Public Furniture/Franks Room': ('page', 'welcome_lounge'),
    'Public Furniture/Library': ('page', 'classics'),
    'Public Furniture/Lido': ('page', 'the_lido'),
    'Public Furniture/Oriental': ('page', 'classics'),
    'Public Furniture/Red Club NX': ('new', 'themes', 'Red Club NX'),
    'Public Furniture/Rooftop': ('new', 'themes', 'Rooftop'),
    'Public Furniture/Snowstorm': ('page', 'snow_storm'),
    'Public Furniture/Welcome Lounge - Modern': ('page', 'welcome_lounge'),
    'NFT Items/Christmas': ('page', 'nft2025'),
    'NFT Items/Ducks': ('page', 'gangnam_duck'),
    'NFT Items/Net Cafe': ('page', 'key_stool'),
    'Zipto Club/HC Neo': ('page', 'club_gifts'),
    'Zipto Club/HC Oldschool': ('page', 'club'),
    'Zipto Club/HC Shadow': ('new', 'customs', 'Shadow VIP'),
    'Wired Furniture/Accessories': ('tree', 'wired', 'Accessories'),
    'Wired Furniture/Timers': ('page', 'wired'),
    # Zipto's own wired boxes and settings furni: our server has no code for
    # them, so they would be boxes that do nothing.
    'Wired Furniture/Triggers': None,
    'Wired Furniture/Effects': None,
    'Wired Furniture/Conditions': None,
    'Wired Furniture/Add-ons': None,
    'Wired Furniture/Configuration Items': None,
    'Pets/Accessories/Baby Accessories': ('page', 'kindergarten'),
    # A crafting table opens the crafting window, and we have no recipes.
    'Crafting': None,
    'Trax': ('page', 'sound'),
}

# Sets whose parent keeps its children in A-Z order get renumbered after the
# insert - absolute positions from the captions there, so a re-run lands the
# same way. Themes keeps More Themes last.
RESORT = {
    'customs': "ORDER BY `caption`",
    'themes': "ORDER BY (`caption` = 'More Themes'), `caption`",
    'bonus': "ORDER BY `caption`",
}

# Neopets get their own Customs set: the ones already sold on Promotional
# move to it as well as Zipto's new ones.
NEOPETS_FROM = 'promotional'


def route_for(folder):
    best = None
    for prefix, dest in ROUTES.items():
        if folder == prefix or folder.startswith(prefix + '/'):
            if best is None or len(prefix) > len(best[0]):
                best = (prefix, dest)
    if best is None:
        raise SystemExit('no route for Zipto folder %r' % folder)
    return best


def esc(value):
    return "'%s'" % str(value).replace('\\', '\\\\').replace("'", "\\'")


def chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def ascii_only(text, what):
    # dbsql talks latin1 to the server; plain ASCII is the one thing that
    # arrives the same however the client is set up.
    if any(ord(ch) > 126 for ch in text):
        raise SystemExit('non-ASCII %s: %r' % (what, text))
    return text


# ---- read the Zipto Import folder --------------------------------------------

manifest = json.load(open(os.path.join(SRC, '_import.json'), encoding='utf-8'))
TOP = 'Classic' + os.sep


def rel(folder):
    """'Classic\\New Furniture\\Neopets' -> 'New Furniture/Neopets'."""
    return folder[len(TOP):].replace(os.sep, '/') if folder.startswith(TOP) else None


# Zipto's page order and each page's icon, by folder
zipto_pages = collections.OrderedDict()
for cat in manifest['categories']:
    r = rel(cat['folder'])
    if r is not None:
        zipto_pages[r] = cat
furni = [f for f in manifest['furni'] if rel(f['folder']) is not None]


# ---- pages ---------------------------------------------------------------------

pages = []           # new pages: dict(id, parent_sql, rank_sql, caption, order, icon_src, resort)
page_of_folder = {}  # Zipto folder -> SQL expression of the page its furni go on
next_page = PAGE_FIRST + 1


def new_page(parent_sql, rank_sql, caption, order, icon_src, resort):
    global next_page
    pid = next_page
    next_page += 1
    pages.append(dict(id=pid, parent_sql=parent_sql, rank_sql=rank_sql,
                      caption=ascii_only(caption, 'caption'), order=order,
                      icon_src=icon_src, resort=resort))
    return pid


def zipto_icon(folder):
    path = os.path.join(SRC, 'Classic', *folder.split('/'), '_icon.png')
    return path if os.path.exists(path) else None


skipped_folders = collections.Counter()
roots = {}           # route prefix -> page id, for 'new' and 'tree'
for f in furni:
    folder = rel(f['folder'])
    if folder in page_of_folder:
        continue
    prefix, dest = route_for(folder)
    if dest is None:
        page_of_folder[folder] = None
        continue
    kind = dest[0]
    if kind == 'page':
        page_of_folder[folder] = '@' + dest[1]
        continue
    parent_var, caption = dest[1], dest[2]
    if prefix not in roots:
        roots[prefix] = new_page('@' + parent_var, '@rank_' + parent_var, caption,
                                 1, zipto_icon(prefix), parent_var in RESORT and parent_var)
    if kind == 'new' or folder == prefix:
        page_of_folder[folder] = str(roots[prefix])
        continue
    # a tree: one page per folder level under the root, in Zipto's order
    parent = roots[prefix]
    walked = prefix
    for part in folder[len(prefix) + 1:].split('/'):
        walked += '/' + part
        if walked not in page_of_folder:
            siblings = [p for p in pages if p['parent_sql'] == str(parent)]
            pid = new_page(str(parent), '@rank_' + parent_var, part, len(siblings) + 1,
                           zipto_icon(walked), None)
            page_of_folder[walked] = str(pid)
        parent = int(page_of_folder[walked])

# Tree pages come out in the order their first furni appear; Zipto's own page
# order is what they should read in, so re-number siblings by it.
order_in_zipto = {folder: n for n, folder in enumerate(zipto_pages)}
folder_of_page = {v: k for k, v in page_of_folder.items() if v and v.isdigit()}
by_parent = collections.defaultdict(list)
for p in pages:
    by_parent[p['parent_sql']].append(p)
for siblings in by_parent.values():
    if all(str(p['id']) in folder_of_page for p in siblings) and siblings[0]['parent_sql'].isdigit():
        siblings.sort(key=lambda p: order_in_zipto.get(folder_of_page[str(p['id'])], 0))
        for n, p in enumerate(siblings):
            p['order'] = n + 1


# ---- furni ---------------------------------------------------------------------

def is_real_description(desc):
    return bool(desc) and '_' not in desc and len(desc.split()) >= 4


TILE_FOLDERS = ('Wired Furniture/Accessories/Tiles',)
GATE_FOLDERS = ('Wired Furniture/Accessories/Gates', 'Wired Furniture/Accessories/Fire Gates')
# Most of these bundles say 1 high whatever they draw, so a floor, rug or path
# is told by its English name and then measured off its own picture.
FLAT = re.compile(r'\b(floors?|tiles?|rugs?|carpet|mat|doormat|path|patch|grass|plates?|water|'
                  r'pebble|stones|snow|lilies|lilypad)\b')
SOFT = re.compile(r'\b(rugs?|carpet|mat|doormat|grass|snow|patch|lilies|lilypad|water)\b')
NOT_FLAT = re.compile(r'\b(table|sofa|chair|couch|bench|stool|stand|shelf|tower|wall|roof|pillar|'
                      r'divider|door|window|lamp|light|plant|tree|machine|block|box|crate)\b')
SPRITE = re.compile(r'_64_([a-z]+)_(\d)_0$')


def drawn_height(data, lib):
    """How high the furni stands, in tiles, from its 64-size picture facing 2
    (or the first way it faces). A flat footprint of any size is drawn twice as
    wide as it is high, so whatever height the drawing has beyond half its width
    is the furni's own - which needs no footprint, and the bundles that lack one
    are exactly the ones this is for."""
    frames = {}
    for key, frame in ((data.get('spritesheet') or {}).get('frames') or {}).items():
        key = key[:-4] if key.endswith('.png') else key
        rect = frame.get('frame') or {}
        frames[key[len(lib) + 1:] if key.startswith(lib + '_') else key] = (rect.get('w', 0), rect.get('h', 0))
    by_dir = collections.defaultdict(list)
    for name, asset in (data.get('assets') or {}).items():
        m = SPRITE.search(name)
        if not m or m.group(1) == 'sd':
            continue
        size = frames.get(asset.get('source') or name)
        if size and size[1]:
            left, top = -int(asset.get('x', 0)), -int(asset.get('y', 0))
            by_dir[m.group(2)].append((left, top, left + size[0], top + size[1]))
    boxes = by_dir.get('2') or by_dir.get('4') or next(iter(by_dir.values()), None)
    if not boxes:
        return None
    width = max(b[2] for b in boxes) - min(b[0] for b in boxes)
    height = max(b[3] for b in boxes) - min(b[1] for b in boxes)
    return max(0.0, (height - width / 2.0) / 32.0)

rows = []
libs_written = {}
report = collections.defaultdict(list)
fid = FURNI_FIRST
os.makedirs(BUNDLE_OUT, exist_ok=True)
os.makedirs(ICON_OUT, exist_ok=True)
os.makedirs(PAGE_ICON_OUT, exist_ok=True)

polar = [f for f in furni if f['classname'].startswith('carpet_polar*') and page_of_folder.get(rel(f['folder']))]
others = [f for f in furni if f not in polar]

for f in others:
    folder = rel(f['folder'])
    page_sql = page_of_folder[folder]
    if page_sql is None:
        skipped_folders[folder] += 1
        continue
    classname, lib = f['classname'], f['classname'].split('*')[0]
    src = os.path.join(SRC, f['folder'], f['nitro'])
    if lib not in libs_written:
        bundle = fb.read_furni(src)
        fb.write_bundle(os.path.join(BUNDLE_OUT, lib + '.nitro'), bundle['entries'])
        libs_written[lib] = bundle
    bundle = libs_written[lib]
    data = json.loads(fb.inflate(bundle['entries'][next(k for k in bundle['entries'] if k.endswith('.json'))]))
    logic = data.get('logicType') or ''
    zfd = f['furnidata']
    name = ascii_only(zn.name_for(classname, f['name']), 'name of %s' % classname)
    desc = zfd.get('description') or ''
    desc = desc if is_real_description(desc) and all(ord(c) < 127 for c in desc) else name

    modes = bundle['modes']
    x, y, z = bundle['x'], bundle['y'], bundle['z']
    if not bundle['has_dims']:
        # no logic block in the bundle: Zipto's furni data has the footprint
        x, y = int(zfd.get('xdim') or 1), int(zfd.get('ydim') or 1)
    words = (name + ' ' + classname).lower()
    interaction = 'default'
    if logic == 'furniture_dice':
        interaction = 'dice'
    elif modes >= 2 and (folder in GATE_FOLDERS or re.search(r'\bgate$', name.lower())):
        interaction = 'gate'
    elif re.search(r'\b(bed|cot)\b', name.lower()) and max(x, y) >= 2:
        interaction = 'bed'
    sit = interaction == 'default' and bool(fb.SEAT.search(words)) and 'table' not in words
    walk = False
    if interaction == 'default' and not sit and not NOT_FLAT.search(name.lower()) and (
            FLAT.search(name.lower()) or any(folder.startswith(t) for t in TILE_FOLDERS)):
        drawn = drawn_height(data, lib)
        if drawn is not None and drawn <= 0.35:
            walk, z = True, round(drawn, 1)
        elif drawn is not None and drawn <= 1.5:
            # a rug's head or a floor's grass blades stand up off it, but you
            # walk on the floor; a raised floor or slab is walked on at its top
            walk, z = True, 0.0 if SOFT.search(name.lower()) else round(drawn, 1)
        else:
            report['flat_name_but_tall'].append('%s %s' % (classname, drawn))
    for key, on in (('sit', sit), ('walk', walk), ('gate', interaction == 'gate'),
                    ('bed', interaction == 'bed'), ('dice', interaction == 'dice')):
        if on:
            report[key].append(classname)
    if not bundle['has_dims']:
        report['no_dims'].append(classname)

    icon_src = os.path.join(SRC, f['folder'], f['icon']) if f.get('icon') else None
    icon_name = classname.replace('*', '_') + '_icon.png'
    if icon_src and os.path.exists(icon_src):
        shutil.copyfile(icon_src, os.path.join(ICON_OUT, icon_name))
    elif not (bundle['icon_frame'] and fb.crop_icon(bundle['entries'], bundle['png'], bundle['icon_frame'],
                                                    os.path.join(ICON_OUT, icon_name))):
        report['no_icon'].append(classname)

    rows.append(dict(id=fid, classname=classname, name=name, desc=ascii_only(desc, 'description'),
                     page=page_sql, x=x, y=y, z=z, sit=sit, walk=walk,
                     lay=interaction == 'bed', interaction=interaction, modes=modes,
                     partcolors=zfd.get('partcolors') or {'color': []},
                     defaultdir=zfd.get('defaultdir') or 0, folder=folder))
    fid += 1


# ---- the polar bear rugs -------------------------------------------------------
# Zipto's carpet_polar draws the same rug as ours but numbers its colours one
# off (its colour 2 is our colour 1), so its file cannot replace ours without
# recolouring every rug already placed. Instead its extra colours are appended
# to OUR file as colours 5, 6, ... - 1 to 4 untouched - and each new colour is
# a new carpet_polar*N furni.

def colour_layers(data, index):
    out = {}
    for vis in data.get('visualizations') or []:
        colours = vis.get('colors') or {}
        if str(index) in colours:
            out[str(vis.get('size'))] = colours[str(index)]
    return out


COLOUR_NAMES = [
    ('Black', (20, 20, 20)), ('Charcoal', (60, 60, 60)), ('Grey', (128, 128, 128)), ('Silver', (190, 190, 190)),
    ('White', (245, 245, 245)), ('Cream', (255, 250, 210)), ('Beige', (225, 205, 160)), ('Sand', (210, 180, 120)),
    ('Brown', (120, 75, 35)), ('Chocolate', (80, 45, 25)), ('Tan', (190, 140, 90)), ('Red', (210, 30, 30)),
    ('Crimson', (150, 10, 30)), ('Coral', (255, 120, 100)), ('Salmon', (250, 150, 130)), ('Orange', (255, 140, 20)),
    ('Peach', (255, 200, 160)), ('Gold', (230, 180, 30)), ('Yellow', (255, 230, 40)), ('Lemon', (255, 250, 140)),
    ('Lime', (170, 230, 50)), ('Green', (40, 160, 50)), ('Forest', (30, 90, 40)), ('Mint', (170, 240, 200)),
    ('Olive', (120, 120, 40)), ('Teal', (20, 140, 140)), ('Turquoise', (60, 210, 200)), ('Cyan', (60, 220, 240)),
    ('Sky Blue', (130, 200, 250)), ('Blue', (40, 90, 220)), ('Navy', (25, 35, 110)), ('Indigo', (75, 40, 150)),
    ('Purple', (140, 60, 190)), ('Lilac', (200, 160, 230)), ('Lavender', (220, 200, 250)), ('Magenta', (220, 40, 180)),
    ('Pink', (250, 150, 200)), ('Hot Pink', (255, 70, 150)), ('Rose', (230, 110, 140)), ('Maroon', (110, 25, 40)),
]


def colour_name(rgb):
    return min(COLOUR_NAMES, key=lambda c: sum((a - b) ** 2 for a, b in zip(c[1], rgb)))[0]


polar_rows = []
if polar:
    target = os.path.join(BUNDLE_OUT, 'carpet_polar.nitro')
    base = target if os.path.exists(target) else POLAR_BASE
    if not base or not os.path.exists(base):
        raise SystemExit('carpet_polar: pass --polar <beta nitro/assets/bundled/furniture/carpet_polar.nitro>')
    ours = fb.bundle_entries(base)
    ours_json = next(k for k in ours if k.endswith('.json'))
    ours_data = json.loads(fb.inflate(ours[ours_json]))
    theirs = fb.bundle_entries(os.path.join(SRC, polar[0]['folder'], polar[0]['nitro']))
    theirs_data = json.loads(fb.inflate(theirs[next(k for k in theirs if k.endswith('.json'))]))
    # our colours 1-4 as they are; a Zipto colour equal to one of them is no new rug
    kept = {json.dumps(colour_layers(ours_data, n), sort_keys=True)
            for n in range(0, 5) if colour_layers(ours_data, n)}
    next_index = 5
    page_sql = page_of_folder[rel(polar[0]['folder'])]
    for f in polar:
        k = int(f['classname'].split('*')[1])
        layers = colour_layers(theirs_data, k)
        key = json.dumps(layers, sort_keys=True)
        if not layers or key in kept:
            report['polar_same_as_ours'].append(f['classname'])
            continue
        kept.add(key)
        n = next_index
        next_index += 1
        for vis in ours_data.get('visualizations') or []:
            if 'colors' in vis and str(vis.get('size')) in layers:
                vis['colors'][str(n)] = layers[str(vis.get('size'))]
        # named, and swatched in the shop, by the colour the rug is drawn in
        tint = next(iter((layers.get('64') or next(iter(layers.values())))['layers'].values()))['color']
        rgb = ((tint >> 16) & 255, (tint >> 8) & 255, tint & 255)
        classname = 'carpet_polar*%d' % n
        icon_src = os.path.join(SRC, f['folder'], f['icon']) if f.get('icon') else None
        if icon_src and os.path.exists(icon_src):
            shutil.copyfile(icon_src, os.path.join(ICON_OUT, 'carpet_polar_%d_icon.png' % n))
        else:
            report['no_icon'].append(classname)
        polar_rows.append(dict(id=fid, classname=classname, name='%s Bear Rug' % colour_name(rgb),
                               desc='%s Bear Rug' % colour_name(rgb), page=page_sql, x=2, y=3, z=0.0,
                               sit=False, walk=True, lay=False, interaction='default', modes=1,
                               partcolors={'color': ['#%02X%02X%02X' % rgb]},
                               defaultdir=0, folder=rel(f['folder']), zipto=f['classname']))
        fid += 1
    ours[ours_json] = json.dumps(ours_data, separators=(',', ':')).encode('utf-8')
    fb.write_bundle(target, ours)
    # the rug's size, height and walkability are the ones our own rows give it
    ref = fb.read_furni(target)
    for r in polar_rows:
        r.update(x=ref['x'], y=ref['y'], z=ref['z'])
    rows.extend(polar_rows)

if fid - 1 > FURNI_LAST:
    raise SystemExit('furni ids ran past %d' % FURNI_LAST)

# Names repeated on one page get a number, in page order: Zombie, Zombie 2...
seen_names = collections.defaultdict(collections.Counter)
for r in rows:
    seen_names[r['page']][r['name']] += 1
    count = seen_names[r['page']][r['name']]
    if count > 1:
        r['name'] = '%s %d' % (r['name'], count)
        if r['desc'] == r['name'].rsplit(' ', 1)[0]:
            r['desc'] = r['name']


# ---- page icons --------------------------------------------------------------

def fit_furni_icon(path, out, size=18):
    from PIL import Image
    image = Image.open(path).convert('RGBA')
    image = image.crop(image.getbbox())
    image.thumbnail((size, size), Image.LANCZOS)
    image.save(out, 'PNG')


for p in pages:
    out = os.path.join(PAGE_ICON_OUT, 'icon_%d.png' % p['id'])
    if p['caption'] == 'Recoloured Plant':
        # Bonus Rares' pages wear their furni, not a year; Zipto's icon here was '2016'
        fit_furni_icon(os.path.join(ICON_OUT, 'Recoloured_Plant_0_icon.png'), out)
        p['icon'] = p['id']
    elif p['icon_src']:
        shutil.copyfile(p['icon_src'], out)
        p['icon'] = p['id']
    else:
        p['icon'] = 193
        report['page_without_icon'].append(p['caption'])


# ---- gamedata ------------------------------------------------------------------

furnitype = [{
    'id': r['id'], 'classname': r['classname'], 'revision': 0, 'category': 'zipto',
    'defaultdir': r['defaultdir'], 'xdim': r['x'], 'ydim': r['y'], 'partcolors': r['partcolors'],
    'name': r['name'], 'description': r['desc'], 'adurl': '', 'offerid': -1, 'buyout': False,
    'rentofferid': -1, 'rentbuyout': False, 'bc': False, 'excludeddynamic': False, 'customparams': '',
    'specialtype': 1, 'canstandon': r['walk'], 'cansiton': r['sit'], 'canlayon': r['lay'],
    'furniline': 'zipto',
} for r in rows]
texts = {}
for r in rows:
    texts['%s_name' % r['classname']] = r['name']
    texts['%s_desc' % r['classname']] = r['desc']

os.makedirs(RECORD_DIR, exist_ok=True)
json.dump({'furnitype': furnitype, 'externaltexts': texts},
          open(os.path.join(RECORD_DIR, 'furnidata-entries.json'), 'w', encoding='utf-8'), indent=1)

# Replace, not append: a re-run with a name fixed must not leave the old entry.
merged = json.load(open(MERGE_FURNI, encoding='utf-8'))
ours_ids = {e['id'] for e in furnitype}
for kind in ('roomitemtypes', 'wallitemtypes'):
    if kind in merged:
        merged[kind]['furnitype'] = [e for e in merged[kind]['furnitype']
                                     if not FURNI_FIRST <= e['id'] <= FURNI_LAST]
merged['roomitemtypes']['furnitype'].extend(furnitype)
json.dump(merged, open(MERGE_FURNI, 'w', encoding='utf-8'))

merged_texts = json.load(open(MERGE_TEXTS, encoding='utf-8'))
merged_texts.update(texts)
json.dump(merged_texts, open(MERGE_TEXTS, 'w', encoding='utf-8'), indent=1)


# ---- SQL -----------------------------------------------------------------------

used_vars = set()
for r in rows:
    if r['page'].startswith('@'):
        used_vars.add(r['page'][1:])
for p in pages:
    for sql in (p['parent_sql'], p['rank_sql']):
        if sql.startswith('@rank_'):
            used_vars.add(sql[len('@rank_'):])
        elif sql.startswith('@'):
            used_vars.add(sql[1:])
used_vars.update(RESORT)
used_vars.add(NEOPETS_FROM)
# a page needs its parents resolved before it
parent_of = {v: parent for v, _, _, parent in EXISTING}
needed = set()
for v in used_vars:
    while v and v not in needed:
        needed.add(v)
        v = parent_of[v]

resolve = []
for var, pid, caption, parent in EXISTING:
    if var not in needed:
        continue
    if parent is None:
        resolve.append("SET @%s := COALESCE(\n    (SELECT `id` FROM `catalog_pages` WHERE `id` = %d AND `caption` = %s LIMIT 1),\n"
                       "    (SELECT `id` FROM `catalog_pages` WHERE `parent_id` = -1 AND `caption` = %s ORDER BY `id` LIMIT 1),\n"
                       "    %d);" % (var, pid, esc(caption), esc(caption), pid))
    else:
        resolve.append("SET @%s := COALESCE(\n    (SELECT `id` FROM `catalog_pages` WHERE `id` = %d AND `caption` = %s LIMIT 1),\n"
                       "    (SELECT `id` FROM `catalog_pages` WHERE `parent_id` = @%s AND `caption` = %s\n"
                       "        ORDER BY `enabled` DESC, `id` LIMIT 1),\n"
                       "    @%s);" % (var, pid, esc(caption), parent, esc(caption), parent))
rank_vars = sorted({p['rank_sql'][len('@rank_'):] for p in pages})
for var in rank_vars:
    resolve.append("SET @rank_%s := COALESCE((SELECT `min_rank` FROM `catalog_pages` WHERE `id` = @%s), 2);" % (var, var))

neopets_page = next(p['id'] for p in pages if p['caption'] == 'Neopets')
n_existing = sum(1 for r in rows if r['page'].startswith('@'))
n_new_pages = sum(1 for r in rows if not r['page'].startswith('@'))
counts = collections.Counter(r['folder'].split('/')[0] for r in rows)

with open(SQL_OUT, 'w', encoding='utf-8', newline='\n') as o:
    o.write("""\
-- PixelRP: the furni Zipto sells in its shop, sorted into ours.
--
-- %(total)d furni from zipto.pw's shop that beta did not have - checked by name
-- and by picture (the same 64-size sprites in the same colour), so nothing
-- here is a second copy of something we sell. Generated by
-- docker/nitro/import-zipto-shop.py from the `Zipto Import` folder; ROUTES
-- there says where each of Zipto's shop pages went:
--
--   %(existing)d onto pages we already had, beside the rest of their set
--      (Elven Easter -> Easter 2026, Sanrio -> Themes > Sanrio ...)
--   %(new)d onto %(pages)d new pages: Customs sets for other hotels' furni
--      (Cokemusic, Christmas Charm, Neopets ...), Themes > Habbo Origins and
--      the public rooms we lacked, Staff > Wired > Accessories, and
--      Staff > Rares > Bonus Rares > Recoloured Plant
--
-- Not imported: Zipto's own wired boxes and settings furni and a crafting
-- table - our server has no code for them.
--
-- Neopets: every neopets_ furni already on Customs > Promotional moves to the
-- new Customs > Neopets set with Zipto's.
--
-- The polar bear rug's new colours are appended to our own carpet_polar
-- bundle as colours 5 and up, so the four we had keep their look.
--
-- The rendering half is the .nitro bundles, icons and FurnitureData entries
-- under nitro/overrides/; the rows below are inert without them. Free, like
-- the rest of the catalog since 90_FreeCatalog.
--
-- Idempotent: fixed id ranges (furni %(f1)d-%(f2)d, pages %(p1)d-%(p2)d), cleared
-- before insert; siblings that read A-Z are renumbered from their captions.

""" % dict(total=len(rows), existing=n_existing, new=n_new_pages, pages=len(pages),
           f1=FURNI_FIRST, f2=FURNI_LAST, p1=PAGE_FIRST, p2=PAGE_LAST))
    o.write('\n'.join(resolve) + '\n\n')
    # item_id is a varchar: compared as text, so no row is converted to a number
    o.write("DELETE FROM `catalog_items` WHERE `item_id` REGEXP '^11[23][0-9]{3}$';\n")
    o.write('DELETE FROM `catalog_pages` WHERE `id` BETWEEN %d AND %d;\n' % (PAGE_FIRST, PAGE_LAST))
    o.write('DELETE FROM `furniture` WHERE `id` BETWEEN %d AND %d;\n\n' % (FURNI_FIRST, FURNI_LAST))

    o.write('INSERT INTO `catalog_pages` (`id`,`parent_id`,`caption`,`icon_image`,`min_rank`,'
            '`min_vip`,`order_num`,`page_link`,`page_layout`,`page_strings_1`,`page_strings_2`,'
            '`visible`,`enabled`) VALUES\n')
    o.write(',\n'.join(
        "    (%d,%s,%s,%d,%s,0,%d,'','default_3x3','','',b'1',b'1')"
        % (p['id'], p['parent_sql'], esc(p['caption']), p['icon'], p['rank_sql'], p['order'])
        for p in pages) + ';\n')

    o.write('\n-- Furniture. id == sprite_id; interaction_modes_count is the states the bundle draws.\n')
    for batch in chunks(rows, ROWS_PER_INSERT):
        o.write('INSERT INTO `furniture` (`id`,`item_name`,`public_name`,`type`,`width`,`length`,'
                '`stack_height`,`can_stack`,`can_sit`,`is_walkable`,`sprite_id`,`allow_recycle`,'
                '`allow_trade`,`allow_marketplace_sell`,`allow_gift`,`allow_inventory_stack`,'
                '`interaction_type`,`behaviour_data`,`interaction_modes_count`,`is_rare`) VALUES\n')
        o.write(',\n'.join(
            "    (%d,%s,%s,'s',%d,%d,%s,'1','%d','%d',%d,'0','1','0','1','1',%s,0,%d,'0')"
            % (r['id'], esc(r['classname']), esc(r['name']), r['x'], r['y'], r['z'],
               r['sit'], r['walk'], r['id'], esc(r['interaction']),
               2 if r['interaction'] == 'gate' else r['modes'])
            for r in batch) + ';\n')

    o.write('\n')
    for batch in chunks(rows, ROWS_PER_INSERT):
        o.write('INSERT INTO `catalog_items` (`page_id`,`item_id`,`catalog_name`,`cost_credits`,'
                '`cost_pixels`,`cost_diamonds`,`amount`,`limited_sells`,`limited_stack`,'
                '`offer_active`,`extradata`,`badge`,`offer_id`) VALUES\n')
        o.write(',\n'.join(
            "    (%s,'%d',%s,0,0,0,1,0,0,'1','','',-1)" % (r['page'], r['id'], esc(r['name']))
            for r in batch) + ';\n')

    o.write("""
-- The Neopets already on Promotional join Zipto's in the new set. Matched as
-- text (item_id is a varchar), so no row is converted to a number.
UPDATE `catalog_items` `ci`
    JOIN `furniture` `f` ON `ci`.`item_id` = CAST(`f`.`id` AS CHAR)
    SET `ci`.`page_id` = %d
    WHERE `ci`.`page_id` = @%s AND `f`.`item_name` LIKE 'neopets\\_%%';
""" % (neopets_page, NEOPETS_FROM))

    for var, order in RESORT.items():
        o.write("""
SET @n := 0;
UPDATE `catalog_pages` SET `order_num` = (@n := @n + 1)
    WHERE `parent_id` = @%s
    %s;
""" % (var, order))

json.dump(dict(report, skipped_folders=dict(skipped_folders), pages=[
    dict(id=p['id'], caption=p['caption'], parent=p['parent_sql'], order=p['order'], icon=p['icon']) for p in pages]),
    open(os.path.join(RECORD_DIR, 'import-report.json'), 'w', encoding='utf-8'), indent=1)

print('furni: %d (ids %d-%d)   on existing pages: %d   on new pages: %d' %
      (len(rows), FURNI_FIRST, fid - 1, n_existing, n_new_pages))
print('new pages: %d (ids %d-%d)   bundles: %d   polar colours: %d' %
      (len(pages), PAGE_FIRST + 1, next_page - 1, len(libs_written), len(polar_rows)))
print('skipped by route: %s' % dict(skipped_folders))
print('sit %d  walk %d  gate %d  bed %d  dice %d  no icon %d  no dims %d' % tuple(
    len(report[k]) for k in ('sit', 'walk', 'gate', 'bed', 'dice', 'no_icon', 'no_dims')))
