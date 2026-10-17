#!/usr/bin/env python3
"""Import the Wulez custom clothing pack (github.com/Wulles/Wuco) into the hotel.

The pack is a Flash-era clothing folder from Brazilian retros (HabboCity and
others, last updated 2021-01-05): 1,891 figure SWFs, a figuremap.xml and an
Arcturus figuredata.xml. About half of it is Habbo's own libraries, which the
hotel already has. This takes the rest and writes all five things a garment
needs (nitro/overrides/README.md, "Avatar libraries"):

  1. nitro/overrides/bundled/figure/<library>.nitro
  2. nitro/overrides/gamedata-merge/FigureMap.json    (libraries appended)
  3. nitro/overrides/gamedata-merge/FigureData.json   (sets appended)
  4. emulator/Config/figuredata.xml                   (the same sets)
  5. emulator/Resources/SQLs/Updates/<n>_ClothingWulez.sql (the shelf)

plus docker/nitro/wulez-clothes/ids.csv, the old -> new id of every set and
part, so a set can still be traced back to the pack.

Which libraries
---------------
A library is imported when the hotel does not have it by name (Habbo's
figuremap as converted on 2026-08-07, build 202608061512, plus the libraries
nitro/overrides adds) and it is not a copy of a Habbo item: any part it shares
with a library Habbo already had when the pack was made (Habbo's 2020-12-29
figuremap, shipped in the same repo under "Habbo Clothes") marks it a copy -
acc_face_U_beard5 is acc_face_U_beard1 under a new name. The pack's own base
libraries (hh_human_*) replace Habbo's and are never taken. A library whose
SWF did not convert to any sprite is reported and skipped.

Renumbering
-----------
Every imported set and part gets a new id. The pack's ids were picked by
retros in 2020, and Habbo has since released items on some of the same
numbers (shirt_U_rainbowstarjump01 draws ch 7590, which is Habbo's
shirt_M_tentacledress now) - and will keep releasing upwards from ~7,700, into
the rest of them. Sets and parts move to their own block, from
FIRST_SET / FIRST_PART, far above anything Habbo will reach and clear of the
handful of large custom ids the hotel already has (19792140 and up). Part ids
are renamed inside each bundle too (asset keys, alias sources, spritesheet
frames: h_std_ch_7737_0_0 -> h_std_ch_300123_0_0), since the client finds a
sprite by part id.

A pack part is claimed by the first imported library, in figuremap order,
whose bundle actually draws it; a second library listing the same part (the
pack has a few duplicated hairs) does not get it.

Sets
----
Every pack set that draws at least one claimed part is imported. Each of its
parts must resolve - to a claimed part (renumbered) or to a part the hotel
already has (kept, e.g. a custom shirt on Habbo's sleeves). A sleeve, hand or
hair-back part (ls/rs/lc/rc/hrb) nothing draws is dropped, as the client would
draw nothing for it anyway; any other unresolvable part drops the set. A set
identical to one already imported (same type, same parts) is not added twice,
and a part a set lists twice is kept once - the emulator keys a set's parts on
id-type with Dictionary.Add, so a repeat would stop it starting.

The rules are the hotel's, not the pack's:
  - gender comes from the library's file name: shirt_M_x is M, shirt_F_x is
    F, and _U_ or no gender token at all (wibbo_dbz_jacket_1) is unisex;
  - club 0, selectable, not preselectable, sellable - owned-only until bought,
    like every set on the shelf;
  - hidden layers are kept.

The shelf
---------
One catalog_clothing row per garment, named after its library like every row
since 260. A garment that ships as a male and a female library
(shirt_M_x / shirt_F_x) is one row holding both sets, as 74 and 156 do; a
library drawing several sets of one type is one row too. Everything is 50
credits, except faces (set type hd), which the store has no shelf for: those
are priced 0, owned-only, like 257's.

Usage:
  python3 docker/nitro/import-wulez-clothes.py \\
      --wuco <Wuco checkout> --bundles <converted .nitro dir> \\
      --habbo-figuremap fm_0806.xml --migration 262

The bundles come from billsonnn/nitro-converter --convert-swf over the
selected SWFs (docker/nitro/README.md). Run --list first to get that list.
Twelve of the pack's SWFs have a broken document class and convert to empty
bundles until it is rewritten (see docker/nitro/wulez-clothes/README.md).

Re-running regenerates every output from scratch (ids are deterministic) but
only ever APPENDS to the gamedata fragments and figuredata.xml if the set ids
are not there yet. The migration file follows sql-updates-by-filename: once
it has run anywhere, a change goes in a new number.
"""
import argparse
import collections
import csv
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from furni_bundle import bundle_entries, inflate, write_bundle  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
FIGURE_DIR = os.path.join(REPO, 'nitro', 'overrides', 'bundled', 'figure')
MAP_FRAGMENT = os.path.join(REPO, 'nitro', 'overrides', 'gamedata-merge', 'FigureMap.json')
DATA_FRAGMENT = os.path.join(REPO, 'nitro', 'overrides', 'gamedata-merge', 'FigureData.json')
FIGUREDATA_XML = os.path.join(REPO, 'emulator', 'Config', 'figuredata.xml')
UPDATES = os.path.join(REPO, 'emulator', 'Resources', 'SQLs', 'Updates')
IDS_CSV = os.path.join(REPO, 'docker', 'nitro', 'wulez-clothes', 'ids.csv')

FIRST_SET = 300000
FIRST_PART = 300000
PRICE = 50
OWNED_ONLY_TYPES = {'hd'}
SECONDARY = {'ls', 'rs', 'lc', 'rc', 'hrb'}
SET_TYPE_ORDER = ['hr', 'hd', 'ch', 'lg', 'sh', 'ha', 'he', 'ea', 'fa', 'ca', 'wa', 'cc', 'cp']

# h_<action>_<part type>_<part id>_<direction>_<frame>, optionally behind the
# library's own name (spritesheet frames are <library>_h_std_...)
SPRITE = re.compile(r'(h_[a-z]+_)([a-z]+)_(\d+)(_\d+_\d+)$')

WULEZ = os.path.join('Wulez Clothes')
HABBO_2020 = os.path.join('Habbo Clothes', 'gordon', 'PRODUCTION-202012291112-442539729', 'figuremap.xml')


def log(*args):
    print(*args, file=sys.stderr)


def xml_map(path):
    return [(lib.get('id'), [(p.get('type'), p.get('id')) for p in lib.findall('part')])
            for lib in ET.parse(path).getroot().findall('lib')]


def gender_of(library):
    for token in library.split('_')[1:-1]:
        if token.upper() in ('M', 'F', 'U'):
            return token.upper()
    return 'U'


def base_of(library):
    bits = library.split('_')
    return '_'.join(b.lower() for b in bits if b.upper() not in ('M', 'F', 'U'))


def bundle_json(path):
    entries = bundle_entries(path)
    key = next((k for k in entries if k.endswith('.json')), None)
    return entries, key, (json.loads(inflate(entries[key])) if key else {})


def drawn_parts(asset_data):
    out = set()
    for name in (asset_data.get('assets') or {}):
        m = SPRITE.match(name)
        if m:
            out.add((m.group(2), m.group(3)))
    return out


def load_sets(path):
    out = []
    for set_type in ET.parse(path).getroot().iter('settype'):
        for s in set_type.findall('set'):
            hidden = [layer.get('parttype') for layer in s.iter('layer')]
            out.append({'type': set_type.get('type'), 'id': s.get('id'), 'attrs': dict(s.attrib),
                        'parts': [dict(p.attrib) for p in s.findall('part')], 'hidden': hidden})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--wuco', required=True)
    ap.add_argument('--bundles')
    ap.add_argument('--habbo-figuremap', required=True)
    ap.add_argument('--migration', type=int)
    ap.add_argument('--list', action='store_true', help='print the libraries to convert and stop')
    args = ap.parse_args()

    gordon = os.path.join(args.wuco, WULEZ, 'gordon', 'PRODUCTION-WULEZ')
    # the pack's figuremap lists a few libraries twice; one entry each
    merged = collections.OrderedDict()
    for lib, parts in xml_map(os.path.join(gordon, 'figuremap.xml')):
        merged.setdefault(lib, []).extend(p for p in parts if p not in merged.get(lib, []))
    pack_map = list(merged.items())
    pack_sets = load_sets(os.path.join(args.wuco, WULEZ, 'gamedata', 'figuredata.xml'))

    hotel_libs = {lib.lower() for lib, _ in xml_map(args.habbo_figuremap)}
    hotel_parts = {p for _, parts in xml_map(args.habbo_figuremap) for p in parts}
    for lib in json.load(open(MAP_FRAGMENT))['libraries']:
        hotel_libs.add(lib['id'].lower())
        hotel_parts.update((p['type'], str(p['id'])) for p in lib.get('parts', []))
    hotel_xml = ET.parse(FIGUREDATA_XML).getroot()
    hotel_parts.update((p.get('type'), p.get('id')) for p in hotel_xml.iter('part'))
    hotel_set_ids = {s.get('id') for s in hotel_xml.iter('set')}
    habbo_2020 = {p for _, parts in xml_map(os.path.join(args.wuco, HABBO_2020)) for p in parts}

    # 1. libraries
    chosen, skipped = [], []
    for lib, parts in pack_map:
        if lib.lower() in hotel_libs:
            continue
        if lib.lower().startswith('hh_'):
            skipped.append((lib, 'pack base library'))
        elif not parts:
            skipped.append((lib, 'no parts in the figuremap'))
        elif any(p in habbo_2020 and p in hotel_parts for p in parts):
            skipped.append((lib, 'copy of a Habbo library'))
        else:
            chosen.append((lib, parts))
    if args.list:
        print('\n'.join(lib for lib, _ in chosen))
        return

    # 2. claims: which library draws each pack part
    claims, bundles, lib_parts = {}, {}, {}
    for lib, parts in chosen:
        path = os.path.join(args.bundles, lib + '.nitro')
        if not os.path.exists(path):
            skipped.append((lib, 'SWF did not convert'))
            continue
        entries, key, data = bundle_json(path)
        drawn = drawn_parts(data)
        if not drawn:
            skipped.append((lib, 'bundle draws nothing'))
            continue
        bundles[lib] = (entries, key, data)
        mine = []
        for p in parts:
            if p in drawn and p not in claims and p not in mine:
                claims[p] = lib
                mine.append(p)
        lib_parts[lib] = mine

    # 3. sets
    resolved, dropped, seen = [], collections.Counter(), set()
    for s in pack_sets:
        if s['type'] not in SET_TYPE_ORDER:
            dropped['set type the hotel does not have'] += 1
            continue
        keys = [(p['type'], p['id']) for p in s['parts']]
        if not any(k in claims for k in keys):
            continue
        parts, ok = [], True
        for p, k in zip(s['parts'], keys):
            if k in [(q['type'], q['id']) for q in parts]:
                continue                       # FigureDataManager keys a set's parts on id-type
            if k in claims or k in hotel_parts:
                parts.append(p)
            elif p['type'] in SECONDARY:
                continue
            else:
                ok = False
                break
        if not ok:
            dropped['a part nothing draws'] += 1
            continue
        shape = (s['type'], tuple(sorted((p['type'], p['id']) for p in parts)))
        if shape in seen:
            dropped['duplicate of another pack set'] += 1
            continue
        seen.add(shape)
        owners = collections.Counter(claims[(p['type'], p['id'])] for p in parts if (p['type'], p['id']) in claims)
        top = max(owners.values())
        library = next(lib for lib in (claims[(p['type'], p['id'])] for p in parts if (p['type'], p['id']) in claims)
                       if owners[lib] == top)
        resolved.append(dict(s, parts=parts, library=library))

    # 4. ids: parts used by an imported set, then sets, all deterministic
    used = {(p['type'], p['id']) for s in resolved for p in s['parts'] if (p['type'], p['id']) in claims}
    part_ids = {}
    for old in sorted({i for _, i in used}, key=int):
        part_ids[old] = FIRST_PART + len(part_ids)
    resolved.sort(key=lambda s: (SET_TYPE_ORDER.index(s['type']), int(s['id'])))
    for n, s in enumerate(resolved):
        s['new_id'] = FIRST_SET + n
        assert str(s['new_id']) not in hotel_set_ids

    def new_part(p):
        k = (p['type'], p['id'])
        return part_ids[p['id']] if k in claims else int(p['id'])

    # every library drawing a part some set wears - not only each set's own
    # (a pack shirt can wear another pack library's sleeves)
    order = [lib for lib, _ in chosen]
    libraries = sorted({claims[k] for k in used}, key=order.index)
    unused = [lib for lib in bundles if lib not in libraries]
    for lib in unused:
        skipped.append((lib, 'no pack set draws it'))

    # 5. bundles
    os.makedirs(FIGURE_DIR, exist_ok=True)
    map_entries = []
    for lib in libraries:
        entries, key, data = bundles[lib]
        mine = {k for k in lib_parts[lib] if k in used}

        def rename(name):
            m = SPRITE.search(name)
            if not m or (m.group(2), m.group(3)) not in mine:
                return name
            return name[:m.start()] + '%s%s_%d%s' % (m.group(1), m.group(2), part_ids[m.group(3)], m.group(4))

        assets = {}
        for name, asset in data['assets'].items():
            asset = dict(asset)
            if 'source' in asset:
                asset['source'] = rename(asset['source'])
            assets[rename(name)] = asset
        data['assets'] = assets
        sheet = data.get('spritesheet') or {}
        if 'frames' in sheet:
            sheet['frames'] = {rename(name): frame for name, frame in sheet['frames'].items()}
        # a few SWFs carried another document class; the bundle is the file's
        data['name'] = lib
        if sheet.get('meta'):
            sheet['meta']['image'] = lib + '.png'
        png = next(blob for name, blob in entries.items() if name.endswith('.png'))
        write_bundle(os.path.join(FIGURE_DIR, lib + '.nitro'),
                     {lib + '.json': json.dumps(data, separators=(',', ':')).encode(), lib + '.png': png})
        map_entries.append({'id': lib, 'revision': 0,
                            'parts': [{'id': part_ids[i], 'type': t} for t, i in lib_parts[lib] if (t, i) in mine]})

    # 6. FigureMap fragment
    fm = json.load(open(MAP_FRAGMENT))
    have = {lib['id'] for lib in fm['libraries']}
    fm['libraries'].extend(e for e in map_entries if e['id'] not in have)
    with open(MAP_FRAGMENT, 'w') as fh:
        json.dump(fm, fh, indent=1)

    # 7. FigureData fragment + figuredata.xml
    def json_set(s):
        out = {'id': s['new_id'], 'gender': gender_of(s['library']), 'club': 0,
               'colorable': s['attrs'].get('colorable') == '1', 'selectable': True, 'preselectable': False,
               'sellable': True,
               'parts': [{'id': new_part(p), 'type': p['type'], 'colorable': p.get('colorable') == '1',
                          'index': int(p.get('index', 0)), 'colorindex': int(p.get('colorindex', 0))}
                         for p in s['parts']]}
        if s['hidden']:
            out['hiddenLayers'] = [{'partType': t} for t in s['hidden']]
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

    # 8. the shelf
    rows = collections.OrderedDict()
    for s in resolved:
        rows.setdefault((s['type'], base_of(s['library'])), []).append(s)
    shelf = []
    for (set_type, _), sets in rows.items():
        libs = list(dict.fromkeys(s['library'] for s in sets))
        shelf.append((','.join(libs), ','.join(str(s['new_id']) for s in sets),
                      0 if set_type in OWNED_ONLY_TYPES else PRICE))

    os.makedirs(os.path.dirname(IDS_CSV), exist_ok=True)
    with open(IDS_CSV, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['kind', 'library', 'type', 'pack_id', 'hotel_id'])
        for s in resolved:
            w.writerow(['set', s['library'], s['type'], s['id'], s['new_id']])
        for lib in libraries:
            for t, i in lib_parts[lib]:
                if (t, i) in used:
                    w.writerow(['part', lib, t, i, part_ids[i]])

    if args.migration:
        path = os.path.join(UPDATES, '%d_ClothingWulez.sql' % args.migration)
        with open(path, 'w') as fh:
            fh.write(migration(shelf, len(libraries), len(resolved)))
        log('wrote', path)

    log('libraries: %d imported, %d skipped' % (len(libraries), len(skipped)))
    for lib, why in skipped:
        log('  skipped %-34s %s' % (lib, why))
    log('sets: %d imported; dropped %s' % (len(resolved), dict(dropped)))
    log('parts: %d renumbered' % len(part_ids))
    log('shelf rows: %d (%d at %d credits, %d owned-only)' % (
        len(shelf), sum(1 for r in shelf if r[2]), PRICE, sum(1 for r in shelf if not r[2])))
    log('genders:', dict(collections.Counter(gender_of(s['library']) for s in resolved)))


def migration(shelf, libraries, sets):
    out = ['''-- pixelrp: the Wulez clothing pack (github.com/Wulles/Wuco, "Wulez Clothes",
-- last updated 2021-01-05) - custom clothing from Brazilian retros, HabboCity
-- first among them. %d libraries the hotel did not have, %d figure sets.
-- Bundles, FigureMap and FigureData ship in nitro/overrides and
-- emulator/Config/figuredata.xml; this is the shelf.
--
-- Generated by docker/nitro/import-wulez-clothes.py, which documents what
-- was taken and why. The pack's set and part ids are renumbered into their
-- own block from 300000 (docker/nitro/wulez-clothes/ids.csv maps them back).
--
-- The hotel's rules, not the pack's: gender follows the library's file name
-- (_M_, _F_, else unisex), a garment shipping as a male and a female library
-- is one row holding both sets, and rows are named after their libraries as
-- every row is since 260. Everything opens at 50 credits like the rest of the
-- shelf; faces are priced 0, owned-only, as the store has no face shelf
-- (257). A row whose name or first set some row already has is left alone.''' % (libraries, sets)]
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
