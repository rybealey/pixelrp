#!/usr/bin/env python3
"""Make every handitem in the library reachable from :carry <id>.

THE PROBLEM THIS SOLVES. `:carry N` does not draw part N. The renderer passes
the id through the CarryItem action's parameter map first
(AvatarImage.appendAction -> getActionDefinitionWithState(...).getParameterValue),
and HabboAvatarActions.json's CarryItem lists only ~224 ids. Everything else
falls through to `default = 1`, which is the cup of water - so an unmapped
handitem does not fail loudly, it silently becomes a cup with the right name
beside it. That is why importing a new hh_human_item library changed nothing:
the assets and the FigureMap entry are necessary but the parameter map is what
actually chooses the sprite.

WHAT THIS EMITS. A gamedata fragment adding, for every `ri` part in the library
that no existing parameter already points at, an identity mapping id -> part id,
to both CarryItem (crr) and UseItem (drk). Identity is the least surprising
rule: `:carry 307` draws part 307. Existing mappings are never touched, so no
handitem anyone already uses changes meaning.

Reads the live library and action data pulled from the server; writes
nitro/overrides/gamedata-merge/HabboAvatarActions.json.
"""
import json
import re
import struct
import sys
import zlib

LIB = sys.argv[1] if len(sys.argv) > 1 else 'hh_human_item.nitro'
ACTIONS = sys.argv[2] if len(sys.argv) > 2 else 'HabboAvatarActions.json'
OUT = 'nitro/overrides/gamedata-merge/HabboAvatarActions.json'
PART = re.compile(r'^h_[a-z]+_(ri|li)_(\d+)_')


def bundle_assets(path):
    raw = open(path, 'rb').read()
    i = 0
    count = struct.unpack_from('>H', raw, i)[0]
    i += 2
    files = {}
    for _ in range(count):
        n = struct.unpack_from('>H', raw, i)[0]
        i += 2
        name = raw[i:i + n].decode()
        i += n
        length = struct.unpack_from('>I', raw, i)[0]
        i += 4
        files[name] = zlib.decompress(raw[i:i + length])
        i += length
    return json.loads(next(v for k, v in files.items() if k.endswith('.json')))['assets']


parts = {'ri': set(), 'li': set()}
for name in bundle_assets(LIB):
    m = PART.match(name)
    if m:
        parts[m.group(1)].add(int(m.group(2)))

actions = json.load(open(ACTIONS))
actions = actions.get('actions', actions)
by_id = {a.get('id'): a for a in actions}

fragment = {'actions': []}
for action_id in ('CarryItem', 'UseItem'):
    action = by_id.get(action_id)
    if action is None:
        sys.exit('%s missing from %s' % (action_id, ACTIONS))
    params = action.get('params') or []
    mapped_ids = {p['id'] for p in params}
    # A part that some id already points at is reachable; leave it be.
    reachable = {p['value'] for p in params}
    added = []
    for part in sorted(parts['ri']):
        key = str(part)
        if key in reachable or key in mapped_ids:
            continue
        added.append({'id': key, 'value': key})
    fragment['actions'].append({'id': action_id, 'params': added})
    print('%-10s %3d existing params, %3d added (default stays %s)'
          % (action_id, len(params), len(added),
             next((p['value'] for p in params if p['id'] == 'default'), '?')))

json.dump(fragment, open(OUT, 'w'), indent=1)
sample = [p['id'] for p in fragment['actions'][0]['params']]
print('wrote %s' % OUT)
print('newly reachable ids: %d, including %s'
      % (len(sample), [i for i in ('307', '314', '315', '1112', '1115') if i in sample]))
