#!/usr/bin/env python3
"""Import the custom clothing in the Habzone asset dump into the hotel.

The dump is a whole Nitro asset tree from habzone.lol (March 2024):
bundled/figure holds 5,151 .nitro libraries, gamedata/ its FigureMap.json and
FigureData.json. Most of it is Habbo's own clothing or the same retro packs
the hotel already took (Wulez), so this takes only what the hotel does not
have, and writes the five things a garment needs (nitro/overrides/README.md,
"Avatar libraries"):

  1. nitro/overrides/bundled/figure/<library>.nitro
  2. nitro/overrides/gamedata-merge/FigureMap.json    (libraries appended)
  3. nitro/overrides/gamedata-merge/FigureData.json   (sets appended)
  4. emulator/Config/figuredata.xml                   (the same sets)
  5. emulator/Resources/SQLs/Updates/<n>_ClothingHabzone.sql (the shelf)

plus docker/nitro/habzone-clothes/ids.csv, the old -> new id of every set
and part, so a set can still be traced back to the dump.

The bundles are already .nitro, so nothing is converted; they are rewritten
(new part ids, strays removed) and copied.

Which libraries
---------------
A library is a candidate when its FigureMap entry names parts, its bundle
draws at least one of them, and the hotel has no library of that name
(Habbo's figuremap as converted on 2026-08-07, build 202608061512, plus every
library and bundle nitro/overrides adds). The dump's own base libraries
(hh_human_*) are never taken. Bundles the dump's FigureMap never mentions are
not clothing anyone could wear there - 254 are avatar effects (EffectMap),
the rest loose props and base sheets - and are reported, not taken.

Names alone miss copies: retros rename Habbo's and each other's items
(chest_acc_U_ttslingbagdp is Habbo's acc_chest_U_ttslingbagdp, Hat_U_sombreru
is Hat_U_sombrero), and ids alone mislead: Habbo has since released items on
many of the dump's numbers (hair_F_taylorhair draws hr 5777, Habbo's
hair_U_nftsummercut24 now). So every sprite is fingerprinted - an md5 of its
pixels - and a candidate's part is a copy when at least COPY_SHARE of its
sprites are drawn, pixel for pixel, by one part the hotel already has (the
dump's own copy of a Habbo library, or any bundle in nitro/overrides). A
library whose every main part is a copy is skipped. Sleeves, hands and hair
backs (ls/rs/lc/rc/hrb) do not count towards that: plain sleeves are the same
pixels on dozens of shirts.

Renumbering
-----------
Every imported set and part gets a new id, in its own block from
FIRST_SET / FIRST_PART (the Wulez pack holds 300000 up), for the reason the
Wulez import gives: the dump's ids collide with Habbo's newer items and will
keep colliding. Part ids are renamed inside each bundle (asset keys, alias
sources, spritesheet frames).

Every other sprite in a bundle is removed. Nitro looks an avatar sprite up by
name across every library it has loaded and takes the first it finds, so a
stray h_std_hr_5777_2_0 left in a bundle would draw over Habbo's hr 5777 for
anyone who happened to load this library first.

A part is claimed by the first candidate library, in FigureMap order, whose
bundle actually draws it.

Sets
----
Every dump set that wears at least one claimed part is imported. Each part it
lists resolves the way the dump itself resolved it, through the library its
FigureMap gives for that part:
  - a claimed part takes its new id;
  - a part of a library the hotel has by name keeps its id if the hotel's
    library has it, or takes the id the Wulez import gave it (ids.csv);
  - a part that is a copy takes the id of the hotel part it copies.
A sleeve, hand or hair-back part that does not resolve is dropped (the client
would draw nothing for it anyway); any other drops the set. A set identical to
one already imported is not added twice, and a part a set lists twice is kept
once - the emulator keys a set's parts on id-type with Dictionary.Add.

The hotel's rules, not the dump's: gender from the library's file name
(_M_ male, _F_ female, _U_ or none unisex), club 0, selectable, not
preselectable, sellable; hidden layers are kept. The Clothing Store files
each row under its set type's category (Head, Torso, Legs) and shows a
player the rows cut for their gender, so that is all the sorting a row needs.

The shelf
---------
One catalog_clothing row per garment, named after its library; a garment
shipping as a male and a female library is one row holding both sets, and a
library holding several different pieces is one row per piece. 50
credits, faces (hd) 0 and owned-only - the same rules as 262.

Usage:
  python3 docker/nitro/import-habzone-clothes.py --source <dump root> \\
      --habbo-figuremap fm_0806.xml [--list | --migration 264]

--list reports what would be taken and why the rest is not, and writes
nothing. Re-running is safe: ids.csv keeps every id an earlier run gave out
(and what an earlier run imported is never re-judged a copy - it is on the
shelf), the bundles are rewritten, and the migration holds only the new rows.
"""
import argparse
import collections
import csv
import hashlib
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from furni_bundle import bundle_entries, inflate, write_bundle  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
FIGURE_DIR = os.path.join(REPO, 'nitro', 'overrides', 'bundled', 'figure')
MAP_FRAGMENT = os.path.join(REPO, 'nitro', 'overrides', 'gamedata-merge', 'FigureMap.json')
DATA_FRAGMENT = os.path.join(REPO, 'nitro', 'overrides', 'gamedata-merge', 'FigureData.json')
FIGUREDATA_XML = os.path.join(REPO, 'emulator', 'Config', 'figuredata.xml')
UPDATES = os.path.join(REPO, 'emulator', 'Resources', 'SQLs', 'Updates')
IDS_CSV = os.path.join(REPO, 'docker', 'nitro', 'habzone-clothes', 'ids.csv')
WULEZ_IDS = os.path.join(REPO, 'docker', 'nitro', 'wulez-clothes', 'ids.csv')

FIRST_SET = 400000
FIRST_PART = 400000
PRICE = 50
COPY_SHARE = 0.9
OWNED_ONLY_TYPES = {'hd'}
SECONDARY = {'ls', 'rs', 'lc', 'rc', 'hrb'}
NOTHING = object()
SET_TYPE_ORDER = ['hr', 'hd', 'ch', 'lg', 'sh', 'ha', 'he', 'ea', 'fa', 'ca', 'wa', 'cc', 'cp']
CATEGORY = {'hr': 'Head', 'ha': 'Head', 'he': 'Head', 'ea': 'Head', 'fa': 'Head', 'hd': 'Face',
            'ch': 'Torso', 'cp': 'Torso', 'cc': 'Torso', 'ca': 'Torso',
            'lg': 'Legs', 'sh': 'Legs', 'wa': 'Legs'}

# <scale>_<action>_<part type>_<part id>_<direction>_<frame>, optionally behind
# the library's own name (spritesheet frames are <library>_h_std_...). The
# scale is h, or sh for the small avatar: the dump's spritesheets carry an
# sh_ frame beside most h_ ones, and it must not be read as its h_ twin.
SPRITE = re.compile(r'(?<![^_])((s?h)_[a-z]+_)([a-z]+)_(\d+)(_\d+_\d+)$')


def log(*args):
    print(*args, file=sys.stderr)


def gender_of(library):
    for token in library.split('_')[1:-1]:
        if token.upper() in ('M', 'F', 'U'):
            return token.upper()
    return 'U'


def base_of(library):
    bits = library.split('_')
    return '_'.join(b.lower() for b in bits if b.upper() not in ('M', 'F', 'U'))


def part_key(t, i):
    return (t, str(i))


def read_bundle(path):
    """(entries, json key, asset data, {part: [sprite fingerprints]}) or None."""
    try:
        entries = bundle_entries(path)
        key = next(k for k in entries if k.endswith('.json'))
        data = json.loads(inflate(entries[key]))
        png = next((v for n, v in entries.items() if n.endswith('.png')), None)
        frames = (data.get('spritesheet') or {}).get('frames') or {}
        image = Image.open(io.BytesIO(inflate(png))).convert('RGBA') if png and frames else None
    except Exception as ex:                    # a truncated bundle (hair_U_danpon)
        log('  unreadable %s: %s' % (os.path.basename(path), ex))
        return None
    prints = collections.defaultdict(list)
    for name, frame in frames.items():
        m = SPRITE.search(name)
        if not m or m.group(2) != 'h' or image is None:
            continue
        r = frame['frame']
        crop = image.crop((r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h']))
        if crop.getbbox() is None or r['w'] * r['h'] < 25:
            continue                           # blank or a few pixels: matches everything
        digest = hashlib.md5(crop.tobytes() + str(crop.size).encode()).hexdigest()[:16]
        prints[(m.group(3), m.group(4))].append(m.group(1) + m.group(5) + ':' + digest)
    return entries, key, data, prints


def drawn_parts(data):
    return {(m.group(3), m.group(4)) for m in map(SPRITE.match, data.get('assets') or {}) if m and m.group(2) == 'h'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True, help='the dump root (bundled/figure, gamedata/)')
    ap.add_argument('--habbo-figuremap', required=True)
    ap.add_argument('--migration', type=int)
    ap.add_argument('--list', action='store_true', help='report what would be imported and stop')
    args = ap.parse_args()

    src_dir = os.path.join(args.source, 'bundled', 'figure')
    src_bundles = {f[:-6]: os.path.join(src_dir, f) for f in os.listdir(src_dir) if f.endswith('.nitro')}
    merged = collections.OrderedDict()
    for lib in json.load(open(os.path.join(args.source, 'gamedata', 'FigureMap.json')))['libraries']:
        parts = merged.setdefault(lib['id'], [])
        parts.extend(k for k in (part_key(p['type'], p['id']) for p in lib.get('parts', []) if p.get('id') is not None)
                     if k not in parts)
    src_map = list(merged.items())
    owner = {}                                 # part -> the library the dump loads it from
    for lib, parts in src_map:
        for k in parts:
            owner.setdefault(k, lib)
    src_sets = [dict(s, type=t['type'])
                for t in json.load(open(os.path.join(args.source, 'gamedata', 'FigureData.json')))['setTypes']
                for s in t['sets']]

    # what an earlier run imported keeps its ids, and is not the hotel's own
    prior_sets, prior_parts, prior_libs = {}, {}, set()
    if os.path.exists(IDS_CSV):
        for row in csv.DictReader(open(IDS_CSV)):
            prior_libs.add(row['library'])
            if row['kind'] == 'set':
                prior_sets[(row['type'], row['pack_id'], row['library'])] = int(row['hotel_id'])
            else:
                prior_parts[(row['type'], row['pack_id'])] = int(row['hotel_id'])
    ours = {str(i) for i in prior_sets.values()}
    wulez = {(r['library'].lower(), r['type'], r['pack_id']): r['hotel_id']
             for r in csv.DictReader(open(WULEZ_IDS)) if r['kind'] == 'part'}

    # the hotel: Habbo's map, then everything nitro/overrides adds
    hotel_lib_parts = collections.defaultdict(set)
    for lib in ET.parse(args.habbo_figuremap).getroot().findall('lib'):
        hotel_lib_parts[lib.get('id').lower()].update(part_key(p.get('type'), p.get('id')) for p in lib.findall('part'))
    for lib in json.load(open(MAP_FRAGMENT))['libraries']:
        if lib['id'] in prior_libs:
            continue
        hotel_lib_parts[lib['id'].lower()].update(part_key(p['type'], p['id']) for p in lib.get('parts', []))
    hotel_libs = set(hotel_lib_parts)
    hotel_libs.update(f[:-6].lower() for f in os.listdir(FIGURE_DIR)
                      if f.endswith('.nitro') and f[:-6] not in prior_libs)
    hotel_parts = {k for parts in hotel_lib_parts.values() for k in parts}
    hotel_xml = ET.parse(FIGUREDATA_XML).getroot()
    hotel_set_ids = {s.get('id') for s in hotel_xml.iter('set') if s.get('id') not in ours}

    # 1. candidates
    skipped = []
    mapped = {lib for lib, _ in src_map}
    effects = {e['lib'] for e in json.load(open(os.path.join(args.source, 'gamedata', 'EffectMap.json')))['effects']}
    for lib in sorted(set(src_bundles) - mapped):
        if lib.lower() not in hotel_libs:
            skipped.append((lib, 'avatar effect' if lib in effects else 'not in the dump\'s FigureMap'))
    candidates = []
    for lib, parts in src_map:
        if lib.lower() in hotel_libs and lib not in prior_libs:
            continue
        if lib.lower().startswith('hh_'):
            skipped.append((lib, 'the dump\'s base library'))
        elif not parts:
            skipped.append((lib, 'no parts in the FigureMap'))
        elif lib not in src_bundles:
            skipped.append((lib, 'no bundle'))
        else:
            candidates.append((lib, parts))

    # 2. fingerprints of everything the hotel draws: the dump's copies of the
    # hotel's libraries, and every bundle in nitro/overrides
    index = collections.defaultdict(set)
    for lib, path in src_bundles.items():
        if lib.lower() in hotel_libs and lib not in prior_libs:
            got = read_bundle(path)
            for k, prints in (got[3].items() if got else ()):
                for p in prints:
                    index[p].add((lib.lower(), k))
    for f in os.listdir(FIGURE_DIR):
        if f.endswith('.nitro') and f[:-6] not in prior_libs:
            got = read_bundle(os.path.join(FIGURE_DIR, f))
            for k, prints in (got[3].items() if got else ()):
                for p in prints:
                    index[p].add((f[:-6].lower(), k))

    def hotel_id(hotel_lib, k):
        """the id the hotel draws the dump's part k of hotel_lib under, or None"""
        if k in hotel_lib_parts.get(hotel_lib, ()):
            return k[1]
        return wulez.get((hotel_lib, k[0], k[1]))

    def copy_of(k, prints):
        """the hotel id of the part k is a pixel copy of, same part type, or None"""
        if not prints:
            return None
        votes = collections.Counter(hit for p in prints for hit in index.get(p, ()))
        for (hotel_lib, hit), n in votes.most_common(3):
            if n < COPY_SHARE * len(prints):
                break
            if hit[0] == k[0] and hotel_id(hotel_lib, hit):
                return hotel_id(hotel_lib, hit)
        return None

    # 3. claims, copies. A library whose every main part with pixels of its
    # own is a copy is skipped; one that only partly is, is checked set by set
    claims, bundles, lib_parts, copies = {}, {}, {}, {}
    for lib, parts in candidates:
        got = read_bundle(src_bundles[lib])
        if not got:
            skipped.append((lib, 'bundle unreadable'))
            continue
        entries, key, data, prints = got
        drawn = drawn_parts(data)
        mine = [k for k in parts if k in drawn and k not in claims]
        if not mine:
            taken = [k for k in parts if k in drawn]
            skipped.append((lib, 'same parts as %s' % claims[taken[0]] if taken else 'bundle draws none of its parts'))
            continue
        for k in mine:
            target = copy_of(k, prints.get(k))
            if target:
                copies[k] = target
        main_parts = [k for k in mine if k[0] not in SECONDARY and prints.get(k)] or \
                     [k for k in mine if prints.get(k)]
        # a library an earlier run imported stays: it is on the shelf, and
        # someone may own it
        if lib not in prior_libs and main_parts and all(k in copies for k in main_parts):
            skipped.append((lib, 'copy of %s-%s' % (main_parts[0][0], copies[main_parts[0]])))
            continue
        for k in mine:
            claims[k] = lib
        bundles[lib] = (entries, key, data)
        lib_parts[lib] = mine

    # 4. resolve every part a set lists, the way the dump resolved it
    src_drawn = {}

    def dump_draws(lib, k):
        if lib not in src_drawn:
            got = read_bundle(src_bundles[lib]) if lib in src_bundles else None
            src_drawn[lib] = drawn_parts(got[2]) if got else set()
        return k in src_drawn[lib]

    def resolve(k):
        """('claim', k) | ('keep', id) | NOTHING (drew nothing in the dump either) | None"""
        if k in claims:
            return ('claim', k)
        lib = owner.get(k)
        if lib is None or not dump_draws(lib, k):
            return NOTHING
        if lib.lower().startswith('hh_'):      # the dump's base body; the hotel has its own
            return ('keep', k[1]) if k in hotel_parts else None
        if lib.lower() in hotel_libs:
            if k in hotel_lib_parts.get(lib.lower(), ()):
                return ('keep', k[1])
            if (lib.lower(), k[0], k[1]) in wulez:
                return ('keep', wulez[(lib.lower(), k[0], k[1])])
            return None
        if k in copies:
            return ('keep', copies[k])
        return None

    resolved, dropped, seen, unresolved = [], collections.Counter(), set(), []
    for s in src_sets:
        if s['type'] not in SET_TYPE_ORDER:
            continue
        keys = [part_key(p['type'], p['id']) for p in s['parts']]
        if not any(k in claims for k in keys):
            continue
        parts, ok, have = [], True, set()
        for p, k in zip(s['parts'], keys):
            r = resolve(k)
            if r is NOTHING:
                continue                       # the set looks as it did in the dump
            if r is None:
                if p['type'] in SECONDARY:
                    continue
                ok = False
                break
            target = r if r[0] == 'claim' else ('keep', (k[0], str(r[1])))
            if target in have:
                continue                       # FigureDataManager keys a set's parts on id-type
            have.add(target)
            parts.append(dict(p, resolved=r))
        if ok and not any(p['resolved'][0] == 'claim' for p in parts):
            ok = False
        claimed = [p['resolved'][1] for p in parts if p['resolved'][0] == 'claim']
        main_claimed = [k for k in claimed if k[0] not in SECONDARY] or claimed
        imported = any(key[:2] == (s['type'], str(s['id'])) for key in prior_sets)
        if ok and not imported and main_claimed and all(k in copies for k in main_claimed):
            dropped['copy of a hotel garment'] += 1
            continue
        if not ok:
            dropped['a part that resolves to nothing'] += 1
            unresolved.append((s['type'], s['id'], k, owner.get(k)))
            continue
        shape = (s['type'], tuple(sorted(str(p['resolved']) for p in parts)))
        if shape in seen:
            dropped['duplicate of another dump set'] += 1
            continue
        seen.add(shape)
        owners = collections.Counter(claims[p['resolved'][1]] for p in parts if p['resolved'][0] == 'claim')
        top = max(owners.values())
        library = next(claims[p['resolved'][1]] for p in parts
                       if p['resolved'][0] == 'claim' and owners[claims[p['resolved'][1]]] == top)
        resolved.append(dict(s, parts=parts, library=library))

    used = {p['resolved'][1] for s in resolved for p in s['parts'] if p['resolved'][0] == 'claim'}
    libraries = [lib for lib, _ in candidates if lib in bundles and any(k in used for k in lib_parts[lib])]
    for lib in bundles:
        if lib not in libraries:
            skipped.append((lib, 'no dump set wears it'))

    def report():
        log('libraries: %d to import, %d skipped' % (len(libraries), len(skipped)))
        for why, n in collections.Counter(re.sub(r'^(copy of|same parts as) .*', r'\1 ...', w)
                                          for _, w in skipped).most_common():
            log('  skipped %5d  %s' % (n, why))
        log('sets: %d; dropped %s' % (len(resolved), dict(dropped)))
        log('by category / gender:')
        grid = collections.Counter((CATEGORY[s['type']], s['type'], gender_of(s['library'])) for s in resolved)
        for (cat, t) in sorted({(c, t) for c, t, _ in grid}, key=lambda x: SET_TYPE_ORDER.index(x[1])):
            log('  %-5s %-3s M %4d  F %4d  U %4d' % (cat, t, grid[(cat, t, 'M')], grid[(cat, t, 'F')], grid[(cat, t, 'U')]))

    if args.list:
        report()
        for lib, why in sorted(skipped, key=lambda x: (x[1], x[0].lower())):
            print('skip\t%s\t%s' % (lib, why))
        for u in unresolved:
            print('drop\t%s-%s\t%s-%s from %s' % (u[0], u[1], u[2][0], u[2][1], u[3]))
        for lib in libraries:
            print('take\t%s\t%s' % (lib, ' '.join('%s-%s' % k for k in lib_parts[lib] if k in used)))
        return

    # 5. ids
    part_ids = {k: prior_parts[k] for k in used if k in prior_parts}
    next_part = max(list(prior_parts.values()) + [FIRST_PART - 1]) + 1
    for k in sorted(used - set(part_ids), key=lambda k: (k[0], int(k[1]))):
        part_ids[k] = next_part
        next_part += 1
    resolved.sort(key=lambda s: (SET_TYPE_ORDER.index(s['type']), int(s['id'])))
    next_set = max(list(prior_sets.values()) + [FIRST_SET - 1]) + 1
    for s in resolved:
        key = (s['type'], str(s['id']), s['library'])
        if key in prior_sets:
            s['new_id'] = prior_sets[key]
        else:
            s['new_id'] = next_set
            next_set += 1
        assert str(s['new_id']) not in hotel_set_ids
    added = [s for s in resolved if (s['type'], str(s['id']), s['library']) not in prior_sets]
    assert len({s['new_id'] for s in resolved}) == len(resolved)
    assert not any((t, str(i)) in hotel_parts for (t, _), i in part_ids.items())

    def new_part(p):
        r = p['resolved']
        return part_ids[r[1]] if r[0] == 'claim' else int(r[1])

    # 6. bundles: kept parts renamed, every other sprite removed
    os.makedirs(FIGURE_DIR, exist_ok=True)
    map_entries, strays = [], 0
    for lib in libraries:
        entries, key, data = bundles[lib]
        mine = {k for k in lib_parts[lib] if k in used}

        def rename(name):
            m = SPRITE.search(name)
            if not m:
                return name
            k = (m.group(3), m.group(4))
            if k not in mine:
                return None
            return name[:m.start()] + '%s%s_%d%s' % (m.group(1), m.group(3), part_ids[k], m.group(5))

        # a kept alias can draw another part's sprite; when that part is not
        # kept, its sprite stays under a name no avatar looks up
        private = {}
        for name, asset in data['assets'].items():
            source = asset.get('source')
            if rename(name) is not None and source and rename(source) is None:
                private[source] = 'pxrp_' + source

        def final(name):
            return private.get(name) or rename(name)

        assets = {}
        for name, asset in data['assets'].items():
            new = final(name)
            if new is None:
                strays += 1
                continue
            asset = dict(asset)
            if 'source' in asset:
                asset['source'] = final(asset['source'])
            assets[new] = asset
        data['assets'] = assets
        sheet = data.get('spritesheet') or {}
        if 'frames' in sheet:
            frames = {}
            # textures are found as <the bundle's name>_<asset>, and the
            # bundle takes its file's name below; a few bundles' frames still
            # carry the library they were copied from (hat_U_lion's say
            # hat_U_panda_), which drew nothing in the dump
            for name, frame in sheet['frames'].items():
                m = SPRITE.search(name)
                bare = name[m.start():] if m else name.split('_', len((data.get('name') or lib).split('_')))[-1]
                bare = private.get(bare) or rename(bare)
                if bare is not None:
                    frames[lib + '_' + bare] = frame
            sheet['frames'] = frames
        data['name'] = lib
        if sheet.get('meta'):
            sheet['meta']['image'] = lib + '.png'
        png = next(blob for name, blob in entries.items() if name.endswith('.png'))
        write_bundle(os.path.join(FIGURE_DIR, lib + '.nitro'),
                     {lib + '.json': json.dumps(data, separators=(',', ':')).encode(), lib + '.png': png})
        map_entries.append({'id': lib, 'revision': 0,
                            'parts': [{'id': part_ids[k], 'type': k[0]} for k in lib_parts[lib] if k in mine]})

    # 7. FigureMap fragment
    fm = json.load(open(MAP_FRAGMENT))
    have = {lib['id'] for lib in fm['libraries']}
    fm['libraries'].extend(e for e in map_entries if e['id'] not in have)
    with open(MAP_FRAGMENT, 'w') as fh:
        json.dump(fm, fh, indent=1)

    # 8. FigureData fragment + figuredata.xml
    def json_set(s):
        out = {'id': s['new_id'], 'gender': gender_of(s['library']), 'club': 0,
               'colorable': bool(s.get('colorable')), 'selectable': True, 'preselectable': False,
               'sellable': True,
               'parts': [{'id': new_part(p), 'type': p['type'], 'colorable': bool(p.get('colorable')),
                          'index': int(p.get('index', 0)), 'colorindex': int(p.get('colorindex', 0))}
                         for p in s['parts']]}
        hidden = [h['partType'] for h in s.get('hiddenLayers') or [] if h.get('partType')]
        if hidden:
            out['hiddenLayers'] = [{'partType': t} for t in hidden]
        return out

    fd = json.load(open(DATA_FRAGMENT))
    by_type = {t['type']: t for t in fd['setTypes']}
    for s in resolved:
        st = by_type.get(s['type'])
        if st is None:
            st = by_type[s['type']] = {'type': s['type'], 'sets': []}
            fd['setTypes'].append(st)
        if all(x['id'] != s['new_id'] for x in st['sets']):
            st['sets'].append(json_set(s))
    with open(DATA_FRAGMENT, 'w') as fh:
        json.dump(fd, fh, indent=1)

    xml = open(FIGUREDATA_XML).read()
    for set_type in SET_TYPE_ORDER:
        lines = []
        for s in resolved:
            if s['type'] != set_type or ('<set id="%d"' % s['new_id']) in xml:
                continue
            j = json_set(s)
            lines.append('<set id="%d" gender="%s" club="0" colorable="%d" selectable="1" preselectable="0">'
                         % (j['id'], j['gender'], j['colorable']))
            for p in j['parts']:
                lines.append('<part id="%d" type="%s" colorable="%d" index="%d" colorindex="%d"/>'
                             % (p['id'], p['type'], p['colorable'], p['index'], p['colorindex']))
            lines.append('</set>')
        if not lines:
            continue
        opening = xml.index('<settype type="%s"' % set_type)
        closing = xml.index('</settype>', opening)
        xml = xml[:closing] + '\n'.join(lines) + '\n' + xml[closing:]
    with open(FIGUREDATA_XML, 'w') as fh:
        fh.write(xml)

    # 9. the shelf
    rows = collections.OrderedDict()
    for s in resolved:
        rows.setdefault((s['type'], base_of(s['library'])), []).append(s)
    # a male and a female library of one garment share a row; a library
    # holding several different pieces (bsstonino_U_accessorio3 is eighteen
    # head accessories) is one row per piece, <library>_2 and on
    shelf, names = [], set()
    for (set_type, _), sets in rows.items():
        by_lib = collections.OrderedDict()
        for s in sets:
            by_lib.setdefault(s['library'], []).append(s)
        for n in range(max(len(v) for v in by_lib.values())):
            piece = [v[n] for v in by_lib.values() if n < len(v)]
            if not any(s in added for s in piece):
                continue                       # on the shelf since an earlier migration
            name = ','.join(s['library'] for s in piece)
            # a library drawing two set types (acc_eye_U_passionateface: ea
            # and fa) is two rows; the migration skips a row by name
            suffix = n + 1
            while suffix > 1 and name + '_%d' % suffix in names or suffix == 1 and name in names:
                suffix += 1
            name += '_%d' % suffix if suffix > 1 else ''
            names.add(name)
            shelf.append((name, ','.join(str(s['new_id']) for s in piece),
                          0 if set_type in OWNED_ONLY_TYPES else PRICE))
    assert all(len(parts) <= 85 for _, parts, _ in shelf)  # catalog_clothing.clothing_parts

    os.makedirs(os.path.dirname(IDS_CSV), exist_ok=True)
    with open(IDS_CSV, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['kind', 'library', 'type', 'pack_id', 'hotel_id'])
        for s in resolved:
            w.writerow(['set', s['library'], s['type'], s['id'], s['new_id']])
        for lib in libraries:
            for k in lib_parts[lib]:
                if k in used:
                    w.writerow(['part', lib, k[0], k[1], part_ids[k]])

    if args.migration:
        path = os.path.join(UPDATES, '%d_ClothingHabzone.sql' % args.migration)
        with open(path, 'w') as fh:
            fh.write(migration(shelf, len(libraries), len(resolved), bool(prior_sets)))
        log('wrote', path)

    report()
    log('parts: %d renumbered; %d stray sprites removed' % (len(part_ids), strays))
    log('shelf rows: %d (%d at %d credits, %d owned-only)' % (
        len(shelf), sum(1 for r in shelf if r[2]), PRICE, sum(1 for r in shelf if not r[2])))


def migration(shelf, libraries, sets, rerun):
    head = '''-- pixelrp: custom clothing from the Habzone asset dump (habzone.lol, March
-- 2024) that the hotel did not have: %d libraries, %d figure sets. Bundles,
-- FigureMap and FigureData ship in nitro/overrides and
-- emulator/Config/figuredata.xml; this is the shelf.
--
-- Generated by docker/nitro/import-habzone-clothes.py, which documents what
-- was taken and why. Set and part ids are renumbered into their own block
-- from 400000 (docker/nitro/habzone-clothes/ids.csv maps them back).
--
-- Same rules as 262: gender follows the library's file name, a garment
-- shipping as a male and a female library is one row, rows are named after
-- their libraries, 50 credits, faces 0 and owned-only. A row whose name or
-- first set some row already has is left alone.''' % (libraries, sets)
    if rerun:
        head = '''-- pixelrp: more of the Habzone clothing (see the first ClothingHabzone
-- migration), added by a later run of docker/nitro/import-habzone-clothes.py.
-- Sets already imported keep their ids; these take the next ones in the block.'''
    out = [head]
    for start in range(0, len(shelf), 200):
        chunk = shelf[start:start + 200]
        selects = []
        for n, (name, parts, price) in enumerate(chunk):
            if n == 0:
                selects.append("  SELECT '%s' AS `clothing_name`, '%s' AS `clothing_parts`, %d AS `price`"
                               % (name, parts, price))
            else:
                selects.append("  SELECT '%s', '%s', %d" % (name, parts, price))
        out.append('''INSERT INTO `catalog_clothing` (`clothing_name`, `clothing_parts`, `price`)
SELECT n.`clothing_name`, n.`clothing_parts`, n.`price`
  FROM (
%s
  ) n
 WHERE NOT EXISTS (SELECT 1 FROM `catalog_clothing` c
                    WHERE c.`clothing_name` = n.`clothing_name`
                       OR FIND_IN_SET(SUBSTRING_INDEX(n.`clothing_parts`, ',', 1), c.`clothing_parts`) > 0);''' % '\n  UNION ALL\n'.join(selects))
    return '\n\n'.join(out) + '\n'


if __name__ == '__main__':
    main()
