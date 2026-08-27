#!/usr/bin/env python3
"""Generate an idempotent SQL update that creates emulator `furniture` rows
for every official furni that has no row yet.

Source of truth: the official furnidata at /tmp/fd.json (fetch it first, see
the plan). The set of existing item_names comes from /tmp/beta_item_names.txt
(exported from the target DB). One row per furnitype entry (incl. each *color
variant) whose classname is not already an item_name. Mapping is conservative
(type s/i floor/wall, interaction_type='default') so no special furni is
mis-mapped into a junk-delivery bug; sprite_id still links the correct visual.

The emitted SQL stages the candidates then anti-join-inserts on item_name, so
re-running is a no-op and the ~430 legacy/custom rows are never touched.
"""
import json
import os
import glob

OFF = json.load(open('/tmp/fd.json'))
have = {l.strip() for l in open('/tmp/beta_item_names.txt') if l.strip()}
# Only generate rows for furni that can actually render: their base-classname
# bundle must exist on disk (color variants share the base bundle). This skips
# the ~11 board-game / system / upstream-broken items that have no bundle, so
# we never create placeable-but-artless furniture.
BUNDLES = {os.path.basename(p)[:-6]
           for p in glob.glob('nitro/assets/bundled/furniture/*.nitro')}
OUT = 'emulator/Resources/SQLs/Updates/31_FullFurniLibrary.sql'


def esc(s):
    return "'" + str(s).replace("\\", "\\\\").replace("'", "\\'") + "'"


def b(x):
    return "'1'" if x in (1, '1', True) else "'0'"


rows = []
for kind, typ, wall in (('roomitemtypes', 's', False), ('wallitemtypes', 'i', True)):
    for f in OFF[kind]['furnitype']:
        cn = f['classname']
        if cn in have:
            continue
        if cn.split('*')[0] not in BUNDLES:
            continue
        width = 1 if wall else int(f.get('xdim', 1) or 1)
        length = 1 if wall else int(f.get('ydim', 1) or 1)
        sh = 0 if wall else float(f.get('height', 0) or 0)
        rows.append("(" + ",".join([
            esc(cn), esc(str(f.get('name', cn))[:56]), esc(typ),
            str(width), str(length), str(sh),
            b(1), b(f.get('cansiton', 0)), b(f.get('canstandon', 0)),
            str(int(f.get('id', 0) or 0)),
            b(f.get('recyclable', 0)), b(f.get('tradeable', 0)),
        ]) + ")")

cols = ("(item_name,public_name,type,width,length,stack_height,"
        "can_stack,can_sit,is_walkable,sprite_id,allow_recycle,allow_trade)")
with open(OUT, 'w') as o:
    o.write("-- Full Habbo furni library: create furniture rows for every official\n")
    o.write("-- furni not already defined. Idempotent (anti-join on item_name);\n")
    o.write("-- never touches legacy/custom rows. Conservative interaction.\n")
    o.write("DROP TEMPORARY TABLE IF EXISTS _furni_stage;\n")
    o.write(
        "CREATE TEMPORARY TABLE _furni_stage (item_name VARCHAR(70), "
        "public_name VARCHAR(56), type VARCHAR(4), width INT, length INT, "
        "stack_height DOUBLE, can_stack VARCHAR(1), can_sit VARCHAR(1), "
        "is_walkable VARCHAR(1), sprite_id INT, allow_recycle VARCHAR(1), "
        "allow_trade VARCHAR(1));\n")
    for i in range(0, len(rows), 500):
        o.write(f"INSERT INTO _furni_stage {cols} VALUES\n"
                + ",\n".join(rows[i:i + 500]) + ";\n")
    o.write(
        "INSERT INTO furniture\n"
        " (item_name,public_name,type,width,length,stack_height,can_stack,"
        "can_sit,is_walkable,sprite_id,allow_recycle,allow_trade,interaction_type)\n"
        " SELECT s.item_name,s.public_name,s.type,s.width,s.length,s.stack_height,"
        "s.can_stack,s.can_sit,s.is_walkable,s.sprite_id,s.allow_recycle,"
        "s.allow_trade,'default'\n"
        " FROM _furni_stage s\n"
        " WHERE NOT EXISTS (SELECT 1 FROM furniture f WHERE f.item_name = s.item_name);\n"
        "DROP TEMPORARY TABLE _furni_stage;\n")
print(f"wrote {OUT} with {len(rows)} candidate rows")
