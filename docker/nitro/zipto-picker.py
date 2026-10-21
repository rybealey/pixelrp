#!/usr/bin/env python3
"""Build the Zipto picker: a page for choosing which of Zipto's furni to import.

    python3 docker/nitro/zipto-picker.py [~/Desktop/Zipto Import]

Writes `_picker.html` into the Zipto Import folder. It opens straight from
disk (the furni icons are read from the folder beside it) and covers the
furni Zipto does NOT sell in its shop - the shop's own went in with
import-zipto-shop.py.

The furni are grouped into sets so they can be judged a set at a time:
  - a source with MIN or more furni (a furni line, or the first word of the
    classname: habbox, yvess5, pokeweebz ...) is split by classname prefix
    into sets of at most MAX (habbox > shone > barriere)
  - the one-offs left over from everywhere else are pooled and sorted by what
    they are (TYPES), in chunks of CHUNK
Colour versions of one furni are one tile. Each set then has a name for what
is in it (zipto-furni/picker-names.json) and a place by what it is - Category
> Sub-category (zipto-furni/picker-categories.json) - and the page lists them
that way: all the Christmas sets together, whoever made them.

Choices are kept in the browser as they are made and leave the page as a
JSON file (Export), which carries each chosen set's furni with it - the
import reads that file and nothing else.
"""
import collections
import html
import json
import os
import re
import sys
from urllib.parse import quote

MIN, MAX, CHUNK = 6, 120, 150
SRC = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else '~/Desktop/Zipto Import')
FINGERPRINTS = os.environ.get('ZIPTO_FP')     # optional: zipto_fp.jsonl, for the furni's logic type

TYPES = [
    ('Beds', 'bed|beds|cama|camas|lit|bett|cot|hammock|hamac|rede'),
    ('Seating', 'chair|chairs|sofa|sofas|couch|bench|stool|seat|throne|armchair|pouf|puff|beanbag|chaise|fauteuil|'
                'canape|cadeira|poltrona|sillon|silla|banco|stoel|stuhl|sessel|tabouret|banquinho|trono|trone|'
                'sitzsack|bank|cushion|coussin|almofada|kussen|pillow'),
    ('Tables & Desks', 'table|tables|desk|mesa|mesinha|tafel|tisch|bureau|escrivaninha|counter|comptoir|balcao|bar'),
    ('Storage', 'shelf|shelves|cabinet|wardrobe|drawer|drawers|dresser|bookcase|bookshelf|estante|armario|etagere|'
                'kast|regal|rack|chest|crate|caixa|coffre|commode|armoire|placard|locker|cupboard'),
    ('Lighting', 'lamp|lamps|light|lights|lantern|candle|candles|lustre|chandelier|lampe|lampada|luminaria|luz|'
                 'lumiere|bougie|vela|licht|neon|lampion|abajur|spot|led'),
    ('Plants & Nature', 'plant|plants|tree|trees|flower|flowers|bush|grass|rock|rocks|stone|palm|cactus|arbre|arvore|'
                        'flor|flores|fleur|fleurs|planta|plante|boom|bloem|pierre|pedra|roche|rocha|vaso|vase|pot|'
                        'hedge|haie|bonsai|garden|jardin|jardim|tuin|leaf|leaves|mushroom|champignon|cogumelo'),
    ('Floors & Rugs', 'floor|tile|tiles|rug|carpet|mat|path|piso|sol|dalle|tapis|tapete|alfombra|vloer|tegel|suelo|'
                      'boden|parquet|chao|pavement|sidewalk|road|rua'),
    ('Walls & Building', 'wall|walls|pillar|column|roof|stairs|stair|step|steps|fence|divider|block|blocks|mur|muro|'
                         'parede|pilar|toit|telhado|escada|escalier|cloture|barriere|cerca|brick|brique|tijolo|'
                         'muur|wand|zaun|treppe|colonne|coluna|arch|arche|beam|poutre'),
    ('Doors & Windows', 'door|doors|gate|window|windows|porte|porta|puerta|deur|janela|fenetre|ventana|raam|portao|'
                        'portail|fenster|tur|curtain|rideau|cortina'),
    ('Pictures & Signs', 'poster|picture|painting|frame|photo|cadre|quadro|cuadro|tableau|affiche|sign|placa|panneau|'
                         'board|banner|flag|drapeau|bandeira|bandera|mural|graffiti|logo|letter|lettre'),
    ('Kitchen & Food', 'kitchen|fridge|oven|stove|food|cake|drink|cup|mug|cuisine|cozinha|cocina|frigo|gateau|bolo|'
                       'pizza|coffee|cafe|tea|bottle|bouteille|garrafa|burger|candy|bonbon|doce|icecream|glace|'
                       'sorvete|bread|pain|pao|fruit|fruta|wine|vin|vinho|beer|biere|cerveja|cookie'),
    ('Bathroom', 'bath|bathtub|shower|toilet|wc|sink|banheiro|bain|douche|baignoire|lavabo|banheira|chuveiro|'
                 'towel|serviette|toalha|mirror|miroir|espelho|spiegel'),
    ('Toys & Figures', 'plush|plushie|teddy|toy|toys|doll|duck|statue|figure|peluche|boneca|boneco|poupee|jouet|'
                       'brinquedo|bear|ours|urso|cat|chat|gato|dog|chien|cachorro|bunny|lapin|coelho|pato|canard|'
                       'eend|bird|oiseau|passaro|fish|poisson|peixe|animal'),
    ('Electronics & Music', 'tv|television|computer|pc|radio|speaker|console|arcade|phone|telephone|jukebox|dj|'
                            'guitar|guitare|piano|music|musique|musica|stereo|camera|laptop|screen|ecran|tela|'
                            'machine|maquina|game|jogo|jeu'),
    ('Vehicles', 'car|cars|bike|bicycle|boat|plane|train|van|truck|carro|voiture|moto|motorcycle|velo|bateau|'
                 'barco|aviao|avion|helicopter|bus|taxi|scooter|skate|kart'),
]

# Every set has a name that says what is in it (zipto-furni/picker-names.json,
# written from contact sheets of each set's icons), because the classnames say
# who made it - gracie, yordi, irinc - and nothing about the furni. The raw
# label stays beside it, small, so a set can still be traced to its source.
SET_NAMES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zipto-furni', 'picker-names.json')

# ... and a place: [category, sub-category] by set id, sorted by what the
# furni are (all the Christmas sets together, whoever made them).
SET_CATEGORIES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zipto-furni', 'picker-categories.json')
# What each odds-and-ends furni is (zipto-furni/odds-types.json): sorted by
# the words in its name in six languages where they said, and by eye from
# sheets of their icons where they did not.
ODDS_TYPES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zipto-furni', 'odds-types.json')
KIND_TO_TYPE = {'Tables & Desks': 'Tables and Desks', 'Plants & Nature': 'Plants and Flowers',
                'Floors & Rugs': 'Floors and Rugs', 'Walls & Building': 'Walls and Building',
                'Doors & Windows': 'Doors and Windows', 'Pictures & Signs': 'Pictures and Signs',
                'Kitchen & Food': 'Kitchen, Food and Drink', 'Toys & Figures': 'Toys and Figures',
                'Electronics & Music': 'Electronics and Games', 'Other': 'Decorations'}
# Not coming into the shop (Twist, 2026-10-21)
LEFT_OUT = ('Clothing Furni', 'Trax Songs', 'Wired and Game Kit')

# There is no Odds and Ends category (Twist, 2026-10-21): each kind of one-off
# goes where that kind lives - (category, sub-category); None for a category
# that is one list of sets.
ODDS_HOME = {
    'Animals': ('Garden and Nature', 'Animals'),
    'Bathroom': ('Rooms', None),
    'Beds': ('Rooms', None),
    'Christmas and Winter': ('Seasonal', 'Christmas and Winter'),
    'Decorations': ('Furniture Sets', 'Decorations'),
    'Doors and Windows': ('Building & Structure', 'Doors and Windows'),
    'Easter': ('Seasonal', 'Easter'),
    'Electronics and Games': ('Rooms', None),
    'Fashion and Accessories': ('Rooms', None),
    'Floors and Rugs': ('Building & Structure', 'Floors and Tiles'),
    'Halloween': ('Seasonal', 'Halloween'),
    'Kitchen, Food and Drink': ('Food and Sweets', None),
    'Letters and Numbers': ('Building & Structure', 'Letters and Numbers'),
    'Lighting': ('Furniture Sets', 'Lighting'),
    'Music': ('Themes', 'Music and Cinema'),
    'Pictures and Signs': ('Themes', 'Art and Pictures'),
    'Plants and Flowers': ('Garden and Nature', 'Plants and Flowers'),
    'Seating': ('Furniture Sets', 'Seating'),
    'Statues and Trophies': ('Rares and Collectibles', 'Statues and Trophies'),
    'Storage': ('Furniture Sets', 'Storage'),
    'Tables and Desks': ('Furniture Sets', 'Tables and Desks'),
    'Toys and Figures': ('Pop Culture', 'Toys and Plushies'),
    'Trees and Nature': ('Garden and Nature', 'Garden'),
    "Valentine's": ('Seasonal', "Valentine's"),
    'Vehicles': ('Themes', 'City and Roleplay'),
    'Walls and Building': ('Building & Structure', 'Walls and Panels'),
}
# A one-off page beside named sets reads 'More Christmas 2'; these are shorter
ODDS_SHORT = {'Christmas and Winter': 'Christmas', 'Kitchen, Food and Drink': 'Food and Drink',
              'Electronics and Games': 'Electronics', 'Fashion and Accessories': 'Fashion',
              'Toys and Figures': 'Toys', 'Trees and Nature': 'Trees', 'Walls and Building': 'Walls',
              'Statues and Trophies': 'Statues'}


# Sub-categories made just for one-offs, where 'Seating 2' needs no 'More'
ODDS_OWN = {('Furniture Sets', k) for k in ('Seating', 'Tables and Desks', 'Storage', 'Lighting', 'Decorations')}


def odds_home(kind):
    cat, sub = ODDS_HOME.get(kind, ('Furniture Sets', 'Decorations'))
    return cat, sub or cat


# Customs is easier to find furni in as many small categories, A-Z (Twist,
# 2026-10-21). Each (category, sub-category) the sorting above gives - None for
# a category that is one list - lands in a category here: a plain name is one
# list of sets, (category, folder) a folder inside it.
B = 'Building & Structure'
RESHAPE = {
    ('Seasonal', 'Autumn'): ('Seasonal', 'Autumn'),
    ('Seasonal', 'Christmas and Winter'): ('Seasonal', 'Christmas & Winter'),
    ('Seasonal', 'Easter'): ('Seasonal', 'Easter'),
    ('Seasonal', 'Halloween'): ('Seasonal', 'Halloween'),
    ('Seasonal', 'Parties and Festivals'): ('Seasonal', 'Parties & Festivals'),
    ('Seasonal', 'Summer and Beach'): ('Seasonal', 'Summer & Beach'),
    ('Seasonal', "Valentine's"): ('Seasonal', "Valentine's"),
    ('Themes', 'Ancient Worlds'): 'Ancient Worlds',
    ('Themes', 'Art and Pictures'): 'Art & Pictures',
    ('Themes', 'Asian and Middle Eastern'): 'Asian & Middle Eastern',
    ('Themes', 'Circus'): ('Seasonal', 'Parties & Festivals'),
    ('Themes', 'City and Roleplay'): 'City & Roleplay',
    ('Themes', 'School'): 'City & Roleplay',
    ('Themes', 'Gothic'): 'Dark & Gothic',
    ('Themes', 'Medieval and Fantasy'): 'Fantasy & Medieval',
    ('Themes', 'Music and Cinema'): 'Music & Cinema',
    ('Themes', 'Ocean'): 'Ocean & Pirates',
    ('Themes', 'Pirates'): 'Ocean & Pirates',
    ('Themes', 'Space and Sci-Fi'): 'Space & Sci-Fi',
    ('Themes', 'Sports and Games'): 'Sports & Games',
    ('Themes', 'Wild West'): 'Wild West',
    ('Rooms', None): 'Rooms',
    ('Furniture Sets', 'Classic and Antique'): ('Furniture Sets', 'Classic & Antique'),
    ('Furniture Sets', 'Modern'): ('Furniture Sets', 'Modern'),
    ('Furniture Sets', 'Other Styles'): ('Furniture Sets', 'Other Styles'),
    ('Furniture Sets', 'Pink and Pastel'): ('Furniture Sets', 'Pink & Pastel'),
    ('Furniture Sets', 'Wood and Rustic'): ('Furniture Sets', 'Wood & Rustic'),
    ('Furniture Sets', 'Dark and Black'): 'Dark & Gothic',
    ('Furniture Sets', 'Decorations'): 'Decorations',
    ('Furniture Sets', 'Lighting'): 'Lighting',
    ('Furniture Sets', 'Seating'): 'Seating',
    ('Furniture Sets', 'Storage'): 'Storage',
    ('Furniture Sets', 'Tables and Desks'): 'Tables & Desks',
    ('Garden and Nature', 'Animals'): 'Animals',
    ('Garden and Nature', 'Garden'): 'Garden',
    ('Garden and Nature', 'Rocks and Crystals'): 'Garden',
    ('Garden and Nature', 'Plants and Flowers'): 'Plants & Flowers',
    (B, 'Bricks and Blocks'): (B, 'Bricks & Blocks'),
    (B, 'Construction'): (B, 'Construction'),
    (B, 'Doors and Windows'): (B, 'Doors & Windows'),
    (B, 'Floors and Tiles'): (B, 'Floors & Tiles'),
    (B, 'Railings, Fences and Trim'): (B, 'Railings, Fences & Trim'),
    (B, 'Roofs and Exteriors'): (B, 'Roofs & Exteriors'),
    (B, 'Walls and Panels'): (B, 'Walls & Panels'),
    (B, 'Letters and Numbers'): 'Letters & Numbers',
    ('Pop Culture', 'Anime'): 'Anime',
    ('Pop Culture', 'Pokémon'): 'Pokemon',
    ('Pop Culture', 'TV and Film'): 'TV & Film',
    ('Pop Culture', 'Toys and Plushies'): 'Toys & Plushies',
    ('Pop Culture', 'Video Games'): 'Video Games',
    ('Rares and Collectibles', 'Collectibles'): ('Rares & Collectibles', 'Collectibles'),
    ('Rares and Collectibles', 'Dragons'): ('Rares & Collectibles', 'Dragons'),
    ('Rares and Collectibles', 'Eggs and Lamps'): ('Rares & Collectibles', 'Eggs & Lamps'),
    ('Rares and Collectibles', 'Rares'): ('Rares & Collectibles', 'Rares'),
    ('Rares and Collectibles', 'Statues and Trophies'): 'Statues & Trophies',
    ('Food and Sweets', None): 'Food & Sweets',
    ('Brands', None): 'Brands',
    ('Group Furni', None): 'Group Furni',
}


def place(cat, sub):
    """(category, folder) for a set sorted as (cat, sub); folder None when the
    category is one list. Anything not in RESHAPE (what we leave out) stays."""
    if sub == cat:
        sub = None
    to = RESHAPE.get((cat, sub), (cat, sub))
    return (to, None) if isinstance(to, str) else to

# Pokemon from everywhere, gathered into one group. The four sets that were
# groups of their own keep their ids, so choices already made still apply.
POKEMON = [
    ('pokeweebz/pokeweebz', 'Pokémon Figures', re.compile(r'^pokeweebz\d+$', re.I)),
    ('pokeweebzs/pokeweebzs', 'Shiny Pokémon Figures', re.compile(r'^pokeweebzs\d+$', re.I)),
    ('pokem/pokem', 'Pokémon Pictures', re.compile(r'^pokem\d+$', re.I)),
    ('pokeball/pokeball', 'Poké Balls', re.compile(r'pokeball|^ltd18_\w*ball$|^ball_poke', re.I)),
    ('pokemon/extras', 'Pokémon Displays and Toys',
     re.compile(r'pikachu|gengar_display|snorlax|pokemon|pokeman|pokeash|pokeplante', re.I)),
]

# A set made mostly of these logic types cannot simply be placed and used.
NOTES = {
    'furniture_purchasable_clothing': 'Clothing furni - they give clothes we have not imported',
    'furniture_soundblock': 'Sound furni - trax songs need sound files that were not downloaded',
    'furniture_guild_customized': 'Group furni - they take the colours of a group',
    'furniture_credit': 'Exchange furni - they turn into coins',
    'furniture_crafting_gizmo': 'Crafting furni - we have no crafting recipes',
}


def _type_re(pat):
    # short words must stand alone (car is not carpet); long ones are also
    # found inside run-together names (squarethrone, rondintable)
    words = pat.split('|')
    short = [w for w in words if len(w) < 5]
    long_ = [w for w in words if len(w) >= 5]
    parts = []
    if short:
        parts.append(r'(?:^|[^a-z])(?:%s)(?:[^a-z]|$)' % '|'.join(short))
    if long_:
        parts.append('(?:%s)' % '|'.join(long_))
    return re.compile('|'.join(parts))


TYPE_RE = [(name, _type_re(pat)) for name, pat in TYPES]


def fix_text(s):
    """Undo UTF-8 read as Windows-1252, as often as it was done."""
    for _ in range(4):
        if not re.search('[ÃÂâ]', s):
            break
        try:
            s = s.encode('cp1252').decode('utf-8')
        except UnicodeError:
            break
    return s


def tokens(lib):
    t = [x for x in re.split(r'[_\-\s]+', lib.lower()) if x] or [lib.lower()]
    # a classname that starts with a number (01_caterbody) is grouped by its first word
    while len(t) > 1 and t[0].isdigit():
        t = t[1:] + [t[0]]
    # and a number stuck to the first word (pokeweebz618, yvess5, 17wautomat) is
    # an item number, not part of the name: c23 inside a name stays whole
    m = re.match(r'^(\d*)([a-z]+)(\d*)$', t[0])
    if m and (m.group(1) or m.group(3)):
        t = [m.group(2)] + t[1:] + [m.group(1) + m.group(3)]
    return t


def kind_of(lib, name):
    text = ' '.join(tokens(lib)) + ' ' + re.sub(r'[^a-z ]', ' ', fix_text(name).lower())
    for kind, rx in TYPE_RE:
        if rx.search(text):
            return kind
    return 'Other'


def pretty(words):
    return ' '.join(w.capitalize() for w in words)


def build_data():
    """The sets, named and placed, as the page shows them."""
    manifest = json.load(open(os.path.join(SRC, '_import.json'), encoding='utf-8'))
    furni = [f for f in manifest['furni'] if f['folder'].startswith("Not in")]
    libs = collections.OrderedDict()
    for f in furni:
        libs.setdefault(f['classname'].split('*')[0], []).append(f)

    logic = {}
    if FINGERPRINTS and os.path.exists(FINGERPRINTS):
        for line in open(FINGERPRINTS, encoding='utf-8'):
            r = json.loads(line)
            logic[r['file'].lower()] = r.get('logic') or ''

    near = {}
    near_csv = os.path.join(SRC, '_possible duplicates.csv')
    if os.path.exists(near_csv):
        import csv
        for row in list(csv.reader(open(near_csv, encoding='utf-8-sig')))[1:]:
            near[row[0]] = 'Looks like our %s (%s, %s of its pictures)' % (row[4] or row[3], row[3], row[5])

    def source(lib, items):
        line = items[0]['furnidata'].get('furniline') or ''
        return 'line ' + line if line else tokens(lib)[0]

    sets = []   # (group, label words, [libs], fixed id or None, name or None)

    # Pokemon first, out of wherever their classnames would have put them
    pokemon = collections.OrderedDict((sid, []) for sid, _, _ in POKEMON)
    for lib in libs:
        for sid, _, rx in POKEMON:
            if rx.search(lib):
                pokemon[sid].append(lib)
                break
    taken = {lib for ls in pokemon.values() for lib in ls}
    for sid, name, _ in POKEMON:
        if pokemon[sid]:
            sets.append(('Pokemon', [sid.split('/')[0]], pokemon[sid], sid, name))

    # Odds and ends are sorted one furni at a time by what each is: the
    # one-offs, and the furni of the mixed leftover sets ('Assorted Furni').
    odds_types = json.load(open(ODDS_TYPES, encoding='utf-8')) if os.path.exists(ODDS_TYPES) else {}
    odds = collections.defaultdict(list)
    odds_taken = set()
    for lib in libs:
        if lib in odds_types and lib not in taken:
            odds[odds_types[lib]].append(lib)
            odds_taken.add(lib)

    by_source = collections.defaultdict(list)
    for lib, items in libs.items():
        if lib not in taken:
            by_source[source(lib, items)].append(lib)

    def split(src, prefix, members, depth):
        groups = collections.defaultdict(list)
        for lib in members:
            t = tokens(lib)
            groups[t[depth] if depth < len(t) - 1 else ''].append(lib)
        loose = list(groups.pop('', []))
        made = 0
        for key, ls in sorted(groups.items()):
            if len(ls) < MIN:
                loose.extend(ls)
            elif len(ls) > MAX and any(len(tokens(l)) > depth + 2 for l in ls):
                split(src, prefix + [key], ls, depth + 1)
                made += 1
            else:
                sets.append((src, prefix + [key], ls, None, None))
                made += 1
        if loose:
            # what no sub-set took; when nothing did, it is the whole set
            sets.append((src, prefix + ['other'] if made else prefix, loose, None, None))

    pool = []
    for src, members in sorted(by_source.items()):
        if len(members) < MIN:
            pool.extend(lib for lib in members if lib not in odds_taken)
        elif len(members) <= MAX:
            sets.append((src, [src], members, None, None))
        else:
            split(src, [src], members, 1)
    # The sets are cut first and the odds-and-ends furni taken out after, so
    # a source keeps the same sets (and ids, and names) it had before.
    sets = [(g, label, [lib for lib in members if lib not in odds_taken], fid, fname)
            for g, label, members, fid, fname in sets]
    sets = [entry for entry in sets if entry[2]]

    # a one-off the sorting has not seen yet goes by its name's words
    for lib in pool:
        kind = kind_of(lib, libs[lib][0]['name'])
        odds[KIND_TO_TYPE.get(kind, kind)].append(lib)
    for kind in sorted(odds):
        ls = sorted(odds[kind], key=str.lower)
        parts = [ls[i:i + CHUNK] for i in range(0, len(ls), CHUNK)]
        for n, part in enumerate(parts):
            label = kind if len(parts) == 1 else '%s %d' % (kind, n + 1)
            sets.append(('Odds and ends', [label], part, 'odds/' + label, label))

    set_names = json.load(open(SET_NAMES, encoding='utf-8')) if os.path.exists(SET_NAMES) else {}

    def icon_url(f):
        if not f.get('icon'):
            return ''
        parts = f['folder'].replace('\\', '/').split('/') + [f['icon']]
        return '/'.join(quote(p) for p in parts)

    out_sets, groups = [], collections.OrderedDict()
    for source_group, label, members, fixed_id, fixed_name in sets:
        # the fifteen one-colour health bar sources read as one group
        group = 'Health Bars' if source_group.endswith('healthbar') else source_group
        items, logics = [], collections.Counter()
        for lib in members:
            variants = libs[lib]
            first = variants[0]
            lg = logic.get(first['nitro'][:-6].lower(), '')
            logics[lg] += 1
            note = near.get(first['classname']) or ''
            if (first.get('note') or '').startswith('new colour'):
                note = 'A new colour of a furni we have'
            items.append([lib, fix_text(first['name'])[:60], len(variants), icon_url(first), note])
        main_logic, n = logics.most_common(1)[0] if logics else ('', 0)
        note = NOTES.get(main_logic, '') if n * 2 > len(members) else ''
        if group in ('wf', 'line wired') or (label and label[0] == 'wf'):
            note = "Zipto's wired - our server cannot run it"
        if group == 'Odds and ends':
            sid, raw, name = fixed_id, '', fixed_name
        else:
            # ids come from the source label, so renaming never loses a choice
            sid = fixed_id or source_group + '/' + '.'.join(label)
            raw = ' > '.join(label)
            words = [w for w in label if w != 'other'] or label
            name = fixed_name or set_names.get(sid) or pretty(words[1:] if len(words) > 1 else words)
        out_sets.append({'id': sid, 'g': group, 't': name, 'raw': raw, 'sg': '' if group == 'Odds and ends' else name,
                         'note': note, 'n': sum(i[2] for i in items), 'items': items})
        groups.setdefault(group, []).append(len(out_sets) - 1)

    # The page lists the sets by what they are - Category > Sub-category - not
    # by where they came from: every set is placed in picker-categories.json.
    cats = json.load(open(SET_CATEGORIES, encoding='utf-8')) if os.path.exists(SET_CATEGORIES) else {}
    subs = collections.OrderedDict()
    for i, s in enumerate(out_sets):
        if s['id'].startswith('odds/'):
            # a one-off page goes where its kind lives: Seating 2 -> Furniture
            # Sets > Seating; beside named sets it is 'More Christmas 2'
            kind = re.sub(r' \d+$', '', s['t'])
            cat, sub = odds_home(kind)
            if (cat, sub) not in ODDS_OWN:
                s['t'] = 'More ' + ODDS_SHORT.get(kind, kind) + s['t'][len(kind):]
            s['sg'] = s['t']
        else:
            cat, sub = cats.get(s['id']) or ('Furniture Sets', 'Decorations')
            if cat == 'Odds and Ends':
                cat, sub = odds_home(sub)
        cat, sub = place(cat, sub)
        sub = sub or cat
        s['g'] = cat + '/' + sub
        subs.setdefault((cat, sub), []).append(i)

    def sub_order(key):
        # A-Z, with what we are leaving out at the bottom
        cat, sub = key
        return cat in LEFT_OUT, cat.lower(), sub.lower()

    data = {'sets': out_sets,
            'groups': [{'id': cat + '/' + sub, 'cat': cat, 'name': sub,
                        'sets': sorted(members, key=lambda i: out_sets[i]['t'].lower()),
                        'n': sum(out_sets[i]['n'] for i in members)}
                       for (cat, sub), members in sorted(subs.items(), key=lambda kv: sub_order(kv[0]))],
            'total': sum(s['n'] for s in out_sets)}
    return data


def main():
    data = build_data()
    page = PAGE.replace('/*DATA*/null', json.dumps(data, separators=(',', ':'), ensure_ascii=False)
                        .replace('</', '<\\/'))
    out = os.path.join(SRC, '_picker.html')
    open(out, 'w', encoding='utf-8').write(page)
    print('%s: %d furni (%d with their colours) in %d sets, %d sub-categories'
          % (out, len({i[0] for s in data['sets'] for i in s['items']}), data['total'], len(data['sets']),
             len(data['groups'])))


PAGE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Zipto Picker</title>
<style>
:root {
  --bg: #f3f3f5; --panel: #ffffff; --line: #e2e4e8; --text: #1f2328; --muted: #6a7078;
  --accent: #e8743b; --accent-soft: #fff4ec; --ok: #2f8f4e; --ok-soft: #e7f5ec;
  --skip: #9aa0a6; --skip-soft: #eef0f2; --warn: #b26b00; --warn-soft: #fff5e0; --tile: #eceef1;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #17191c; --panel: #1f2226; --line: #31353b; --text: #e6e8eb; --muted: #9aa1a9;
    --accent: #f0915f; --accent-soft: #3a2a20; --ok: #5cc07f; --ok-soft: #1f3327;
    --skip: #7d838a; --skip-soft: #2a2d31; --warn: #e0a64a; --warn-soft: #3a2f1c; --tile: #2a2e33;
  }
}
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; }
body { background: var(--bg); color: var(--text); font: 13px/1.4 system-ui, -apple-system, "Segoe UI", sans-serif; }
header { position: sticky; top: 0; z-index: 5; display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center;
  padding: 8px 14px; background: var(--panel); border-bottom: 1px solid var(--line); }
header h1 { font-size: 14px; margin: 0; }
.tally { color: var(--muted); }
.tally b { color: var(--text); }
header .grow { flex: 1; }
input[type=search], input[type=text] { font: inherit; color: var(--text); background: var(--bg);
  border: 1px solid var(--line); border-radius: 4px; padding: 4px 8px; }
input[type=search] { width: 220px; }
button, select { font: inherit; color: var(--text); background: var(--panel); border: 1px solid var(--line);
  border-radius: 4px; padding: 3px 9px; cursor: pointer; }
button:hover { border-color: var(--muted); }
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
.layout { display: grid; grid-template-columns: 250px 1fr; height: calc(100% - 46px); }
nav { overflow-y: auto; border-right: 1px solid var(--line); background: var(--panel); padding: 6px 0; }
nav .g { display: flex; justify-content: space-between; gap: 6px; padding: 4px 12px; cursor: pointer; }
nav .g:hover { background: var(--bg); }
nav .g.on { background: var(--accent-soft); color: var(--accent); }
nav .g .c { color: var(--muted); font-variant-numeric: tabular-nums; }
nav .g .done, nav .cat .done { color: var(--ok); }
nav .cat { display: flex; justify-content: space-between; gap: 6px; padding: 6px 12px; cursor: pointer; font-weight: 600; }
nav .cat:hover { background: var(--bg); }
nav .cat .c { color: var(--muted); font-weight: 400; font-variant-numeric: tabular-nums; }
nav .cat .chev { display: inline-block; width: 10px; color: var(--muted); }
nav .g.sub { padding-left: 30px; }
nav .cat.g.on { background: var(--accent-soft); color: var(--accent); }
.ghead .crumb { color: var(--muted); font-weight: 400; }
nav .navtools { padding: 4px 12px 8px; display: flex; gap: 6px; align-items: center; color: var(--muted); }
main { overflow-y: auto; padding: 12px 16px 60px; }
.ghead { display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; margin-bottom: 10px; }
.ghead h2 { font-size: 15px; margin: 0; }
.ghead .c { color: var(--muted); }
.set { background: var(--panel); border: 1px solid var(--line); border-radius: 5px; margin-bottom: 10px; }
.set.import { border-color: var(--ok); }
.set.skip { opacity: .55; }
.shead { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: center; padding: 6px 10px; border-bottom: 1px solid var(--line); }
.shead .t { font-weight: 600; }
.shead .c { color: var(--muted); }
.shead .raw { color: var(--muted); font-size: 11px; }
.shead .grow { flex: 1; }
.seg { display: inline-flex; border: 1px solid var(--line); border-radius: 4px; overflow: hidden; }
.seg button { border: 0; border-radius: 0; padding: 3px 10px; }
.seg button + button { border-left: 1px solid var(--line); }
.seg .in.on { background: var(--ok); color: #fff; }
.seg .sk.on { background: var(--skip); color: #fff; }
.note { font-size: 12px; color: var(--warn); background: var(--warn-soft); border-radius: 3px; padding: 1px 6px; }
.name { width: 200px; }
.grid { display: flex; flex-wrap: wrap; gap: 4px; padding: 8px 10px; }
.it { position: relative; width: 58px; height: 58px; display: flex; align-items: center; justify-content: center;
  background: var(--tile); border-radius: 4px; cursor: pointer; border: 2px solid transparent; }
.it img { max-width: 54px; max-height: 54px; image-rendering: pixelated; }
.it .noimg { font-size: 9px; color: var(--muted); word-break: break-all; padding: 2px; text-align: center; line-height: 1.1; }
.it .v { position: absolute; right: 1px; bottom: 0; font-size: 10px; color: var(--muted); }
.it.near { border-color: var(--warn); }
.it.out { opacity: .2; }
.it.out::after { content: ""; position: absolute; left: 6px; right: 6px; top: 50%; border-top: 2px solid var(--text); transform: rotate(-35deg); }
.more { margin: 0 10px 10px; }
.hint { color: var(--muted); margin: 4px 0 12px; max-width: 900px; }
.legend { display: inline-flex; gap: 4px; align-items: center; }
.sw { display: inline-block; width: 12px; height: 12px; border-radius: 3px; background: var(--tile); border: 2px solid var(--warn); vertical-align: -2px; }
@media (max-width: 760px) {
  .layout { grid-template-columns: 1fr; height: auto; }
  nav { max-height: 220px; border-right: 0; border-bottom: 1px solid var(--line); }
  input[type=search] { width: 100%; }
}
</style>
</head>
<body>
<header>
  <h1>Zipto Picker</h1>
  <span class="tally" id="tally"></span>
  <span class="grow"></span>
  <input type="search" id="q" placeholder="Search furni or sets">
  <button id="export" class="primary" title="Save your choices to a file for the import">Export choices</button>
  <button id="load" title="Load a choices file you exported before">Load choices</button>
  <input type="file" id="file" accept=".json" hidden>
</header>
<div class="layout">
  <nav>
    <div class="navtools">
      <label><input type="checkbox" id="openonly"> Only what is still undecided</label>
    </div>
    <div id="groups"></div>
  </nav>
  <main id="main"></main>
</div>
<script>
const DATA = /*DATA*/null;
const KEY = 'zipto-picker-v1';
const SHOW = 96;
let state = { sets: {}, out: {} };
try { const s = JSON.parse(localStorage.getItem(KEY) || 'null'); if (s && s.sets) state = s; } catch (e) {}
function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} tally(); }
let current = DATA.groups[0].id;
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function decided(i) { const st = state.sets[DATA.sets[i].id]; return st && st.s; }
function furniIn(set) { return set.items.reduce((n, it) => n + (state.out[it[0]] ? 0 : it[2]), 0); }
function tally() {
  let si = 0, fi = 0, sk = 0;
  DATA.sets.forEach((s, i) => { const d = decided(i); if (d === 'import') { si++; fi += furniIn(s); } else if (d === 'skip') sk++; });
  const left = DATA.sets.length - si - sk;
  document.getElementById('tally').innerHTML =
    `Import <b>${si}</b> sets (<b>${fi.toLocaleString()}</b> furni) &middot; Skip <b>${sk}</b> &middot; Undecided <b>${left}</b> of ${DATA.sets.length}`;
  renderGroups();
}
const openCats = new Set();
function renderGroups() {
  const only = document.getElementById('openonly').checked;
  const cur = DATA.groups.find(g => g.id === current);
  const cats = [];
  DATA.groups.forEach(g => { let c = cats.find(x => x.name === g.cat); if (!c) cats.push(c = { name: g.cat, subs: [], n: 0 }); c.subs.push(g); c.n += g.n; });
  document.getElementById('groups').innerHTML = cats.map(c => {
    const undecided = c.subs.reduce((n, g) => n + g.sets.filter(i => !decided(i)).length, 0);
    if (only && !undecided && !(cur && cur.cat === c.name)) return '';
    const open = openCats.has(c.name) || (cur && cur.cat === c.name);
    const subs = open ? c.subs.map(g => {
      const left = g.sets.filter(i => !decided(i)).length;
      if (only && !left && g.id !== current) return '';
      const mark = left ? `<span class="c">${g.n.toLocaleString()}</span>` : `<span class="c done">done</span>`;
      return `<div class="g sub${g.id === current ? ' on' : ''}" data-g="${esc(g.id)}"><span>${esc(g.name)}</span>${mark}</div>`;
    }).join('') : '';
    const mark = undecided ? `<span class="c">${c.n.toLocaleString()}</span>` : `<span class="c done">done</span>`;
    // a category with one list of sets and no sub-categories is a single row
    if (c.subs.length === 1)
      return `<div class="cat g${c.subs[0].id === current ? ' on' : ''}" data-g="${esc(c.subs[0].id)}"><span><span class="chev"></span> ${esc(c.name)}</span>${mark}</div>`;
    return `<div class="cat${open ? ' open' : ''}" data-cat="${esc(c.name)}"><span><span class="chev">${open ? '&#9662;' : '&#9656;'}</span> ${esc(c.name)}</span>${mark}</div>${subs}`;
  }).join('');
}
function itemHtml(it) {
  const [c, n, v, icon, note] = it;
  const tip = `${c}\n${n}${v > 1 ? `\n${v} colours` : ''}${note ? '\n' + note : ''}`;
  const img = icon ? `<img loading="lazy" decoding="async" src="${icon}" alt="">` : `<span class="noimg">${esc(c)}</span>`;
  return `<div class="it${note ? ' near' : ''}${state.out[c] ? ' out' : ''}" data-c="${esc(c)}" title="${esc(tip)}">${img}${v > 1 ? `<span class="v">${v}</span>` : ''}</div>`;
}
function setHtml(i, all) {
  const s = DATA.sets[i], st = state.sets[s.id] || {};
  const items = all ? s.items : s.items.slice(0, SHOW);
  const more = s.items.length > items.length ? `<button class="more" data-more="${i}">Show all ${s.items.length}</button>` : '';
  return `<section class="set ${st.s || ''}" data-i="${i}">
    <div class="shead">
      <span class="t">${esc(s.t)}</span>${s.raw ? `<span class="raw">${esc(s.raw)}</span>` : ''}<span class="c">${s.n.toLocaleString()} furni</span>
      ${s.note ? `<span class="note">${esc(s.note)}</span>` : ''}
      <span class="grow"></span>
      ${st.s === 'import' ? `<input type="text" class="name" data-name="${i}" placeholder="${esc(s.sg || 'Set name')}" value="${esc(st.name || '')}" title="Name of the Customs set">` : ''}
      <span class="seg"><button class="in${st.s === 'import' ? ' on' : ''}" data-set="${i}" data-v="import">Import</button><button class="sk${st.s === 'skip' ? ' on' : ''}" data-set="${i}" data-v="skip">Skip</button></span>
    </div>
    <div class="grid">${items.map(itemHtml).join('')}</div>${more}
  </section>`;
}
function renderGroup() {
  const g = DATA.groups.find(x => x.id === current);
  document.getElementById('main').innerHTML = `
    <div class="ghead"><h2>${g.name === g.cat ? '' : `<span class="crumb">${esc(g.cat)} &rsaquo;</span> `}${esc(g.name)}</h2><span class="c">${g.sets.length} sets, ${g.n.toLocaleString()} furni</span>
      <span class="grow"></span>
      <button data-all="import">Import every set here</button> <button data-all="skip">Skip every set here</button></div>
    <p class="hint">Import or Skip each set. Click a furni to leave just that one out. A tile with a number has that many colours.
      <span class="legend"><span class="sw"></span> looks like a furni we already have (hover for which).</span></p>
    ${g.sets.map(i => setHtml(i, false)).join('')}`;
  document.getElementById('main').scrollTop = 0;
}
function renderSearch(q) {
  q = q.toLowerCase();
  const hits = [];
  DATA.sets.forEach((s, i) => {
    if (s.t.toLowerCase().includes(q) || (s.raw || '').toLowerCase().includes(q) || s.g.toLowerCase().includes(q) || s.items.some(it => it[0].toLowerCase().includes(q) || it[1].toLowerCase().includes(q))) hits.push(i);
  });
  document.getElementById('main').innerHTML = `<div class="ghead"><h2>Search: ${esc(q)}</h2><span class="c">${hits.length} sets</span></div>` +
    hits.slice(0, 40).map(i => setHtml(i, false)).join('') + (hits.length > 40 ? `<p class="hint">Showing 40 of ${hits.length} sets - narrow the search.</p>` : '');
}
function rerenderSet(i) {
  const el = document.querySelector(`section[data-i="${i}"]`);
  if (el) { const all = !el.querySelector('.more'); el.outerHTML = setHtml(i, all); }
}

document.addEventListener('click', e => {
  const t = e.target.closest('[data-cat],[data-g],[data-set],[data-all],[data-more],.it');
  if (!t) return;
  if (t.dataset.cat) {
    const c = t.dataset.cat, cur = DATA.groups.find(g => g.id === current);
    if (openCats.has(c) || (cur && cur.cat === c)) openCats.delete(c); else openCats.add(c);
    if (!(cur && cur.cat === c) && openCats.has(c)) { current = DATA.groups.find(g => g.cat === c).id; document.getElementById('q').value = ''; renderGroup(); }
    renderGroups(); return;
  }
  if (t.dataset.g) { current = t.dataset.g; document.getElementById('q').value = ''; renderGroups(); renderGroup(); return; }
  if (t.dataset.more) { const el = t.closest('section'); el.outerHTML = setHtml(+t.dataset.more, true); return; }
  if (t.dataset.all) {
    DATA.groups.find(x => x.id === current).sets.forEach(i => { const id = DATA.sets[i].id; state.sets[id] = Object.assign(state.sets[id] || {}, { s: t.dataset.all }); });
    save(); renderGroup(); return;
  }
  if (t.dataset.set) {
    const i = +t.dataset.set, id = DATA.sets[i].id, cur = state.sets[id] || {};
    cur.s = cur.s === t.dataset.v ? undefined : t.dataset.v;
    state.sets[id] = cur; save(); rerenderSet(i); return;
  }
  if (t.classList.contains('it')) {
    const c = t.dataset.c;
    if (state.out[c]) delete state.out[c]; else state.out[c] = true;
    t.classList.toggle('out', !!state.out[c]); save();
  }
});
document.addEventListener('input', e => {
  if (e.target.dataset.name !== undefined) {
    const id = DATA.sets[+e.target.dataset.name].id;
    state.sets[id] = Object.assign(state.sets[id] || {}, { name: e.target.value }); save();
  }
});
let timer;
document.getElementById('q').addEventListener('input', e => {
  clearTimeout(timer);
  timer = setTimeout(() => { const q = e.target.value.trim(); if (q.length >= 2) renderSearch(q); else renderGroup(); }, 200);
});
document.getElementById('openonly').addEventListener('change', renderGroups);
document.getElementById('export').addEventListener('click', () => {
  const picked = [];
  DATA.sets.forEach(s => {
    const st = state.sets[s.id];
    if (!st || !st.s) return;
    picked.push({ id: s.id, group: s.g, title: s.t, source: s.raw, choice: st.s, name: (st.name || '').trim() || s.sg,
      furni: st.s === 'import' ? s.items.filter(it => !state.out[it[0]]).map(it => it[0]) : [] });
  });
  const blob = new Blob([JSON.stringify({ saved: new Date().toISOString(), sets: picked, left_out: Object.keys(state.out) }, null, 1)], { type: 'application/json' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'zipto-picks.json'; a.click();
});
document.getElementById('load').addEventListener('click', () => document.getElementById('file').click());
document.getElementById('file').addEventListener('change', async e => {
  const f = e.target.files[0]; if (!f) return;
  try {
    const d = JSON.parse(await f.text());
    state = { sets: {}, out: {} };
    (d.sets || []).forEach(s => { state.sets[s.id] = { s: s.choice, name: s.name }; });
    (d.left_out || []).forEach(c => { state.out[c] = true; });
    save(); renderGroup();
  } catch (err) { alert('That file could not be read: ' + err.message); }
});
tally(); renderGroup();
</script>
</body>
</html>
'''

if __name__ == '__main__':
    main()
