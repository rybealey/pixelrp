# Catalog Rebuild: Full-Library Exposure + Reorg (Subsystems #3 + #4)

**Date:** 2026-08-27
**Branch:** `beta` (assets/gamedata rsync'd to beta; catalog SQL applied to beta DB)
**Scope:** Expose the full furni library in a rebuilt catalog with real names and
coin pricing, reorganizing the **Furni** and **Staff** tabs. Combines #3 (names +
pricing) and #4 (catalog org) because you cannot catalog an item without a price
and a name. **Builders is off-limits — never read, write, or reference it.**

## Current state (beta, measured 2026-08-27)

- `furniture`: 18,577 rows (full library exists after #2); ~11k are not catalogued.
- `catalog_pages`: 289 pages, 4 roots — Front Page(1), Furni(9224), Builders(912362,
  off-limits), Staff(9225). 267 are `default_3x3` furni pages; ~22 are functional
  layouts (marketplace, pets, bots, guild, recycler, badge_display, trophies, roomads,
  loyalty/duckets info, frontpage).
- `catalog_items`: 7,634 rows. `item_id` = single `furniture.id` (string); `catalog_name`
  = display name; `cost_credits`/`cost_pixels`(duckets)/`cost_diamonds`. Norm is cheap:
  mode 3 credits; 743 items use duckets, 136 diamonds.
- Legacy cruft: Habboon Club (5 → 7/8/46), Habboon Exchange (13), "Rares to Sort" (201),
  duplicate/messy pages.
- furnidata taxonomy: `category` is 75% `"other"` (unusable); `furniline` has 326 groups
  (usable). Blocks: buildersclub ~2,216 (Builders), nft* ~1,800, rare+bonusrare ~869,
  ad_sales ~374.

## Goals

1. Every catalog-eligible furni is buyable, in a coherent furniline-based tree.
2. Rebuild Furni (public) + Staff (rank ≥5) into one clean structure; retire legacy pages.
3. Real names for everything (resolve ~413 placeholders).
4. Coin-only pricing via a deterministic value-based formula; **duckets eliminated.**

## Non-goals / hard rules

- **Builders (912362 subtree) untouched** — excluded from all reads/writes.
- **No duckets.** No catalog_item may use `cost_pixels`; existing duckets items re-priced
  to coins; duckets-specific pages (info_duckets, Duckets Shop) removed/converted.
- Diamonds retained only for existing diamond items / genuinely VIP-premium; not introduced
  broadly.
- Preserve functional pages and their behavior (marketplace, pets, bots, guild, recycler,
  badge_display, trophies, roomads, VIP, navigation/teleport furni, wired).
- Do not delete `furniture` rows or bundles. This subsystem is catalog + names only.

## Design

### A. Preserve vs rebuild

- **Preserve as-is** (re-parent under the correct tab if needed, keep layout + items):
  all non-`default_3x3` functional pages (marketplace, pets/pets3, bots, guild_*, recycler_info,
  badge_display, trophies, roomads, info_loyalty, spaces_new, frontpage4), plus the custom
  PixelRP pages (navigation furni, VIP Silver/Gold). Builders subtree untouched.
- **Rebuild** the plain furni-browsing pages (the 267 `default_3x3` furni pages) into the
  new furniline tree below. Existing furni items are re-homed by the same classifier, so
  nothing purchasable is lost — just relocated + re-priced in coins.
- **Remove:** Habboon Club (5,7,8,46), Habboon Exchange (13), info_duckets / Duckets Shop
  (50 and its duckets pages), and now-empty legacy pages.

### B. Classifier (furnidata → destination), applied to every furni

Deterministic, in priority order:

1. `classname` starts `ads_` OR `furniline == ad_sales` → **EXCLUDE** (not catalogued).
2. `furniline` starts `buildersclub` → **EXCLUDE** (Builders owns it).
3. `furniline` starts `nft` → **Staff ▸ NFT**.
4. `furniline` in {`rare`,`bonusrare`} OR `rare == true` → **Staff ▸ Rares**.
5. `furniline` contains `ltd` → **Staff ▸ LTD**.
6. `category` in {`wired`,`wired_effect`,`wired_condition`,`wired_add_on`} → **Furni ▸ Functional ▸ Wired**.
7. `category` in {`games`} → **Furni ▸ Functional ▸ Games**; `pets` → **Functional ▸ Pets**;
   `music`,`sound_fx` → **Functional ▸ Sound**.
8. `furniline` matches seasonal regex (`hween|halloween|xmas|christmas|valentine|easter|
   summer|spring|autumn|ranch_c\d|_c2\d`) → **Furni ▸ Seasonal ▸ <line>**.
9. `furniline` in {`classics`,`base`} or classic plastic/wood basics → **Furni ▸ Classics**.
10. has a `furniline` → **Furni ▸ Themed Lines ▸ <line>**.
11. no `furniline` (254) → **Furni ▸ Misc ▸ <category>** (functional-category fallback).

Page caption = prettified line/category (Title Case, underscores→spaces, "PixelRP"
never "Habbo"). Lines with < N items (e.g. <5) are merged into a combined page per parent
to avoid hundreds of near-empty pages. One `catalog_items` row per furni (incl. `*variant`),
`item_id` = `furniture.id`, `catalog_name` = resolved name.

### C. Pricing formula (coins only; deterministic)

```
if destination == Staff/Rares or LTD:  price = 25000
elif destination == Staff/NFT:         price = 50000
else (public furni):
    base   = min(3 + 2*(xdim*ydim - 1), 15)     # 1x1=3, 2x1=5, 2x2=9 … cap 15
    adjust = +5 if category in {bed} ;
             +2 if category in {lighting, music, sound_fx} ;
             set 2 if category in {wired*, games}          # cheap functional
    price  = base + adjust
```
- All in `cost_credits`. `cost_pixels` (duckets) always 0. Existing duckets items are
  re-priced by this formula. Existing diamond items keep `cost_diamonds` (premium).

### D. Names (#3)

- Pull `external_flash_texts` from the 9 regional Habbo domains and merge
  (habbo-downloader `collectAllTexts` logic) → a `<classname>_name` / `_desc` map that
  covers items localized in some region even when `.com` shows a placeholder.
- For every catalog-eligible furni whose name is a placeholder (`"<classname> name"`) or
  empty: update `ExternalTexts.json` (client) and `furniture.public_name` (server), and use
  the resolved name for `catalog_name`. Prettified-classname fallback where no region has it.
- Re-run `rename-habbo-to-pixelrp.py` after, rsync gamedata to beta.

### E. Data model + idempotency

The id space is scattered (existing pages run up to ~912365; a reserved range is unsafe), so
idempotency uses a **keep-list**, not an id range:

- **KEEP set** = the explicit ids of pages we preserve: the whole Builders subtree (912362
  and descendants), all functional-layout pages (marketplace, pets, bots, guild_*,
  recycler_info, badge_display, trophies, roomads, info_loyalty, spaces_new, frontpage4),
  the custom PixelRP pages (navigation furni, VIP Silver/Gold), and the two roots we reuse
  (Furni 9224, Staff 9225, Front Page 1). Computed by walking the tree, never hardcoded blind.
- **Regenerate** = within one transaction: delete every `catalog_pages` row under Furni/Staff
  that is NOT in KEEP, delete every `catalog_items` row whose `page_id` is not in KEEP, then
  insert the freshly generated tree + items. Builders and KEEP pages are never touched.
  Generated pages take fresh auto-increment ids each run; items reference them within the same
  run, and the emulator reloads the whole catalog on restart — so churned ids are harmless.
- Written as a tracked SQL update in the emulator submodule
  (`emulator/Resources/SQLs/Updates/`). The generator is a committed script
  (`docker/nitro/gen-catalog.py`) reading furnidata + the resolved-names map + the live
  KEEP-set export, emitting the SQL. Re-runnable and reviewable.

## Verification

- Row counts: catalog_items rises to ~ (preserved + all catalog-eligible furni); 0 rows with
  `cost_pixels > 0`; Builders subtree row-identical to before.
- In-client (beta): Furni tab shows the new thematic tree; open a Seasonal line, **buy a
  sample item** (coins deducted, item delivered, places + renders); Staff tab shows Rares/NFT
  to a rank ≥5 account and is hidden from a regular account; Club/Exchange/duckets gone.
- No placeholder `"classname name"` remains as a `catalog_name`.
- Builders tab visually unchanged.

## Rollback

- Pre-change `mysqldump` of `catalog_pages` + `catalog_items` taken first (restore = reload).
- The keep-list delete only removes non-KEEP Furni/Staff pages/items; Builders, functional,
  and custom pages are untouched by construction, so a full restore is rarely needed.

## Execution order (high level, detailed in the plan)

1. Backup catalog tables. 2. Resolve names (#3) → gamedata + name map. 3. Build classifier +
pricing generator → catalog SQL (reserved range). 4. Dry-run against a throwaway MySQL loaded
with the real catalog schema; verify counts, no duckets, Builders untouched. 5. Apply to beta,
restart, verify in-client (buy a sample). 6. CHANGELOG (now player-facing: new furni + shop
reorg) + memory.

## Boundary

This is the final subsystem of the epic. After it, the full library is buyable, named, priced
in coins, and organized. Builders remains untouched throughout.
