#!/usr/bin/env python3
"""Furni whose double click does nothing, or never reaches all of its states.

A plain furni (interaction_type 'default') double-clicks through
InteractorGenericSwitch, which cycles extra_data 0, 1, ... up to
interaction_modes_count - 1 and does nothing at all when the count is 1. The
count is only ever as good as whoever wrote the row: the full library import
(31) never set it, so ~3,900 Habbo furni took the column's default; the Habbo
sync (85) and Kasja (84) importers wrote 1 for everything; and the pack
importers counted animations, which misses state 0 when it has no animation of
its own. The bundle is what the client actually draws, so the bundle decides.

Reads a dump of the furniture table and the asset tree, and prints a migration
that RAISES each plain furni's count to the states its bundle draws. It never
lowers one: a higher count only costs a click that looks like nothing, while
a lower one somebody set on purpose could hide a state the server uses.

Run on the VPS from the checkout, against the database it is meant for:

    docker exec pixelrp-beta-db-1 sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" pixelrp -B -e \\
        "SELECT item_name, type, sprite_id, interaction_type, interaction_modes_count FROM furniture"' \\
        > /tmp/furniture.tsv
    python3 docker/nitro/fix-furni-state-counts.py /tmp/furniture.tsv > 287_FurniStateCounts.sql

The count itself is furni_bundle.click_modes - the same rule the importers
use, which also says which bundles it leaves at 1 and why. Rows with any other
interaction type are left alone: gates, dice, wheels, teleports and the rest
read the count their own way, or not at all.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furni_bundle as fb

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEARCH = [
    os.path.join(REPO, 'nitro/assets/bundled/furniture'),
    os.path.join(REPO, 'nitro/overrides/bundled/furniture'),
]
FURNIDATA = os.path.join(REPO, 'nitro/assets/gamedata/FurnitureData.json')


def read_rows(path):
    """The furniture dump. mysql -B escapes tabs and newlines but not a bare
    CR, which a few public names carry - so split on LF only."""
    rows, header = [], None
    with open(path, encoding='utf-8', newline='\n') as fh:
        for line in fh:
            parts = line.rstrip('\n').replace('\r', '').split('\t')
            if header is None:
                header = parts
                continue
            if len(parts) == len(header):
                rows.append(dict(zip(header, parts)))
    return rows


def classnames():
    """(type, sprite id) -> classname: how the client finds a row's bundle."""
    data = json.load(open(FURNIDATA, encoding='utf-8'))
    found = {}
    for section, kind in (('roomitemtypes', 's'), ('wallitemtypes', 'i')):
        for furni in data[section]['furnitype']:
            found[(kind, int(furni['id']))] = furni['classname']
    return found


_modes = {}


def bundle_modes(base):
    """The count one bundle's states call for, or None when there is no bundle."""
    if base not in _modes:
        _modes[base] = None
        path = next((os.path.join(d, base + '.nitro') for d in SEARCH
                     if os.path.exists(os.path.join(d, base + '.nitro'))), None)
        if path:
            try:
                _modes[base] = fb.read_furni(path)['modes']
            except (StopIteration, ValueError, KeyError, OSError):
                pass
    return _modes[base]


def main():
    rows = read_rows(sys.argv[1])
    names = classnames()
    # Keyed on (sprite_id, type), the pair the client finds the bundle by, so
    # every row drawing the same art gets the same count.
    raise_to = {}
    for row in rows:
        if row['interaction_type'].lower() not in ('default', ''):
            continue
        key = (int(row['sprite_id']), row['type'])
        classname = names.get((row['type'], key[0]))
        modes = bundle_modes(classname.split('*')[0]) if classname else None
        # 0 and 1 both mean "no click", so a furni with one state is left be.
        if modes and modes > max(1, int(row['interaction_modes_count'])):
            raise_to.setdefault(key, (classname, modes))

    print("""-- Furni whose double click did nothing, or stopped short of its states.
--
-- A plain furni (interaction_type 'default') double-clicks through
-- InteractorGenericSwitch, which cycles 0, 1, ... up to
-- interaction_modes_count - 1 and returns at once when the count is 1. The
-- counts came from imports that never read the art: 31_FullFurniLibrary never
-- set one, 84 (Kasja) and 85 (Habbo sync) wrote 1 for everything. So the
-- Washing Machine (hygge_c25_washer, three states: door open with the cat,
-- the cat still, door shut) toggled only the cat and its door never shut, and
-- most of the rest could not be clicked at all.
--
-- Each count below is the states the furni's own bundle draws - 0, then every
-- state from 1 up until the first gap - from
-- docker/nitro/fix-furni-state-counts.py, which also says what it leaves alone
-- and why. %d furni.
--
-- Keyed on sprite_id and type - the pair the client finds a furni's bundle by,
-- and indexed - rather than item_name, which is latin1 and matched without
-- case. The classname is there to read, not joined on. Idempotent, plain furni
-- only, and it never lowers a count.
DROP TEMPORARY TABLE IF EXISTS _furni_states;
CREATE TEMPORARY TABLE _furni_states (
    sprite_id INT NOT NULL, type VARCHAR(4) NOT NULL, classname VARCHAR(255) NOT NULL,
    modes INT NOT NULL, PRIMARY KEY (sprite_id, type));
INSERT INTO _furni_states (sprite_id, type, classname, modes) VALUES""" % len(raise_to))
    print(',\n'.join("(%d,'%s','%s',%d)" % (sprite, kind, name.replace('\\', '\\\\').replace("'", "\\'"), modes)
                     for (sprite, kind), (name, modes)
                     in sorted(raise_to.items(), key=lambda kv: kv[1][0])) + ';')
    print("""UPDATE `furniture` f
  JOIN _furni_states s ON s.sprite_id = f.sprite_id AND s.type = f.type
   SET f.`interaction_modes_count` = s.modes
 WHERE LOWER(f.`interaction_type`) IN ('default', '')
   AND f.`interaction_modes_count` < s.modes;
DROP TEMPORARY TABLE _furni_states;""")
    print('%d furni raised' % len(raise_to), file=sys.stderr)


if __name__ == '__main__':
    main()
