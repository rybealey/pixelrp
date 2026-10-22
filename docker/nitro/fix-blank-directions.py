#!/usr/bin/env python3
"""Furni that can be turned to a way they draw nothing - and vanish.

    python3 docker/nitro/fix-blank-directions.py <out dir> <bundle dir>... [--dry-run]

A furni turns through the directions its bundle lists (logic.model.directions,
in degrees), and the renderer draws each from that direction's pictures. Some
bundles list a direction they have no picture for: ptrnhout4 draws only facing
270 (and 0, the same picture flipped), but lists 180 and 90 too, so two of its
four turns left it invisible (Twist, 2026-10-22). Others list a direction that
is no direction at all - 2880, 1440 - from a broken conversion.

For each such bundle this writes one to <out dir> (nitro/overrides/bundled/
furniture) whose directions are only the ones it draws, in its own order, so a
turn skips the blank ones and a fresh placement starts on one it draws. The
pictures are untouched. A bundle that draws no direction at all is reported and
left; so are the ones that are blank on purpose (EXCLUDE): an invisible block,
the stack tile, clothing and wired - and balls, whose list holds the ways they
roll (1 to 7) beside their turns.

"Draws" means a layer's first picture of state 0 is in the sprite sheet, after
following asset 'source' links. Earlier <bundle dir>s win over later ones.
Placed furni facing a blank way need their own migration (none on beta did).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furni_bundle as fb

LETTERS = 'abcdefghijklmnopqrstuvwxyz'
EXCLUDE = ('clothing_', 'wf_', 'room_invisible', 'tile_walkmagic', 'free_placement')


def blank_turns(lib, data):
    """(turns, the ones it draws) for a bundle, or None when nothing is wrong."""
    vis = next((v for v in data.get('visualizations') or [] if v.get('size') == 64), None)
    model = (data.get('logic') or {}).get('model') or {}
    turns = model.get('directions') or []
    if not vis or not turns:
        return None
    if any(isinstance(t, (int, float)) and 0 < t < 45 for t in turns):
        return None                         # a ball lists the ways it rolls, 1 to 7: not turns
    frames = {(k[:-4] if k.endswith('.png') else k) for k in ((data.get('spritesheet') or {}).get('frames') or {})}
    assets = data.get('assets') or {}
    layers = int(vis.get('layerCount') or 1)
    start = {}
    for layer, la in (((vis.get('animations') or {}).get('0') or {}).get('layers') or {}).items():
        for seq in (la.get('frameSequences') or {}).values():
            for f in (seq.get('frames') or {}).values():
                start.setdefault(int(layer), int(f.get('id', 0)))

    def drawn(name):
        hops = 0
        while (assets.get(name) or {}).get('source') and hops < 5:
            name, hops = assets[name]['source'], hops + 1
        return (lib + '_' + name) in frames or name in frames

    def draws(turn):
        if not isinstance(turn, (int, float)) or turn < 0 or turn >= 360 or turn % 45:
            return False
        return any(drawn('%s_64_%s_%d_%d' % (lib, LETTERS[n], int(turn) // 45, start.get(n, 0))) for n in range(layers))

    kept = [t for t in turns if draws(t)]
    return None if len(kept) == len(turns) else (turns, kept)


def main():
    args = [a for a in sys.argv[1:] if a != '--dry-run']
    dry = '--dry-run' in sys.argv
    out, sources = args[0], args[1:]
    seen, fixed, nothing = set(), [], []
    for folder in sources:
        for name in sorted(os.listdir(folder)):
            if not name.endswith('.nitro') or name in seen:
                continue
            seen.add(name)
            lib = name[:-6]
            if lib.startswith(EXCLUDE):
                continue
            try:
                entries = fb.bundle_entries(os.path.join(folder, name))
                key = next(k for k in entries if k.endswith('.json'))
                data = json.loads(fb.inflate(entries[key]))
            except (StopIteration, ValueError, KeyError, OSError):
                continue
            found = blank_turns(lib, data)
            if not found:
                continue
            turns, kept = found
            if not kept:
                nothing.append(lib)
                continue
            fixed.append((lib, turns, kept))
            if not dry:
                data['logic']['model']['directions'] = kept
                entries[key] = json.dumps(data, separators=(',', ':')).encode('utf-8')
                fb.write_bundle(os.path.join(out, name), entries)
    for lib, turns, kept in fixed:
        print('%-34s %s -> %s' % (lib, turns, kept))
    print('%d furni turned only to ways they draw%s; %d draw no way at all, left: %s'
          % (len(fixed), ' (dry run)' if dry else '', len(nothing), ' '.join(nothing[:20])))


if __name__ == '__main__':
    main()
