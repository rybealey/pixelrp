#!/usr/bin/env python3
"""Rebuild the Furni + Staff catalog: Lines / Themes / Seasonal / Games taxonomy.

Reads: /tmp/fd.json (furnidata), /tmp/furni_names.json (resolved names),
/tmp/furni_id_map.tsv (item_name -> furniture.id).

Emits emulator/Resources/SQLs/Updates/39_CatalogReorg.sql:
  1. delete the previously generated range (pages + items at id >= GEN_BASE),
  2. insert the new tree + one catalog_items row per catalogued furni.

Taxonomy (Furni tab):
  Lines      - curated classic furniture ranges (Area, Iced, Lodge, Mode, ...)
  Themes     - every other furniline, alphabetical, small ones -> "More Themes"
  Seasonal   - Holiday parents (Christmas, Halloween, ...) with per-year child
               pages; yearless items sit on the holiday parent itself.
               NOTE: year pages are 3 levels below the tab root - needs the
               recursive CatalogIndexComposer (2026-08-28).
  Games      - per-game pages (Battle Banzai, Freeze, Football, ...) matched by
               environment / classname prefix / category=games
  Functional - Wired (incl. wired_trigger), Pets, Sound
  Classics / Misc
Staff tab: Rares, NFT (per collection), LTD - unchanged in spirit.

Clothing never enters the catalog (classify drops clothing_*): outfits are
granted via the avatar editor, not sold (migration 37).

Every page gets a curated icon_image (icons live at
nitro/assets/c_images/catalogue/icon_N.png; full official 1..369 set synced
from habbo-downloader). Fallbacks come from the original DB's caption->icon
pairs, then the section default - never the coin purse unless truly generic.

Idempotent: re-running deletes the generated range and rebuilds it.
"""
import json
import re
from collections import defaultdict

GEN_BASE = 920000  # generated page ids live at/above this (real pages < 913000)
FURNI_ROOT, STAFF_ROOT = 9224, 9225
MERGE_MIN = 5      # Themes with fewer items fold into "More Themes"

OFF = json.load(open('/tmp/fd.json'))
NAMES = json.load(open('/tmp/furni_names.json'))
FID = {}
for _l in open('/tmp/furni_id_map.tsv'):
    if '\t' in _l:
        nm, fid = _l.rstrip('\n').split('\t', 1)
        FID[nm] = fid

# --- curated classic furniture ranges (everything else with a furniline is a Theme) ---
LINES = {
    'anna', 'antique', 'area', 'bazaar', 'coco', 'cubie', 'dark_modern', 'darkelegant',
    'diner', 'dream', 'ecotron', 'elegant', 'executive', 'glass', 'gothic', 'hygge',
    'iced', 'iced_dark', 'kuurna', 'legacy', 'lodge', 'lodge_dark', 'mode', 'mode_gold',
    'modern', 'neon', 'organo', 'origins', 'pastel', 'plasto', 'pura', 'pura_dark',
    'relax', 'romantique', 'santorini', 'shalimar', 'stellar', 'usva', 'vaporwave',
}

# --- seasonal holiday routing: substring -> holiday caption (checked in order) ---
HOLIDAYS = [
    ('xmas', 'Christmas'), ('christmas', 'Christmas'),
    ('habboween', 'Halloween'), ('halloween', 'Halloween'), ('hween', 'Halloween'),
    ('easter', 'Easter'),
    ('valentine', "Valentine's"),
    ('newyear', 'New Year'),
    ('cny', 'Chinese New Year'),
    ('st_patrick', "St. Patrick's"),
    ('summer', 'Summer'),
    ('spring', 'Spring'),
    ('fall', 'Autumn'), ('autumn', 'Autumn'),
    ('wintercabin', 'Winter'), ('winterhorizon', 'Winter'), ('winter', 'Winter'),
    ('arctic', 'Winter'), ('snowboard', 'Winter'),
]
HOLIDAY_ORDER = ['Christmas', 'Halloween', 'Easter', "Valentine's", 'New Year',
                 'Chinese New Year', "St. Patrick's", 'Spring', 'Summer', 'Autumn', 'Winter']

# --- per-game routing ---
GAME_ORDER = ['Battle Banzai', 'Freeze', 'Football', 'Ice Hockey', 'Ice Tag',
              'Snow Storm', 'Lost Monkey', 'Score Boards', 'More Games']


def game_of(f):
    cn = f['classname']; env = (f.get('environment') or '').lower()
    line = (f.get('furniline') or '').lower(); cat = f.get('category', '')
    if cn.startswith('bb_') or env == 'battle_banzai': return 'Battle Banzai'
    if cn == 'es_tagging' or env == 'ice_tag': return 'Ice Tag'
    if cn.startswith('hockey_') or cn in ('es_puck', 'es_skating_ice') or env == 'ice_hockey': return 'Ice Hockey'
    if cn.startswith('es_') or env == 'freeze' or line == 'freeze': return 'Freeze'
    if cn.startswith(('fball_', 'football12_')) or env == 'football' or line == 'football': return 'Football'
    if cn.startswith('snst_') or line == 'snowwar': return 'Snow Storm'
    if cn.startswith('lm_') or env == 'lost_monkey': return 'Lost Monkey'
    if cn.startswith('highscore'): return 'Score Boards'
    if cat == 'games': return 'More Games'
    return None


# --- proper display names for furnilines the prettifier mangles ---
NAME_MAP = {
    'hhistory_2024': 'Habbo History', 'habbo15': '15th Anniversary',
    'habbo20': '20th Anniversary', 'habbo25': '25th Anniversary',
    'habbolympics': 'Habbolympics', 'olympics16': 'Olympics 2016',
    'habbopalooza': 'Habbopalooza', 'habbopalooza_2014': 'Habbopalooza 2014',
    'habbowood': 'Habbowood', 'habbo_stars': 'Habbo Stars',
    'habbo_club_gifts': 'Club Gifts', 'old_hc_gifts': 'Classic Club Gifts',
    'attic15': 'The Attic', 'nt_newbie_room': 'Newbie Rooms', 'newbie': 'Starter',
    'room_noob': 'Starter Rooms', 'room_lido': 'The Lido',
    'room_theatredome': 'Theatredome', 'room_welcomelounge': 'Welcome Lounge',
    'room_wl15': 'Welcome Lounge', 'room_cof15': 'Coffee House',
    'room_gh15': 'Gaming Hall', 'room_hall15': 'Hallways',
    'room_hcl15': 'Club Lounge', 'room_info15': 'Infobus',
    'room_pcnc15': 'Picnic', 'room_picnic': 'Picnic', 'room_thr15': 'Theatre',
    'room_xbar': 'X Bar', 'ua': 'Starter', 'user_acquisition': 'Starter',
    'fxbox': 'FX Box', 'skorea': 'South Korea', 'nyc': 'New York',
    'dark_modern': 'Modern Dark', 'darkelegant': 'Elegant Dark',
    'iced_dark': 'Iced Dark', 'lodge_dark': 'Lodge Dark', 'mode_gold': 'Mode Gold',
    'pura_dark': 'Pura Dark', 'auto_items': 'Automobiles', 'ad_neopets': None,
    'credit_furni': 'Credit Furni', 'duckets': 'Ducket Furni',
    'gold_arc': 'Golden Arcade', 'lost_city': 'Lost City', 'lost_tribe': 'Lost Tribe',
    'pj_party': 'PJ Party', 'dessertcafe': 'Dessert Cafe',
    'gothiccafe': 'Gothic Cafe', 'icecream_parlor': 'Ice Cream Parlor',
    'sunsetcafe': 'Sunset Cafe', 'cat_cafe': 'Cat Cafe',
    'coral_kingdom': 'Coral Kingdom', 'candyland': 'Candyland',
    'cyberpunk20': 'Cyberpunk 2020', 'neonpunk': 'Neonpunk',
    'monsterplant': 'Monster Plants', 'bubblejuice': 'Bubble Juice',
    'wildwest': 'Wild West', 'traffic_signs': 'Traffic Signs',
    'pet_accessories': 'Pet Accessories', 'club_shop': 'Club Shop',
    'university_2023': 'University 2023', 'garden16': 'Garden 2016',
    'garden18': 'Garden 2018', 'garden20': 'Garden 2020', 'garden21': 'Garden 2021',
    'newyear': 'New Year', 'cny': 'Chinese New Year', 'st_patricks': "St. Patrick's",
    'nftmint': 'NFT Mint', 'nftmerch': 'NFT Merch',
    'xmas2010_quest_items': 'Christmas 2010', 'summer2011_quest_items': 'Summer 2011',
    'summer26': 'Summer 2026', 'xmas_c17_man': 'Christmas 2017',
}

# --- curated icons (caption -> icon id), picked by eye from the official set ---
ICONS = {
    # top level
    'lines': 2, 'themes': 191, 'seasonal': 320, 'games': 202, 'functional': 65,
    'classics': 2, 'misc': 6, 'wired': 80, 'pets': 8, 'sound': 257,
    'rares': 28, 'nft': 92, 'ltd': 145,
    # holidays
    'christmas': 168, 'halloween': 34, 'easter': 181, "valentine's": 144,
    'new year': 274, 'chinese new year': 15, "st. patrick's": 212,
    'spring': 328, 'summer': 57, 'autumn': 320, 'winter': 290,
    # games
    'battle banzai': 199, 'freeze': 44, 'football': 56, 'ice hockey': 88,
    'ice tag': 5, 'snow storm': 33, 'lost monkey': 45, 'score boards': 60,
    'more games': 202,
    # lines
    'area': 14, 'iced': 13, 'iced dark': 13, 'lodge': 37, 'lodge dark': 37,
    'mode': 39, 'mode gold': 39, 'pura': 48, 'pura dark': 48, 'executive': 27,
    'plasto': 111, 'glass': 85, 'gothic': 352, 'neon': 299, 'diner': 32,
    'dream': 343, 'pastel': 343, 'hygge': 359, 'relax': 304, 'elegant': 310,
    'elegant dark': 310, 'santorini': 365, 'celestial': 307, 'stellar': 307,
    # themes
    'pirates': 191, 'plants': 220, 'rugs': 116, 'trophies': 60, 'garden': 123,
    'spaces': 225, 'horse': 132, 'army': 259, 'university': 230,
    'university 2023': 230, 'school': 345, 'japan': 301, 'tokyo': 301,
    'asian': 357, 'south korea': 357, 'dino': 302, 'greek': 273, 'olympus': 273,
    'ancients': 321, 'gothic cafe': 352, 'circus': 340, 'habbowood': 278,
    'art': 311, 'graffiti': 335, 'ice cream parlor': 332, 'dessert cafe': 322,
    'candyland': 329, 'mystics': 91, 'fantasy': 91, 'wild west': 229,
    'mafia': 366, 'cyberpunk': 269, 'cyberpunk 2020': 269, 'neonpunk': 269,
    'scifi': 326, 'automobiles': 305, 'traffic signs': 305, 'coral kingdom': 280,
    'rainbow': 286, 'rainyday': 356, 'baths': 17, 'kitchen': 53,
    'supermarket': 219, 'cat cafe': 314, 'penguins': 275, 'birds': 261,
    'nests': 261, 'jungle': 353, 'tiki': 45, 'lost city': 298, 'lost tribe': 79,
    'vikings': 208, 'steampunk': 296, 'sanrio': 141, 'smiley': 107,
    'monster plants': 313, '15th anniversary': 344, '20th anniversary': 292,
    '25th anniversary': 355, 'habbolympics': 162, 'olympics 2016': 162,
    'sport': 162, 'snowboard': 140, 'festival': 285, 'habbopalooza': 285,
    'habbopalooza 2014': 285, 'suncity': 341, 'disco': 296, 'band': 308,
    'music': 308, 'arcade': 202, 'chess': 183, 'puzzle box': 179, 'bling': 92,
    'boutique': 175, 'runway': 351, 'wonderland': 358, 'voodoo': 369,
    'ducket furni': 118, 'credit furni': 101, 'diamond': 92,
    'golden arcade': 84, 'collectibles': 360, 'gifts': 189, 'presents': 189,
    'club gifts': 9, 'classic club gifts': 9, 'loyalty': 361, 'guilds': 268,
    'flags': 16, 'starter': 122, 'starter rooms': 122, 'newbie rooms': 122,
    'windows': 63, 'country': 233, 'mexico': 231, 'india': 54, 'america': 87,
    'habbo history': 129, 'pet accessories': 43, 'club shop': 9,
    'recycler': 213, 'hobbies': 100, 'display': 63, 'background': 98,
    'miniatures': 306, 'merch': 344, 'hotel': 344, 'pj party': 359,
    'winter cabin': 294, 'mushroom': 3, 'fruit': 319, 'coco': 322,
}
ICON_REF = json.load(open('/tmp/icon_ref.json')) if __import__('os').path.exists('/tmp/icon_ref.json') else {}
SECTION_DEFAULT = {'Lines': 2, 'Themes': 191, 'Seasonal': 320, 'Games': 202,
                   'Functional': 65, 'Classics': 2, 'Misc': 6,
                   'Rares': 28, 'NFT': 92, 'LTD': 145}


def icon_for(caption, section, inherit=None):
    # Curated picks win (and "Christmas 2023" inherits the curated Christmas
    # icon so a holiday's years stay uniform); the original-DB reference pairs
    # only fill captions we never curated.
    k = caption.lower()
    base = re.sub(r"\s*\d{4}$", '', k).strip()
    if k in ICONS: return ICONS[k]
    if base in ICONS: return ICONS[base]
    if k in ICON_REF: return ICON_REF[k]
    if base in ICON_REF: return ICON_REF[base]
    if inherit: return inherit
    return SECTION_DEFAULT.get(section, 1)


def pretty(line):
    if line in NAME_MAP:
        return NAME_MAP[line]
    t = re.sub(r'[_\-]+', ' ', line).strip()
    t = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', t)
    t = re.sub(r'(?<=[a-z])(?=\d{4})', ' ', t)  # xmas2023 -> xmas 2023
    words = []
    for w in t.split():
        words.append(w.upper() if w in ('nft', 'hc', 'diy', 'pj') else w.capitalize())
    return ' '.join(words)[:35] or 'Furni'


def holiday_of(line):
    for token, holiday in HOLIDAYS:
        if token in line:
            m = re.search(r'(20\d\d)', line)
            if not m:
                m2 = re.search(r'(?<!\d)(\d\d)$', line)
                year = f'20{m2.group(1)}' if m2 else None
            else:
                year = m.group(1)
            return holiday, year
    return None


def classify(f):
    """-> (tab, section, subpath tuple) or None. subpath () = items on section page."""
    cn = f['classname']
    line = (f.get('furniline') or '').lower()
    cat = f.get('category', '')
    # never sold: ads, test furni, builders sets, clothing (avatar editor only)
    if cn.startswith(('ads_', 'test_', 'clothing_')):
        return None
    if line in ('ad_sales', 'test', 'testing', 'clothing') or line.startswith(('ad_', 'buildersclub')):
        return None
    # pixelrp/infrastructure lines are Builders-owned (nav teleporters, the ATM);
    # they live in the Builders tree, never as a Furni theme.
    if line in ('pixelrp', 'infrastructure'):
        return None
    # staff shelves
    if line.startswith('nft'):
        return ('STAFF', 'NFT', (pretty(line),))
    if line in ('rare', 'bonusrare') or f.get('rare'):
        return ('STAFF', 'Rares', ('Bonus Rares' if line == 'bonusrare' else 'Rares',))
    if 'ltd' in line:
        return ('STAFF', 'LTD', ())
    # games before anything furniline-based
    game = game_of(f)
    if game:
        return ('FURNI', 'Games', (game,))
    # functional
    if cat in ('wired', 'wired_effect', 'wired_condition', 'wired_add_on', 'wired_trigger') or line == 'wired':
        return ('FURNI', 'Functional', ('Wired',))
    if cat == 'pets' or line in ('horse', 'pet_accessories'):
        # rideable-horse gear + pet accessories belong with pets
        return ('FURNI', 'Functional', ('Pets',))
    if cat in ('music', 'sound_fx'):
        return ('FURNI', 'Functional', ('Sound',))
    # seasonal: Holiday > Year
    hol = holiday_of(line)
    if hol:
        holiday, year = hol
        return ('FURNI', 'Seasonal', (holiday, f'{holiday} {year}') if year else (holiday,))
    if line in ('classics', 'base'):
        return ('FURNI', 'Classics', ())
    if line in LINES:
        return ('FURNI', 'Lines', (pretty(line),))
    if line:
        return ('FURNI', 'Themes', (pretty(line),))
    return ('FURNI', 'Misc', ())


def price(section, f):
    if section in ('Rares', 'LTD'):
        return 25000
    if section == 'NFT':
        return 50000
    cat = f.get('category', '')
    if cat.startswith('wired') or cat == 'games':
        return 2
    w = int(f.get('xdim', 1) or 1); l = int(f.get('ydim', 1) or 1)
    base = min(3 + 2 * (w * l - 1), 15)
    if cat == 'bed':
        base += 5
    elif cat in ('lighting', 'music', 'sound_fx'):
        base += 2
    return base


# --- classify everything ---
by_path = defaultdict(list)   # (tab, section, subpath) -> [(classname, f)]
skipped = 0
for kind in ('roomitemtypes', 'wallitemtypes'):
    for f in OFF[kind]['furnitype']:
        cn = f['classname']
        if cn not in FID:
            skipped += 1
            continue
        d = classify(f)
        if d is None:
            continue
        by_path[d].append((cn, f))

# fold tiny Themes into "More Themes"
theme_counts = defaultdict(int)
for (tab, sec, sub), its in by_path.items():
    if tab == 'FURNI' and sec == 'Themes' and len(sub) == 1:
        theme_counts[sub[0]] += len(its)
folded = defaultdict(list)
for key in list(by_path):
    tab, sec, sub = key
    if tab == 'FURNI' and sec == 'Themes' and len(sub) == 1 and theme_counts[sub[0]] < MERGE_MIN:
        folded[('FURNI', 'Themes', ('More Themes',))].extend(by_path.pop(key))
for key, its in folded.items():
    by_path[key].extend(its)

# --- build the page tree ---
SECTIONS = [   # (tab, section, caption, min_rank)
    ('FURNI', 'Lines', 'Lines', 1),
    ('FURNI', 'Themes', 'Themes', 1),
    ('FURNI', 'Seasonal', 'Seasonal', 1),
    ('FURNI', 'Games', 'Games', 1),
    ('FURNI', 'Functional', 'Functional', 1),
    ('FURNI', 'Classics', 'Classics', 1),
    ('FURNI', 'Misc', 'Misc', 1),
    ('STAFF', 'Rares', 'Rares', 5),
    ('STAFF', 'NFT', 'NFT', 5),
    ('STAFF', 'LTD', 'LTD', 5),
]

pages = []       # (id, parent_id, caption, icon, min_rank, order)
items = []       # (page_id, item_id, catalog_name, cost)
page_id_of = {}  # (tab, section, subpath-prefix) -> page id
next_id = GEN_BASE


def make_page(key, parent, caption, section, rank, order, inherit_icon=None):
    global next_id
    next_id += 1
    icon = icon_for(caption, section, inherit_icon)
    pages.append((next_id, parent, caption, icon, rank, order))
    page_id_of[key] = next_id
    return next_id


order = 1
for tab, sec, cap, rank in SECTIONS:
    root = FURNI_ROOT if tab == 'FURNI' else STAFF_ROOT
    make_page((tab, sec, ()), root, cap, sec, rank, order)
    order += 1

# section sub-pages
sub_orders = defaultdict(int)


def sub_sort_key(tab, sec, sub):
    if not sub:
        return ()
    if sec == 'Seasonal':
        head = sub[0]
        hidx = HOLIDAY_ORDER.index(head) if head in HOLIDAY_ORDER else 99
        return (hidx, sub[-1])       # holiday order, then year ascending
    if sec == 'Games':
        return (GAME_ORDER.index(sub[0]) if sub[0] in GAME_ORDER else 99,)
    if sec == 'Functional':
        return (['Wired', 'Pets', 'Sound'].index(sub[0]) if sub[0] in ('Wired', 'Pets', 'Sound') else 9,)
    if sub[0].startswith('More '):
        return ('zzzz',)             # merged pages sort last
    return (sub[0].lower(),)


all_keys = sorted(by_path.keys(), key=lambda k: (k[0], k[1], sub_sort_key(*k)))
for tab, sec, sub in all_keys:
    rank = 5 if tab == 'STAFF' else 1
    parent_key = (tab, sec, ())
    inherit = None
    for depth in range(1, len(sub) + 1):
        prefix = (tab, sec, sub[:depth])
        if prefix not in page_id_of:
            parent = page_id_of[parent_key]
            sub_orders[parent_key] += 1
            make_page(prefix, parent, sub[depth - 1][:35], sec, rank,
                      sub_orders[parent_key], inherit)
        inherit = pages[[p[0] for p in pages].index(page_id_of[prefix])][3]
        parent_key = prefix

for (tab, sec, sub), its in by_path.items():
    target = page_id_of[(tab, sec, sub)]
    for cn, f in sorted(its, key=lambda x: NAMES.get(x[0], x[0]).lower()):
        items.append((target, FID[cn], NAMES.get(cn, cn)[:100], price(sec, f)))

# prune childless empty pages (e.g. an empty LTD section)
pages_with_items = {it[0] for it in items}
kept = set(pages_with_items)
changed = True
while changed:
    changed = False
    parents_of_kept = {par for (pgid, par, *_) in pages if pgid in kept}
    for pgid, par, *_ in pages:
        if pgid not in kept and pgid in parents_of_kept:
            kept.add(pgid); changed = True
pages = [p for p in pages if p[0] in kept]


# --- emit SQL ---
def esc(s):
    return "'" + str(s).replace("\\", "\\\\").replace("'", "\\'") + "'"


OUT = 'emulator/Resources/SQLs/Updates/39_CatalogReorg.sql'
with open(OUT, 'w') as o:
    o.write("-- Reorganize the Furni + Staff catalog: Lines / Themes /\n")
    o.write("-- Seasonal (Holiday > Year) / per-game Games pages, proper page\n")
    o.write("-- names and curated per-page icons. Regenerates the whole\n")
    o.write(f"-- generated range (>= {GEN_BASE}); Builders and legacy pages untouched.\n")
    o.write(f"DELETE FROM catalog_items WHERE page_id >= {GEN_BASE};\n")
    o.write(f"DELETE FROM catalog_pages WHERE id >= {GEN_BASE};\n")
    for pgid, par, cap, icon, rk, ordn in pages:
        o.write("INSERT INTO catalog_pages "
                "(id,parent_id,caption,icon_image,min_rank,min_vip,order_num,page_link,"
                "page_layout,page_strings_1,page_strings_2,visible,enabled) VALUES "
                f"({pgid},{par},{esc(cap)},{icon},{rk},0,{ordn},'','default_3x3','','',b'1',b'1');\n")
    for i in range(0, len(items), 400):
        o.write("INSERT INTO catalog_items "
                "(page_id,item_id,catalog_name,cost_credits,cost_pixels,cost_diamonds,"
                "amount,limited_sells,limited_stack,offer_active,extradata,badge,offer_id) VALUES\n")
        chunk = [f"({pg},{esc(iid)},{esc(nm)},{cr},0,0,1,0,0,'1','','',-1)"
                 for pg, iid, nm, cr in items[i:i + 400]]
        o.write(",\n".join(chunk) + ";\n")

print(f"pages: {len(pages)}  items: {len(items)}  (no furniture row: {skipped})")
sec_counts = defaultdict(lambda: [0, 0])
for pgid, par, cap, icon, rk, ordn in pages:
    pass
for (tab, sec, sub), its in sorted(by_path.items()):
    sec_counts[(tab, sec)][0] += 1
    sec_counts[(tab, sec)][1] += len(its)
for (tab, sec), (np_, ni) in sorted(sec_counts.items()):
    print(f"  {tab:5} {sec:10} leaf-paths: {np_:3}  items: {ni}")
default_icons = sum(1 for p in pages if p[3] == 1)
print(f"pages still on coin-purse icon: {default_icons}")
