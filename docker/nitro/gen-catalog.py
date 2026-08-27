#!/usr/bin/env python3
"""Rebuild the Furni + Staff catalog for the full furni library.

Reads: /tmp/fd.json (furnidata), /tmp/furni_names.json (resolved names),
/tmp/furni_id_map.tsv (item_name -> furniture.id), /tmp/keep_final.txt (page
ids to preserve), /tmp/delete_pages.txt (old Furni/Staff pages to remove).

Emits emulator/Resources/SQLs/Updates/33_CatalogRebuild.sql:
  1. delete catalog_items not on a KEEP page (old furni + any prior generated),
  2. delete the old Furni/Staff furni pages + Club/Exchange/Duckets, and any
     prior generated pages (id >= GEN_BASE),
  3. de-brand/re-home the kept functional pages,
  4. insert generated parent pages + line pages (ids from GEN_BASE up),
  5. insert one catalog_items row per catalogued furni (coins only).

Idempotent: re-running deletes the generated range and rebuilds it; Builders,
functional, custom, and VIP pages (all in KEEP) are never touched.
"""
import json
import re

GEN_BASE = 920000  # generated page ids live at/above this (real pages < 913000)

OFF = json.load(open('/tmp/fd.json'))
NAMES = json.load(open('/tmp/furni_names.json'))
FID = {}
for line in open('/tmp/furni_id_map.tsv'):
    if '\t' in line:
        nm, fid = line.rstrip('\n').split('\t', 1)
        FID[nm] = fid
KEEP = sorted(int(x) for x in open('/tmp/keep_final.txt') if x.strip())
DELETE = sorted(int(x) for x in open('/tmp/delete_pages.txt') if x.strip())
BUILDERS = sorted(int(x) for x in open('/tmp/builders_pages.txt') if x.strip())

SEASONAL = re.compile(r'hween|halloween|xmas|christmas|valentine|easter|summer|'
                      r'spring|autumn|ranch_c\d|_c2\d')


def classify(f):
    cn = f['classname']; line = (f.get('furniline') or '').lower(); cat = f.get('category', '')
    if cn.startswith('ads_') or cn.startswith('test_') or line in ('ad_sales', 'test'):
        return None
    if line.startswith('buildersclub'):
        return None
    if line.startswith('nft'):
        return ('STAFF', 'NFT', line)
    if line in ('rare', 'bonusrare') or f.get('rare'):
        return ('STAFF', 'Rares', line or 'rare')
    if 'ltd' in line:
        return ('STAFF', 'LTD', line)
    if cat in ('wired', 'wired_effect', 'wired_condition', 'wired_add_on'):
        return ('FURNI', 'Wired', 'wired')
    if cat == 'games':
        return ('FURNI', 'Games', 'games')
    if cat == 'pets':
        return ('FURNI', 'Pets', 'pets')
    if cat in ('music', 'sound_fx'):
        return ('FURNI', 'Sound', 'sound')
    if SEASONAL.search(line):
        return ('FURNI', 'Seasonal', line)
    if line in ('classics', 'base'):
        return ('FURNI', 'Classics', 'classics')
    if line:
        return ('FURNI', 'Themed', line)
    return ('FURNI', 'Misc', cat or 'misc')


def price(dest, f):
    grp = dest[1]
    if grp in ('Rares', 'LTD'):
        return 25000
    if grp == 'NFT':
        return 50000
    cat = f.get('category', '')
    if cat in ('wired', 'wired_effect', 'wired_condition', 'wired_add_on', 'games'):
        return 2
    w = int(f.get('xdim', 1) or 1); l = int(f.get('ydim', 1) or 1)
    base = min(3 + 2 * (w * l - 1), 15)
    if cat == 'bed':
        base += 5
    elif cat in ('lighting', 'music', 'sound_fx'):
        base += 2
    return base


def pretty_line(line):
    t = re.sub(r'[_\-]+', ' ', line).strip()
    t = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', t)
    return ' '.join(w.capitalize() for w in t.split())[:35] or 'Furni'


# --- classify everything, bucket by (tab, parent, line) ---
from collections import defaultdict
buckets = defaultdict(list)   # (tab, parent) -> list of (line, classname, f)
for kind in ('roomitemtypes', 'wallitemtypes'):
    for f in OFF[kind]['furnitype']:
        cn = f['classname']
        if cn not in FID:            # no furniture row -> not catalogable
            continue
        d = classify(f)
        if d is None:
            continue
        buckets[(d[0], d[1])].append((d[2], cn, f))

# --- page tree: parents (fixed) + line pages ---
FURNI_ROOT, STAFF_ROOT = 9224, 9225
PARENTS = [   # (group, tab_root, caption, min_rank)
    ('Seasonal',  FURNI_ROOT, 'Seasonal',      1),
    ('Themed',    FURNI_ROOT, 'Themed Lines',  1),
    ('Classics',  FURNI_ROOT, 'Classics',      1),
    ('Functional', FURNI_ROOT, 'Functional',   1),
    ('Wired',     None, 'Wired', 1), ('Games', None, 'Games', 1),
    ('Pets', None, 'Pets', 1), ('Sound', None, 'Sound', 1),
    ('Misc',      FURNI_ROOT, 'Misc',          1),
    ('Rares',     STAFF_ROOT, 'Rares',         5),
    ('NFT',       STAFF_ROOT, 'NFT',           5),
    ('LTD',       STAFF_ROOT, 'LTD',           5),
]
pid = GEN_BASE
parent_id = {}
pages = []   # (id, parent_id, caption, min_rank, order)
order = 1
# Functional is a parent holding Wired/Games/Pets/Sound
for grp, root, cap, rk in PARENTS:
    pid += 1
    if grp in ('Wired', 'Games', 'Pets', 'Sound'):
        par = parent_id['Functional']
    else:
        par = root
    parent_id[grp] = pid
    pages.append((pid, par, cap, rk, order)); order += 1

# line pages under each group (consolidate lines with < MERGE_MIN items)
MERGE_MIN = 5
items = []   # (page_id, item_id, catalog_name, cost_credits)
lpid = GEN_BASE + 100
for (tab, grp), entries in buckets.items():
    par = parent_id[grp]
    rk = 5 if tab == 'STAFF' else 1
    byline = defaultdict(list)
    for line, cn, f in entries:
        byline[line].append((cn, f))
    small = []
    o = 1
    for line, its in sorted(byline.items(), key=lambda kv: -len(kv[1])):
        if grp in ('Wired', 'Games', 'Pets', 'Sound', 'Classics', 'Misc'):
            # single-purpose groups: everything on the parent page itself
            target = par
        elif len(its) < MERGE_MIN:
            small.extend(its); continue
        else:
            lpid += 1
            pages.append((lpid, par, pretty_line(line), rk, o)); o += 1
            target = lpid
        for cn, f in its:
            items.append((target, FID[cn], NAMES.get(cn, cn)[:100],
                          price((tab, grp), f)))
    if small:
        lpid += 1
        pages.append((lpid, par, f'More {grp}'[:35], rk, o))
        for cn, f in small:
            items.append((lpid, FID[cn], NAMES.get(cn, cn)[:100], price((tab, grp), f)))

# --- prune pages with no items and no child pages (e.g. an empty LTD parent) ---
pages_with_items = {it[0] for it in items}
kept_ids = set(pages_with_items)
changed = True
while changed:                       # keep any page that parents a kept page
    changed = False
    child_parents = {par for (pgid, par, *_ ) in pages if pgid in kept_ids}
    for pgid, par, *_ in pages:
        if pgid not in kept_ids and pgid in child_parents:
            kept_ids.add(pgid); changed = True
pages = [p for p in pages if p[0] in kept_ids]

# --- emit SQL ---
def esc(s): return "'" + str(s).replace("\\", "\\\\").replace("'", "\\'") + "'"
keepcsv = ",".join(str(x) for x in KEEP)
delcsv = ",".join(str(x) for x in DELETE)
OUT = 'emulator/Resources/SQLs/Updates/33_CatalogRebuild.sql'
with open(OUT, 'w') as o:
    o.write("-- Rebuild Furni+Staff catalog for the full library. Idempotent.\n")
    o.write("-- Builders + functional + custom pages (KEEP) never touched.\n")
    o.write(f"DELETE FROM catalog_items WHERE page_id NOT IN ({keepcsv});\n")
    o.write(f"DELETE FROM catalog_pages WHERE id IN ({delcsv}) OR id >= {GEN_BASE};\n")
    # de-brand / re-home kept functional pages
    o.write("UPDATE catalog_pages SET caption='Recycler' WHERE id=5;\n")
    o.write(f"UPDATE catalog_pages SET parent_id={FURNI_ROOT}, caption='Room Promo' WHERE id=53;\n")
    o.write("UPDATE catalog_pages SET caption='Groups' WHERE id=9036;\n")
    for pgid, par, cap, rk, ordn in pages:
        o.write("INSERT INTO catalog_pages "
                "(id,parent_id,caption,icon_image,min_rank,min_vip,order_num,page_link,"
                "page_layout,page_strings_1,page_strings_2,visible,enabled) VALUES "
                f"({pgid},{par},{esc(cap)},1,{rk},0,{ordn},'','default_3x3','','',b'1',b'1');\n")
    for i in range(0, len(items), 400):
        o.write("INSERT INTO catalog_items "
                "(page_id,item_id,catalog_name,cost_credits,cost_pixels,cost_diamonds,"
                "amount,limited_sells,limited_stack,offer_active,extradata,badge,offer_id) VALUES\n")
        chunk = [f"({pg},{esc(iid)},{esc(nm)},{cr},0,0,1,0,0,'1','','',-1)"
                 for pg, iid, nm, cr in items[i:i + 400]]
        o.write(",\n".join(chunk) + ";\n")
    # Sweep preserved (KEEP-page) items too: no duckets, no placeholder names.
    # EXCLUDE the Builders subtree from both sweeps (Builders is off-limits).
    bldcsv = ",".join(str(x) for x in BUILDERS)
    o.write("-- retire duckets on remaining non-Builders items: fold into coins\n")
    o.write("UPDATE catalog_items SET cost_credits=cost_credits+cost_pixels, cost_pixels=0 "
            f"WHERE cost_pixels>0 AND page_id NOT IN ({bldcsv});\n")
    o.write("-- fix placeholder catalog_names on kept non-Builders pages from public_name\n")
    o.write("UPDATE catalog_items ci JOIN furniture f ON ci.item_id=f.id "
            "SET ci.catalog_name=f.public_name WHERE ci.catalog_name LIKE '% name' "
            f"AND f.public_name NOT LIKE '% name' AND ci.page_id NOT IN ({bldcsv});\n")

pub = sum(1 for p, *_ in items if True)
from collections import Counter
bc = Counter((t, g) for (t, g) in buckets)
print(f"pages generated: {len(pages)}  items generated: {len(items)}")
for (tab, grp), entries in sorted(buckets.items()):
    print(f"  {tab:5} {grp:10} lines aside, items: {len(entries)}")
