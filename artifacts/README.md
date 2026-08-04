# artifacts/ — files YOU must supply

Nothing in this folder (except this README and `.gitkeep` markers) is committed
or invented by tooling. If a required file is missing, the stack stops with an
error naming it — it never substitutes anything.

## artifacts/arcturus/ — the emulator build

Place **exactly one** emulator jar here:

    artifacts/arcturus/Habbo-4.0.1-beta-jar-with-dependencies.jar   (name may vary)

Easiest path — build it from the official source in one command:

    ./scripts/build-emulator.sh

(clones the official repo @ ms3-upgrade, patches out the beta build's
interactive 'Press ENTER' gate — which otherwise blocks forever in a container
— and Maven-builds with the same image as upstream CI.)

Alternatively drop a downloaded jar: Arcturus Morningstar 4.0.x has **no formal
GitLab releases** — jars are distributed as GitLab CI artifacts (2-week expiry)
on https://git.krews.org/morningstar/Arcturus-Community (branch `ms3-upgrade`)
and via the 4.0.x announcement threads (DevBest) / Krews Discord. Any 4.0.1+
build for Java 21 works — but note a STOCK beta jar stops at the interactive
gate on every container start (`docker attach pixelrp-emulator-1`, press ENTER,
detach with Ctrl-P Ctrl-Q). If you drop more than one jar here the emulator
refuses to guess and asks you to keep one.

## artifacts/arcturus/plugins/ — NitroWebsockets (REQUIRED)

    artifacts/arcturus/plugins/NitroWebsockets-3.2.jar

Arcturus 4.0.x still has **no built-in websocket support** (verified against
the ms3-upgrade source, 2026-08). The Nitro client can only speak WebSocket, so
this plugin is required. Fetch it with one command:

    make fetch-ws-plugin

(downloads from the official Krews repo:
https://git.krews.org/morningstar/nitrowebsockets-for-ms/-/raw/master/target/NitroWebsockets-3.2.jar)

Compatibility note: the plugin was built against MS 3.x; the plugin APIs it
uses still exist in 4.0.x and the community runs this combination, but it is
not officially blessed. Any other `*.jar` you drop in this folder is also
copied into the emulator's `plugins/` directory at start. This folder is the
single source of truth: on every start the emulator's persisted plugins dir
(`data/emulator/plugins/`) is reconciled to match the jars here, so deleting
or replacing a jar in this folder takes full effect on the next `make up` —
no stale copies linger (plugin config files/subdirs are left alone).

## artifacts/sql/ — database bootstrap (applied ONCE, in this exact order)

    artifacts/sql/01-base.sql               ← Arcturus base schema dump
    artifacts/sql/02-3_5_4-to-3_5_5.sql     ← repo sqlupdates/"Update 3_5_4 to 3_5_5.sql"
    artifacts/sql/03-3_5_5-to-4_0_0.sql     ← repo sqlupdates/"UPDATE 3_5_5 TO 4_0_0.sql"

Rename your files to these exact names — the init script refuses to start with
any of the three missing. Sources:

- Base: the Krews 3.5.5 release bundle (`Morningstar_3.5.5.zip`, "includes base
  database") or whichever Arcturus base dump you use. Avoid the
  `ms4-base-database` repo — it targets the abandoned 4.0-DEVPREVIEW line.
- Updates: the emulator repo's `sqlupdates/` folder on branch `ms3-upgrade`.
- Running a 4.0.2/4.0.3-beta jar? Also drop the matching extras; they run in
  lexical order after the required three:

      artifacts/sql/04-4_0_1-to-4_0_2-beta.sql   ← sqlupdates/"4_0_1_TO_4_0_2-beta.sql"
      artifacts/sql/05-4_0_2-beta-to-4_0_3-beta.sql

Caveat: the updates are not idempotent. If `02` fails on an already-applied
change, your base dump is newer than 3.5.4 — remove the already-applied update
file(s), run `make reset`, and `make up` again.

## artifacts/nitro-assets/ — game assets (served at http://localhost:3000/game-assets)

Drop your Nitro asset pack here (nitro-converter output, or a prebuilt default
asset pack). Two helpers cover the essentials:

- the official Krews default-assets pack (`git.krews.org/nitro/default-assets`)
  supplies `bundled/generic` (incl. the required preloads), basic furniture,
  `images/` and `sounds/`;
- `./scripts/fetch-gamedata.sh` generates the gamedata JSONs from Habbo's live
  endpoints via the official nitro-converter.

Clothing/effect/pet `.nitro` bundles come from converting YOUR SWF pack — see
`artifacts/flash-assets/` below and run:

    make convert-assets

One-shot: converts clothing/effects/pets from the local pack (fast) plus the
full official furniture catalog (downloads from images.habbo.com — the first
run takes a while; re-runs resume, existing outputs are never overwritten).
Failed SWFs are listed in a summary at the end rather than skipped silently. Expected layout — this folder IS the
client's `asset.url` root:

    nitro-assets/
      bundled/
        figure/<lib>.nitro      furniture/<lib>.nitro    pet/<lib>.nitro
        effect/<lib>.nitro      generic/<lib>.nitro
      gamedata/
        FurnitureData.json  ProductData.json  FigureData.json  FigureMap.json
        EffectMap.json  HabboAvatarActions.json  ExternalTexts.json  UITexts.json
      images/          (loading_icon.png, clear_icon.png, big_arrow.png, wallet/…)
      sounds/          (<sample>.mp3)
      c_images/        (album1584/, catalogue/, Quests/, notifications/ — SWF-era images)
      dcr/hof_furni/   (icons/, mp3/ — furni icons and sound machine samples)

Two of those trees are produced for you rather than shipped in any pack:

  dcr/hof_furni/icons/  ← `make convert-assets` extracts these straight out of
                          the converted furniture bundles (no CDN needed)
  c_images/catalogue/   ← `make fetch-catalog-icons` downloads the catalog page
                          icons your catalog_pages table references, from
                          Habbo's public image CDN

The client preloads and REQUIRES: `bundled/generic/avatar_additions.nitro`,
`bundled/generic/group_badge.nitro`, `bundled/generic/floor_editor.nitro`,
`images/loading_icon.png`, `images/clear_icon.png`, `images/big_arrow.png`.

If your pack nests things differently (e.g. `swf/c_images`), either rearrange it
to match or adjust `NITRO_IMAGE_LIBRARY_URL` / `NITRO_HOF_FURNI_URL` overrides in
docker-compose.yml (see nitro service comments).

An empty folder does not block startup — the nitro container just logs a
warning and the client shows an eternal loading screen until assets exist.

## artifacts/flash-assets/ — your SWF pack (input for `make convert-assets`)

Copy a Habbo flash client pack here, flat (the `.swf` files plus
`figuremap.xml` / `effectmap.xml` at the top level), e.g.:

    cp -R ~/Downloads/flash-assets-PRODUCTION-<version>/. artifacts/flash-assets/

This is the source for clothing/effect/pet conversion. Furniture is NOT in
these packs — the converter pulls it per-revision from the official
`images.habbo.com/dcr/hof_furni/` CDN instead. The pack is read-only to the
converter and never modified.
