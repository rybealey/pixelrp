#!/usr/bin/env python3
"""Plain furni whose clicks go through a state that shows nothing new, or that
cannot be clicked at all.

A plain furni (interaction_type 'default') double-clicks through
InteractorGenericSwitch: 0, 1, ... up to interaction_modes_count - 1, or the
states in click_states when that is set. Three things are wrong with some:

- a state that looks exactly like one before it, so that click seems to do
  nothing - often a count that runs past the states the art draws (Theatre Rug:
  14 for 13 looks), sometimes the art drawing one look twice;
- the Washing Machine's: one look moving, the same look stopped, one other
  still look - a click should go moving <-> other, never to the stopped copy
  (289 set the Washer itself by hand);
- a count of 0 or 1 on art that has two or more looks, so it never switches.

furni_bundle.click_states says which states a click should go through. This
never adds a state the count does not already reach - a count somebody set is
their decision - except for the third case, where 0 or 1 was never set at all;
and art that already has a count of 2+ on another row waits for that decision.
Rows staff changed in the Function tool are left out of the dump.

Reads a dump of the furniture table, FurnitureData (to find each row's bundle,
the way the client does: type + sprite id) and the bundle folders, and prints
a migration. Pillow and numpy are needed, so run it where they are, with the
bundles copied down from the server:

    docker exec pixelrp-beta-db-1 sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" pixelrp -B -e \\
        "SELECT id, item_name, type, sprite_id, interaction_type, interaction_modes_count, click_states
           FROM furniture WHERE id NOT IN (SELECT definition_id FROM rp_furni_function_log
                WHERE field IN (\\"interaction_modes_count\\", \\"click_states\\"))"' > furniture.tsv
    python3 docker/nitro/fix-furni-click-states.py furniture.tsv FurnitureData.json <bundle dir>... \\
        > NNN_FurniClickStates.sql
"""
import json
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furni_bundle as fb

DIRS = []


def read_rows(path):
    """mysql -B escapes tabs and newlines but not a bare CR - split on LF only."""
    rows, header = [], None
    with open(path, encoding='utf-8', newline='\n') as fh:
        for line in fh:
            parts = line.rstrip('\n').replace('\r', '').split('\t')
            if header is None:
                header = parts
            elif len(parts) == len(header):
                rows.append(dict(zip(header, parts)))
    return rows


def classnames(path):
    """(type, sprite id) -> classname: how the client finds a row's bundle."""
    data = json.load(open(path, encoding='utf-8'))
    found = {}
    for section, kind in (('roomitemtypes', 's'), ('wallitemtypes', 'i')):
        for furni in data[section]['furnitype']:
            found[(kind, int(furni['id']))] = furni['classname']
    return found


def states(job):
    """(row id, the states a click should go through) - None without a bundle."""
    fid, base, count = job
    path = next((os.path.join(d, base + '.nitro') for d in DIRS
                 if os.path.exists(os.path.join(d, base + '.nitro'))), None)
    if not path:
        return fid, None
    try:
        return fid, fb.click_states(fb.bundle_entries(path), base, count)
    except (StopIteration, ValueError, KeyError, OSError, IndexError):
        return fid, None


def init(dirs):
    DIRS.extend(dirs)


def main():
    rows = read_rows(sys.argv[1])
    names = classnames(sys.argv[2])
    plain = [r for r in rows if r['interaction_type'].lower() in ('default', '') and r['type'] in ('s', 'i')]
    decided = {(r['sprite_id'], r['type']) for r in plain if int(r['interaction_modes_count']) > 1}
    jobs = []
    for r in plain:
        count = int(r['interaction_modes_count'])
        if r['click_states'] not in ('', 'NULL'):
            continue                        # already chosen by hand
        if count <= 1 and (r['sprite_id'], r['type']) in decided:
            continue
        classname = names.get((r['type'], int(r['sprite_id']))) or r['item_name']
        jobs.append((int(r['id']), classname.split('*')[0], count if count > 1 else None))
    with Pool(min(14, os.cpu_count() or 1), initializer=init, initargs=(sys.argv[3:],)) as pool:
        found = dict(pool.imap_unordered(states, jobs, chunksize=40))

    by_id = {int(r['id']): r for r in plain}
    changes = []
    for fid, keep in sorted(found.items()):
        if not keep:
            continue
        r = by_id[fid]
        old = int(r['interaction_modes_count'])
        if old <= 1 and len(keep) < 2:
            continue
        click = '' if keep == list(range(len(keep))) else ','.join(map(str, keep))
        new = (max(keep) + 1, click)
        if new != (old, ''):
            changes.append((fid, r['item_name'], old) + new)

    print("""-- Plain furni whose clicks went through a state that shows nothing new, or
-- that could not be clicked at all - %d furni, from
-- docker/nitro/fix-furni-click-states.py (furni_bundle.click_states says why
-- each state stays or goes):
--
-- - a state that looked exactly like one before it, so that click seemed to do
--   nothing - mostly a count running past the looks the art draws;
-- - the Washing Machine's three looks - moving, the same stopped, one other
--   still: clicks now go moving <-> the other, skipping the stopped copy;
-- - a count of 0 or 1 on art with two or more looks, never set by anyone.
--
-- No count goes up past what it reached before except in that last case, and
-- nothing staff set in the Function tool is touched. Each row changes only if
-- it still holds the count it was read with and no click_states, so anything
-- changed since is left alone. Idempotent.
DROP TEMPORARY TABLE IF EXISTS _furni_clicks;
CREATE TEMPORARY TABLE _furni_clicks (
    id INT NOT NULL PRIMARY KEY, item_name VARCHAR(255) NOT NULL,
    old_count INT NOT NULL, new_count INT NOT NULL, click_states VARCHAR(64) NOT NULL);
INSERT INTO _furni_clicks (id, item_name, old_count, new_count, click_states) VALUES""" % len(changes))
    print(',\n'.join("(%d,'%s',%d,%d,'%s')" % (fid, name.replace('\\', '\\\\').replace("'", "\\'"), old, count, click)
                     for fid, name, old, count, click in changes) + ';')
    print("""UPDATE `furniture` f
  JOIN _furni_clicks c ON c.id = f.id
   SET f.`interaction_modes_count` = c.new_count, f.`click_states` = c.click_states
 WHERE LOWER(f.`interaction_type`) IN ('default', '')
   AND f.`interaction_modes_count` = c.old_count
   AND f.`click_states` = '';
DROP TEMPORARY TABLE _furni_clicks;""")
    print('%d furni changed' % len(changes), file=sys.stderr)


if __name__ == '__main__':
    main()
