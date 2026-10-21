"""Pick a page's icon from its own furni.

A furniture line wears its chair, the way Habbo's own lines do; anything else
wears its most solid, most colourful piece - never a sliver, a dot or a plain
square that says nothing at small size. A folder never wears the icon of a
page inside it, and pages side by side are kept apart where they can be.
"""
import os
import re
from functools import lru_cache

from PIL import Image

CHAIR = re.compile(r'chair|stool|armchair|seat|sofa|bench|throne|chaise|cadeira|stoel|stuhl', re.I)


@lru_cache(maxsize=None)
def icon_score(path):
    """Bigger, squarer and more colourful scores higher; 0 for a missing file."""
    if not path or not os.path.exists(path):
        return 0.0
    try:
        img = Image.open(path).convert('RGBA')
    except Exception:
        return 0.0
    import numpy as np
    a = np.asarray(img)
    solid = a[..., 3] > 128
    opaque = int(solid.sum())
    if opaque < 40:
        return 0.0
    rgb = (a[..., :3][solid] >> 4).astype(np.int32)
    colours = np.unique(rgb[:, 0] * 256 + rgb[:, 1] * 16 + rgb[:, 2])
    ys, xs = np.nonzero(solid)
    bw, bh = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
    squareness = min(bw, bh) / max(bw, bh)            # a sliver of a plank scores low
    return (opaque ** 0.5) * min(len(colours), 30) * (0.4 + 0.6 * squareness)


def pick(items, path_of, avoid=(), prefer=None, prefer_chair=False):
    """The item whose icon is best among `items` (each item -> a file path via
    `path_of`), skipping any whose path is in `avoid`. Items matching `prefer`
    (a regex on classname and name), then chairs if asked, are tried first.
    Returns the item, or None."""
    pools = []
    if prefer:
        rx = re.compile(prefer, re.I)
        pools.append([it for it in items if rx.search(it[0] + ' ' + (it[1] or ''))])
    if prefer_chair:
        pools.append([it for it in items if CHAIR.search(it[0] + ' ' + (it[1] or ''))])
    pools.append(items)
    for pool in pools:
        best, best_score = None, 0.0
        for it in pool:
            p = path_of(it)
            if not p or p in avoid:
                continue
            s = icon_score(p)
            if s > best_score:
                best, best_score = it, s
        if best:
            return best
    return None
