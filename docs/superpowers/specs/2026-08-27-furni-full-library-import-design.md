# Furni Full-Library Import (Subsystem #2)

**Date:** 2026-08-27
**Branch:** `beta` (assets rsync'd to beta VPS; furniture rows applied to beta DB only)
**Scope:** Subsystem #2 of the furni/catalog epic. Make the entire ~13.6k Habbo furni
library *exist and render and be placeable* in-game. Titles/descriptions polish and
pricing = #3; catalog organization = #4. The Builders catalog category is off-limits
across the whole epic.

## Problem / current state (measured 2026-08-27, beta)

- **13,581** `.nitro` furniture bundles on disk (render client-side), produced Aug 7 by
  `billsonnn/nitro-converter`.
- **`FurnitureData.json`** defines 18,103 furnitype entries (17,267 floor + 836 wall),
  incl. 4,793 `*color` variants; names/descriptions/categories already populated (and
  rebranded PixelRP by `rename-habbo-to-pixelrp.py`).
- **Emulator `furniture` table: only 7,139 rows.** So ~11k furni have bundles + client
  defs but **no DB row — they cannot be placed or owned in-game.**
- Current official furnidata (`www.habbo.com/gamedata/furnidata_json`, reachable via a
  307→200 redirect) lists **156 furni we don't have at all** (Halloween/autumn 2026) and
  **178 base classnames with no local bundle** (the 156 new + ~22 that failed the Aug 7
  conversion).

## Goals

1. Every furni in the official library exists in-game: renders, is placeable, owned,
   tradeable, with a baseline `public_name`/description from furnidata.
2. Bring assets current: convert the 178 missing bundles; fix render/placement breakage.
3. Authoritative catalog icons for the new/broken/gap items.
4. Apply to **beta only**.

## Non-goals

- No catalog placement, pricing, or name/description polish (that's #3/#4). New furni are
  **not** added to any `catalog_page` here — they exist but aren't shopabble yet.
- Do **not** regenerate/overwrite the customized `FurnitureData.json` / `ExternalTexts.json`
  (would revert the PixelRP rebrand + in-place fixes). Merge new entries only.
- Do **not** touch the 430 legacy/custom DB rows (custom navigation furni 100001–100005 +
  old Arcturus/Habboon imports).
- No prod changes.
- The **Builders** category is untouched.

## Design — six steps (produced locally, deployed to beta)

### Step 1 — Convert the 178 missing bundles (`nitro-converter`)

- Clone `billsonnn/nitro-converter`, `yarn install && yarn build`. Configure to
  self-discover from `www.habbo.com` (the documented empty-config pattern; endpoint
  confirmed reachable).
- **Seed its furniture output dir with the existing 13,581 bundle filenames** (hardlink/copy)
  so the converter *skips* them and downloads/converts only the ~178 missing furniture
  (converter skips existing outputs — verified behavior). Ignore its figure/effect/pet/gamedata output.
- Copy **only the newly-produced `.nitro` bundles** into `nitro/assets/bundled/furniture/`.
  Nothing else from the converter's output enters the repo.
- Post-copy: `fix-bundle-compression.py` then `fix-dangling-sources.py` on the new bundles
  (renderer requires zlib entries + non-dangling aliases).

### Step 2 — Merge new client defs (156)

- Append the 156 new furnitype entries to `nitro/assets/gamedata/FurnitureData.json`
  (correct floor/wall array), and their `<classname>_name` / `<classname>_desc` keys to
  `ExternalTexts.json`. Then run `rename-habbo-to-pixelrp.py` (idempotent) so new text is
  rebranded consistently. All other ~11k already have client defs — untouched.

### Step 3 — Generate emulator `furniture` rows (11,394)

One row per official furnitype entry (incl. each `*N` variant) that has no DB row.
Deterministic map furnidata → `furniture`:

| furniture column | source | notes |
|---|---|---|
| `item_name` | `classname` (with `*`) | natural key |
| `public_name` | `name` | baseline; #3 polishes |
| `type` | `'s'` floor / `'i'` wall | **conservative**; special types refined later |
| `width` / `length` | `xdim` / `ydim` (floor); `1`/`1` (wall) | |
| `stack_height` | `height` (floor) else `0` | |
| `can_sit` | `cansiton` | |
| `is_walkable` | `canstandon` | |
| `can_stack` | `canputstuffon` (fallback `1`) | |
| `sprite_id` | `id` | links bundle/icon |
| `allow_recycle` / `allow_trade` | `recyclable` / `tradeable` | |
| `interaction_type` | `'default'` | **conservative** — no special behavior mapping in #2 |
| all others | table defaults | |

- Emitted as an **idempotent** SQL update in `emulator/Resources/SQLs/Updates/`. Mechanism:
  the ~11,394 candidate rows are staged, then inserted via an **anti-join** —
  `INSERT INTO furniture (...) SELECT ... FROM <staging> s WHERE NOT EXISTS (SELECT 1 FROM
  furniture f WHERE f.item_name = s.item_name)`. Re-running inserts nothing already present
  and **never touches the 430 legacy rows** (their classnames aren't in the candidate set by
  construction). `furniture.id` is a plain auto-increment PK (≠ `sprite_id`; no unique index
  on `item_name`), so ids are assigned once on first apply and stay stable thereafter — **#4
  queries the actual post-insert ids** rather than assuming a deterministic id. Auto-applies
  on deploy (tracked in `_applied_sql_updates`).
- **Rationale for conservative interaction:** wrong `type`/`interaction_type` on special
  furni (pets, effects, dispensers, teleporters) causes junk-delivery / broken-placement
  bugs. Plain placeable is always safe: the item renders and places; special behavior is a
  later, opt-in refinement. `sprite_id` still links the correct visual.

### Step 4 — Repair sweep (all bundles)

`python3 docker/nitro/fix-bundle-compression.py nitro/assets` then
`fix-dangling-sources.py nitro/assets` across the whole tree (idempotent) — catches
"functionally broken when placed" / render breakage without a hand list.

### Step 5 — Icons (targeted, authoritative)

- Run `habbo-downloader --command furnitures` (or `ficons`) scoped to fetch official
  `_icon.png` for the new/missing/broken items + the known ~2% coverage gaps (multi-part
  sets, board games). Place under `dcr/hof_furni/icons/`.
- `extract-furni-icons.py` for the 178 new bundles; `fetch-variant-icons.py` if new
  `*variant` classnames appeared. Leave the working 98% as-is.

### Step 6 — Deploy to beta

- `rsync -az` only the changed files under `nitro/assets/` (new `.nitro` + new icons) to
  `/opt/pixelrp-beta/nitro/assets/` — **never** the whole `nitro/` tree (would clobber the
  beta `renderer-config.json` wss endpoint).
- Apply the Step-3 SQL to the beta DB (`docker exec pixelrp-beta-db-1 …`, by container name).
- Restart the beta emulator (furni defs cached at boot). Hard-reload client.

## Verification

- `furniture` row count rises by 11,394; the 430 legacy rows unchanged; spot-check 10
  generated rows (dimensions/sit/walk vs furnidata).
- In-client (beta): several newly-added furni (a plain floor item, a wall item, a sittable,
  a new Halloween item) render in the catalog-independent path and **place correctly** in a
  test room — no junk/placeholder. New bundles serve 200 with `application/octet-stream`.
- `FurnitureData.json` still contains the PixelRP rebrand (grep a known rebranded string);
  no Habbo branding reintroduced.
- Repair scripts report clean (no remaining dangling sources on the new bundles).

## Risks & mitigations

- **Row-generation correctness** → conservative type/interaction; validate a sample
  in-game before trusting the full 11,394 apply; SQL is idempotent so a corrected re-run is safe.
- **Gamedata clobbering** → converter output is cherry-picked (bundles only); gamedata
  merged by script, never overwritten; rebrand re-run after.
- **Habbo WAF (463)** → transient; node-fetch follows the 307 redirect; retry/backoff.
  Asset CDN (`images.habbo.com`) confirmed unblocked.
- **Wrong rsync scope** → explicit file-list rsync under `nitro/assets/` only.
- **Deploy** → beta only; prod compose files untouched.

## Rollback

- Bundles/icons are additive files — deletable. `FurnitureData.json`/`ExternalTexts.json`
  changes are a scripted, revertable diff (git-ignored, so keep a pre-merge copy).
- The furniture-row SQL is a single tracked update; a companion `DELETE FROM furniture WHERE
  item_name IN (…)` (the 11,394 generated names — disjoint from the 430 legacy names) cleanly
  reverses it without touching legacy rows. Run before #4 wires catalog references; after #4,
  reverse #4 first.

## Execution order

1. Snapshot beta `furniture` count. 2. nitro-converter → 178 bundles → repair. 3. Merge 156
client defs + rebrand. 4. Generate + write the furniture-row SQL. 5. Repair sweep + icons.
6. Deploy to beta, apply SQL, restart, verify in-client. 7. Update CHANGELOG (player-facing:
"lots of new furniture exists in the hotel") + memory.

## Boundary

#2 = exists + renders + placeable (furniture rows, baseline names). **#3** = titles/
descriptions + pricing. **#4** = catalog organization + placement (catalog_items, pages).
