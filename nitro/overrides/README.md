# Asset overrides

Files here are rsynced over the server's git-ignored `nitro/assets/` tree on
every beta deploy (same layout: `bundled/effect/…`, `bundled/furniture/…`,
`gamedata/…`). Build effect bundles with `docker/nitro/make-badge-effect.py`.

Two directories, two different mechanisms:

- **`bundled/`, `gamedata/`** — a plain overlay. A file here REPLACES the
  server's file outright, which suits a bundle or a small custom file like
  `EffectMap.json`.
- **`gamedata-override/`** — flat `{key: text}` files whose keys REPLACE what
  the shipped gamedata says. Merging deliberately cannot do that (its whole job
  is protecting the official library), so renaming a shipped string lives here,
  and putting a file in this directory is the deliberate act that says so.
- **`gamedata-merge/`** — fragments, merged into the matching
  `gamedata/<name>.json` on the server by
  `docker/nitro/apply-gamedata-fragments.py` (a deploy step). This exists
  because `FurnitureData.json` holds the whole 18k-entry official library and
  lives only on the server: dropping a fragment into the overlay would wipe it.
  Entries whose classname (or text key) is already present are left alone, so
  the official library always wins and a re-run adds nothing.

## Furniture catalog icons (`dcr/hof_furni/icons/`)

The client fetches `dcr/hof_furni/icons/<classname>_icon.png` (a `*variant`
becomes `<base>_<param>_icon.png`). Two sources, in this order:

1. `docker/nitro/extract-furni-icons.py` crops the icon out of our own `.nitro`
   bundles. Free, and it works for custom furni — but only when the bundle
   actually contains an icon frame, and plenty do not.
2. `habbo-downloader` for the rest:
   ```bash
   npx habbo-downloader -c ficons        # NOT "ficon" - the tool's table is wrong
   ```
   It writes `dcr/hof_furni/<classname>_icon.png` **flat**, while the client
   wants them under `icons/`, so move them. The full set is ~18k files / 121 MB;
   only ever commit the ones the server is actually missing.

A missing icon is silent — the catalog just shows a blank tile — so the way to
find them is to probe `<classname>_icon.png` for every classname in
`FurnitureData.json`. As of 2026-09-08 that was 269 of 18,348 (1.5%), of which
253 existed officially and 16 (Chess, TicTacToe, BattleShip, Poker, post.it,
tile_cursor, floortile ...) have no icon anywhere and never will.

Custom furniture ships as **four** things, and missing any one of them breaks
something quietly:

1. the `.nitro` bundle in `bundled/furniture/`;
2. `<classname>_icon.png` in `dcr/hof_furni/icons/` — the client does NOT take
   the icon from the bundle, even though the converter puts one there.
   `renderer-config`'s `furni.asset.icon.url` is
   `${hof.furni.url}/icons/%libname%%param%_icon.png`, a plain static PNG, so
   without this file the shop shows a blank tile;
3. its `FurnitureData.json` + `ExternalTexts.json` entries in `gamedata-merge/`;
4. the `furniture` / `catalog_items` rows in an emulator SQL update.

All four are generated together — see `docker/nitro/import-kasja.py`.

Note: the prod deploy does not rsync this directory at all; its asset tree is
maintained separately. That has to be resolved before any of this reaches prod.

## Avatar libraries (`bundled/figure/`)

`hh_human_item.nitro` is the handitem library — every item `:carry <id>` can put
in an avatar's hand. It is an overlay file, so the copy here REPLACES the
server's outright; convert a new one from its SWF with
`node ./dist/Main.js --convert-swf` (see `docker/nitro/README.md`) and drop it
in.

**A handitem needs THREE things, not one.** The bundle, a `FigureMap` entry, and
a `CarryItem` parameter — miss any one and it fails silently:

1. the `.nitro` bundle holding `h_crr_ri_<part>_<dir>_<frame>`;
2. `gamedata-merge/FigureMap.json` registering `{"id": <part>, "type": "ri"}`
   under `hh_human_item`, or the client never asks for the asset;
3. `gamedata-merge/HabboAvatarActions.json` adding `{"id": "<carry id>",
   "value": "<part>"}` to `CarryItem` (and `UseItem` for the drink animation).

**`:carry N` does not draw part N.** The renderer maps the id through
`CarryItem`'s parameter list first, and that list covers only ~224 ids. Anything
unmapped falls through to `default = 1` — the cup of water — so an unmapped
handitem renders as a cup with the correct name beside it, which reads as
"nothing happened" rather than as an error. `docker/nitro/gen-handitem-params.py`
generates identity mappings for every part no existing parameter points at.

**The bundle alone does not make a handitem reachable.** The client asks
`FigureMap.json` which library provides part *N* before it fetches anything, so
an id that is in the bundle but not in the map is simply never requested and
`:carry <id>` renders nothing at all — no error, no missing-asset box. Any id a
new library adds has to be registered too, as a `gamedata-merge/FigureMap.json`
fragment listing `{"id": N, "type": "ri"}` under `hh_human_item`. To find what
is missing, list the `ri`/`li` ids in the bundle's asset names
(`h_std_ri_<id>_<dir>_<frame>`) and subtract the ids the map already has.

**Clients cache it for a week.** `renderer-config`'s `avatar.asset.url` ends in
`?v=YYYYMMDD` and nginx serves the assets tree with `max-age=604800`, so
replacing the file does nothing for anyone who already has it until that `v=`
is bumped. That config is VPS-only — excluded from the deploy rsync — so it is
a manual edit on the box, in `nitro/client/renderer-config.json`. A hard reload
gets you the new file for testing without touching it.
