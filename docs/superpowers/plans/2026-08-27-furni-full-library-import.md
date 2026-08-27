# Furni Full-Library Import (#2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the entire ~13.6k Habbo furni library exist, render, and be placeable in-game on beta — 178 new bundles converted, 156 new client defs merged, 11,394 emulator `furniture` rows generated — without exposing anything in the catalog yet.

**Architecture:** Produce assets + gamedata locally, generate an idempotent SQL update for the emulator `furniture` table, rsync the git-ignored assets to the beta VPS, and let the tracked SQL apply on a beta deploy. Nothing is added to any catalog page (that's #4); pricing/name polish is #3.

**Tech Stack:** `billsonnn/nitro-converter` (Node/yarn, SWF→.nitro), `higoka/habbo-downloader` (official icons), Python3 (Pillow) for the repo's existing furni scripts, MySQL 8 (beta DB), Docker/SSH, GitHub Actions beta deploy.

## Global Constraints

- Apply to **beta only**. No prod compose files, no prod DB, no `main`-branch code changes.
- The **Builders** catalog category is off-limits — never read, write, or reference it.
- **Never regenerate/overwrite** `nitro/assets/gamedata/FurnitureData.json` or `ExternalTexts.json` wholesale — merge new entries only (preserves the PixelRP rebrand + in-place fixes).
- **Never touch the 430 legacy/custom `furniture` rows** (custom navigation furni + old Arcturus imports). All inserts are anti-joined on `item_name`.
- rsync **only changed files under `nitro/assets/`** to beta — never the whole `nitro/` tree (would clobber beta's `renderer-config.json` wss endpoint).
- VPS DB access is **by container name**: `docker exec pixelrp-beta-db-1 sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot "$MYSQL_DATABASE" ...'` (never `compose exec` from a cwd — project-resolution trap).
- Committed artifacts: **scripts** (`docker/nitro/*`) and the **SQL update** (`emulator/Resources/SQLs/Updates/*`). Asset outputs under `nitro/assets/` are git-ignored and shipped by rsync, never committed.
- No em-dashes in any player-facing string. Every player-facing change gets a CHANGELOG entry.
- Conservative interaction: generated rows use `type` s/i (floor/wall) and `interaction_type='default'`. No special-behavior mapping in #2.

---

### Task 1: Convert the 178 missing `.nitro` bundles (nitro-converter, furniture-only)

**Files:**
- Create (scratch, outside repo): `~/scratch/nitro-converter/` checkout + `configuration.json`
- Modify (git-ignored, via copy): `nitro/assets/bundled/furniture/*.nitro` (new bundles only)

**Interfaces:**
- Produces: the set of new bundle filenames `NEW_BUNDLES` (the ~178 classnames with no prior bundle), used by Task 4 (icons) and Task 5 (rsync manifest).

- [ ] **Step 1: Record the pre-state (the 178 must be absent)**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
python3 - <<'PY'
import json, os, glob
L = json.load(open('/tmp/fd.json'))  # current official furnidata (re-fetch if stale, see Step 2)
off_base = {f['classname'].split('*')[0] for f in L['roomitemtypes']['furnitype']} | {f['classname'].split('*')[0] for f in L['wallitemtypes']['furnitype']}
bundles = {os.path.basename(p)[:-6] for p in glob.glob('nitro/assets/bundled/furniture/*.nitro')}
missing = sorted(off_base - bundles)
open('/tmp/missing_bundles.txt','w').write('\n'.join(missing))
print("missing base classnames with no bundle:", len(missing))
PY
```
Expected: prints ~178. `/tmp/missing_bundles.txt` written.

- [ ] **Step 2: Refresh official furnidata (WAF-safe) and re-run Step 1 if the count drifted**

```bash
curl -sSL -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36" \
  "https://www.habbo.com/gamedata/furnidata_json/1" -o /tmp/fd.json
python3 -c "import json;d=json.load(open('/tmp/fd.json'));print('official types:',len(d['roomitemtypes']['furnitype'])+len(d['wallitemtypes']['furnitype']))"
```
Expected: HTTP follows 307→200; prints ~18,103 (follow with Step 1 re-run).

- [ ] **Step 3: Clone + build nitro-converter**

```bash
mkdir -p ~/scratch && cd ~/scratch
git clone --recurse-submodules https://github.com/billsonnn/nitro-converter.git
cd nitro-converter && cp configuration.json.example configuration.json
yarn install && yarn build
```
Expected: build succeeds, `dist/` present.

- [ ] **Step 4: Configure furniture-only + seed output so existing bundles are skipped**

Set these keys in `~/scratch/nitro-converter/configuration.json` (leave `flash.client.url`, `furnidata.load.url`, `productdata.load.url` blank for auto-discovery; set `figuredata.load.url` and `external.variables.url` to the `www.habbo.com` endpoints as in the repo's `docker/nitro/README.md` Step 3b):

```json
"convert.figure": "0",
"convert.effect": "0",
"convert.pet": "0",
"convert.furniture": "1"
```

Seed the converter's furniture output dir with the 13,581 existing bundle *filenames* (0-byte touch is enough — the converter skips a class if its output filename already exists):

```bash
OUT=~/scratch/nitro-converter/assets/bundled/furniture
mkdir -p "$OUT"
for f in /Users/rybealey/Documents/Personal/pixelrp/plus/nitro/assets/bundled/furniture/*.nitro; do
  touch "$OUT/$(basename "$f")"
done
ls "$OUT" | wc -l   # expect ~13,581
```
Expected: ~13,581 seed files.

- [ ] **Step 5: Run the conversion (furniture only, ~178 real conversions)**

```bash
cd ~/scratch/nitro-converter && yarn start 2>&1 | tee /tmp/converter.log | tail -20
```
Expected: it downloads furnidata, skips ~13,581 existing, converts ~178 new furniture SWF→.nitro. Non-fatal "Invalid SWF" skips for a handful are acceptable (pre-existing official quirks).

- [ ] **Step 6: Copy ONLY the newly-produced (non-zero-byte) bundles into the repo**

```bash
cd ~/scratch/nitro-converter/assets/bundled/furniture
REPO=/Users/rybealey/Documents/Personal/pixelrp/plus/nitro/assets/bundled/furniture
new=0
for f in *.nitro; do
  if [ -s "$f" ] && [ ! -f "$REPO/$f" ]; then cp "$f" "$REPO/$f"; new=$((new+1)); fi
done
echo "copied new bundles: $new"
```
Expected: prints roughly the missing count (≤178; some official furni have no SWF and stay missing — that's fine).

- [ ] **Step 7: Repair the new bundles (compression + dangling sources)**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
python3 docker/nitro/fix-bundle-compression.py nitro/assets
python3 docker/nitro/fix-dangling-sources.py nitro/assets
```
Expected: reports any gzip→zlib re-encodes and alias remaps; furniture "unresolved" lines are expected (furni bundles use a different key format, intentionally untouched).

- [ ] **Step 8: Verify a new bundle parses**

```bash
python3 - <<'PY'
import glob, os, struct, zlib
REPO='nitro/assets/bundled/furniture'
missing=set(open('/tmp/missing_bundles.txt').read().split())
got=[b for b in missing if os.path.exists(f"{REPO}/{b}.nitro")]
print("new bundles now present:", len(got), "of", len(missing))
# parse the first one's container header
p=f"{REPO}/{got[0]}.nitro"; d=open(p,'rb').read()
n=struct.unpack_from('>H',d,0)[0]
print("sample", got[0], "file-count in container:", n)
PY
```
Expected: prints the count present and a plausible container file-count (>0). No commit (assets are git-ignored).

---

### Task 2: Merge the 156 new client defs into gamedata

**Files:**
- Create: `docker/nitro/merge-new-furnidata.py` (committed)
- Modify (git-ignored): `nitro/assets/gamedata/FurnitureData.json`, `nitro/assets/gamedata/ExternalTexts.json`

**Interfaces:**
- Consumes: `/tmp/fd.json` (official furnidata), current local `FurnitureData.json`.
- Produces: updated local gamedata with the new entries, rebranded.

- [ ] **Step 1: Write the merge script**

Create `docker/nitro/merge-new-furnidata.py`: load official `/tmp/fd.json` and local `nitro/assets/gamedata/FurnitureData.json`; compute the set of classnames present in official but absent locally; append those furnitype dicts to the correct `roomitemtypes`/`wallitemtypes` array; for each, add `<classname>_name` and `<classname>_desc` keys to `ExternalTexts.json` from the official entry's `name`/`description` (only if absent). Print counts. Idempotent (skips entries already present).

```python
#!/usr/bin/env python3
import json, sys
OFF = json.load(open('/tmp/fd.json'))
FD_PATH = 'nitro/assets/gamedata/FurnitureData.json'
ET_PATH = 'nitro/assets/gamedata/ExternalTexts.json'
fd = json.load(open(FD_PATH))
et = json.load(open(ET_PATH))

def merge(kind):
    local = fd[kind]['furnitype']
    have = {f['classname'] for f in local}
    added = 0
    for f in OFF[kind]['furnitype']:
        if f['classname'] not in have:
            local.append(f)
            nk, dk = f"{f['classname']}_name", f"{f['classname']}_desc"
            if nk not in et: et[nk] = f.get('name', f['classname']); 
            if dk not in et: et[dk] = f.get('description', '')
            added += 1
    return added

a = merge('roomitemtypes'); b = merge('wallitemtypes')
json.dump(fd, open(FD_PATH,'w'), ensure_ascii=False, separators=(',',':'))
json.dump(et, open(ET_PATH,'w'), ensure_ascii=False, separators=(',',':'))
print(f"added floor={a} wall={b} new furnitype entries")
```

- [ ] **Step 2: Snapshot pre-merge (for rollback)**

```bash
cp nitro/assets/gamedata/FurnitureData.json /tmp/FurnitureData.pre.json
cp nitro/assets/gamedata/ExternalTexts.json /tmp/ExternalTexts.pre.json
```

- [ ] **Step 3: Run the merge**

```bash
python3 docker/nitro/merge-new-furnidata.py
```
Expected: "added floor=~150 wall=~6 new furnitype entries" (~156 total).

- [ ] **Step 4: Re-apply the PixelRP rebrand (idempotent) + validate JSON**

```bash
python3 docker/nitro/rename-habbo-to-pixelrp.py
python3 -c "import json; json.load(open('nitro/assets/gamedata/FurnitureData.json')); json.load(open('nitro/assets/gamedata/ExternalTexts.json')); print('gamedata JSON valid')"
grep -c '"a Pixel"' nitro/assets/gamedata/ExternalTexts.json >/dev/null && echo "rebrand present"
```
Expected: JSON valid; rebrand marker still present (not reverted).

- [ ] **Step 5: Verify new count**

```bash
python3 -c "import json,os,glob; d=json.load(open('nitro/assets/gamedata/FurnitureData.json')); print('total furnitype now:', len(d['roomitemtypes']['furnitype'])+len(d['wallitemtypes']['furnitype']))"
```
Expected: ~18,103 (was 17,952).

- [ ] **Step 6: Commit the script only**

```bash
git add docker/nitro/merge-new-furnidata.py
git commit -m "tooling: merge-new-furnidata.py (append new official furni to gamedata)"
```

---

### Task 3: Generate the 11,394 `furniture` rows SQL

**Files:**
- Create: `docker/nitro/gen-furniture-rows.py` (committed)
- Create: `emulator/Resources/SQLs/Updates/31_FullFurniLibrary.sql` (committed, tracked, auto-applies on deploy)

**Interfaces:**
- Consumes: official furnidata (merged local `FurnitureData.json`), current beta `furniture.item_name` list.
- Produces: `31_FullFurniLibrary.sql` — a self-contained, idempotent update.

- [ ] **Step 1: Export current beta furniture item_names**

```bash
ssh 67.219.109.182 'docker exec pixelrp-beta-db-1 sh -c '"'"'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -N -uroot "$MYSQL_DATABASE" -e "SELECT item_name FROM furniture;"'"'"'' > /tmp/beta_item_names.txt
wc -l /tmp/beta_item_names.txt   # ~7,139
```

- [ ] **Step 2: Write the generator**

Create `docker/nitro/gen-furniture-rows.py`. For every furnitype entry in the merged local `FurnitureData.json` whose `classname` is NOT in `/tmp/beta_item_names.txt`, emit a staging row. Map per the spec table. Escape strings. Emit SQL that: creates a staging table, bulk-inserts the candidates, anti-join-inserts into `furniture`, drops staging.

```python
#!/usr/bin/env python3
import json
fd = json.load(open('nitro/assets/gamedata/FurnitureData.json'))
have = {l.strip() for l in open('/tmp/beta_item_names.txt') if l.strip()}
def esc(s): return "'" + str(s).replace("\\","\\\\").replace("'","\\'") + "'"
def b(x): return "'1'" if x in (1,'1',True) else "'0'"
rows = []
for kind, typ, wall in (('roomitemtypes','s',False), ('wallitemtypes','i',True)):
    for f in fd[kind]['furnitype']:
        cn = f['classname']
        if cn in have: continue
        width  = 1 if wall else int(f.get('xdim',1) or 1)
        length = 1 if wall else int(f.get('ydim',1) or 1)
        sh     = 0 if wall else float(f.get('height',0) or 0)
        rows.append("(" + ",".join([
            esc(cn), esc(f.get('name',cn)[:56]), esc(typ),
            str(width), str(length), str(sh),
            b(1), b(f.get('cansiton',0)), b(f.get('canstandon',0)),
            str(int(f.get('id',0) or 0)),
            b(f.get('recyclable',0)), b(f.get('tradeable',0)),
        ]) + ")")
print(f"-- {len(rows)} candidate rows", flush=False)
with open('emulator/Resources/SQLs/Updates/31_FullFurniLibrary.sql','w') as o:
    o.write("-- Full Habbo furni library: create furniture rows for every official\n")
    o.write("-- furni not already defined. Idempotent (anti-join on item_name);\n")
    o.write("-- never touches legacy/custom rows. Conservative interaction.\n")
    o.write("DROP TEMPORARY TABLE IF EXISTS _furni_stage;\n")
    o.write("CREATE TEMPORARY TABLE _furni_stage (item_name VARCHAR(70), public_name VARCHAR(56), type VARCHAR(4), width INT, length INT, stack_height DOUBLE, can_stack VARCHAR(1), can_sit VARCHAR(1), is_walkable VARCHAR(1), sprite_id INT, allow_recycle VARCHAR(1), allow_trade VARCHAR(1));\n")
    # chunk inserts to keep statements under max_allowed_packet
    cols = "(item_name,public_name,type,width,length,stack_height,can_stack,can_sit,is_walkable,sprite_id,allow_recycle,allow_trade)"
    for i in range(0, len(rows), 500):
        o.write(f"INSERT INTO _furni_stage {cols} VALUES\n" + ",\n".join(rows[i:i+500]) + ";\n")
    o.write("""INSERT INTO furniture
 (item_name,public_name,type,width,length,stack_height,can_stack,can_sit,is_walkable,sprite_id,allow_recycle,allow_trade,interaction_type)
 SELECT s.item_name,s.public_name,s.type,s.width,s.length,s.stack_height,s.can_stack,s.can_sit,s.is_walkable,s.sprite_id,s.allow_recycle,s.allow_trade,'default'
 FROM _furni_stage s
 WHERE NOT EXISTS (SELECT 1 FROM furniture f WHERE f.item_name = s.item_name);
DROP TEMPORARY TABLE _furni_stage;
""")
print("wrote emulator/Resources/SQLs/Updates/31_FullFurniLibrary.sql")
```

- [ ] **Step 3: Generate and sanity-check counts**

```bash
python3 docker/nitro/gen-furniture-rows.py
grep -c "^(" emulator/Resources/SQLs/Updates/31_FullFurniLibrary.sql   # ~11,394 value rows
```
Expected: ~11,394.

- [ ] **Step 4: Dry-run against a throwaway MySQL to prove it parses + inserts the right count**

```bash
# spin an ephemeral mysql, load a minimal furniture table, apply the update
docker run --rm -d --name furni_dryrun -e MYSQL_ALLOW_EMPTY_PASSWORD=1 -e MYSQL_DATABASE=t mysql:8.0
until docker exec furni_dryrun mysqladmin -uroot ping --silent 2>/dev/null; do sleep 2; done
# create a furniture table matching prod schema, seed the 7,139 existing item_names, apply
ssh 67.219.109.182 'docker exec pixelrp-beta-db-1 sh -c '"'"'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --no-data "$MYSQL_DATABASE" furniture'"'"'' > /tmp/furniture_schema.sql
docker exec -i furni_dryrun mysql -uroot t < /tmp/furniture_schema.sql
awk 'NR>0' /tmp/beta_item_names.txt | sed "s/'/''/g" | awk '{print "INSERT INTO furniture (item_name,public_name,sprite_id) VALUES (\x27"$0"\x27,\x27x\x27,0);"}' | docker exec -i furni_dryrun mysql -uroot t
before=$(docker exec furni_dryrun mysql -N -uroot t -e "SELECT COUNT(*) FROM furniture;")
docker exec -i furni_dryrun mysql -uroot t < emulator/Resources/SQLs/Updates/31_FullFurniLibrary.sql
after=$(docker exec furni_dryrun mysql -N -uroot t -e "SELECT COUNT(*) FROM furniture;")
echo "before=$before after=$after delta=$((after-before))"
# idempotency: apply again, delta must be 0
docker exec -i furni_dryrun mysql -uroot t < emulator/Resources/SQLs/Updates/31_FullFurniLibrary.sql
again=$(docker exec furni_dryrun mysql -N -uroot t -e "SELECT COUNT(*) FROM furniture;")
echo "after second apply=$again (must equal $after)"
docker rm -f furni_dryrun
```
Expected: `delta=11394`; second apply leaves the count unchanged (idempotent).

- [ ] **Step 5: Spot-check generated values vs furnidata**

```bash
grep -m1 "shelves_norja'" emulator/Resources/SQLs/Updates/31_FullFurniLibrary.sql
```
Expected: dimensions/sit/walk match `shelves_norja` in furnidata (1x1, non-sit, walkable per its flags).

- [ ] **Step 6: Commit generator + SQL**

```bash
git add docker/nitro/gen-furniture-rows.py emulator/Resources/SQLs/Updates/31_FullFurniLibrary.sql
git commit -m "feat: generate furniture rows for the full Habbo furni library (beta)"
```

---

### Task 4: Targeted authoritative icons

**Files:**
- Modify (git-ignored): `nitro/assets/dcr/hof_furni/icons/*.png` (new/gap icons only)

**Interfaces:**
- Consumes: `NEW_BUNDLES` (Task 1), the repo's icon scripts.

- [ ] **Step 1: Extract icons for the new bundles**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
python3 docker/nitro/extract-furni-icons.py
```
Expected: coverage report; new bundles' icons written under `dcr/hof_furni/icons/`.

- [ ] **Step 2: Fill remaining gaps with official icons (habbo-downloader)**

Install once (`npm i -g habbo-downloader`), then fetch official furni icons into a scratch dir and copy only the icons we still lack:

```bash
mkdir -p ~/scratch/hdl && cd ~/scratch/hdl
habbo-downloader -c furnitures -d com -o ./resource 2>&1 | tail -5
# copy only icons missing locally
ICONS=/Users/rybealey/Documents/Personal/pixelrp/plus/nitro/assets/dcr/hof_furni/icons
find ./resource/dcr/hof_furni -name '*_icon.png' | while read f; do
  b=$(basename "$f"); [ -f "$ICONS/$b" ] || cp "$f" "$ICONS/$b"
done
```
Expected: fills the ~2% multi-part/board-game gaps and any new-variant icons. (habbo-downloader auto-follows the furnidata redirect; the CDN is unblocked.)

- [ ] **Step 3: Verify icon coverage for new items**

```bash
python3 - <<'PY'
import os
ICONS='nitro/assets/dcr/hof_furni/icons'
miss=[b for b in open('/tmp/missing_bundles.txt').read().split() if b and not os.path.exists(f"{ICONS}/{b}_icon.png")]
print("new items still without an icon:", len(miss), miss[:10])
PY
```
Expected: 0 or a small handful (multi-part sets with no dedicated icon frame — acceptable). No commit (icons git-ignored).

---

### Task 5: Deploy to beta + apply + verify in-client

**Files:**
- Modify: `CHANGELOG.md` (committed)

- [ ] **Step 1: Snapshot beta furniture count (before)**

```bash
ssh 67.219.109.182 'docker exec pixelrp-beta-db-1 sh -c '"'"'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -N -uroot "$MYSQL_DATABASE" -e "SELECT COUNT(*) FROM furniture;"'"'"''
```
Expected: ~7,139.

- [ ] **Step 2: rsync only changed assets to beta (bundles, icons, gamedata)**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
rsync -az nitro/assets/bundled/furniture/ 67.219.109.182:/opt/pixelrp-beta/nitro/assets/bundled/furniture/
rsync -az nitro/assets/dcr/hof_furni/icons/ 67.219.109.182:/opt/pixelrp-beta/nitro/assets/dcr/hof_furni/icons/
rsync -az nitro/assets/gamedata/FurnitureData.json nitro/assets/gamedata/ExternalTexts.json 67.219.109.182:/opt/pixelrp-beta/nitro/assets/gamedata/
```
Expected: only the new/changed files transfer. (No `--delete`; never rsync the whole `nitro/` tree.)

- [ ] **Step 3: Push the SQL commit to beta and deploy (applies the tracked update)**

A push to `beta` auto-triggers `deploy-beta.yml` (confirmed in subsystem #1) — do not also `gh workflow run` (would double-deploy). Push, then watch the run the push created:

```bash
git push origin beta
sleep 6
rid=$(gh run list --workflow=deploy-beta.yml -L1 --json databaseId --jq '.[0].databaseId')
gh run watch "$rid" --exit-status --interval 10
```
Expected: deploy green; the "Apply database patches" step applies `31_FullFurniLibrary.sql` and records it in `_applied_sql_updates`; emulator restarts (reloads furni defs). Assets are already in place from Step 2's rsync (they are git-ignored and do not ship via the deploy).

- [ ] **Step 4: Verify furniture count (after) + idempotency marker**

```bash
ssh 67.219.109.182 'docker exec pixelrp-beta-db-1 sh -c '"'"'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -N -uroot "$MYSQL_DATABASE" -e "
SELECT \"furniture rows:\", COUNT(*) FROM furniture;
SELECT \"applied?\", filename FROM _applied_sql_updates WHERE filename LIKE \"%31_FullFurniLibrary%\";
"'"'"''
```
Expected: ~18,533 rows (7,139 + 11,394); the update recorded as applied.

- [ ] **Step 5: In-client placement check (beta, hard-reload)**

Log into beta as ClaudeTest, and (staff) verify a few newly-added furni place correctly in a test room: pick one plain floor item, one wall item, one sittable, and one new Halloween item by classname. Confirm each renders (not a placeholder cube) and places on the grid. This is the gate that the conservative row generation is sound before we build the catalog on top of it in #4.

Expected: all four render and place; no junk/placeholder. If any placeholder appears, re-check its bundle (Task 1 repair) and its `sprite_id` in the generated row.

- [ ] **Step 6: CHANGELOG + memory**

```bash
# add a player-facing CHANGELOG entry under a new dated section:
#   "Thousands of new furniture items now exist in the hotel" (Added)
git add CHANGELOG.md && git commit -m "docs: changelog - full furni library exists on beta"
git push origin beta
```
Then update project memory: a new note that the full library is imported on beta (furniture rows generated by `gen-furniture-rows.py` + `31_FullFurniLibrary.sql`), catalog exposure still pending (#4). Link `[[pixelrp-custom-furni-import]]`, `[[pixelrp-nongit-deploy-items]]`.

---

## Self-Review

**Spec coverage:** Step-1 bundles→Task1; Step-2 client-def merge→Task2; Step-3 furniture rows→Task3; Step-4 repair sweep→Task1 Step7; Step-5 icons→Task4; Step-6 deploy→Task5. Boundary (no catalog rows) honored — no task writes `catalog_items`/`catalog_pages`. Builders untouched. All covered.

**Placeholder scan:** every code/SQL step contains real content; no TBD. The conservative-interaction rule is explicit. Icon "small handful may lack a frame" is a measured acceptable outcome, not a placeholder.

**Type consistency:** `NEW_BUNDLES`/`/tmp/missing_bundles.txt` produced in Task 1, consumed in Task 4/5. `31_FullFurniLibrary.sql` produced in Task 3, applied in Task 5. `item_name` anti-join key consistent across Task 3 and rollback. furniture column list identical in staging, insert, and dry-run.
