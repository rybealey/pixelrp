#!/usr/bin/env python3
"""Build the shop planner: the whole furni shop on one page, to be mapped out.

    ZIPTO_FP=<zipto_fp.jsonl> python3 docker/nitro/shop-planner.py <beta export dir> [~/Desktop/Zipto Import]

Writes `_shop-planner.html` into the Zipto Import folder. It shows every tab
and page of the shop as beta has it today, with the proposal for Customs
already applied:

  - Customs becomes twelve category folders (the Zipto picker's categories,
    without Trax Songs, Wired and Game Kit and Clothing Furni), with their
    sub-categories, and every Zipto set in its place
  - the sets Customs has today move into those folders (CUSTOMS_PLAN);
    Holidays splits into the Seasonal folders its three pages belong in
  - where Zipto has a set on the same subject as one we sell, its furni join
    ours (MERGES), or go inside ours as a page when ours has pages of its own

Anything can then be moved, renamed, merged or put in a new folder on the
page, and the result leaves as a JSON file (Export) that the import reads.

The beta export dir holds three tab-separated dumps (utf8mb4):
  catalog_pages2.tsv  id parent_id caption icon_image min_rank order_num page_link page_layout visible enabled
                      [mirror target: page_strings_1 where page_link = mirror]
  catalog_items2.tsv  id page_id item_id catalog_name
  furniture2.tsv      id item_name public_name type
and the Zipto Import folder holds beta's icons in _pixel/icons and
_pixel/catalogue (copied from nitro/assets/dcr/hof_furni/icons and
c_images/catalogue).
"""
import collections
import importlib.util
import json
import os
import re
import sys
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
EXPORT = sys.argv[1]
SRC = os.path.expanduser(sys.argv[2] if len(sys.argv) > 2 else '~/Desktop/Zipto Import')

spec = importlib.util.spec_from_file_location('zipto_picker', os.path.join(HERE, 'zipto-picker.py'))
picker = importlib.util.module_from_spec(spec)
sys.argv = [sys.argv[0], SRC]
spec.loader.exec_module(picker)

CUSTOMS = 944000
SKIP_CATEGORIES = picker.LEFT_OUT

# Where each set Customs has today goes: caption -> (category, sub-category),
# named as the picker sorts them; picker.place() turns that into the folder.
B = 'Building & Structure'
CUSTOMS_PLAN = {
    'Adobe': ('Furniture Sets', 'Modern'),
    'Aesthetic & Pastel': ('Furniture Sets', 'Pink and Pastel'),
    'Animal Crossing': ('Pop Culture', 'Video Games'),
    'Animals': ('Garden and Nature', 'Animals'),
    'Arcade Machines': ('Pop Culture', 'Video Games'),
    'Asian': ('Themes', 'Asian and Middle Eastern'),
    'Asthorine': (B, 'Doors and Windows'),
    'Ate': ('Rooms', None),
    'Axov Glass': (B, 'Doors and Windows'),
    'Bathroom': ('Rooms', None),
    'Beach': ('Seasonal', 'Summer and Beach'),
    'Beach & Water': ('Seasonal', 'Summer and Beach'),
    'Beauty Salon': ('Rooms', None),
    'Blue Classic': ('Furniture Sets', 'Classic and Antique'),
    'Bricks': (B, 'Bricks and Blocks'),
    'Brothel': ('Rooms', None),
    'Bsstonino': ('Furniture Sets', 'Other Styles'),
    'Building': (B, 'Construction'),
    'Building & Structure': (B, None),        # split: see SPLITS
    'Cartier': ('Brands', None),
    'Casino': ('Themes', 'Sports and Games'),
    'Cheapyxony': ('Furniture Sets', 'Modern'),
    'Christmas Charm': ('Seasonal', 'Christmas and Winter'),
    'Church': ('Rooms', None),
    'Cokemusic': ('Brands', None),
    'Constellations': ('Themes', 'Space and Sci-Fi'),
    'Cottage & Country': ('Furniture Sets', 'Wood and Rustic'),
    'Decoration & Art': ('Themes', 'Art and Pictures'),
    'Details': ('Furniture Sets', 'Decorations'),
    'Disneyland': ('Pop Culture', 'TV and Film'),
    'Exterior Modern': (B, 'Roofs and Exteriors'),
    'Fantasy & Medieval': ('Themes', 'Medieval and Fantasy'),
    'Feerique': ('Themes', 'Medieval and Fantasy'),
    'Flirty': ('Seasonal', "Valentine's"),
    'Fruit Chairs': ('Furniture Sets', 'Seating'),
    'Fuel Station': ('Themes', 'City and Roleplay'),
    'Garage': ('Themes', 'City and Roleplay'),
    'Garden & Nature': ('Garden and Nature', 'Garden'),
    'Greek & Classical': ('Themes', 'Ancient Worlds'),
    'Gym': ('Themes', 'Sports and Games'),
    'Haddin Statues': ('Rares and Collectibles', 'Statues and Trophies'),
    'Hanami': ('Themes', 'Asian and Middle Eastern'),
    'Harry Potter': ('Pop Culture', 'TV and Film'),
    'Holidays': ('Seasonal', None),          # split: see SPLITS
    'Honey': ('Food and Sweets', None),
    'Ice Age': ('Pop Culture', 'TV and Film'),
    'Icy Blue': ('Seasonal', 'Christmas and Winter'),
    'Kindergarten': ('Rooms', None),
    'Kitchen': ('Rooms', None),
    'Labubu': ('Pop Culture', 'Toys and Plushies'),
    'Living Room & Bedroom': ('Rooms', None),
    'Mafia': ('Themes', 'City and Roleplay'),
    'Man Cave': ('Rooms', None),
    'Mario': ('Pop Culture', 'Video Games'),
    'Mcdonalds': ('Brands', None),
    'Medieval Doors': (B, 'Doors and Windows'),
    'Micromania': ('Pop Culture', 'Video Games'),
    'Mines': ('Themes', 'City and Roleplay'),
    'Mini Items': ('Pop Culture', 'Toys and Plushies'),
    'Minimalistic': ('Furniture Sets', 'Modern'),
    'Modern': ('Furniture Sets', 'Modern'),
    'Nature': ('Garden and Nature', 'Garden'),
    'Neopets': ('Pop Culture', 'Video Games'),
    'Office': ('Rooms', None),
    'Oriental': ('Themes', 'Asian and Middle Eastern'),
    'Pallets': ('Furniture Sets', 'Wood and Rustic'),
    'Palms': ('Garden and Nature', 'Plants and Flowers'),
    'Persia': ('Themes', 'Asian and Middle Eastern'),
    'Promotional': ('Brands', None),
    'Rabbits invasion': ('Pop Culture', 'Video Games'),
    'Railings': (B, 'Railings, Fences and Trim'),
    'Regazza': ('Themes', 'City and Roleplay'),
    'Retro': ('Furniture Sets', 'Other Styles'),
    'Rooftops': (B, 'Roofs and Exteriors'),
    'Rylai Japan': ('Themes', 'Asian and Middle Eastern'),
    'Sanrio': ('Pop Culture', 'Toys and Plushies'),
    'Scandinavian & Cabin': ('Furniture Sets', 'Wood and Rustic'),
    'Selva': ('Garden and Nature', 'Garden'),
    'Shadow VIP': ('Rooms', None),
    'Shops, Cafés & Venues': ('Rooms', None),
    'Spatial': ('Themes', 'Space and Sci-Fi'),
    'Stage Production': ('Themes', 'Music and Cinema'),
    'Tennis': ('Themes', 'Sports and Games'),
    'Tiles': (B, 'Floors and Tiles'),
    'Traffic': ('Themes', 'City and Roleplay'),
    'Underground': ('Themes', 'City and Roleplay'),
    'Victorians': ('Furniture Sets', 'Classic and Antique'),
    'Virus': ('Seasonal', 'Halloween'),
    'White Christmas': ('Seasonal', 'Christmas and Winter'),
    'Windows': (B, 'Doors and Windows'),
    'Zara': ('Brands', None),
}
# Our sets that are emptied, each page inside going to the folder it belongs in
# (None: any other page). Holidays' pages go to their Seasonal folders; Building
# & Structure is now a whole category, so its pages spread over its folders.
SPLITS = {
    'Holidays': {'Christmas': ('Seasonal', 'Christmas and Winter'), 'Halloween': ('Seasonal', 'Halloween'),
                 "Valentine's Day": ('Seasonal', "Valentine's"), None: ('Seasonal', 'Parties and Festivals')},
    'Building & Structure': {'Blocks': (B, 'Bricks and Blocks'), 'Construction': (B, 'Construction'),
                             'Walls & Floors': (B, 'Walls and Panels'), 'Borders': (B, 'Floors and Tiles'),
                             'Exteriors': (B, 'Roofs and Exteriors'), 'House Set': (B, 'Roofs and Exteriors'),
                             None: (B, 'Bricks and Blocks')},
    # its pages are the Modern folder's own (Furniture Sets > Modern > Modern)
    'Modern': {None: ('Furniture Sets', 'Modern')},
    # and these are their category's own
    'Fantasy & Medieval': {None: ('Themes', 'Medieval and Fantasy')},
}
# Our pages renamed where their new folder would repeat the name
# (Building & Structure > Construction > Construction)
RENAMES = {944008: 'Construction Site', 955401: 'Posts and Fittings',
           955361: 'Halloween Decor',          # Seasonal > Halloween > Halloween
           955160: 'Modern Basics',            # Furniture Sets > Modern > Modern
           944035: 'Harry Potter Extras',      # Harry Potter > Harry Potter
           955320: 'Garden Odds',              # Garden > Garden & Nature > Garden
           955142: 'Home Basics',              # Rooms > Living Room & Bedroom > Rooms
           964014: 'Sheep and Friends'}        # Animals > Animals
# Our one-page sets that are a page of another of our sets under the same
# name, now that both sit in one category: caption -> (that set, its page).
# Their furni join that page.
PIXEL_MERGES = {'Oriental': ('Asian', 'Oriental'), 'Nature': ('Garden & Nature', 'Nature'),
                'Beach': ('Beach & Water', 'Beach')}
# Zipto sets that are a set of ours under another name: set id -> our set
MERGE_IDS = {'habbox/habbox.fr': 'Asthorine',          # Asthorine doors and windows
             'bw/bw': 'Harry Potter'}                  # Gryffindor ... Slytherin furni, a Dementor
# Zipto sets that go inside one of our sets with pages, by what they are
# called: our set -> a regex on the Zipto set's name. One Kitchen, not two.
INSIDE = {'Kitchen': r'\bkitchen\b'}
# Folders renamed since an earlier build: the planner moves saved edits across
ALIASES = {'c:Building': 'c:' + B, 'c:Building/Doors and Windows': 'c:%s/Doors and Windows' % B,
           'c:Building/Floors and Tiles': 'c:%s/Floors and Tiles' % B,
           'c:Building/Letters and Numbers': 'c:%s/Letters and Numbers' % B,
           'c:Building/Walls and Blocks': 'c:%s/Walls and Panels' % B}
# Seasonal stayed a category (Twist): the build that had its folders on their own
ALIASES.update({'c:' + k: 'c:Seasonal/' + k for k in (
    'Autumn', 'Christmas & Winter', 'Easter', 'Halloween', 'Parties & Festivals', 'Summer & Beach', "Valentine's")})


def folder_id(cat, sub):
    return 'c:' + cat + ('/' + sub if sub else '')


def aliases():
    """Old folder id -> the folder it is now, for every folder the builds
    before the many-categories reshape had."""
    out = {folder_id(*old): folder_id(*picker.place(*old)) for old in picker.RESHAPE}
    out.update({old: out.get(new, new) for old, new in ALIASES.items()})
    return {old: new for old, new in out.items() if old != new}
# Zipto set name -> our Customs set it joins
MERGES = {
    "McDonald's": 'Mcdonalds',
    'Harry Potter': 'Harry Potter',
    'Harry Potter Pets': 'Harry Potter',
    'Super Mario': 'Mario',
    'Mafia Den': 'Mafia',
    'Gym Equipment': 'Gym',
    'Poker Room': 'Casino',
}


LINES = 2000001
# Lines whose own chair is missing or reads badly small: the piece picked by eye
LINE_ICONS = {
    'Classics': 'classic7_dvdr', 'Dream': 'dream_c24_rainbowroad3', 'Glass': 'glass_sofa',
    'Iced Dark': 'icedblk_c16_sofachair*10', 'Legacy': 'bed_trad', 'Lodge': 'divider_arm2',
    'Lodge Dark': 'lodge_dark_divider', 'Mode Gold': 'mode_gold_bardeskcorner*1',
    'Origins': 'plasto_c24_shelf*10', 'Relax': 'rela_hchair',
}
# What a folder should be shown by (a regex on classname and name)
FOLDER_HINTS = {
    'Seasonal': r'christmas.?tree|xmas.?tree|xmastree',
    'Rooms': r'sofa|couch', 'Furniture Sets': r'armchair', 'Pokemon': r'^pokeweebz025 ',
    B: r'brick', 'Rares and Collectibles': r'^rare_dragonlam', 'Dark and Gothic': r'gothic|skull|black',
    'Ocean and Pirates': r'pirate|fish|coral', 'Fantasy and Medieval': r'throne|castle|dragon',
    'Food and Sweets': r'cake|cupcake|donut|doughnut|icecream|ice_cream|pizza|burger|candy',
    'Brands': r'mcdonald|coca|coke', 'Group Furni': r'flag|banner|gld',
    'Christmas and Winter': r'christmas.?tree|xmas.?tree|xmastree|snowman', 'Halloween': r'(^|_)pumpkin',
    'Easter': r'egg|bunny', "Valentine's": r'heart', 'Autumn': r'leaves|autumn.*tree',
    'Summer and Beach': r'parasol|palm|beach', 'Parties and Festivals': r'balloon|gift|present',
    'Wild West': r'western|cactus|saloon',
    'Asian and Middle Eastern': r'lantern|sakura|bonsai', 'Ancient Worlds': r'column|pillar|pharaoh|viking',
    'Space and Sci-Fi': r'rocket|planet|alien', 'City and Roleplay': r'(^|_)car(\b|_)|traffic',
    'Music and Cinema': r'guitar|piano|jukebox|speaker',
    'Sports and Games': r'chess|football|basketball|bowling', 'Art and Pictures': r'painting|easel',
    'Modern': r'sofa|armchair',
    'Wood and Rustic': r'wood|cabin|log', 'Pink and Pastel': r'pink|pastel',
    'Classic and Antique': r'chandelier|armchair', 'Other Styles': r'chair',
    'Plants and Flowers': r'flower|plant', 'Garden': r'garden|fence', 'Animals': r'(^|_)(dog|duck|bunny|horse|penguin|panda)(_|\d| |$)',
    'Floors and Tiles': r'tile|floor', 'Doors and Windows': r'door',
    'Bricks and Blocks': r'brick|block', 'Walls and Panels': r'wall|panel', 'Roofs and Exteriors': r'roof',
    'Railings, Fences and Trim': r'barriere|fence|rampe', 'Construction': r'crane|construct', 'Letters and Numbers': r'letter|alpha',
    'Anime': r'naruto', 'Video Games': r'mario|pacman|arcade',
    'TV and Film': r'harry|potter|toystory|disney', 'Toys and Plushies': r'plush|teddy|duck', 'Rares': r'rare',
    'Statues and Trophies': r'statue|trophy', 'Eggs and Lamps': r'lamp', 'Dragons': r'dragon', 'Collectibles': r'gold',
    'Lighting': r'(^|_)lamp|lantern|chandelier', 'Bathroom': r'bath|toilet|shower|sink',
    'Trees and Nature': r'(^|_)(tree|oak|palm)(_|\d| |$)',
    'Music': r'guitar|piano|drum|speaker|jukebox', 'Electronics and Games': r'(^|_)tv|computer|arcade|console',
    'Walls and Building': r'brick|wall|pillar', 'Kitchen, Food and Drink': r'fridge|oven|cake',
    'Toys and Figures': r'plush|teddy', 'Decorations': r'vase|statue', 'Tables and Desks': r'table|desk',
    'Storage': r'shelf|cabinet|wardrobe|chest', 'Beds': r'(^|_)bed', 'Vehicles': r'(^|_)(car|bike|truck|bus)(_|\d| |$)',
    'Pictures and Signs': r'painting|poster', 'Seating': r'armchair|sofa|chair', 'Floors and Rugs': r'rug|carpet',
    'Fashion and Accessories': r'bag|shoe|hat',
}


# Hints are looked up with '&' read as 'and'
FOLDER_HINTS = {k.replace(' & ', ' and '): v for k, v in FOLDER_HINTS.items()}

# Folders whose hint still found nothing that reads well: the piece picked by eye
FOLDER_ICONS = {
    'c:Fantasy & Medieval': 'throne_bed',
    'c:Seasonal': 'sapincoloreyvess_noel',
    'c:Seasonal/Easter': 'Easter_Cloud_1',
    'c:Food & Sweets': 'wedding_cake',
    'c:Toys & Plushies': 'hfdiy_lovebear_iceblue',
    'c:Group Furni': 'shadow_clr_group_hangflag',
    'c:Furniture Sets/Classic & Antique': 'victorian2_106',
    'c:Garden': 'W04_Arvore_Grande_Carvalho',
    'c:Building & Structure/Walls & Panels': 'prisma_colorw_amethyst',
    'c:Building & Structure/Floors & Tiles': 'suelos_cespeds',
    'c:Building & Structure/Roofs & Exteriors': 'nify_toit_rouge_chalet',
    'c:Building & Structure/Railings, Fences & Trim': 'wibbo_Barrierehorizon_Alaska',
}


def choose_icons(nodes):
    """Pages in Customs, and the Lines, wear one of their own furni.

    A set wears its best piece; a folder wears a piece that says what it is
    (FOLDER_HINTS) and never the icon of a page directly inside it; pages side
    by side are kept apart. Our own Customs sets keep the icons they have."""
    from urllib.parse import unquote
    sys.path.insert(0, HERE)
    import shop_icons as si

    def path_of(it):
        return os.path.join(SRC, unquote(it[3])) if it and it[3] else None

    children = collections.defaultdict(list)
    for n in nodes.values():
        if not n.get('dropped'):
            children[n.get('merge') or n['parent']].append(n['id'])

    def own(nid):
        return nodes[nid]['items'] + [it for k in children[nid] if nodes[k].get('merge') == nid
                                      for it in nodes[k]['items']]

    def below(nid):
        out = list(own(nid))
        for k in children[nid]:
            if not nodes[k].get('merge'):
                out += below(k)
        return out

    def depth_first(nid):
        for k in children[nid]:
            yield from depth_first(k)
        yield nid

    used_by_parent = collections.defaultdict(set)
    for nid in depth_first('p%d' % CUSTOMS):
        n = nodes[nid]
        if nid == 'p%d' % CUSTOMS or n['src'] == 'pixel' or n.get('merge'):
            if n['icon']:
                used_by_parent[n['parent']].add(path_of(['', '', 0, n['icon']]))
            continue
        kid_icons = {path_of(['', '', 0, nodes[k]['icon']]) for k in children[nid] if nodes[k]['icon']}
        avoid = kid_icons | used_by_parent[n['parent']]
        items = own(nid) or below(nid)
        if n['src'] == 'new':
            items = below(nid)
        best = next((it for it in items if it[0] == FOLDER_ICONS.get(nid)), None) or \
            si.pick(items, path_of, avoid=avoid, prefer=FOLDER_HINTS.get(n['name'].replace(' & ', ' and ')))
        if best:
            n['icon'] = best[3]
            used_by_parent[n['parent']].add(path_of(best))

    used = set()
    for nid, n in nodes.items():
        if n['parent'] != 'p%d' % LINES:
            continue
        want = LINE_ICONS.get(n['name'])
        best = next((it for it in n['items'] if it[0] == want), None) if want else None
        best = best or si.pick(n['items'], path_of, avoid=used, prefer_chair=True)
        if best:
            n['icon'] = best[3]
            n['newIcon'] = True
            used.add(path_of(best))


def tsv(name):
    out = []
    for line in open(os.path.join(EXPORT, name), encoding='utf-8'):
        out.append(line.rstrip('\n').split('\t'))
    return out


def main():
    furniture = {r[0]: (r[1], r[2]) for r in tsv('furniture2.tsv') if len(r) >= 3}
    pages = {}
    for r in tsv('catalog_pages2.tsv'):
        pages[int(r[0])] = dict(id=int(r[0]), parent=int(r[1]), caption=r[2], icon=int(r[3]),
                                rank=int(r[4]), order=int(r[5]), link=r[6], layout=r[7],
                                visible=r[8] == '1', enabled=r[9] == '1',
                                mirror=int(r[10]) if len(r) > 10 and r[10].isdigit() else 0)
    items = collections.defaultdict(list)
    for r in tsv('catalog_items2.tsv'):
        if len(r) < 3:
            continue
        fid = r[2].split(';')[0]
        cn, public = furniture.get(fid, ('', ''))
        icon = '_pixel/icons/' + quote(cn.replace('*', '_') + '_icon.png') if cn else ''
        items[int(r[1])].append([cn or fid, (r[3] if len(r) > 3 else '') or public, 1, icon, ''])

    nodes = collections.OrderedDict()

    def add(nid, name, parent, kind, src, order, its=None, icon='', extra=None):
        nodes[nid] = dict(id=nid, name=name, parent=parent, kind=kind, src=src, order=order,
                          items=its or [], icon=icon, **(extra or {}))
        return nid

    # ---- the shop as beta has it
    for pid, p in sorted(pages.items(), key=lambda kv: (kv[1]['order'], kv[0])):
        kind = 'tab' if p['parent'] == -1 else ('heading' if p['link'] == 'heading' else
                                               'mirror' if p['link'] == 'mirror' else 'page')
        extra = {'hidden': not (p['visible'] and (p['enabled'] or kind in ('heading', 'mirror'))), 'page': pid}
        if kind == 'mirror' and p['mirror']:
            # a mirror holds nothing itself: the shop shows that page's branch here too
            extra['mirror'] = 'p%d' % p['mirror']
        add('p%d' % pid, p['caption'], None if p['parent'] == -1 else 'p%d' % p['parent'], kind, 'pixel',
            p['order'], items[pid], '_pixel/catalogue/icon_%d.png' % p['icon'], extra)

    # ---- Customs: category folders, A-Z
    data = picker.build_data()

    def ensure(cat, sub):
        """The folder for a category (and folder in it) as picker.place() names them."""
        nid = folder_id(cat, sub)
        if nid not in nodes:
            add(nid, sub or cat, ensure(cat, None) if sub else 'p%d' % CUSTOMS, 'page', 'new', 0)
        return nid

    # our Customs sets into the folders
    by_caption = {}
    for nid, n in list(nodes.items()):
        if n['parent'] == 'p%d' % CUSTOMS and n['src'] == 'pixel':
            by_caption[n['name']] = nid
            cat, sub = CUSTOMS_PLAN.get(n['name'], ('Furniture Sets', 'Decorations'))
            if n['name'] in SPLITS:
                split = SPLITS[n['name']]
                for kid in [k for k in nodes.values() if k['parent'] == nid]:
                    kid['parent'] = ensure(*picker.place(*split.get(kid['name'], split[None])))
                n['parent'] = None          # emptied: dropped
                n['dropped'] = True
                continue
            n['parent'] = ensure(*picker.place(cat, sub))
    was = {}
    for pid, name in RENAMES.items():
        was['p%d' % pid] = nodes['p%d' % pid]['name']
        nodes['p%d' % pid]['name'] = name

    def has_pages(nid):
        return any(n['parent'] == nid for n in nodes.values())

    # our one-page sets that are a page of another of ours: their furni join it
    for caption, (owner, page) in PIXEL_MERGES.items():
        src, home = by_caption.get(caption), by_caption.get(owner)
        into = next((k for k, n in nodes.items() if home and n['parent'] == home and n['name'] == page), None)
        if src and into and not has_pages(src):
            nodes[src]['merge'] = into

    # Zipto's sets
    fp = {}
    if picker.FINGERPRINTS and os.path.exists(picker.FINGERPRINTS):
        for line in open(picker.FINGERPRINTS, encoding='utf-8'):
            r = json.loads(line)
            fp[r['file'].lower()] = r.get('logic') or ''
    manifest = json.load(open(os.path.join(SRC, '_import.json'), encoding='utf-8'))
    nitro_of = {}
    for f in manifest['furni']:
        nitro_of.setdefault(f['classname'].split('*')[0], f['nitro'][:-6].lower())

    def unusable(lib):
        lg = fp.get(nitro_of.get(lib, ''), '')
        return lg == 'furniture_purchasable_clothing' or lib.lower().startswith(
            ('trax_set', 'wf_act', 'wf_cnd', 'wf_trg', 'wf_xtra'))

    skipped = add('t:skip', 'Not importing', None, 'tab', 'new', 99, extra={'note': 'Trax, Wired and Clothing - left out'})
    for s in data['sets']:
        cat, sub = s['g'].split('/', 1)
        sub = None if sub == cat else sub
        keep = [it for it in s['items'] if not unusable(it[0])]
        gone = [it for it in s['items'] if unusable(it[0])]
        nid = 'z:' + s['id']
        if cat in SKIP_CATEGORIES:
            add(nid, s['t'], skipped, 'page', 'zipto', 0, s['items'], extra={'raw': s['raw']})
            continue
        if gone:
            add(nid + ':gone', s['t'] + ' (left out)', skipped, 'page', 'zipto', 0, gone)
        if not keep:
            continue
        target = MERGE_IDS.get(s['id']) or MERGES.get(s['t']) or next(
            (owner for owner, rx in INSIDE.items() if re.search(rx, s['t'], re.I)), None)
        parent = ensure(cat, sub)
        extra = {'raw': s['raw'], 'note': s.get('note', '')}
        if target and target in by_caption:
            ours = nodes[by_caption[target]]
            if has_pages(ours['id']):
                parent = ours['id']        # a page inside ours
            else:
                extra['merge'] = ours['id']    # its furni join our page
        add(nid, s['t'], parent, 'page', 'zipto', 0, keep, extra=extra)

    # A Zipto set called what one of our pages in the same category is called
    # joins that page (Arcade Machines, Sakura, Modern Kitchen ...): one page
    # of that name, not two side by side.
    def category_of(nid):
        while nodes[nid]['parent'] and nodes[nid]['parent'] != 'p%d' % CUSTOMS:
            nid = nodes[nid]['parent']
        return nid if nodes[nid]['parent'] else None

    def same(name):
        return re.sub(r'[^a-z0-9]', '', name.lower().replace('&', 'and'))

    ours = {}
    for nid, n in nodes.items():
        if n['src'] == 'pixel' and n['items'] and not n.get('merge') and not n.get('dropped') \
                and not has_pages(nid) and category_of(nid):
            for name in (n['name'], was.get(nid)):
                if name:
                    ours.setdefault((category_of(nid), same(name)), nid)
    for nid, n in nodes.items():
        if n['src'] == 'zipto' and not n.get('merge') and n['parent'] != skipped and category_of(nid):
            home = ours.get((category_of(nid), same(n['name'])))
            if home:
                n['merge'] = home

    # a sub-category holding a single page is just that page: it opens straight
    # onto its furni; a folder left empty (its sets joined ours) goes
    for nid in sorted((k for k in nodes if k.startswith('c:')), key=lambda k: -k.count('/')):
        inside = [n for n in nodes.values() if n['parent'] == nid]
        pages = len([n for n in inside if not n.get('merge')])
        if pages == 0 or (pages == 1 and '/' in nid and not nodes[nid]['items']):
            for n in inside:
                n['parent'] = nodes[nid]['parent']
            nodes[nid]['parent'] = None
            nodes[nid]['dropped'] = True
        elif pages == 1 and not nodes[nid]['items']:
            # a whole category of one set opens straight onto it: its furni
            # are the category's own (Wild West)
            only = next(n for n in inside if not n.get('merge'))
            if not has_pages(only['id']):
                only['merge'] = nid

    # Anything still named twice in one category, or like the folder it is in,
    # is said here, so the next build does not ship it
    shown = [n for n in nodes.values() if not n.get('dropped') and not n.get('merge') and category_of(n['id'])]
    seen = collections.defaultdict(list)
    for n in shown:
        seen[(category_of(n['id']), same(n['name']))].append(n['id'])
    for (cat, _), ids in seen.items():
        if len(ids) > 1:
            print('twice in %s: %s' % (nodes[cat]['name'], ', '.join('%s (%s)' % (nodes[i]['name'], i) for i in ids)))

    choose_icons(nodes)
    out = {'nodes': list(nodes.values()), 'customs': 'p%d' % CUSTOMS, 'aliases': aliases(),
           'saved': None}
    page = PAGE.replace('/*DATA*/null', json.dumps(out, separators=(',', ':'), ensure_ascii=False)
                        .replace('</', '<\\/'))
    path = os.path.join(SRC, '_shop-planner.html')
    open(path, 'w', encoding='utf-8').write(page)
    n_pages = sum(1 for n in nodes.values() if n['kind'] == 'page' and n['parent'])
    print('%s: %d nodes, %d pages' % (path, len(nodes), n_pages))


PAGE = open(os.path.join(HERE, 'shop-planner.html'), encoding='utf-8').read()

if __name__ == '__main__':
    main()
