# Asset overrides

Files here are rsynced over the server's git-ignored `nitro/assets/` tree on
every beta deploy (same layout: `bundled/effect/…`, `bundled/furniture/…`,
`gamedata/…`). Build effect bundles with `docker/nitro/make-badge-effect.py`.

Two directories, two different mechanisms:

- **`bundled/`, `gamedata/`** — a plain overlay. A file here REPLACES the
  server's file outright, which suits a bundle or a small custom file like
  `EffectMap.json`.
- **`gamedata-merge/`** — fragments, merged into the matching
  `gamedata/<name>.json` on the server by
  `docker/nitro/apply-gamedata-fragments.py` (a deploy step). This exists
  because `FurnitureData.json` holds the whole 18k-entry official library and
  lives only on the server: dropping a fragment into the overlay would wipe it.
  Entries whose classname (or text key) is already present are left alone, so
  the official library always wins and a re-run adds nothing.

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

**Clients cache it for a week.** `renderer-config`'s `avatar.asset.url` ends in
`?v=YYYYMMDD` and nginx serves the assets tree with `max-age=604800`, so
replacing the file does nothing for anyone who already has it until that `v=`
is bumped. That config is VPS-only — excluded from the deploy rsync — so it is
a manual edit on the box, in `nitro/client/renderer-config.json`. A hard reload
gets you the new file for testing without touching it.
