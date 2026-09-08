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
  FigureMap.json       fragment {"libraries": [{"id": ..., "parts": [...]}]};
                       parts are added to the named library, matched on
                       (id, type), and an unknown library is appended whole.
                       This is what makes a handitem REACHABLE: the bundle can
                       hold ri_314 all it likes, but until FigureMap says
                       hh_human_item provides part 314 the client never asks
                       for it, and :carry 314 renders nothing.
  ExternalTexts.json   fragment {key: text}; existing keys are left alone.
  HabboAvatarActions.json
                       fragment {"actions": [{"id": ..., "params": [...]}]};
                       params are added to the named action, keyed on the param
                       id, and existing ids (including "default") are never
                       overwritten. This is what makes `:carry <id>` reach a
                       handitem at all: the renderer maps the id through
                       CarryItem's params before it ever looks for a sprite, and
                       an unmapped id silently falls back to default = the cup.

There is a second directory, `gamedata-override/`, for the opposite case: keys
that must REPLACE what the official gamedata already says. Merging cannot do
that by design - it exists to protect the official library from being clobbered
- so changing a shipped string (renaming a button, say) needs the override
channel, and putting a file there is the deliberate act that says so.

Run from the deploy checkout root. Idempotent by construction.
"""
import json
import os
import sys

MERGE_DIR = 'nitro/assets/gamedata-merge'
OVERRIDE_DIR = 'nitro/assets/gamedata-override'
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


def merge_figuremap(fragment, target):
    added = 0
    libraries = target.setdefault('libraries', [])
    by_id = {lib.get('id'): lib for lib in libraries}
    for lib in fragment.get('libraries') or []:
        existing = by_id.get(lib.get('id'))
        if existing is None:
            libraries.append(lib)
            added += len(lib.get('parts') or [])
            continue
        parts = existing.setdefault('parts', [])
        # Ids arrive as ints here and as ints in the served file, but compare
        # as strings so a fragment written with "314" still matches 314.
        have = {(str(p.get('id')), p.get('type')) for p in parts}
        for part in lib.get('parts') or []:
            key = (str(part.get('id')), part.get('type'))
            if key in have:
                continue
            parts.append(part)
            have.add(key)
            added += 1
    return added


def merge_actions(fragment, target):
    added = 0
    actions = target.get('actions') if isinstance(target, dict) else target
    by_id = {a.get('id'): a for a in actions}
    for action in fragment.get('actions') or []:
        existing = by_id.get(action.get('id'))
        if existing is None:
            continue                       # never invent an action
        params = existing.setdefault('params', [])
        have = {p.get('id') for p in params}
        for param in action.get('params') or []:
            if param.get('id') in have:
                continue                   # an existing mapping always wins
            params.append(param)
            have.add(param.get('id'))
            added += 1
    return added


def merge_texts(fragment, target):
    added = 0
    for key, value in fragment.items():
        if key not in target:
            target[key] = value
            added += 1
    return added


def apply_overrides():
    """gamedata-override/: keys here REPLACE the shipped ones.

    Only flat {key: text} files are supported - a structural override (a whole
    furnitype, a whole action) is a merge with different rules, and guessing at
    one silently would be worse than refusing it.
    """
    if not os.path.isdir(OVERRIDE_DIR):
        return
    for name in sorted(os.listdir(OVERRIDE_DIR)):
        if not name.endswith('.json'):
            continue
        target_path = os.path.join(TARGET_DIR, name)
        if not os.path.exists(target_path):
            print('skipped override %s: no %s on this server' % (name, target_path))
            continue
        fragment, target = load(os.path.join(OVERRIDE_DIR, name)), load(target_path)
        if not isinstance(fragment, dict) or not isinstance(target, dict) \
                or any(not isinstance(v, str) for v in fragment.values()):
            print('skipped override %s: only flat {key: text} files are supported' % name)
            continue
        changed = sum(1 for k, v in fragment.items() if target.get(k) != v)
        target.update(fragment)
        if changed:
            save(target_path, target)
        print('%s: %d keys overridden' % (name, changed))


if not os.path.isdir(MERGE_DIR):
    print('no gamedata fragments to merge')
    apply_overrides()
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
    elif name == 'FigureMap.json':
        added = merge_figuremap(fragment, target)
    elif name == 'HabboAvatarActions.json':
        added = merge_actions(fragment, target)
    else:
        added = merge_texts(fragment, target)
    if added:
        save(target_path, target)
    print('%s: %d entries added' % (name, added))

apply_overrides()
