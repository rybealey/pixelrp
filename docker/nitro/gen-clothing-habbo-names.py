#!/usr/bin/env python3
"""Name every catalog_clothing row after its Habbo clothing library.

catalog_clothing.clothing_name grew up as a mix of furni classnames
(clothing_camotank), imported placeholders (staff_3499) and tidied library
names (shirt_U_paintoutfit, which is not a library). The library name -
shirt_M_paintoutfit, the .swf / .nitro file the set is drawn from - is the one
name HabboAssets (habboassets.com/swfs/clothing), Habbo's figuremap and our own
FigureMap all share, so it is the name to cross-reference by.

A catalog_clothing row holds figure set ids, not libraries, so the mapping is
set id -> library, resolved through the set's part ids:

  1. figuredata.xml gives each set's parts (type + part id).
  2. A figuremap gives each library's parts (type + part id). Ours is Habbo's
     figuremap as converted on 2026-08-07 (build 202608061512) plus the
     libraries nitro/overrides adds; Habbo's current figuremap fills in any
     part neither has.
  3. The set takes the library most of its parts come from, ignoring the
     shared hh_human_* base libraries unless that is all there is, and the
     other gender's library (an F set borrowing shirt_M_x's sleeves) unless
     that is all there is. A tie goes to the library whose gender token
     matches the set (shirt_F_x for an F set), then to a unisex one.
  4. Sets no figuremap places fall back to HabboAssets' own set listing for
     the library (imaging/info/clothing/<library>), when one was fetched.

Writes the migration (a set -> library table and the SQL that renames rows
from it, so it works on whatever rows the live table has) and, with
--habboassets, a CSV of every HabboAssets clothing library and whether the
hotel has it.

Inputs are downloaded, not fetched here:
  curl -o fm_0806.xml https://images.habbo.com/gordon/flash-assets-PRODUCTION-202608061512-663981953/figuremap.xml
  curl -o fm_now.xml  https://images.habbo.com/gordon/<current build>/figuremap.xml
  /api/v2/swfs/libraries?kind=clothing&per_page=200&page=N  -> library names
  /imaging/info/clothing/<library>                          -> sets per library

  python3 docker/nitro/gen-clothing-habbo-names.py \\
      --figuremap fm_0806.xml --figuremap-current fm_now.xml \\
      --habboassets names.json --ha-info info/ \\
      --sql emulator/Resources/SQLs/Updates/260_ClothingHabboNames.sql \\
      --csv docs/clothing-habboassets.csv
"""
import argparse
import collections
import csv
import json
import os
import xml.etree.ElementTree as ET

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
FIGUREDATA = os.path.join(REPO, 'emulator', 'Config', 'figuredata.xml')
OVERRIDE_MAP = os.path.join(REPO, 'nitro', 'overrides', 'gamedata-merge', 'FigureMap.json')


def xml_map(path):
    libs = {}
    for lib in ET.parse(path).getroot().findall('lib'):
        libs[lib.get('id')] = [(p.get('type'), p.get('id')) for p in lib.findall('part')]
    return libs


def json_map(path):
    return {lib['id']: [(p['type'], str(p['id'])) for p in lib.get('parts', [])]
            for lib in json.load(open(path))['libraries']}


def gender_token(library):
    bits = library.split('_')
    return bits[1].upper() if len(bits) > 2 else ''


def pick(counts, gender):
    # an F set can borrow the M library's sleeves (6307 jacket_F_nftwinter25
    # draws 5 parts from jacket_M_nftwinter25 and 2 of its own), so the other
    # gender's library only wins when there is nothing else
    other = {'M': 'F', 'F': 'M'}.get(gender)
    rank = {gender: 0, 'U': 1}
    return sorted(counts, key=lambda lib: (gender_token(lib) == other, -counts[lib],
                                           rank.get(gender_token(lib), 2), lib))[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--figuremap', required=True, help='Habbo figuremap.xml our FigureMap was converted from')
    ap.add_argument('--figuremap-current', help="Habbo's current figuremap.xml")
    ap.add_argument('--habboassets', help='JSON list of every HabboAssets clothing library name')
    ap.add_argument('--ha-info', help='directory of imaging/info/clothing/<library>.json responses')
    ap.add_argument('--sql', required=True)
    ap.add_argument('--csv')
    args = ap.parse_args()

    ours = xml_map(args.figuremap)
    ours.update(json_map(OVERRIDE_MAP))
    current = xml_map(args.figuremap_current) if args.figuremap_current else {}

    # (type, part id) -> library; our own FigureMap wins over Habbo's current one
    by_part = {}
    for libs in (current, ours):
        for lib, parts in libs.items():
            for part in parts:
                by_part[part] = lib

    ha_sets = {}   # set id -> library, from HabboAssets' listing
    if args.ha_info:
        for name in sorted(os.listdir(args.ha_info)):
            try:
                info = json.load(open(os.path.join(args.ha_info, name)))
            except ValueError:
                continue
            for rev in info.get('revisions', []):
                for s in rev.get('sets', []):
                    ha_sets.setdefault(str(s['id']), info['library'])

    sets = {}      # set id -> (type, gender, library or None, every library it draws from)
    for settype in ET.parse(FIGUREDATA).getroot().iter('settype'):
        for s in settype.findall('set'):
            counts = collections.Counter(by_part[(p.get('type'), p.get('id'))]
                                         for p in s.findall('part') if (p.get('type'), p.get('id')) in by_part)
            named = collections.Counter({k: v for k, v in counts.items() if not k.startswith('hh_')})
            lib = pick(named or counts, s.get('gender')) if counts else ha_sets.get(s.get('id'))
            sets[s.get('id')] = (settype.get('type'), s.get('gender'), lib, set(counts) | {lib} - {None})

    mapped = {sid: v[2] for sid, v in sets.items() if v[2]}
    unmapped = sorted((sid for sid, v in sets.items() if not v[2]), key=int)
    longest = max(len(lib) for lib in mapped.values())

    with open(args.sql, 'w') as out:
        out.write(HEADER.format(sets=len(sets), mapped=len(mapped), unmapped=len(unmapped),
                                unmapped_ids=', '.join(unmapped) or 'none'))
        out.write('CREATE TEMPORARY TABLE `rp_habbo_library` (\n'
                  '  `set_id` int(11) NOT NULL,\n'
                  f'  `library` varchar({max(64, longest)}) NOT NULL,\n'
                  '  PRIMARY KEY (`set_id`)\n'
                  ') ENGINE=InnoDB;\n')
        rows = sorted(mapped.items(), key=lambda kv: int(kv[0]))
        for i in range(0, len(rows), 500):
            chunk = rows[i:i + 500]
            out.write('\nINSERT INTO `rp_habbo_library` (`set_id`, `library`) VALUES\n')
            out.write(',\n'.join(f"({sid}, '{lib}')" for sid, lib in chunk))
            out.write(';\n')
        out.write(BODY)

    print(f'{len(sets)} sets, {len(mapped)} mapped, {len(unmapped)} unmapped: {" ".join(unmapped)}')
    print(f'wrote {args.sql}')

    if args.csv and args.habboassets:
        write_csv(args.csv, json.load(open(args.habboassets)), ours, current, sets, ha_sets)
        print(f'wrote {args.csv}')


def write_csv(path, ha_names, ours, current, sets, ha_sets):
    our_sets = collections.defaultdict(list)
    for sid, (_, _, _, libs) in sets.items():
        for lib in libs:
            our_sets[lib].append(sid)
    lib_sets = collections.defaultdict(set)
    for sid, lib in ha_sets.items():
        lib_sets[lib].add(sid)
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['library', 'status', 'in_our_figuremap', 'in_habbo_figuremap', 'our_set_ids', 'habboassets_set_ids'])
        for lib in sorted(ha_names, key=str.lower):
            in_ours = lib in ours
            in_now = lib in current
            ids = sorted(our_sets.get(lib, []), key=int)
            habbo_ids = sorted((s for s in lib_sets.get(lib, ()) if not s.startswith('-')), key=int)
            if in_ours and (ids or lib.startswith('hh_')):
                status = 'imported'
            elif in_ours:
                status = 'library only'
            elif ids:
                status = 'figuredata only'
            elif not in_now:
                status = 'retired'
            else:
                status = 'missing'
            w.writerow([lib, status, int(in_ours), int(in_now), ' '.join(ids), ' '.join(habbo_ids)])


HEADER = """\
-- pixelrp: every Clothing Store row named after its Habbo clothing library.
--
-- clothing_name was a mix of furni classnames (clothing_camotank), imported
-- placeholders (staff_3499) and tidied names that are not libraries at all
-- (shirt_U_paintoutfit). It now holds the library each of the row's sets is
-- drawn from (shirt_M_paintoutfit,shirt_F_paintoutfit) - the name
-- habboassets.com/swfs/clothing, Habbo's figuremap and our own FigureMap all
-- use - in the same order as clothing_parts, so a row can be looked up there
-- directly. A set two of a row's ids share is named once.
--
-- Generated by docker/nitro/gen-clothing-habbo-names.py from
-- emulator/Config/figuredata.xml and the figuremaps; see the script for how a
-- set is matched to its library. {sets} figure sets, {mapped} matched.
-- {unmapped} match nothing (part ids no figuremap or HabboAssets listing has):
-- {unmapped_ids}.
-- A row holding any of those keeps its name, and is listed at the end.
--
-- Nothing on the shelf changes. The store shows display_name and falls back
-- to tidying clothing_name only when there is none, so a row being renamed
-- that has no display_name first gets the label it was showing, written down.
-- Nothing is keyed by clothing_name: the furni, backpack tokens and the
-- buy packet all go by row id. user_clothing.part, a copy of the name kept
-- per owned set, takes that set's own library.
--
-- Both name columns widen to fit a multi-library name. Idempotent: a second
-- run finds every row already named.

"""

BODY = """
ALTER TABLE `catalog_clothing` MODIFY `clothing_name` varchar(255) NOT NULL DEFAULT '';
ALTER TABLE `user_clothing` MODIFY `part` varchar(255) NOT NULL DEFAULT '';

-- Each row's new name: its sets' libraries in clothing_parts order, and how
-- many of its set ids matched.
CREATE TEMPORARY TABLE `rp_clothing_habbo_name` (
  `id` int(11) NOT NULL,
  `sets` int(11) NOT NULL,
  `matched` int(11) NOT NULL,
  `new_name` varchar(1024) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;

INSERT INTO `rp_clothing_habbo_name` (`id`, `sets`, `matched`, `new_name`)
SELECT x.`id`, x.`sets`, SUM(x.`matched`), GROUP_CONCAT(x.`library` ORDER BY x.`pos` SEPARATOR ',')
  FROM (
  SELECT c.`id`,
         1 + LENGTH(c.`clothing_parts`) - LENGTH(REPLACE(c.`clothing_parts`, ',', '')) AS `sets`,
         m.`library`,
         MIN(FIND_IN_SET(m.`set_id`, REPLACE(c.`clothing_parts`, ' ', ''))) AS `pos`,
         COUNT(*) AS `matched`
    FROM `catalog_clothing` c
    JOIN `rp_habbo_library` m ON FIND_IN_SET(m.`set_id`, REPLACE(c.`clothing_parts`, ' ', '')) > 0
   GROUP BY c.`id`, `sets`, m.`library`
  ) x
 GROUP BY x.`id`, x.`sets`;

-- Rows that will be renamed: every set matched, the name fits, and it differs.
DELETE FROM `rp_clothing_habbo_name` WHERE `matched` < `sets` OR LENGTH(`new_name`) > 255;
DELETE n FROM `rp_clothing_habbo_name` n
  JOIN `catalog_clothing` c ON c.`id` = n.`id`
 WHERE CAST(c.`clothing_name` AS BINARY) = CAST(n.`new_name` AS BINARY);

-- The shelf label those rows were showing, as the client tidies it: drop a
-- leading "clothing_", split on underscores and spaces, capitalise each word.
CREATE TEMPORARY TABLE `rp_clothing_tidy` (
  `id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;

INSERT INTO `rp_clothing_tidy` (`id`, `name`)
SELECT c.`id`,
       TRIM(BOTH '_' FROM REGEXP_REPLACE(
         IF(CAST(LEFT(c.`clothing_name`, 9) AS BINARY) = CAST('clothing_' AS BINARY), SUBSTRING(c.`clothing_name`, 10), c.`clothing_name`),
         '[_[:space:]]+', '_'))
  FROM `catalog_clothing` c
  JOIN `rp_clothing_habbo_name` n ON n.`id` = c.`id`
 WHERE COALESCE(c.`display_name`, '') = '';

CREATE TEMPORARY TABLE `rp_clothing_label` (
  `id` int(11) NOT NULL,
  `label` varchar(255) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;

INSERT INTO `rp_clothing_label` (`id`, `label`)
SELECT w.`id`, GROUP_CONCAT(CONCAT(UPPER(LEFT(w.`word`, 1)), SUBSTRING(w.`word`, 2)) ORDER BY w.`n` SEPARATOR ' ')
  FROM (
  SELECT t.`id`, k.`n`, SUBSTRING_INDEX(SUBSTRING_INDEX(t.`name`, '_', k.`n`), '_', -1) AS `word`
    FROM `rp_clothing_tidy` t
    JOIN (SELECT 1 AS `n` UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5
          UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9 UNION ALL SELECT 10
          UNION ALL SELECT 11 UNION ALL SELECT 12 UNION ALL SELECT 13 UNION ALL SELECT 14 UNION ALL SELECT 15) k
      ON k.`n` <= 1 + LENGTH(t.`name`) - LENGTH(REPLACE(t.`name`, '_', ''))
  ) w
 WHERE w.`word` <> ''
 GROUP BY w.`id`;

UPDATE `catalog_clothing` c
  JOIN `rp_clothing_label` l ON l.`id` = c.`id`
   SET c.`display_name` = LEFT(l.`label`, 64);

SELECT CONCAT('shelf labels written down before renaming: ', COUNT(*)) AS `receipt` FROM `rp_clothing_label`;

UPDATE `catalog_clothing` c
  JOIN `rp_clothing_habbo_name` n ON n.`id` = c.`id`
   SET c.`clothing_name` = n.`new_name`;

SELECT CONCAT('clothing rows renamed: ', COUNT(*)) AS `receipt` FROM `rp_clothing_habbo_name`;

UPDATE `user_clothing` u
  JOIN `rp_habbo_library` m ON CAST(m.`set_id` AS BINARY) = CAST(u.`part_id` AS BINARY)
   SET u.`part` = m.`library`
 WHERE CAST(u.`part` AS BINARY) <> CAST(m.`library` AS BINARY);

-- Rows still not on a library name: a set id no figuremap places, or one
-- figuredata does not have at all.
SELECT CONCAT('not renamed: #', c.`id`, ' ', c.`clothing_name`, ' (', c.`clothing_parts`, ')') AS `receipt`
  FROM `catalog_clothing` c
 WHERE 1 + LENGTH(c.`clothing_parts`) - LENGTH(REPLACE(c.`clothing_parts`, ',', ''))
       <> (SELECT COUNT(*) FROM `rp_habbo_library` m
            WHERE FIND_IN_SET(m.`set_id`, REPLACE(c.`clothing_parts`, ' ', '')) > 0);

DROP TEMPORARY TABLE `rp_clothing_label`;
DROP TEMPORARY TABLE `rp_clothing_tidy`;
DROP TEMPORARY TABLE `rp_clothing_habbo_name`;
DROP TEMPORARY TABLE `rp_habbo_library`;
"""

if __name__ == '__main__':
    main()
