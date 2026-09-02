# Builders catalog divider + Cartier store import

**Date:** 2026-09-01
**Branch:** beta (beta-first; prod promotion is a later, manual step)

## Goal

Two related changes to the **Builders** catalog tab (page `912362`, staff-only, `min_rank=2`):

1. Add a **visual divider** at the bottom of the Builders navigation list, separating the
   built-in builder categories from new store sections.
2. Add a new **Cartier** category below the divider and import the 25 furni in
   `~/Downloads/Cartier Store` (`Habblet_carter_01`..`26`, no `19`) into it.

## Part A — Divider

There is no native divider in the catalog navigation: every page renders as a clickable
icon+text row (`CatalogNavigationItemView.tsx`). We add one, keyed on an invisible sentinel
that already reaches the client with **zero emulator/renderer changes**.

The catalog index wire writes each page's `page_link` as `NodeData.pageName`
(`CatalogIndexComposer.cs:73` → `CatalogNode.ts` → `node.pageName`), independent of the
visible caption (`localization`).

- **DB page** (child of Builders `912362`): id `912374`, `page_link='divider'`,
  `caption='-'`, `visible=1`, `enabled=0`, `min_rank=2`, `min_vip=0`, `order_num=1000`
  (immediately after Bots `@999`), `page_layout='default_3x3'` (unused). No children, no items.
  `enabled=0` means the index emits it via `WriteNodeIndex` with `pageId=-1` (non-loadable).
- **Client patch** (`client/` submodule): in `CatalogNavigationItemView.tsx`, when
  `node.pageName === 'divider'`, render a non-clickable separator (styled `Base`, not
  `LayoutGridItem`) instead of the clickable row. Add matching SCSS
  (`nitro-catalog-navigation-divider`). Rebuild with `docker/nitro/build-client.sh`.

## Part B — Cartier category + furni import

Follows the established custom-furni import procedure (assets + FurnitureData + DB rows).

### Catalog page
`Cartier` under Builders `912362`: id `912375`, `caption='Cartier'`,
`page_layout='default_3x3'`, `min_rank=2`, `min_vip=0`, `order_num=1001` (below the divider),
`visible=1`, `enabled=1`, `icon_image=193` (reused Builders icon).

### furniture rows — ids 100010–100034 (verified free in `furniture` and `FurnitureData.json`)
- `item_name=Habblet_carter_NN`, `public_name='Cartier 01'..'Cartier 25'` (generic first pass;
  rename pass to follow after in-game review), `sprite_id=id`, `type='s'`.
- `interaction_type='default'`, `interaction_modes_count`= each item's real multistate count
  (extracted from the size-64 visualization; ranges 1–12).
- `width`/`length` from each bundle's logic dimensions. Non-1×1: `carter_08/15/26`=2×1,
  `carter_14/21`=2×2; rest 1×1.
- `can_stack=1`, `can_sit=0`, `is_walkable=0`, `allow_trade=1`, `allow_gift=1`,
  `allow_marketplace_sell=0`, `allow_recycle=0`, `is_rare=0`.

Bundle → id → dims → states:

| bundle | id | dims | states |
|---|---|---|---|
| carter_01 | 100010 | 1×1 | 6 |
| carter_02 | 100011 | 1×1 | 6 |
| carter_03 | 100012 | 1×1 | 5 |
| carter_04 | 100013 | 1×1 | 5 |
| carter_05 | 100014 | 1×1 | 7 |
| carter_06 | 100015 | 1×1 | 3 |
| carter_07 | 100016 | 1×1 | 4 |
| carter_08 | 100017 | 2×1 | 2 |
| carter_09 | 100018 | 1×1 | 4 |
| carter_10 | 100019 | 1×1 | 3 |
| carter_11 | 100020 | 1×1 | 7 |
| carter_12 | 100021 | 1×1 | 12 |
| carter_13 | 100022 | 1×1 | 12 |
| carter_14 | 100023 | 2×2 | 4 |
| carter_15 | 100024 | 2×1 | 3 |
| carter_16 | 100025 | 1×1 | 2 |
| carter_17 | 100026 | 1×1 | 10 |
| carter_18 | 100027 | 1×1 | 2 |
| carter_20 | 100028 | 1×1 | 4 |
| carter_21 | 100029 | 2×2 | 3 |
| carter_22 | 100030 | 1×1 | 6 |
| carter_23 | 100031 | 1×1 | 1 |
| carter_24 | 100032 | 1×1 | 6 |
| carter_25 | 100033 | 1×1 | 4 |
| carter_26 | 100034 | 2×1 | 2 |

### catalog_items rows — ids 9120010–9120034, page `912375`
- `item_id=furniture.id`, `catalog_name=public_name`, coin-only pricing
  `cost_credits = min(3 + 2*(tiles−1), 15)` → 1×1=3, 2×1=5, 2×2=9; `cost_pixels=0`,
  `cost_diamonds=0`, `amount=1`, `offer_active=1`.

### Assets (gitignored — beta rsync now, prod later)
- Copy 25 `.nitro` → `nitro/assets/bundled/furniture/`.
- Add 25 `roomitemtypes` entries to `nitro/assets/gamedata/FurnitureData.json`
  (`id=sprite_id`, `classname=Habblet_carter_NN`, dims, `category`, sensible defaults).
- Extract 25 icons → `nitro/assets/dcr/hof_furni/icons/Habblet_carter_NN_icon.png`
  (reuse `extract-furni-icons.py` logic for just these bundles).

### Delta SQL
`emulator/Resources/SQLs/Updates/59_CartierStore.sql`, idempotent:
- `INSERT IGNORE` Builders parent guard; delete-then-insert pages `912374`/`912375`;
  delete-then-insert `furniture` ids `100010–100034`; delete `catalog_items` by
  `page_id=912375` (and id range), re-insert.

## Out of scope / notes
- Naming: generic `Cartier NN` now; friendly rename pass after in-game verification.
- Emulator caches catalog + furni defs at boot → restart emulator; hard-reload client.
- Prod promotion (later): rsync only the changed `nitro/assets/` files + replay the SQL
  update; do not clobber prod's renderer config. See memory `pixelrp-nongit-deploy-items`.
- CHANGELOG.md entry required (player-facing).
