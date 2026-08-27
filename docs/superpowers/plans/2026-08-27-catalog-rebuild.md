# Catalog Rebuild (#3 + #4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Rebuild the beta Furni + Staff catalog into a clean furniline tree exposing the whole library (~12,570 public + ~2,895 staff items), with resolved English names and coin-only pricing; Builders and functional pages untouched.

**Architecture:** Two committed Python generators read furnidata + a live KEEP-set export and emit tracked SQL updates (names → `public_name`; catalog tree → delete-non-KEEP + insert). Dry-run against a throwaway MySQL, then apply on beta via the tracked deploy path.

**Tech Stack:** Python3, MySQL 8 (beta DB), Docker/SSH, emulator submodule SQL updates, GitHub Actions beta deploy.

## Global Constraints

- **Beta only.** No prod, no `main`-branch code beyond the beta branch.
- **Builders (page 912362 + its whole subtree) is off-limits** — never read for writes, never in any DELETE/INSERT. Verified untouched after.
- **No duckets.** No generated `catalog_items` row may set `cost_pixels`; it is always 0. Existing duckets items are re-priced to coins by the rebuild.
- **KEEP set never modified:** Builders subtree, functional-layout pages (marketplace, pets/pets3, bots, guild_*, recycler_info, badge_display, trophies, roomads, info_loyalty, spaces_new, frontpage4), custom PixelRP pages (navigation furni, VIP Silver 6 / Gold 912347), roots Front Page(1)/Furni(9224)/Staff(9225).
- `catalog_items.item_id` = single `furniture.id` (string). `catalog_name` = resolved name. No `catalog_name` may be a literal `"<classname> name"`.
- Classifier priority + pricing formula per the spec (`docs/superpowers/specs/2026-08-27-catalog-rebuild-design.md`). Rares/LTD=25000, NFT=50000 coins.
- No em-dashes in player-facing strings. CHANGELOG entry required (this IS player-facing).
- All generated SQL idempotent and re-runnable. Dry-run before beta.

---

### Task 1: Name resolver → `public_name` SQL (#3)

**Files:**
- Create: `docker/nitro/gen-furni-names.py` (committed)
- Create: `emulator/Resources/SQLs/Updates/32_FurniNames.sql` (committed, in emulator submodule)
- Produces: `/tmp/furni_names.json` (classname → resolved name), consumed by Task 2.

- [ ] **Step 1: Write the resolver + prettifier**

Create `docker/nitro/gen-furni-names.py`: for each furnitype in `/tmp/fd.json`, resolve a name:
`.com` `name` if it is not `"<classname> name"` and non-empty; else prettify the classname —
strip a leading known line/season token (`hween_c26_`, `ranch_c26_`, `nft*_`, etc. via a
`re.sub(r'^(?:[a-z]+_)?c?2?\d*_?', ...)` conservative prefix trim), replace `_`/`*` with spaces,
split camelCase, Title Case. Emit `/tmp/furni_names.json` AND
`emulator/Resources/SQLs/Updates/32_FurniNames.sql` that updates `furniture.public_name` for
every furni whose name resolved (staged + join on `item_name`, idempotent):

```python
#!/usr/bin/env python3
import json, re
OFF = json.load(open('/tmp/fd.json'))
def prettify(cn):
    base = re.sub(r'\*\d+$', '', cn)
    base = re.sub(r'^(hween|xmas|valentines?|easter|summer|spring|autumn|ranch|nft\w*|ltd\d*|duckets|diamond|bonus\w*|hc)_(c?\d{2,4}_)?', '', base)
    base = base.replace('_', ' ').replace('.', ' ')
    base = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', base)
    return ' '.join(w.capitalize() for w in base.split()) or cn
names = {}
for kind in ('roomitemtypes', 'wallitemtypes'):
    for f in OFF[kind]['furnitype']:
        cn = f['classname']; nm = str(f.get('name', '')).strip()
        names[cn] = nm if nm and nm != f"{cn} name" else prettify(cn)
json.dump(names, open('/tmp/furni_names.json', 'w'), ensure_ascii=False)
def esc(s): return "'" + s.replace("\\","\\\\").replace("'","\\'") + "'"
rows = [f"({esc(cn)},{esc(nm[:56])})" for cn, nm in names.items()]
with open('emulator/Resources/SQLs/Updates/32_FurniNames.sql', 'w') as o:
    o.write("DROP TEMPORARY TABLE IF EXISTS _name_stage;\n")
    o.write("CREATE TEMPORARY TABLE _name_stage (item_name VARCHAR(70), nm VARCHAR(56));\n")
    for i in range(0, len(rows), 500):
        o.write("INSERT INTO _name_stage (item_name,nm) VALUES\n" + ",\n".join(rows[i:i+500]) + ";\n")
    o.write("UPDATE furniture f JOIN _name_stage s ON f.item_name=s.item_name SET f.public_name=s.nm;\n")
    o.write("DROP TEMPORARY TABLE _name_stage;\n")
print(f"names: {len(names)}; rows: {len(rows)}")
```

- [ ] **Step 2: Generate + verify no placeholder survives**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
python3 docker/nitro/gen-furni-names.py
python3 -c "import json; n=json.load(open('/tmp/furni_names.json')); ph=[k for k,v in n.items() if v.strip().endswith(' name') and v.split()[0]==k.split('*')[0]]; print('resolved:',len(n),'lingering-placeholder:',len(ph)); print('sample:',list(n.items())[:3])"
```
Expected: ~18,103 names; lingering-placeholder = 0; samples read as real English.

- [ ] **Step 3: Commit (submodule SQL + parent script)**

```bash
cd emulator && git add Resources/SQLs/Updates/32_FurniNames.sql && git commit -m "feat: resolve furni public_name for the full library" && git push origin pixelrp && cd ..
git add docker/nitro/gen-furni-names.py
git commit -m "tooling: gen-furni-names.py (.com name or prettified classname)"
```

---

### Task 2: KEEP-set + catalog generator → catalog SQL (#4)

**Files:**
- Create: `docker/nitro/gen-catalog.py` (committed)
- Create: `emulator/Resources/SQLs/Updates/33_CatalogRebuild.sql` (committed, submodule)
- Consumes: `/tmp/fd.json`, `/tmp/furni_names.json`, `/tmp/beta_item_names.txt` (furniture rows), `/tmp/keep_pages.txt`.

**Interfaces:**
- Consumes: `/tmp/furni_names.json` (Task 1). Produces the catalog SQL applied in Task 4.

- [ ] **Step 1: Export the live KEEP set + furniture id map from beta**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
# Builders subtree ids (recursive), functional-layout pages, custom pages, roots
ssh 67.219.109.182 'docker exec pixelrp-beta-db-1 sh -c '"'"'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -N -uroot "$MYSQL_DATABASE" -e "
WITH RECURSIVE b AS (SELECT id FROM catalog_pages WHERE id=912362 UNION ALL SELECT p.id FROM catalog_pages p JOIN b ON p.parent_id=b.id)
SELECT id FROM b
UNION SELECT id FROM catalog_pages WHERE page_layout NOT IN (\"default_3x3\",\"default_3x3_color_grouping\")
UNION SELECT id FROM catalog_pages WHERE id IN (1,9224,9225,6,912347);
"'"'"'' 2>/dev/null | sort -u > /tmp/keep_pages.txt
wc -l /tmp/keep_pages.txt
# furniture id per classname (item_name -> id) for item_id linkage
ssh 67.219.109.182 'docker exec pixelrp-beta-db-1 sh -c '"'"'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -N -uroot "$MYSQL_DATABASE" -e "SELECT item_name, id FROM furniture;"'"'"'' 2>/dev/null > /tmp/furni_id_map.tsv
wc -l /tmp/furni_id_map.tsv
```
Expected: keep_pages has the Builders subtree + ~22 functional + custom + roots; furni_id_map ~18,577 rows.

- [ ] **Step 2: Write the generator**

Create `docker/nitro/gen-catalog.py`. Load furnidata, names, furni id map, keep set. Classify
each furni (spec §B, incl. `test_`/`ads_` exclude). Build the page tree under two reused roots
(Furni 9224, Staff 9225): thematic parents (Seasonal, Themed Lines, Classics, Functional▸{Wired,
Games,Pets,Sound}, Misc) and Staff parents (Rares, NFT, LTD); one page per furniline (lines with
<5 items merged into a per-parent "More <parent>" page). Assign generated page ids from
`MAX(existing)+1` upward in the script (read a base via a placeholder the SQL resolves with a
variable), OR emit pages first and resolve item `page_id` via a `caption`+`parent` join in SQL.
Price via spec §C (coins; `cost_pixels`=0). One `catalog_items` row per non-excluded furni,
`item_id`=furniture.id, `catalog_name`=resolved name. Emit
`emulator/Resources/SQLs/Updates/33_CatalogRebuild.sql`:

1. `DELETE FROM catalog_items WHERE page_id NOT IN (<keep>);`
2. `DELETE FROM catalog_pages WHERE parent_id IN (9224,9225) AND id NOT IN (<keep>);`
   (plus their orphaned descendants — delete by computed non-keep id list, never a keep id, never Builders)
3. Insert generated parent pages, then line pages (parent_id via the parents' new ids), then items.

Use a staging/`@var` approach so generated page ids are stable within the run and items link
correctly. The script prints per-bucket counts.

- [ ] **Step 3: Generate + sanity counts**

```bash
python3 docker/nitro/gen-catalog.py
echo "generated item rows: $(grep -cE "VALUES|\),\(" emulator/Resources/SQLs/Updates/33_CatalogRebuild.sql)"
grep -c "cost_pixels" emulator/Resources/SQLs/Updates/33_CatalogRebuild.sql   # sanity: only in column lists, never a nonzero value
```
Expected: generator prints PUBLIC ~12,570 / STAFF ~2,895 / EXCLUDED ~2,638.

---

### Task 3: Dry-run both SQLs against a throwaway MySQL

- [ ] **Step 1: Load real catalog + furniture schema and data into an ephemeral MySQL**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
docker rm -f cat_dryrun >/dev/null 2>&1
docker run --rm -d --name cat_dryrun -e MYSQL_ALLOW_EMPTY_PASSWORD=1 -e MYSQL_DATABASE=t mysql:8.0 >/dev/null
until docker exec cat_dryrun mysqladmin -uroot ping --silent >/dev/null 2>&1; do sleep 2; done
ssh 67.219.109.182 'docker exec pixelrp-beta-db-1 sh -c '"'"'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot "$MYSQL_DATABASE" catalog_pages catalog_items furniture'"'"'' 2>/dev/null > /tmp/cat_dump.sql
docker exec -i cat_dryrun mysql -uroot t < /tmp/cat_dump.sql
```

- [ ] **Step 2: Apply names + catalog SQL; assert invariants**

```bash
bld_before=$(docker exec cat_dryrun mysql -N -uroot t -e "WITH RECURSIVE b AS (SELECT id FROM catalog_pages WHERE id=912362 UNION ALL SELECT p.id FROM catalog_pages p JOIN b ON p.parent_id=b.id) SELECT COUNT(*) FROM catalog_items WHERE page_id IN (SELECT id FROM b);")
docker exec -i cat_dryrun mysql -uroot t < emulator/Resources/SQLs/Updates/32_FurniNames.sql
docker exec -i cat_dryrun mysql -uroot t < emulator/Resources/SQLs/Updates/33_CatalogRebuild.sql
bld_after=$(docker exec cat_dryrun mysql -N -uroot t -e "WITH RECURSIVE b AS (SELECT id FROM catalog_pages WHERE id=912362 UNION ALL SELECT p.id FROM catalog_pages p JOIN b ON p.parent_id=b.id) SELECT COUNT(*) FROM catalog_items WHERE page_id IN (SELECT id FROM b);")
echo "Builders items before=$bld_before after=$bld_after (MUST be equal)"
echo "duckets rows: $(docker exec cat_dryrun mysql -N -uroot t -e "SELECT COUNT(*) FROM catalog_items WHERE cost_pixels>0;") (MUST be 0)"
echo "placeholder catalog_names: $(docker exec cat_dryrun mysql -N -uroot t -e "SELECT COUNT(*) FROM catalog_items WHERE catalog_name REGEXP ' name$';") (MUST be 0)"
echo "total catalog_items: $(docker exec cat_dryrun mysql -N -uroot t -e "SELECT COUNT(*) FROM catalog_items;")"
```
Expected: Builders before==after; duckets=0; placeholder=0; total ≈ preserved + ~15,465.

- [ ] **Step 3: Idempotency — apply catalog SQL again, counts unchanged**

```bash
t1=$(docker exec cat_dryrun mysql -N -uroot t -e "SELECT COUNT(*) FROM catalog_items;")
docker exec -i cat_dryrun mysql -uroot t < emulator/Resources/SQLs/Updates/33_CatalogRebuild.sql
t2=$(docker exec cat_dryrun mysql -N -uroot t -e "SELECT COUNT(*) FROM catalog_items;")
echo "idempotent: $t1 == $t2 ?"
docker rm -f cat_dryrun >/dev/null 2>&1
```
Expected: t1 == t2. If any invariant fails, fix the generator and regenerate before Task 4.

- [ ] **Step 4: Commit generator + catalog SQL**

```bash
cd emulator && git add Resources/SQLs/Updates/33_CatalogRebuild.sql && git commit -m "feat: rebuild Furni+Staff catalog for the full library (coin pricing, furniline tree)" && git push origin pixelrp && cd ..
git add docker/nitro/gen-catalog.py
git commit -m "tooling: gen-catalog.py (KEEP-set delete + furniline tree + coin pricing)"
```

---

### Task 4: Deploy to beta + verify + finalize

- [ ] **Step 1: Backup beta catalog tables**

```bash
ssh 67.219.109.182 'docker exec pixelrp-beta-db-1 sh -c '"'"'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot "$MYSQL_DATABASE" catalog_pages catalog_items'"'"'' 2>/dev/null | ssh 67.219.109.182 "cat > /opt/pixelrp-backups/catalog-prerebuild-$(date +%s).sql" 2>/dev/null || echo "run backup inline on the box"
```
(If the pipe is awkward, run `mysqldump ... > /opt/pixelrp-backups/catalog-prerebuild.sql` directly on the box.)

- [ ] **Step 2: Bump emulator pointer, push beta, watch deploy (applies 32 + 33)**

```bash
cd /Users/rybealey/Documents/Personal/pixelrp/plus
git add emulator && git commit -m "feat: catalog rebuild + furni names on beta (bump emulator)"
git push origin beta
sleep 6; rid=$(gh run list --workflow=deploy-beta.yml -L1 --json databaseId --jq '.[0].databaseId')
gh run watch "$rid" --exit-status --interval 10
```
Expected: green; "Apply database patches" applies 32_FurniNames + 33_CatalogRebuild.

- [ ] **Step 3: Verify on beta (same invariants as dry-run, live)**

```bash
ssh 67.219.109.182 'docker exec pixelrp-beta-db-1 sh -c '"'"'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot "$MYSQL_DATABASE" -e "
SELECT \"catalog_items:\", COUNT(*) FROM catalog_items;
SELECT \"duckets rows (must 0):\", COUNT(*) FROM catalog_items WHERE cost_pixels>0;
SELECT \"placeholder names (must 0):\", COUNT(*) FROM catalog_items WHERE catalog_name REGEXP \" name$\";
SELECT \"Club/Exchange gone (must 0):\", COUNT(*) FROM catalog_pages WHERE id IN (5,7,8,46,13);
SELECT \"Builders intact:\", COUNT(*) FROM catalog_pages WHERE id=912362 OR parent_id=912362;
"'"'"'' 2>&1 | grep -v "Permanently added"
```

- [ ] **Step 4: In-client check (hand to user)**

Log into beta and confirm: the Furni tab shows the new thematic tree (Seasonal / Themed Lines /
Classics / Functional / Misc); open a Seasonal page, **buy a sample item in coins** (balance
drops, item delivered, places + renders); the Staff tab (rank ≥5) shows Rares/NFT and is hidden
from a regular account; Club/Exchange are gone; Builders looks unchanged. (Manual in-game test
per project preference.)

- [ ] **Step 5: CHANGELOG + memory**

```bash
# CHANGELOG: new dated section, Added: "The catalog is stocked with thousands more furni"
# + "Shop reorganized"; Changed: "Prices now in coins" (mention duckets retired). No em-dashes.
git add CHANGELOG.md && git commit -m "docs: changelog - full furni catalog + shop reorg on beta"
git push origin beta
```
Then update memory: catalog rebuilt on beta (full library buyable, coin-only, furniline tree,
Club/Exchange removed, Builders untouched); epic complete on beta, main-merge pending user.

---

## Self-Review

**Spec coverage:** §A preserve/rebuild→Task2 KEEP-set; §B classifier→Task2; §C pricing→Task2;
§D names→Task1; §E idempotency→Task2/Task3 idempotency check. Removals (Club/Exchange/duckets)
→Task2 delete + Task4 verify. Builders-untouched invariant→Task3 Step2 + Task4 Step3. All covered.

**Placeholder scan:** generators contain real code; the one deferred detail (exact page-id
linkage via `@var`/join) is described with the mechanism, resolved concretely when writing
`gen-catalog.py` in Task 2 Step 2 and proven by the Task 3 dry-run. Pricing/classifier values
are exact.

**Type consistency:** `/tmp/furni_names.json` produced Task 1, consumed Task 2. `item_id` =
`furniture.id` throughout. `cost_pixels`=0 invariant asserted in Task 3 + Task 4. KEEP set
(`/tmp/keep_pages.txt`) built Task 2 Step 1, used in the DELETEs. 32/33 SQL numbers consistent.
