"""English names for the Zipto furni that come in from outside Zipto's shop.

There are ~24,000 of them, so they are named by rule, not one by one as the
shop's ~1,600 were (zipto_names.py):

- Zipto's own name, with its broken accents mended and folded to plain ASCII
  (the database is spoken to in latin1), or the classname made into words when
  the name is only a placeholder;
- the furni maker's or hotel's tag taken off (Hfdiy, Hellsinore, Yvess ...);
- the common furniture words of French, Spanish, Portuguese, Dutch, German and
  Italian put into English, an adjective moved in front of its noun ('Bain
  Blanc' -> 'White Bath') and 'X de Y' turned round ('Bol De Cuisine' ->
  'Kitchen Bowl'); words stuck together are split where every piece is known
  ('Escolamoderna' -> 'Modern School');
- the Pokemon figures, which Zipto names only 'Pokeweebz', by their number.

A word nothing here knows stays as it is: a brand or a character's name is
usually right as it stands, and staff can rename any furni in the shop.
"""
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ENGLISH = set(open(os.path.join(HERE, 'zipto-furni', 'english-words.txt'), encoding='utf-8').read().split())

# Makers' and hotels' tags: a name reads the same without them.
MAKERS = set('''
yvess yvess5 hellsinore hfdiy finley cstm niooo fbnncls ebm wibbocustom wibbo irinc cait marion zhentou
xsongzi lucifer luopei hubba apo bletween lizzy habbox habblet hbx bssitalia bss falque rk osn realliferpg
isakwouto lipe shtrdl mkq krm hekos habboin habbocity hcity hekoscity hlive livefurni leahabblet mybobba
ipixxel thesubfurni xkekos kyat leeyas ravenmtsh galeriabergstrom casabergstrom bergstrom mel isa mbl clr hm tn wm
bbb stv sg tp qxe sdb cus iceblue bobbassa bobba hobba hubbe habsjov machi haaziq newhaaziq awhey liverare
hbooh redd bdayfs wataeis xueze kasja cheapyxony lea stef corinna esme tyla malin pavin mivi smouks
garance lyvo ntr netsky frogg yejihb seops shokinholaint monrp weapz idk ss vt lm hn ml alp tvoh
habboin habbocity bsstonino eline toinou ipixxel podestry dralaxy rctnglr chailong vantassel dcdragi
sl iso co co2 osrs hbo hboct biorella isabel aurelio stef shone heidi markus mut sonnyangels
'''.split())

# word -> English. A '+' marks an adjective, which goes in front of its noun.
WORDS = {
    # French
    'noel': 'Christmas', 'paque': 'Easter', 'paques': 'Easter', 'ete': 'Summer', 'hiver': 'Winter',
    'automne': 'Autumn', 'printemps': 'Spring', 'plante': 'Plant', 'plantes': 'Plants', 'fleur': 'Flower',
    'fleurs': 'Flowers', 'arbre': 'Tree', 'arbuste': 'Shrub', 'feuille': 'Leaf', 'feuilles': 'Leaves',
    'herbe': 'Grass', 'pierre': 'Stone', 'rocher': 'Rock', 'bois': '+Wooden', 'verre': 'Glass',
    'mur': 'Wall', 'sol': 'Floor', 'plafond': 'Ceiling', 'toit': 'Roof', 'porte': 'Door', 'portes': 'Doors',
    'fenetre': 'Window', 'fenetres': 'Windows', 'escalier': 'Stairs', 'colonne': 'Column', 'pilier': 'Pillar',
    'bloc': 'Block', 'dalle': 'Tile', 'carrelage': 'Tiles', 'tapis': 'Rug', 'rideau': 'Curtain',
    'rideaux': 'Curtains', 'coussin': 'Cushion', 'coussins': 'Cushions', 'couverture': 'Blanket',
    'oreiller': 'Pillow', 'chaise': 'Chair', 'chaises': 'Chairs', 'fauteuil': 'Armchair', 'canape': 'Sofa',
    'tabouret': 'Stool', 'banc': 'Bench', 'lit': 'Bed', 'matelas': 'Mattress', 'armoire': 'Wardrobe',
    'commode': 'Dresser', 'bureau': 'Desk', 'etagere': 'Shelf', 'etageres': 'Shelves', 'planche': 'Board',
    'tableau': 'Painting', 'cadre': 'Frame', 'miroir': 'Mirror', 'lampe': 'Lamp', 'lampadaire': 'Floor Lamp',
    'lustre': 'Chandelier', 'bougie': 'Candle', 'bougies': 'Candles', 'lumiere': 'Light', 'horloge': 'Clock',
    'cuisine': 'Kitchen', 'salle': 'Room', 'chambre': 'Bedroom', 'bain': 'Bath', 'baignoire': 'Bathtub',
    'douche': 'Shower', 'evier': 'Sink', 'lavabo': 'Washbasin', 'robinet': 'Tap', 'toilette': 'Toilet',
    'toilettes': 'Toilet', 'frigo': 'Fridge', 'refrigerateur': 'Fridge', 'four': 'Oven', 'poubelle': 'Bin',
    'couverts': 'Cutlery', 'theiere': 'Teapot', 'grillepain': 'Toaster', 'cafetiere': 'Coffee Maker',
    'ilot': 'Island', 'comptoir': 'Counter', 'couteaux': 'Knives', 'assiette': 'Plate', 'bol': 'Bowl',
    'tasse': 'Cup', 'verres': 'Glasses', 'bouteille': 'Bottle', 'bouteilles': 'Bottles', 'gateau': 'Cake',
    'microonde': 'Microwave', 'lavevaisselle': 'Dishwasher', 'essuietout': 'Paper Towels', 'cuisson': 'Cooking',
    'cadeau': 'Gift', 'cadeaux': 'Gifts', 'ballon': 'Balloon', 'ballons': 'Balloons', 'coeur': 'Heart',
    'etoile': 'Star', 'lune': 'Moon', 'soleil': 'Sun', 'nuage': 'Cloud', 'chat': 'Cat', 'chien': 'Dog',
    'cochon': 'Pig', 'lapin': 'Rabbit', 'oiseau': 'Bird', 'poisson': 'Fish', 'cheval': 'Horse', 'vache': 'Cow',
    'ours': 'Bear', 'poupee': 'Doll', 'jouet': 'Toy', 'jouets': 'Toys', 'livre': 'Book', 'livres': 'Books',
    'boite': 'Box', 'caisse': 'Crate', 'coffre': 'Chest', 'tonneau': 'Barrel', 'baril': 'Barrel',
    'barriere': 'Barrier', 'cloture': 'Fence', 'chalet': 'Chalet', 'chateau': 'Castle', 'jardin': 'Garden',
    'fontaine': 'Fountain', 'vitrail': 'Stained Glass', 'chiffres': 'Numbers', 'lettre': 'Letter',
    'lettres': 'Letters', 'grec': '+Greek', 'grecque': '+Greek', 'egypte': '+Egyptian', 'japonais': '+Japanese',
    'japonaise': '+Japanese', 'chinois': '+Chinese', 'osier': '+Wicker', 'rose': '+Pink', 'rouge': '+Red',
    'vert': '+Green', 'verte': '+Green', 'bleu': '+Blue', 'bleue': '+Blue', 'noir': '+Black', 'noire': '+Black',
    'blanc': '+White', 'blanche': '+White', 'jaune': '+Yellow', 'marron': '+Brown', 'gris': '+Grey',
    'grise': '+Grey', 'violet': '+Purple', 'dore': '+Gold', 'doree': '+Gold', 'argent': '+Silver',
    'grand': '+Big', 'grande': '+Big', 'petit': '+Small', 'petite': '+Small', 'vieux': '+Old',
    'nouveau': '+New', 'moderne': '+Modern', 'ancien': '+Antique', 'ancienne': '+Antique', 'mini': '+Mini',
    'plume': 'Feather', 'pouf': 'Pouf', 'terrain': 'Ground', 'pot': 'Pot', 'vase': 'Vase', 'sapin': 'Fir Tree',
    'bonhomme': 'Snowman', 'neige': 'Snow', 'citrouille': 'Pumpkin', 'squelette': 'Skeleton', 'cercueil': 'Coffin',
    'tombe': 'Grave', 'fantome': 'Ghost', 'sorciere': 'Witch',
    # Spanish
    'mesa': 'Table', 'silla': 'Chair', 'sillon': 'Armchair', 'cama': 'Bed', 'estante': 'Shelf',
    'estanteria': 'Shelves', 'armario': 'Wardrobe', 'alfombra': 'Rug', 'cojin': 'Cushion', 'cuadro': 'Painting',
    'puerta': 'Door', 'ventana': 'Window', 'pared': 'Wall', 'muro': 'Wall', 'suelo': 'Floor', 'suelos': 'Floors',
    'techo': 'Roof', 'tejado': 'Roof', 'cocina': 'Kitchen', 'bano': 'Bathroom', 'nevera': 'Fridge',
    'horno': 'Oven', 'espejo': 'Mirror', 'maceta': 'Flowerpot', 'macetero': 'Planter', 'flor': 'Flower',
    'flores': 'Flowers', 'arbol': 'Tree', 'arbusto': 'Shrub', 'cesped': 'Lawn', 'piedra': 'Stone',
    'madera': '+Wooden', 'lampara': 'Lamp', 'farol': 'Lantern', 'vela': 'Candle', 'velas': 'Candles',
    'reloj': 'Clock', 'barra': 'Bar', 'botellas': 'Bottles', 'bebida': 'Drink', 'caja': 'Box',
    'cajas': 'Boxes', 'baul': 'Trunk', 'cortina': 'Curtain', 'cortinas': 'Curtains', 'escalera': 'Stairs',
    'columna': 'Column', 'arco': 'Arch', 'castillo': 'Castle', 'dormitorio': 'Bedroom', 'salon': 'Living Room',
    'microonda': 'Microwave', 'mueble': 'Cabinet', 'muebles': 'Furniture', 'taburete': 'Stool',
    'banco': 'Bench', 'asiento': 'Seat', 'esquina': 'Corner', 'borde': 'Edge', 'rosa': '+Pink',
    'azul': '+Blue', 'rojo': '+Red', 'roja': '+Red', 'verde': '+Green', 'negro': '+Black', 'negra': '+Black',
    'blanco': '+White', 'blanca': '+White', 'amarillo': '+Yellow', 'morado': '+Purple', 'naranja': '+Orange',
    'dorado': '+Gold', 'plata': '+Silver', 'gris_es': '+Grey', 'pequeno': '+Small', 'pequena': '+Small',
    'nuevo': '+New', 'viejo': '+Old', 'antiguo': '+Antique', 'antigua': '+Antique', 'moderno': '+Modern',
    'moderna': '+Modern', 'redondo': '+Round', 'redonda': '+Round', 'navidad': 'Christmas',
    'pascua': 'Easter', 'verano': 'Summer', 'invierno': 'Winter', 'otono': 'Autumn', 'regalo': 'Gift',
    'corazon': 'Heart', 'estrella': 'Star', 'gato': 'Cat', 'perro': 'Dog', 'cerdo': 'Pig', 'conejo': 'Rabbit',
    'pajaro': 'Bird', 'pez': 'Fish', 'caballo': 'Horse', 'oso': 'Bear', 'muneca': 'Doll', 'libro': 'Book',
    'libros': 'Books', 'fuente': 'Fountain', 'jardin_es': 'Garden', 'agua': 'Water', 'fuego': 'Fire',
    'cuchillos': 'Knives', 'cafetera': 'Coffee Maker', 'estractor': 'Extractor', 'cubo': 'Bucket',
    'set': 'Set', 'pared_': 'Wall', 'vitrales': 'Stained Glass', 'vinilos': 'Vinyls', 'cine': 'Cinema',
    # Portuguese
    'cadeira': 'Chair', 'poltrona': 'Armchair', 'tapete': 'Rug', 'almofada': 'Cushion', 'quadro': 'Painting',
    'porta': 'Door', 'janela': 'Window', 'parede': 'Wall', 'chao': 'Floor', 'cozinha': 'Kitchen',
    'banheiro': 'Bathroom', 'geladeira': 'Fridge', 'fogao': 'Stove', 'espelho': 'Mirror', 'arvore': 'Tree',
    'pedra': 'Stone', 'madeira': '+Wooden', 'vermelho': '+Red', 'vermelha': '+Red', 'preto': '+Black',
    'preta': '+Black', 'branco': '+White', 'branca': '+White', 'amarelo': '+Yellow', 'roxo': '+Purple',
    'laranja': '+Orange', 'dourado': '+Gold', 'prata': '+Silver', 'pequeno_pt': '+Small', 'elegante': '+Elegant',
    'escola': 'School', 'pascoa': 'Easter', 'natal': 'Christmas', 'doce': 'Sweet', 'doces': 'Sweets',
    'culinaria': 'Kitchen', 'sanduicheira': 'Sandwich Maker', 'cabana': 'Cabin', 'vitral': 'Stained Glass',
    'luminaria': 'Lamp', 'cortinha': 'Curtain', 'prateleira': 'Shelf', 'gaveta': 'Drawer',
    'plantinha': 'Small Plant', 'noz': 'Nut', 'nozes': 'Nuts', 'deefrigerateur': 'Fridge',
    'jeucarte': 'Card Game', 'pingouin': 'Penguin', 'trone': 'Throne', 'semaforo': 'Traffic Light',
    'cajon': 'Drawer', 'maquinacoser': 'Sewing Machine', 'eismaschine': 'Ice Cream Machine',
    'dragonlam': 'Dragon Lamp', 'rond': '+Round', 'ronde': '+Round', 'carre': '+Square', 'aspirateur': 'Vacuum Cleaner',
    'trofeo': 'Trophy', 'ascenseur': 'Lift', 'briques': 'Bricks', 'marbre': '+Marble', 'banlieue': 'Suburb', 'galeria': 'Gallery',
    # Dutch
    'stoel': 'Chair', 'tafel': 'Table', 'bank': 'Sofa', 'kast': 'Cupboard', 'kussen': 'Cushion',
    'schilderij': 'Painting', 'deur': 'Door', 'raam': 'Window', 'muur': 'Wall', 'vloer': 'Floor',
    'keuken': 'Kitchen', 'badkamer': 'Bathroom', 'koelkast': 'Fridge', 'boom': 'Tree', 'steen': 'Stone',
    'hout': '+Wooden', 'blauw': '+Blue', 'rood': '+Red', 'groen': '+Green', 'zwart': '+Black', 'wit': '+White',
    'geel': '+Yellow', 'paars': '+Purple', 'oranje': '+Orange', 'goud': '+Gold', 'zilver': '+Silver',
    'groot': '+Big', 'klein': '+Small', 'kerst': 'Christmas', 'pasen': 'Easter', 'huiskamer': 'Living Room',
    'slaapkamer': 'Bedroom', 'draak': 'Dragon', 'bouw': 'Building', 'veld': 'Field', 'tegel': 'Tile',
    'trap': 'Stairs', 'dak': 'Roof', 'blok': 'Block', 'pilaar': 'Pillar',
    # German
    'stuhl': 'Chair', 'tisch': 'Table', 'bett': 'Bed', 'schrank': 'Cupboard', 'tur': 'Door', 'fenster': 'Window',
    'boden': 'Floor', 'kuche': 'Kitchen', 'baum': 'Tree', 'holz': '+Wooden', 'blau': '+Blue', 'rot': '+Red',
    'grun': '+Green', 'schwarz': '+Black', 'weiss': '+White', 'gelb': '+Yellow', 'regal': 'Shelf',
    'teppich': 'Rug', 'sessel': 'Armchair', 'drachenlampe': 'Dragon Lamp', 'drachen': 'Dragon',
    # Italian
    'sedia': 'Chair', 'tavolo': 'Table', 'letto': 'Bed', 'divano': 'Sofa', 'armadio': 'Wardrobe',
    'cuscino': 'Cushion', 'finestra': 'Window', 'cucina': 'Kitchen', 'bagno': 'Bathroom', 'specchio': 'Mirror',
    'albero': 'Tree', 'legno': '+Wooden', 'rosso': '+Red', 'nero': '+Black', 'bianco': '+White',
    'giallo': '+Yellow', 'fiore': 'Flower', 'fiori': 'Flowers', 'tramonto': 'Sunset',
    # Swedish / Turkish
    'badrum': 'Bathroom', 'bedrum': 'Bedroom', 'banyo': 'Bathroom', 'kok': 'Kitchen',
    # shorthand
    'blk': '+Black', 'wht': '+White', 'grn': '+Green', 'flr': 'Floor', 'xmas': 'Christmas',
    'hween': 'Halloween', 'bday': 'Birthday', 'bdy': 'Birthday', 'tv': 'TV', 'pc': 'PC', 'dj': 'DJ',
    'vip': 'VIP', 'hp': 'HP', 'ufo': 'UFO', 'diy': 'DIY', 'rgb': 'RGB', 'led': 'LED',
}
# Words that are English too but mean the foreign thing in a name that is foreign
TWO_WAY = {'lit', 'four', 'bank', 'trap', 'or', 'sol', 'rose', 'bad', 'set'}
CONNECTORS = {'de', 'du', 'des', 'da', 'do', 'das', 'dos', 'del', 'di', 'della', 'van', 'von', 'en'}
ARTICLES = {'le', 'la', 'les', 'el', 'los', 'las', 'het', 'der', 'die', 'il', 'lo', 'un', 'une', 'uno', 'una'}
KNOWN = ENGLISH | set(WORDS)


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


def ascii_fold(s):
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')


def split_word(word):
    """'escolamoderna' -> ['escola', 'moderna'] when every piece is a known
    word of 3+ letters; None when it does not split cleanly."""
    n = len(word)
    best = [None] * (n + 1)
    best[0] = []
    for i in range(n):
        if best[i] is None:
            continue
        for j in range(i + 3, n + 1):
            piece = word[i:j]
            if piece in KNOWN and (best[j] is None or len(best[i]) + 1 < len(best[j])):
                best[j] = best[i] + [piece]
    parts = best[n]
    return parts if parts and 1 < len(parts) <= 3 else None


def words_of(raw, classname):
    raw = ascii_fold(fix_text(raw or ''))
    if not raw or raw == classname or '_' in raw or raw.lower() == classname.lower():
        raw = classname
    raw = re.sub(r'(_desc|_name)$', '', raw)
    raw = re.sub(r'([a-z])([A-Z])', r'\1 \2', raw)             # camelCase
    raw = re.sub(r'(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])', ' ', raw)
    return [w for w in re.split(r"[\s_\-\.,/()+&]+", raw) if w]


POKEMON = re.compile(r'^pokeweebz(s?)0*(\d+)$', re.I)


def english(raw, classname, maker_words=()):
    """The furni's English name: see the module docstring."""
    m = POKEMON.match(classname)
    if m:
        return ('Shiny Pokemon %03d' if m.group(1) else 'Pokemon %03d') % int(m.group(2))
    m = re.match(r'^pokem0*(\d+)$', classname, re.I)
    if m:
        return 'Pokemon Picture %d' % int(m.group(1))
    makers = MAKERS | {w.lower() for w in maker_words}
    words = [w for w in words_of(raw, classname)]
    # a long run of letters nobody knows may be words stuck together
    out = []
    for w in words:
        low = w.lower()
        if low not in KNOWN and low not in makers and len(low) >= 7 and low.isalpha():
            parts = split_word(low)
            if parts:
                out += parts
                continue
        out.append(w)
    words = out
    keep = []
    for n, w in enumerate(words):
        low = w.lower()
        if low in makers or low in ARTICLES:
            continue
        if w.isdigit() and n and words[n - 1].lower() in makers:
            continue                              # rk1, yvess5: the maker's own number
        keep.append(w)
    if not [w for w in keep if not w.isdigit()]:
        return None                               # nothing but a maker's tag: the set's name will do
    # a number in front reads better behind: 13 Tarot Card -> Tarot Card 13
    while keep and keep[0].isdigit() and len(keep) > 1:
        keep = keep[1:] + keep[:1]
    foreign = any(w.lower() in WORDS and w.lower() not in ENGLISH for w in keep)
    tokens = []                                   # (text, is_adjective, was_translated)
    for w in keep:
        low = w.lower()
        tr = WORDS.get(low) if (low not in ENGLISH or (foreign and low in TWO_WAY)) else None
        if tr:
            tokens.append((tr.lstrip('+'), tr.startswith('+'), True))
        elif low in CONNECTORS and foreign:
            tokens.append(('<of>', False, True))
        elif w.isdigit():
            tokens.append((str(int(w)), False, False))
        elif w.isupper() and len(w) <= 4 and w.isalpha():
            tokens.append((w, False, False))
        else:
            tokens.append((w[:1].upper() + w[1:].lower(), False, False))
    # 'Bol <of> Cuisine' -> 'Cuisine Bol' (translated: Kitchen Bowl)
    if any(t[0] == '<of>' for t in tokens):
        i = next(n for n, t in enumerate(tokens) if t[0] == '<of>')
        head, tail = tokens[:i], tokens[i + 1:]
        tail = [t for t in tail if t[0] != '<of>']
        number = [t for t in tail if t[0].isdigit()]
        tail = [t for t in tail if not t[0].isdigit()]
        tokens = tail + head + number
    # a translated adjective goes in front of the noun before it: Bain Blanc -> White Bath
    i = 1
    while i < len(tokens):
        if tokens[i][1] and tokens[i][2] and not tokens[i - 1][1] and not tokens[i - 1][0].isdigit():
            tokens[i - 1], tokens[i] = tokens[i], tokens[i - 1]
            i += 2
        else:
            i += 1
    name = ' '.join(t[0] for t in tokens)
    name = re.sub(r'\b(\w+) \1\b', r'\1', name)   # 'Lamp Lamp'
    name = re.sub(r'\s+', ' ', name).strip()
    return name or classname
