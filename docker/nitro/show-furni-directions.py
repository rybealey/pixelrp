#!/usr/bin/env python3
"""Which directions does a furni bundle actually declare?

A piece that will not rotate in-game is usually not a server refusal. The
client picks the next rotation out of the bundle's own list - nitro-renderer's
FurnitureLogic reads `logic.model.directions` into FURNITURE_ALLOWED_DIRECTIONS,
and RoomObjectEventHandler.getValidRoomObjectDirection then takes
`(index + 1) % length`. A bundle declaring ONE direction makes "next" the same
one, so the rotate button sends a move whose rotation never changed and the
piece sits there.

That is invisible from the database, which is why this reads the bundle:

    python3 docker/nitro/show-furni-directions.py boutique_mannequin1
    python3 docker/nitro/show-furni-directions.py 'boutique_*'      # a whole line
    python3 docker/nitro/show-furni-directions.py --rotatable-only 'xmas_*'

Looks in the live asset tree first, then the repo's overrides, so it works on
the VPS and on a dev checkout without being told which.
"""
import glob
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


def bundles_for(pattern):
    """Every bundle matching, nearest tree first, one entry per classname."""
    found, seen = [], set()

    for directory in SEARCH:
        for path in sorted(glob.glob(os.path.join(directory, pattern + '.nitro'))):
            name = os.path.basename(path)[:-6]

            if name in seen:
                continue

            seen.add(name)
            found.append(path)

    return found


def directions(path):
    entries = fb.bundle_entries(path)
    name = next((k for k in entries if k.endswith('.json')), None)

    if not name:
        return None

    data = json.loads(fb.inflate(entries[name]))

    return ((data.get('logic') or {}).get('model') or {}).get('directions')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    only_stuck = '--rotatable-only' not in sys.argv and '--stuck-only' in sys.argv

    if not args:
        raise SystemExit(__doc__)

    paths = []

    for pattern in args:
        paths.extend(bundles_for(pattern))

    if not paths:
        raise SystemExit('no bundle matched %s in:\n  %s' % (', '.join(args), '\n  '.join(SEARCH)))

    stuck = 0

    for path in paths:
        name = os.path.basename(path)[:-6]

        try:
            dirs = directions(path)
        except Exception as error:
            print(f'{name:<44} unreadable ({error})')
            continue

        count = len(dirs) if dirs else 0

        if count < 2:
            stuck += 1

        if only_stuck and count >= 2:
            continue

        verdict = 'CANNOT rotate - one direction' if count == 1 else \
                  'CANNOT rotate - none declared' if count == 0 else \
                  f'{count} directions'

        print(f'{name:<44} {str(dirs or []):<28} {verdict}')

    print(f'\n{len(paths)} bundle(s), {stuck} that cannot rotate')


if __name__ == '__main__':
    main()
