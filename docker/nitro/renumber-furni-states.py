#!/usr/bin/env python3
"""Give a furni only the looks a click should go through, numbered 0, 1, ...

    python3 docker/nitro/renumber-furni-states.py <in.nitro> <out.nitro> 0,2

New state 0 draws what old state 0 drew, new state 1 what old state 2 drew,
and so on, in every size - so the count can be 2 and the furni really has two
states, instead of a count of 3 with click_states skipping one (289 did that
for the Washing Machine; Twist: it should only have 2 states). An old state
number that is not reused keeps drawing what it drew, so a piece saved in it
before the migration moved it still looks right.

Write the result to nitro/overrides/bundled/furniture/<classname>.nitro and
move placed pieces' states to the new numbers in the same migration that sets
the count. A browser holding the old bundle shows the old looks until it
reloads the furni (a hard refresh).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furni_bundle as fb


def main():
    src, dst, keep = sys.argv[1], sys.argv[2], [int(s) for s in sys.argv[3].split(',')]
    entries = fb.bundle_entries(src)
    name = next(k for k in entries if k.endswith('.json'))
    data = json.loads(fb.inflate(entries[name]))
    for vis in data.get('visualizations') or []:
        anims = vis.get('animations')
        if not anims:
            continue
        renumbered = dict(anims)
        for new, old in enumerate(keep):
            if str(old) in anims:
                renumbered[str(new)] = anims[str(old)]
            else:
                renumbered.pop(str(new), None)     # it drew frame 0, and so will the new one
        vis['animations'] = dict(sorted(renumbered.items(), key=lambda kv: (not kv[0].isdigit(), int(kv[0]) if kv[0].isdigit() else 0, kv[0])))
    entries[name] = json.dumps(data, separators=(',', ':')).encode('utf-8')
    fb.write_bundle(dst, entries)
    print('%s: states %s -> 0..%d' % (os.path.basename(dst), ','.join(map(str, keep)), len(keep) - 1))


if __name__ == '__main__':
    main()
