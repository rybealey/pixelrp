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
