#!/usr/bin/env python3
"""Merge nitro/assets/gamedata-merge/*.json into nitro/assets/gamedata/.

The overrides tree (nitro/overrides/) is a plain rsync overlay: a file there
replaces the server's file outright. That works for a small custom file like
EffectMap.json and cannot work for FurnitureData.json, which holds the whole
18k-entry official library and exists only on the server - a fragment would
wipe it.

So custom gamedata ships as a FRAGMENT under gamedata-merge/ and this merges it
in on the server, after the rsync and before the client is restarted:

  FurnitureData.json   fragment {"roomitemtypes": {"furnitype": [...]}}; entries
                       whose classname is already present are left alone, so an
                       official entry always wins and a re-run is a no-op.
  ExternalTexts.json   fragment {key: text}; existing keys are left alone.

Run from the deploy checkout root. Idempotent by construction.
"""
import json
import os
import sys

MERGE_DIR = 'nitro/assets/gamedata-merge'
TARGET_DIR = 'nitro/assets/gamedata'


def load(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def save(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(data, fh)
    os.replace(tmp, path)          # never leave a half-written gamedata file


def merge_furnituredata(fragment, target):
    added = 0
    for kind in ('roomitemtypes', 'wallitemtypes'):
        entries = fragment.get(kind, {}).get('furnitype') or []
        if not entries:
            continue
        target.setdefault(kind, {}).setdefault('furnitype', [])
        have = {f['classname'] for f in target[kind]['furnitype']}
        for entry in entries:
            if entry['classname'] in have:
                continue
            target[kind]['furnitype'].append(entry)
            have.add(entry['classname'])
            added += 1
    return added


def merge_texts(fragment, target):
    added = 0
    for key, value in fragment.items():
        if key not in target:
            target[key] = value
            added += 1
    return added


if not os.path.isdir(MERGE_DIR):
    print('no gamedata fragments to apply')
    sys.exit(0)

for name in sorted(os.listdir(MERGE_DIR)):
    if not name.endswith('.json'):
        continue
    target_path = os.path.join(TARGET_DIR, name)
    if not os.path.exists(target_path):
        print('skipped %s: no %s on this server' % (name, target_path))
        continue
    fragment, target = load(os.path.join(MERGE_DIR, name)), load(target_path)
    if name == 'FurnitureData.json':
        added = merge_furnituredata(fragment, target)
    else:
        added = merge_texts(fragment, target)
    if added:
        save(target_path, target)
    print('%s: %d entries added' % (name, added))
