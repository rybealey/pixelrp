#!/usr/bin/env python3
"""Import the Zipto furni from outside Zipto's shop into Customs, the way the
Shop Planner's map says.

    python3 docker/nitro/import-zipto-customs.py <shop-plan.json> <beta dump dir> \
        [--src ~/Desktop/Zipto Import] [--planner <Zipto Import>/_shop-planner.html]

The map (Export map in docker/nitro/shop-planner.html) says where every page
goes; the planner page it was exported from carries each Zipto set's furni and
its icon. The beta dump dir holds what the planner was built from
(catalog_pages2.tsv for the captions as they are) and furniture_fix.tsv +
FurnitureData.json (what beta has now, so nothing is imported twice).

What changes:
  Customs      becomes its category folders, A-Z; our own sets move into them
               (catalog_pages.parent_id), renamed where the map renames them;
               one of ours the map joins to another has its furni moved there
               and is hidden; the sets the map empties (Holidays ...) hidden
  Zipto sets   a new page each (or their furni join one of ours), ~24,000
               furni with English names (zipto_english.py), the walk/sit/bed
               rules of the shop import, clicks from furni_bundle.click_states
  Furni lines  the Lines pages wear their own chair (catalog icon 969xxx)

Leaves out what the map leaves out: Trax, wired, clothing.

Emits:
  emulator/Resources/SQLs/Updates/<n>_ZiptoCustoms.sql
  nitro/overrides/bundled/furniture/<lib>.nitro, dcr/hof_furni/icons/<classname>_icon.png
  nitro/overrides/c_images/catalogue/icon_<n>.png
  nitro/overrides/gamedata-merge/{FurnitureData,ExternalTexts}.json
  docker/nitro/zipto-furni/customs-{furnidata-entries,import-report}.json

Ids: furni 213000-246999 (id == sprite_id), pages 965000-965999, page icons
icon_<page id>.png, the Lines' icons 969001 up.
"""
import collections
import json
import os
import re
import shutil
import sys
from urllib.parse import unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furni_bundle as fb
import zipto_english as ze

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def repo(*parts):
    return os.path.join(REPO, *parts)


SQL_OUT = repo('emulator/Resources/SQLs/Updates/299_ZiptoCustoms.sql')
RECORD_DIR = repo('docker/nitro/zipto-furni')
MERGE_FURNI = repo('nitro/overrides/gamedata-merge/FurnitureData.json')
MERGE_TEXTS = repo('nitro/overrides/gamedata-merge/ExternalTexts.json')
BUNDLE_OUT = repo('nitro/overrides/bundled/furniture')
ICON_OUT = repo('nitro/overrides/dcr/hof_furni/icons')
PAGE_ICON_OUT = repo('nitro/overrides/c_images/catalogue')
FURNI_FIRST, FURNI_LAST = 213000, 246999
PAGE_FIRST, PAGE_LAST = 965000, 965999
LINE_ICON_FIRST = 969001
CUSTOMS = 'p944000'
ROWS_PER_INSERT = 400
CAPTION_MAX, NAME_MAX = 35, 56

# Zipto's black_corner is the Victoria pack's zwartehoekblok (295), same art
SKIP = {'black_corner'}

args = sys.argv[1:]


def option(flag, default):
    if flag in args:
        i = args.index(flag)
        value = args[i + 1]
        del args[i:i + 2]
        return os.path.expanduser(value)
    return default


SRC = option('--src', os.path.expanduser('~/Desktop/Zipto Import'))
PLANNER = option('--planner', os.path.join(SRC, '_shop-planner.html'))
PLAN, DUMP = args[0], args[1]


def esc(value):
    return "'%s'" % str(value).replace('\\', '\\\\').replace("'", "\\'")


def chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def ascii_only(text, what):
    if any(ord(ch) > 126 for ch in text):
        raise SystemExit('non-ASCII %s: %r' % (what, text))
    return text


def tsv(name):
    rows, header = [], None
    for line in open(os.path.join(DUMP, name), encoding='utf-8', newline='\n'):
        parts = line.rstrip('\n').replace('\r', '').split('\t')
        if header is None and not parts[0].isdigit():
            header = parts
            continue
        rows.append(parts)
    return rows


# ---- the map ---------------------------------------------------------------------

page = open(PLANNER, encoding='utf-8').read()
DATA = json.loads(re.search(r'const DATA = (.*?);\nconst KEY', page, re.S).group(1))
base = {n['id']: n for n in DATA['nodes']}
plan = json.load(open(PLAN, encoding='utf-8'))
nodes = {}
for p in plan['nodes']:
    n = dict(base.get(p['id']) or {'items': [], 'icon': ''})
    n.update(id=p['id'], name=p['name'], parent=p['parent'], kind=p['kind'], src=p['src'],
             merge=p['merge'], page=p.get('page'))
    nodes[n['id']] = n
dropped = [n for i, n in base.items() if i not in nodes]

children = collections.defaultdict(list)
for n in nodes.values():
    if not n['merge']:
        children[n['parent']].append(n['id'])


def under_customs(nid):
    while nid:
        if nid == CUSTOMS:
            return True
        nid = (nodes.get(nid) or base.get(nid) or {}).get('parent')
    return False


def a_z(ids):
    return sorted(ids, key=lambda i: nodes[i]['name'].lower())


beta_caption = {int(r[0]): r[2] for r in tsv('catalog_pages2.tsv')}

# new pages: every folder and Zipto set in Customs, depth first, A-Z
page_id = {}
next_page = PAGE_FIRST + 1


def number(nid):
    global next_page
    for k in a_z(children[nid]):
        if nodes[k]['src'] in ('new', 'zipto'):
            page_id[k] = next_page
            next_page += 1
        number(k)


number(CUSTOMS)
if next_page - 1 > PAGE_LAST:
    raise SystemExit('page ids ran past %d' % PAGE_LAST)


def page_of(nid):
    """The catalog page id a node is, or None."""
    if nid in page_id:
        return page_id[nid]
    if nid.startswith('p'):
        return int(nid[1:])
    return None


new_pages, moves, renames, orders = [], [], [], []
for parent in [CUSTOMS] + [i for i in nodes if i != CUSTOMS and under_customs(i)]:
    for order, k in enumerate(a_z(children[parent]), 1):
        n = nodes[k]
        if k in page_id:
            new_pages.append(dict(id=page_id[k], parent=page_of(parent), node=k,
                                  caption=ascii_only(ze.ascii_fold(n['name']), 'caption')[:CAPTION_MAX], order=order))
        elif n['src'] == 'pixel':
            pid = page_of(k)
            moves.append((pid, page_of(parent)))
            orders.append((pid, order))
            if n['name'] != beta_caption.get(pid):
                renames.append((pid, ascii_only(ze.ascii_fold(n['name']), 'caption of %s' % k)[:CAPTION_MAX]))

# our own pages joined to another, and the ones the map empties
joins = [(page_of(n['id']), page_of(n['merge'])) for n in nodes.values()
         if n['src'] == 'pixel' and n['merge'] and under_customs(n['merge'])]
hidden = [page_of(n['id']) for n in dropped if n['src'] == 'pixel' and n['id'].startswith('p')
          and under_customs(n['parent'] or CUSTOMS)] + [src for src, _ in joins]

# the Lines that wear a new icon
lines = [n for n in nodes.values() if n.get('newIcon')]


# ---- what beta already has -------------------------------------------------------

have = {r[1].lower() for r in tsv('furniture_fix.tsv') if len(r) > 1}
gamedata = json.load(open(os.path.join(DUMP, 'FurnitureData.json'), encoding='utf-8'))
have |= {e['classname'].lower() for k in ('roomitemtypes', 'wallitemtypes')
         for e in gamedata[k]['furnitype'] if not FURNI_FIRST <= e['id'] <= FURNI_LAST}


# ---- furni -----------------------------------------------------------------------

manifest = json.load(open(os.path.join(SRC, '_import.json'), encoding='utf-8'))
variants = collections.OrderedDict()
for f in manifest['furni']:
    if f['folder'].startswith('Not in'):
        variants.setdefault(f['classname'].split('*')[0], []).append(f)
for lib in variants:
    variants[lib].sort(key=lambda f: int(f['classname'].split('*')[1]) if '*' in f['classname'] else -1)

FLAT = re.compile(r'\b(floors?|tiles?|rugs?|carpets?|mats?|doormat|path|patch|grass|plates?|water|'
                  r'pebbles?|stones|snow|lilies|lilypad|lawn|ground)\b')
SOFT = re.compile(r'\b(rugs?|carpets?|mats?|doormat|grass|snow|patch|lilies|lilypad|water|lawn)\b')
NOT_FLAT = re.compile(r'\b(table|sofa|chair|couch|bench|stool|stand|shelf|tower|wall|roof|pillar|'
                      r'divider|door|window|lamp|light|plant|tree|machine|block|box|crate)\b')
SPRITE = re.compile(r'_64_([a-z]+)_(\d)_0$')
LOGIC_TYPES = {'furniture_dice': 'dice', 'furniture_custom_stack_height': 'stacktool',
               'furniture_one_way_door': 'onewaygate', 'furniture_badge_display': 'badge_display'}


def drawn_height(data, lib):
    """How high the furni stands, in tiles, from its 64-size picture (as in
    import-zipto-shop.py): what the drawing has beyond half its width."""
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


COLOUR_NAMES = [
    ('Black', (20, 20, 20)), ('Grey', (128, 128, 128)), ('Silver', (190, 190, 190)), ('White', (245, 245, 245)),
    ('Cream', (255, 250, 210)), ('Beige', (225, 205, 160)), ('Brown', (120, 75, 35)), ('Tan', (190, 140, 90)),
    ('Red', (210, 30, 30)), ('Coral', (255, 120, 100)), ('Orange', (255, 140, 20)), ('Peach', (255, 200, 160)),
    ('Gold', (230, 180, 30)), ('Yellow', (255, 230, 40)), ('Lime', (170, 230, 50)), ('Green', (40, 160, 50)),
    ('Mint', (170, 240, 200)), ('Olive', (120, 120, 40)), ('Teal', (20, 140, 140)), ('Turquoise', (60, 210, 200)),
    ('Sky Blue', (130, 200, 250)), ('Blue', (40, 90, 220)), ('Navy', (25, 35, 110)), ('Purple', (140, 60, 190)),
    ('Lilac', (200, 160, 230)), ('Magenta', (220, 40, 180)), ('Pink', (250, 150, 200)), ('Maroon', (110, 25, 40)),
]


def tint_of(data, classname):
    """The colour a 'lib*N' furni is drawn in: the first layer its colour N
    tints in anything but white. Zipto's furni data says white for all."""
    if '*' not in classname:
        return None
    n = classname.split('*')[1]
    for vis in data.get('visualizations') or []:
        layers = ((vis.get('colors') or {}).get(n) or {}).get('layers') or {}
        for layer in layers.values():
            colour = layer.get('color')
            if isinstance(colour, int) and colour & 0xFFFFFF != 0xFFFFFF:
                return '#%06X' % (colour & 0xFFFFFF)
    return None


def colour_of(furnidata, tint=None):
    colours = ([tint] if tint else []) + ((furnidata.get('partcolors') or {}).get('color') or [])
    for c in colours:
        m = re.match(r'#?([0-9a-fA-F]{6})$', str(c).strip())
        if m:
            v = int(m.group(1), 16)
            rgb = ((v >> 16) & 255, (v >> 8) & 255, v & 255)
            return min(COLOUR_NAMES, key=lambda c: sum((a - b) ** 2 for a, b in zip(c[1], rgb)))[0]
    return None


rows = []
report = collections.defaultdict(list)
layouts = {}
fid = FURNI_FIRST
for d in (BUNDLE_OUT, ICON_OUT, PAGE_ICON_OUT, RECORD_DIR):
    os.makedirs(d, exist_ok=True)

sets = [n for n in nodes.values() if n['src'] == 'zipto' and n['items'] and under_customs(n['merge'] or n['parent'])]
sets.sort(key=lambda n: (page_id.get(n['id']) or page_of(n['merge']) or 0, n['name'].lower()))
for s in sets:
    target = page_of(s['merge']) if s['merge'] else page_id[s['id']]
    guild = 0
    for item in s['items']:
        lib = item[0]
        for f in variants.get(lib, []):
            classname = f['classname']
            if classname.lower() in have or lib.lower() in SKIP:
                report['already_on_beta'].append(classname)
                continue
            if re.search(r' \(\d+\)$', lib):
                # 'hekoscity_revistas (1)': the download's second copy of a furni this has
                report['download_copy'].append(classname)
                continue
            src = os.path.join(SRC, f['folder'], f['nitro'])
            try:
                bundle = fb.read_furni(src)
            except Exception as e:  # a broken download is left out, never fatal
                report['unreadable'].append('%s %s' % (classname, e))
                continue
            entries = bundle['entries']
            data = json.loads(fb.inflate(entries[next(k for k in entries if k.endswith('.json'))]))
            logic = data.get('logicType') or ''
            if logic == 'furniture_purchasable_clothing' or lib.lower().startswith(
                    ('trax_set', 'wf_act', 'wf_cnd', 'wf_trg', 'wf_xtra')):
                report['left_out'].append(classname)
                continue
            out = os.path.join(BUNDLE_OUT, lib + '.nitro')
            if '*' not in classname or not os.path.exists(out):
                fb.write_bundle(out, entries)
            zfd = f['furnidata'] or {}
            name = ze.english(f['name'], classname) or ze.english(s['name'], s['name']) or s['name']
            x, y, z = bundle['x'], bundle['y'], bundle['z']
            if not bundle['has_dims']:
                x, y = int(zfd.get('xdim') or 1), int(zfd.get('ydim') or 1)
                report['no_dims'].append(classname)
            states = fb.click_states(entries, lib)
            modes, click = max(states) + 1, ''
            if states != list(range(len(states))):
                click = ','.join(map(str, states))
            low = name.lower()
            interaction = LOGIC_TYPES.get(logic, 'default')
            if logic == 'furniture_guild_customized':
                interaction = 'gld_gate' if re.search(r'\bgate\b', low) else 'gld_item'
                guild += 1
            elif interaction == 'default' and modes >= 2 and re.search(r'\bgate$', low):
                interaction = 'gate'
            elif interaction == 'default' and re.search(r'\b(bed|cot)\b', low) and max(x, y) >= 2:
                interaction = 'bed'
            if interaction in ('gate', 'gld_gate'):
                modes, click = 2, ''
            words = (name + ' ' + classname).lower()
            sit = interaction in ('default', 'gld_item') and bool(fb.SEAT.search(words)) and 'table' not in words
            walk = False
            if interaction in ('default', 'stacktool') and not sit and not NOT_FLAT.search(low) and FLAT.search(low):
                drawn = drawn_height(data, lib)
                if drawn is not None and drawn <= 0.35:
                    walk, z = True, round(drawn, 1)
                elif drawn is not None and drawn <= 1.5:
                    walk, z = True, 0.0 if SOFT.search(low) else round(drawn, 1)
                else:
                    report['flat_name_but_tall'].append('%s %s' % (classname, drawn))
            if interaction == 'stacktool':
                walk, z = True, 0.0
            for key, on in (('sit', sit), ('walk', walk)):
                if on:
                    report[key].append(classname)
            if interaction != 'default':
                report[interaction].append(classname)

            icon_src = os.path.join(SRC, f['folder'], f['icon']) if f.get('icon') else None
            icon_name = classname.replace('*', '_') + '_icon.png'
            if icon_src and os.path.exists(icon_src):
                shutil.copyfile(icon_src, os.path.join(ICON_OUT, icon_name))
            elif not (bundle['icon_frame'] and fb.crop_icon(entries, bundle['png'], bundle['icon_frame'],
                                                            os.path.join(ICON_OUT, icon_name))):
                report['no_icon'].append(classname)
            tint = tint_of(data, classname)
            partcolors = zfd.get('partcolors') or {'color': []}
            if tint and all(str(c).upper() in ('#FFFFFF', 'FFFFFF') for c in partcolors.get('color') or []):
                partcolors = {'color': [tint]}            # the shop's swatch in the colour it is
            rows.append(dict(id=fid, classname=classname, lib=lib, name=name, page=target, x=x, y=y, z=z,
                             sit=sit, walk=walk, lay=interaction == 'bed', interaction=interaction,
                             modes=modes, click=click, colour=colour_of(zfd, tint),
                             partcolors=partcolors,
                             defaultdir=zfd.get('defaultdir') or 0, set=s['name']))
            fid += 1
    if not s['merge'] and guild * 2 > len(s['items']):
        layouts[target] = 'guild_custom_furni'
if fid - 1 > FURNI_LAST:
    raise SystemExit('furni ids ran past %d' % FURNI_LAST)

# Colours of one furni read 'Red Chair', 'Blue Chair'; any other name used twice
# on a page gets a number in page order: Pumpkin, Pumpkin 2 ...
by_lib = collections.defaultdict(list)
for r in rows:
    by_lib[r['lib']].append(r)
for group in by_lib.values():
    shared = collections.Counter(r['name'] for r in group)
    for r in group:
        if shared[r['name']] > 1 and r['colour'] and r['colour'].lower() not in r['name'].lower():
            r['name'] = '%s %s' % (r['colour'], r['name'])
seen = collections.defaultdict(collections.Counter)
for r in rows:
    seen[r['page']][r['name']] += 1
    count = seen[r['page']][r['name']]
    if count > 1:
        r['name'] = '%s %d' % (r['name'], count)
for r in rows:
    r['name'] = ascii_only(r['name'][:NAME_MAX].strip(), 'name of %s' % r['classname'])


# ---- page icons ------------------------------------------------------------------

def fit_icon(path, out, size=18):
    from PIL import Image
    image = Image.open(path).convert('RGBA')
    box = image.getbbox()
    if box:
        image = image.crop(box)
    image.thumbnail((size, size), Image.LANCZOS)
    image.save(out, 'PNG')


def icon_path(rel):
    return os.path.join(SRC, unquote(rel)) if rel else None


def own_items(nid):
    yield from nodes[nid]['items']
    for k in children[nid]:
        yield from own_items(k)


for p in new_pages:
    src = icon_path(nodes[p['node']].get('icon'))
    if not (src and os.path.exists(src)):
        # no icon chosen: the first of its own furni (or its folders') that has one
        src = next((icon_path(it[3]) for it in own_items(p['node'])
                    if it[3] and os.path.exists(icon_path(it[3]))), None)
    if not (src and os.path.exists(src)):
        # nor a Zipto icon: the icon this import cut from one of its bundles
        src = next((os.path.join(ICON_OUT, r['classname'].replace('*', '_') + '_icon.png') for r in rows
                    if r['page'] == p['id'] and os.path.exists(
                        os.path.join(ICON_OUT, r['classname'].replace('*', '_') + '_icon.png'))), None)
    if src and os.path.exists(src):
        fit_icon(src, os.path.join(PAGE_ICON_OUT, 'icon_%d.png' % p['id']))
        p['icon'] = p['id']
    else:
        p['icon'] = 193
        report['page_without_icon'].append(p['caption'])
line_icons = []
for k, n in enumerate(sorted(lines, key=lambda n: n['name'])):
    src = icon_path(n.get('icon'))
    if src and os.path.exists(src):
        number = LINE_ICON_FIRST + k
        fit_icon(src, os.path.join(PAGE_ICON_OUT, 'icon_%d.png' % number))
        line_icons.append((page_of(n['id']), number))


# ---- gamedata --------------------------------------------------------------------

furnitype = [{
    'id': r['id'], 'classname': r['classname'], 'revision': 0, 'category': 'customs',
    'defaultdir': r['defaultdir'], 'xdim': r['x'], 'ydim': r['y'], 'partcolors': r['partcolors'],
    'name': r['name'], 'description': r['name'], 'adurl': '', 'offerid': -1, 'buyout': False,
    'rentofferid': -1, 'rentbuyout': False, 'bc': False, 'excludeddynamic': False, 'customparams': '',
    'specialtype': 1, 'canstandon': r['walk'], 'cansiton': r['sit'], 'canlayon': r['lay'],
    'furniline': 'customs',
} for r in rows]
texts = {}
for r in rows:
    texts['%s_name' % r['classname']] = r['name']
    texts['%s_desc' % r['classname']] = r['name']
json.dump({'furnitype': furnitype, 'externaltexts': texts},
          open(os.path.join(RECORD_DIR, 'customs-furnidata-entries.json'), 'w', encoding='utf-8'), indent=1)

merged = json.load(open(MERGE_FURNI, encoding='utf-8'))
for kind in ('roomitemtypes', 'wallitemtypes'):
    if kind in merged:
        merged[kind]['furnitype'] = [e for e in merged[kind]['furnitype']
                                     if not FURNI_FIRST <= e['id'] <= FURNI_LAST]
merged['roomitemtypes']['furnitype'].extend(furnitype)
json.dump(merged, open(MERGE_FURNI, 'w', encoding='utf-8'))
merged_texts = json.load(open(MERGE_TEXTS, encoding='utf-8'))
merged_texts.update(texts)
json.dump(merged_texts, open(MERGE_TEXTS, 'w', encoding='utf-8'), indent=1)


# ---- SQL -------------------------------------------------------------------------

with open(SQL_OUT, 'w', encoding='utf-8', newline='\n') as o:
    o.write("""\
-- PixelRP: Customs as the Shop Planner maps it, with the Zipto furni from
-- outside Zipto's shop.
--
-- Customs is %(cats)d categories, A-Z, each a list of sets or a few folders of
-- them. Our own sets move into them (%(moves)d pages, %(renames)d renamed where a
-- folder would repeat a name); %(joins)d of ours join another of the same name;
-- the sets the map empties are hidden (a hidden page is one flag to undo).
--
-- %(furni)d furni from Zipto's download that beta did not have - by name or by
-- picture - on %(pages)d new pages (sets and folders), English names, free like
-- the rest of the catalog. Not imported: Trax, wired, clothing. The furni
-- lines wear their own chair (catalog icons %(icons)s).
--
-- Generated by docker/nitro/import-zipto-customs.py from the map Twist
-- exported (shop-plan.json, %(saved)s). The rendering half is the bundles,
-- icons and FurnitureData under nitro/overrides/.
--
-- Idempotent: fixed id ranges (furni %(f1)d-%(f2)d, pages %(p1)d-%(p2)d), cleared
-- before insert; moves and orders are absolute.

SET @rank := COALESCE((SELECT `min_rank` FROM `catalog_pages` WHERE `id` = 944000), 2);

DELETE FROM `catalog_items` WHERE `item_id` REGEXP '^2(1[3-9]|[23][0-9]|4[0-6])[0-9]{3}$';
DELETE FROM `catalog_pages` WHERE `id` BETWEEN %(p1)d AND %(p2)d;
DELETE FROM `furniture` WHERE `id` BETWEEN %(f1)d AND %(f2)d;

""" % dict(cats=len(children[CUSTOMS]), moves=len(moves), renames=len(renames), joins=len(joins),
           furni=len(rows), pages=len(new_pages), icons='%d-%d' % (LINE_ICON_FIRST, LINE_ICON_FIRST + len(line_icons) - 1),
           saved=plan.get('saved', '?')[:10], f1=FURNI_FIRST, f2=FURNI_LAST, p1=PAGE_FIRST, p2=PAGE_LAST))

    o.write('INSERT INTO `catalog_pages` (`id`,`parent_id`,`caption`,`icon_image`,`min_rank`,'
            '`min_vip`,`order_num`,`page_link`,`page_layout`,`page_strings_1`,`page_strings_2`,'
            '`visible`,`enabled`) VALUES\n')
    o.write(',\n'.join(
        "    (%d,%d,%s,%d,@rank,0,%d,'',%s,'','',b'1',b'1')"
        % (p['id'], p['parent'], esc(p['caption']), p['icon'], p['order'],
           esc(layouts.get(p['id'], 'default_3x3')))
        for p in new_pages) + ';\n\n')

    o.write('-- our own sets into the folders, A-Z\n')
    for pid, parent in moves:
        o.write('UPDATE `catalog_pages` SET `parent_id` = %d WHERE `id` = %d;\n' % (parent, pid))
    for pid, order in orders:
        o.write('UPDATE `catalog_pages` SET `order_num` = %d WHERE `id` = %d;\n' % (order, pid))
    for pid, caption in renames:
        o.write('UPDATE `catalog_pages` SET `caption` = %s WHERE `id` = %d;\n' % (esc(caption), pid))
    o.write('\n-- ours that join another of the same name, and the sets the map empties\n')
    for src, into in joins:
        o.write('UPDATE `catalog_items` SET `page_id` = %d WHERE `page_id` = %d;\n' % (into, src))
    for pid in hidden:
        o.write("UPDATE `catalog_pages` SET `visible` = b'0', `enabled` = b'0' WHERE `id` = %d;\n" % pid)
    o.write('\n-- the furni lines wear their own chair\n')
    for pid, number in line_icons:
        o.write('UPDATE `catalog_pages` SET `icon_image` = %d WHERE `id` = %d;\n' % (number, pid))

    o.write('\n-- Furniture. id == sprite_id; clicks from furni_bundle.click_states.\n')
    for batch in chunks(rows, ROWS_PER_INSERT):
        o.write('INSERT INTO `furniture` (`id`,`item_name`,`public_name`,`type`,`width`,`length`,'
                '`stack_height`,`can_stack`,`can_sit`,`is_walkable`,`sprite_id`,`allow_recycle`,'
                '`allow_trade`,`allow_marketplace_sell`,`allow_gift`,`allow_inventory_stack`,'
                '`interaction_type`,`behaviour_data`,`interaction_modes_count`,`is_rare`) VALUES\n')
        o.write(',\n'.join(
            "    (%d,%s,%s,'s',%d,%d,%s,'1','%d','%d',%d,'0','1','0','1','1',%s,0,%d,'0')"
            % (r['id'], esc(r['classname']), esc(r['name']), r['x'], r['y'], r['z'],
               r['sit'], r['walk'], r['id'], esc(r['interaction']), r['modes'])
            for r in batch) + ';\n')
    clicks = [r for r in rows if r['click']]
    if clicks:
        o.write('\n')
        for r in clicks:
            o.write("UPDATE `furniture` SET `click_states` = '%s' WHERE `id` = %d;\n" % (r['click'], r['id']))
    o.write('\n')
    for batch in chunks(rows, ROWS_PER_INSERT):
        o.write('INSERT INTO `catalog_items` (`page_id`,`item_id`,`catalog_name`,`cost_credits`,'
                '`cost_pixels`,`cost_diamonds`,`amount`,`limited_sells`,`limited_stack`,'
                '`offer_active`,`extradata`,`badge`,`offer_id`) VALUES\n')
        o.write(',\n'.join(
            "    (%d,'%d',%s,0,0,0,1,0,0,'1','','',-1)" % (r['page'], r['id'], esc(r['name']))
            for r in batch) + ';\n')

json.dump(dict({k: v for k, v in report.items()}, pages=len(new_pages), moves=len(moves), renames=renames,
               joins=joins, hidden=hidden, line_icons=line_icons, layouts=layouts),
          open(os.path.join(RECORD_DIR, 'customs-import-report.json'), 'w', encoding='utf-8'), indent=1)
print('furni %d (ids %d-%d)  new pages %d (%d-%d)  moved %d  renamed %d  joined %d  hidden %d  line icons %d'
      % (len(rows), FURNI_FIRST, fid - 1, len(new_pages), PAGE_FIRST + 1, next_page - 1, len(moves),
         len(renames), len(joins), len(hidden), len(line_icons)))
print('  '.join('%s %d' % (k, len(v)) for k, v in sorted(report.items())))
