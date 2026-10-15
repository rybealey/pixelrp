#!/usr/bin/env python3
"""Correct a custom furni's declared footprint in all three places it is stated.

A furni's tile footprint is declared THREE times, and a mismatch between them
fails quietly and differently in each direction:

  1. `furniture`.`width` / `length` - what the emulator blocks and paths around.
  2. `FurnitureData.json` xdim / ydim - what the client's placement ghost covers.
  3. the .nitro bundle's `logic.model.dimensions` - the object's logical size in
     the renderer.

Plenty of scene customs ship with (3) wrong: the art spans two tiles but the
XML says 1x1, so the hedge renders long while the selection box and the blocked
tile cover one square. Fixing only the database gives the opposite mismatch -
the server blocks two tiles while the client still thinks it is one.

Usage:
    python3 docker/nitro/set-furni-dimensions.py <classname> <width> <length>

Rewrites the bundle and the gamedata fragment in place and prints the SQL line
to add to an emulator update - the database is not touched from here, because
`furniture` rows are versioned through Resources/SQLs/Updates.
"""
import json
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furni_bundle as fb

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUNDLE = os.path.join(REPO, 'nitro/overrides/bundled/furniture/%s.nitro')
MERGE_FURNI = os.path.join(REPO, 'nitro/overrides/gamedata-merge/FurnitureData.json')


def patch_bundle(classname, width, length):
    path = BUNDLE % classname
    if not os.path.exists(path):
        return None
    entries = fb.bundle_entries(path)
    json_name = next(k for k in entries if k.endswith('.json'))
    data = json.loads(fb.inflate(entries[json_name]))
    dims = data.setdefault('logic', {}).setdefault('model', {}).setdefault('dimensions', {})
    before = (dims.get('x'), dims.get('y'))
    dims['x'] = width
    dims['y'] = length
    entries[json_name] = zlib.compress(json.dumps(data).encode('utf-8'), 9)
    fb.write_bundle(path, entries)
    return before


def patch_gamedata(classname, width, length):
    data = json.load(open(MERGE_FURNI, encoding='utf-8'))
    for entry in data['roomitemtypes']['furnitype']:
        if entry['classname'] == classname:
            before = (entry.get('xdim'), entry.get('ydim'))
            entry['xdim'] = width
            entry['ydim'] = length
            json.dump(data, open(MERGE_FURNI, 'w', encoding='utf-8'))
            return before, entry['id']
    return None, None


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    classname, width, length = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])

    bundle_before = patch_bundle(classname, width, length)
    print('bundle    %s -> (%d, %d)' % (bundle_before or 'NOT FOUND', width, length))

    gamedata_before, definition_id = patch_gamedata(classname, width, length)
    print('gamedata  %s -> (%d, %d)' % (gamedata_before or 'NOT FOUND', width, length))

    if definition_id:
        print('\nSQL for an emulator update:')
        print("UPDATE `furniture` SET `width` = %d, `length` = %d WHERE `id` = %d "
              "AND `item_name` = '%s' LIMIT 1;" % (width, length, definition_id, classname))


if __name__ == '__main__':
    main()
