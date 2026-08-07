# Nitro client build recipe

This documents exactly how `nitro/client/` (built HTML5 client, git-ignored) and
`nitro/assets/` (converted game assets, git-ignored) were produced, and how to
reproduce them. Only `nitro/renderer-config.json` is committed to the repo.

nginx (`web` service, see `docker/web/nginx.conf`) serves the whole `./nitro`
host directory at `/nitro-assets/`, so:

- `nitro/client/*`  → `http://localhost:8080/nitro-assets/client/*`
- `nitro/assets/*`  → `http://localhost:8080/nitro-assets/assets/*`

The emulator's revision file `emulator/Resources/Revisions/1.6.6.json` sets
`"Name": "NITRO-1-6-6"` and only accepts a `ClientHelloEvent` handshake string
that matches exactly. That string is *not* an arbitrary version we invent — it
is derived by `@nitrots/nitro-renderer` from its own hard-coded release
version (`NitroVersion.RENDERER_VERSION`), which happens to be `1.6.6`, the
current `latest` on the npm registry. This made version selection trivial:
build `nitro-react` against whatever `nitro-renderer` version its own
`package.json`/`yarn.lock` already pin, and the handshake string comes out
correct with **no source patch and no config override**.

## Step 1: Client (nitro-react + nitro-renderer)

Cloned to a scratch directory (NOT inside this repo):

```bash
git clone https://github.com/billsonnn/nitro-react.git nitro-react
cd nitro-react
```

- Repo: `billsonnn/nitro-react`
- Branch: `main`
- Commit built: `75ff874b73d5fc5672a38c536444efa0f0d27e8f` ("Merge pull request #173 from ArpyAge/patch-1")
- No git submodules (`nitro-renderer` is consumed as an npm dependency, not a submodule).
- `package.json` has pinned `"@nitrots/nitro-renderer": "^1.6.6"` since commit
  `e1b93470` (2023-01-18, "Bump renderer version") and it has not moved since —
  `git blame` on that line at the built commit still shows `e1b93470`.
- `yarn.lock` resolves `@nitrots/nitro-renderer` to exactly `1.6.6`
  (npm registry `dist-tags.latest` is also `1.6.6` — no newer release exists).

Where the handshake build string comes from, inside the installed
`@nitrots/nitro-renderer@1.6.6` package (source: `billsonnn/nitro-renderer`,
`src/core/NitroVersion.ts` and
`src/nitro/communication/messages/outgoing/handshake/ClientHelloMessageComposer.ts`):

```ts
// NitroVersion.ts
public static RENDERER_VERSION: string = '1.6.6';

// ClientHelloMessageComposer.ts
this._data = [`NITRO-${NitroVersion.RENDERER_VERSION.replaceAll('.', '-')}`, 'HTML5', ...];
```

`NITRO-1-6-6` — exact match to `emulator/Resources/Revisions/1.6.6.json`'s
`"Name"` field. **No patch applied.**

### Required patch: subpath deployment (index.html + vite `base`)

`nitro-react`'s default build assumes it's served from the domain root (`/`).
This client is served from a subpath (`/nitro-assets/client/`), and two
things in the unmodified build break under that:

1. Vite emits `<script src="/assets/...">`, `<link href="/assets/...">` etc.
   with a **root-absolute** path regardless of the page's own location — the
   `<base href="./">` tag in `index.html` does not affect these, since Vite
   writes them absolute at build time. Fixed by building with
   `vite build --base=/nitro-assets/client/` instead of the plain `yarn build`
   / `npm run build`, which is a documented Vite CLI flag (not a source
   patch) — it makes Vite emit `/nitro-assets/client/assets/...` for every
   built asset reference.
2. `index.html` hard-codes
   `NitroConfig["config.urls"] = [ '/renderer-config.json', '/ui-config.json' ]`
   as a literal root-absolute path in an inline `<script>` — this is runtime
   JS the browser resolves at `fetch()` time, so `vite build --base` does
   **not** touch it (that flag only rewrites asset references Vite itself
   emits, not arbitrary strings in an inline script). Left as-is, the config
   fetch would hit `http://localhost:8080/renderer-config.json` (site root)
   instead of the client's own directory, 404, and the app would never boot.
   **Source patch applied** (`index.html`, before `vite build`): changed the
   two entries to `'./renderer-config.json'` and `'./ui-config.json'`
   (relative — resolved against the page's own `<base href="./">`, which was
   already present unmodified). This is the only source patch made anywhere
   in this task; it addresses subpath deployment, not the handshake version
   string (which required no patch — see above).

Build (Node v22.22.3 host, yarn 4.13.0 via the repo's `yarn.lock`, `nodeLinker: node-modules`):

```bash
yarn install
# apply the index.html patch above, then:
npx vite build --base=/nitro-assets/client/     # NOT plain `yarn build` / `npm run build`
```

Install into the repo:

```bash
mkdir -p <repo>/nitro/client
cp -R dist/* <repo>/nitro/client/
cp <repo>/nitro/renderer-config.json <repo>/nitro/client/renderer-config.json   # see Step 2
cp public/ui-config.json.example <repo>/nitro/client/ui-config.json  # unmodified defaults
```

`ui-config.json` is required (not just `renderer-config.json`): `index.html`
declares `NitroConfig["config.urls"]` (see patch above) and
`ConfigurationManager` in `nitro-renderer` fetches both URLs, in order,
merging them into one interpolated config before the app boots. If either
404s, boot fails. `ui-config.json` was left at repo defaults (cosmetic/catalog
knobs); nothing in it gates the local-dev verification bar.

## Step 2: renderer-config.json

`public/renderer-config.json.example` in `nitro-react` is the authoritative
template — every key it defines was carried over into
`nitro/renderer-config.json` (committed), with only the network-facing values
changed to point at the local stack:

| key | value |
|---|---|
| `socket.url` | `ws://localhost:2096` |
| `asset.url` | `http://localhost:8080/nitro-assets/assets` |
| `image.library.url` | `http://localhost:8080/nitro-assets/assets/c_images/` |
| `hof.furni.url` | `http://localhost:8080/nitro-assets/assets/dcr/hof_furni` |
| `images.url` | `${asset.url}/images` |
| `gamedata.url` | `${asset.url}/gamedata` |
| `sounds.url` | `${asset.url}/sounds/%sample%.mp3` |
| `external.texts.url` | `["${gamedata.url}/ExternalTexts.json", "${gamedata.url}/UITexts.json"]` |
| `external.samples.url` | `${hof.furni.url}/mp3/sound_machine_sample_%sample%.mp3` |
| `furnidata.url` | `${gamedata.url}/FurnitureData.json` |
| `productdata.url` | `${gamedata.url}/ProductData.json` |
| `avatar.actions.url` | `${gamedata.url}/HabboAvatarActions.json` |
| `avatar.figuredata.url` | `${gamedata.url}/FigureData.json` |
| `avatar.figuremap.url` | `${gamedata.url}/FigureMap.json` |
| `avatar.effectmap.url` | `${gamedata.url}/EffectMap.json` |
| `avatar.asset.url` | `${asset.url}/bundled/figure/%libname%.nitro` |
| `avatar.asset.effect.url` | `${asset.url}/bundled/effect/%libname%.nitro` |
| `furni.asset.url` | `${asset.url}/bundled/furniture/%libname%.nitro` |
| `furni.asset.icon.url` | `${hof.furni.url}/icons/%libname%%param%_icon.png` |
| `pet.asset.url` | `${asset.url}/bundled/pet/%libname%.nitro` |
| `generic.asset.url` | `${asset.url}/bundled/generic/%libname%.nitro` |
| `badge.asset.url` | `${image.library.url}album1584/%badgename%.gif` |
| everything else (fps, pong, mandatory libraries, default figuredata, pet types, `preload.assets.urls`, ...) | copied verbatim from the template — no local override needed |

`image.library.url` (`c_images/`) and `hof.furni.url` (`dcr/hof_furni`) point
into the same `assets/` tree for consistency, but those two raw-SWF-era trees
(badge/catalog icon images, furni HOF icons) were **not** populated by this
task — see "Known gaps" below. They are not on the boot/loader path that Step
6 verifies.

## Step 3: Assets

Two sources were combined under `nitro/assets/` (git-ignored, ~notated sizes
below):

### 3a. Community default asset pack (base skeleton)

```bash
git clone https://git.mc8051.de/nitro/default-assets.git nitro/assets
```

- Repo: `git.mc8051.de/nitro/default-assets` (referenced from the
  `Gurkengewuerz/nitro-docker` README as the standard "download the default
  assets" step for this exact client)
- Branch: `master` (default)
- Commit: `e8b882f84095ad3b3b6bb0b31e03d0cf8f7e104c`
- Size: ~9.3 MB
- Provided: `images/` (loading/clear/big-arrow icons, reception backgrounds,
  wallet/navigator icons), `sounds/*.mp3`, `logos/`, and a small
  `bundled/generic/*` set (`avatar_additions.nitro`, `group_badge.nitro`,
  `floor_editor.nitro`, `room.nitro`, placeholders, tile cursor, selection
  arrow) plus a `bundled/furniture/poster*.nitro` set (~110 poster items).
- **Did not include**: `FurnitureData.json`, `ProductData.json`,
  `FigureData.json`, `FigureMap.json`, `EffectMap.json`, or any
  `bundled/figure|effect|pet` assets — only `HabboAvatarActions.json` and
  `UITexts.json` existed in `gamedata/`. Confirmed nothing in this repo (CMS
  routes, emulator resources) generates these either — see repo audit notes
  below.

### 3b. nitro-converter run against live official Habbo endpoints (fallback route, used because 3a was gamedata-incomplete)

```bash
git clone --recurse-submodules https://github.com/billsonnn/nitro-converter.git nitro-converter
cd nitro-converter
cp configuration.json.example configuration.json    # left flash.client.url / furnidata.load.url
                                                      # / productdata.load.url empty so the tool
                                                      # auto-discovers them from
                                                      # external.variables.url (official Habbo)
yarn install
yarn build
yarn start
```

- Repo: `billsonnn/nitro-converter`, branch `main`, commit
  `e0a1800a83feda5f9b1b5cfde7fed0181de7b06f`. No submodules. Ran unmodified —
  the `Main.ts` `skip` flag bug that `nitro-docker`'s Dockerfile patches with
  `sed` (forcing `skip = true` on an older pinned commit) is not present on
  current `main`.
- `configuration.json`: `figuredata.load.url` set to
  `https://www.habbo.com/gamedata/figuredata/1`,
  `external.variables.url` set to `https://www.habbo.com/gamedata/external_variables/1`,
  everything else left blank/default so the tool self-discovers
  `flash.client.url`, `furnidata.load.url`, `productdata.load.url`, the SWF
  download bases, etc. from Habbo's own `external_variables` payload — this
  is the standard, documented usage pattern (see the tool's own README).
- Output (written to `./assets/` relative to the tool, then copied into
  `<repo>/nitro/assets/`, merging with 3a — 3b's `gamedata/*.json` overwrote
  3a's placeholders):
  - `gamedata/FurnitureData.json`, `ProductData.json`, `FigureData.json`,
    `FigureMap.json`, `EffectMap.json`, `ExternalTexts.json` — converted live
    from official Habbo XML/JSON gamedata endpoints into Nitro's expected
    JSON schema.
  - `bundled/furniture/*.nitro`, `bundled/figure/*.nitro`,
    `bundled/effect/*.nitro`, `bundled/pet/*.nitro` — every furniture,
    clothing/figure, effect, and pet SWF converted to `.nitro` bundles.

### Final `nitro/assets/` contents (after merging 3a + 3b)

Total size: **410 MB** (`nitro/assets/`), well under the ~1-2 GB the brief
budgeted for.

| path | size | notes |
|---|---|---|
| `gamedata/*.json` (8 files) | 13 MB | FurnitureData 8.3 MB, ExternalTexts 3.8 MB, FigureData 1.1 MB, FigureMap 364 KB, EffectMap 15 KB, ProductData 63 B (see gap note), HabboAvatarActions 25 KB, UITexts 3 KB |
| `bundled/furniture/*.nitro` | 327 MB | 13,576 files (13,483 freshly converted + ~93 from the default-assets pack, deduplicated by filename) |
| `bundled/figure/*.nitro` | 55 MB | 2,957 files |
| `bundled/effect/*.nitro` | 6.0 MB | 249 files |
| `bundled/pet/*.nitro` | 4.8 MB | 36 files |
| `bundled/generic/*.nitro` | 380 KB | 9 files (from 3a: `avatar_additions`, `group_badge`, `floor_editor`, `room`, `place_holder`, `place_holder_pet`, `place_holder_wall`, `tile_cursor`, `selection_arrow`) |
| `images/`, `sounds/`, `logos/` | 3.6 MB | from 3a, unchanged |

`nitro-converter`'s run took ~40 minutes total (furniture: ~35 min for
13,505 items; figure: ~6.5 min for 2,957; effect: ~24s for 249; pet: ~10s for
36), all downloaded live from `images.habbo.com` / `www.habbo.com`. 5 SWFs
failed to convert ("Invalid SWF", e.g. `floortile`) out of 13,505 furniture
attempts — those are pre-existing quirks in the official asset set unrelated
to this task, not required for the verification bar, and not investigated
further.

### Known gaps (documented, not blocking)

- `image.library.url` (`c_images/`) and `hof.furni.url` (`dcr/hof_furni/`) —
  the raw, unconverted badge/catalog-icon and furni-HOF-icon SWF/image trees
  — were not populated by this task. Neither `default-assets` nor
  `nitro-converter` produces these (they're a separate raw-download tree, e.g.
  via `habbo-downloader --command icons|badges|badgeparts`). They affect
  catalog images, furni icons in the catalog, and badge rendering — not the
  standalone client boot / login screen covered by this task's verification
  bar. **Resolved** by `extract-furni-icons.py` and `mirror-c-images.sh` —
  see "Catalog & badge images" below.
- `ProductData.json` converts to `{"productdata":{"product":[{"code":"pixel","description":""}]}}`
  — this is what official Habbo's `productdata` endpoint itself returns
  today (effectively deprecated/empty upstream), not a converter bug.
- **`FigureMap.json` had two malformed entries** — `face_M_nftscarface2`
  and `face_F_nftscarface2` converted with `"parts": null` instead of an
  array. `nitro-renderer`'s avatar figure-map downloader
  (`processFigureMap`, in `nitro-renderer-*.js`) does `for (const part of
  library.parts)` with no null guard, so it throws ("`e.parts is not
  iterable`") partway through parsing the map — which only runs once a
  real SSO ticket authenticates, so this was invisible to this task's own
  no-SSO verification (Step 6) and only surfaced in Task 9's logged-in E2E
  walk. Fixed **in place** on the live `nitro/assets/gamedata/FigureMap.json`
  (git-ignored, so this note is the only record of it) by replacing both
  `null` values with `[]`. If you regenerate `nitro/assets/` from scratch
  via Step 3, re-check for `"parts": null` entries in the fresh
  `FigureMap.json` before deploying it:
  `python3 -c "import json; d=json.load(open('nitro/assets/gamedata/FigureMap.json')); print([l['id'] for l in d['libraries'] if not isinstance(l.get('parts'), list)])"`

## Step 4: Build and install (full command sequence actually run)

```bash
cd nitro-react
yarn install
# patch index.html's config.urls to './renderer-config.json' / './ui-config.json' (see Step 1)
npx vite build --base=/nitro-assets/client/
mkdir -p <repo>/nitro/client
cp -R dist/* <repo>/nitro/client/
cp <repo>/nitro/renderer-config.json <repo>/nitro/client/renderer-config.json
cp public/ui-config.json.example <repo>/nitro/client/ui-config.json
```

## Step 5: Point the CMS at it

```bash
docker compose exec db mysql -u${DB_USER} -p${DB_PASSWORD} ${DB_NAME} \
  -e "UPDATE website_settings SET value='/nitro-assets/client' WHERE \`key\`='nitro_path';"
docker compose exec cms php artisan cache:clear
```

Executed against the running compose stack; `website_settings.nitro_path`
confirmed updated to `/nitro-assets/client` and Laravel's cache cleared.

## Step 6: Verification

Against the running compose stack (`db`/`emulator`/`cms`/`web` all up):

**Client index and configs (curl):**

```
$ curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://localhost:8080/nitro-assets/client/index.html
200 text/html
$ curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://localhost:8080/nitro-assets/client/renderer-config.json
200 application/json
$ curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://localhost:8080/nitro-assets/client/ui-config.json
200 application/json
$ curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://localhost:8080/nitro-assets/client/assets/index-552ff3e4.js
200 application/javascript
$ curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://localhost:8080/nitro-assets/client/assets/vendor-48792d42.js
200 application/javascript
$ curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://localhost:8080/nitro-assets/client/assets/nitro-renderer-493a6bde.js
200 application/javascript
$ curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://localhost:8080/nitro-assets/client/src/assets/index.css
200 text/css
```

**Gamedata + preload assets the client fetches on boot (curl):**

```
FurnitureData.json   200 application/json
ProductData.json     200 application/json
FigureData.json      200 application/json
FigureMap.json       200 application/json
EffectMap.json       200 application/json
ExternalTexts.json   200 application/json
UITexts.json         200 application/json
HabboAvatarActions.json 200 application/json
bundled/generic/avatar_additions.nitro   200 text/plain
bundled/generic/group_badge.nitro        200 text/plain
bundled/generic/floor_editor.nitro       200 text/plain
images/loading_icon.png                  200 image/png
images/clear_icon.png                    200 image/png
images/big_arrow.png                     200 image/png
```

Spot-checked one file from each newly converted bundle type — all 200:

```
furniture  CFC_100_coin_gold.nitro   200 text/plain
figure     Hair_F_Bob.nitro          200 text/plain
effect     AlienMask.nitro           200 text/plain
pet        bear.nitro                200 text/plain
```

**Real browser load (headless Chromium via the Claude Browser pane),
navigated to `http://localhost:8080/nitro-assets/client/index.html` with no
`?sso=`:**

- Console: `Nitro 2.2.0 - Renderer 1.6.6` banner logged (confirms the
  installed `@nitrots/nitro-renderer` build is exactly `1.6.6`), zero errors.
- Network panel: every request the loader issued returned `200 OK` — the
  full boot sequence (index.html → JS/CSS bundles → `renderer-config.json` +
  `ui-config.json` → gamedata JSONs → the 3 `preload.assets.urls` `.nitro`
  bundles → the 3 preload images). **Zero 404s.**
- Screen: shows the Nitro loading duck animation, then **"Handshake
  Failed"** — this is the expected terminal state per the brief ("It will
  stall at authentication without an SSO ticket — that's correct here");
  the client connects to `ws://localhost:2096`, sends `ClientHelloEvent`
  with build `NITRO-1-6-6` (accepted — no "Unknown revision connected"
  warning in emulator logs), then has no SSO ticket to continue with.

**WebSocket endpoint (Node `ws`, since the Nitro binary handshake can't be
driven from curl — verifying the TCP/WS upgrade itself, which is the
emulator-side half of the contract this task owns):**

```
$ node ws_test.mjs      # ws://localhost:2096 direct
WS_OPEN: TCP/WS upgrade accepted by emulator

$ node ws_test_proxy.mjs  # ws://localhost:8080/ws (nginx proxy path, for the VPS/wss case)
PROXY_WS_OPEN
```

**Emulator logs**: no `"Unknown revision connected"` warnings appeared for
any of the test connections above (that warning is `ClientHelloEvent`'s
explicit failure path when the build string isn't in
`RevisionsCache.Revisions` — see
`emulator/Communication/Packets/Incoming/Handshake/ClientHelloEvent.cs`,
which does an exact dictionary lookup on the string read off the wire against
each `Revision.Name` loaded from `emulator/Resources/Revisions/*.json`).

**Bar met**: client bundle loads (200, correct content-types), every
configured asset URL the loader requests first returns 200, ws endpoint
upgrades (both direct and via the nginx `/ws` proxy). Full in-room E2E
(actual SSO ticket, entering a room, seeing furniture/avatars render) is
Task 9's job, per the brief.

## Reproducing this build

1. `git clone https://github.com/billsonnn/nitro-react.git` and check out
   `75ff874b73d5fc5672a38c536444efa0f0d27e8f` (or any newer `main` commit —
   `nitro-renderer` has not moved past `1.6.6` on npm as of this writing, but
   verify `yarn.lock` still resolves it to `1.6.6` before trusting the
   handshake string).
2. `yarn install`, patch `index.html`'s `config.urls` per the subpath-deployment
   note above, then `npx vite build --base=/nitro-assets/client/` (not plain
   `yarn build`), copy `dist/*` into `nitro/client/`.
3. Copy `nitro/renderer-config.json` (this repo, already committed) and a
   fresh `ui-config.json` (from `nitro-react/public/ui-config.json.example`)
   into `nitro/client/`.
4. Populate `nitro/assets/` per Step 3 above (default-assets pack +
   nitro-converter run). Budget ~30-45 minutes for the full furniture/figure/
   effect/pet conversion pass against official Habbo.
5. Run Step 5's DB update + cache:clear against the running compose stack.
6. Verify per Step 6.

## Troubleshooting: client stuck at 80%

The final 20% of the Nitro loading bar is `RoomEngineEvent.ENGINE_INITIALIZED`,
which only fires after all six mandatory room libraries (`room`, `tile_cursor`,
`selection_arrow`, `place_holder`, `place_holder_wall`, `place_holder_pet`)
have been downloaded AND parsed into collections. Two failure modes were found
and fixed here — both fail silently (no console error, no failed request):

1. **Wrong Content-Type.** nitro-renderer's `AssetManager.downloadAssets`
   switches on the response `Content-Type` and only parses bundles served as
   `application/octet-stream`. nginx's default mime map serves `.nitro` as
   `text/plain`, so every bundle is skipped. Fixed in `docker/web/nginx.conf`
   with `types { application/octet-stream nitro; }`.

2. **gzip-compressed bundle entries.** The renderer's `NitroBundle` parser
   uses `pako.inflate` (zlib only). 99 bundles from the default asset pack
   (mostly posters + 5 of the 6 mandatory generic libraries) had their inner
   entries gzip-compressed. `fix-bundle-compression.py` re-encodes gzip
   entries as zlib in place; run it after (re)importing any asset pack:

       python3 docker/nitro/fix-bundle-compression.py nitro/assets

**After fixing either issue, hard-refresh the browser (Cmd+Shift+R).** The
`.nitro` bundles are served with `max-age=604800`, so browsers that loaded the
broken responses keep replaying them from cache — including the wrong
Content-Type — until forced past the cache.

## Troubleshooting: avatars missing nose/mouth

The converter emitted the standard-expression face sprites
(`h_std_fc_1_<dir>_0` in `hh_human_face.nitro`) as aliases whose `source`
pointed at NFT "scarface" part images (`*_fc_6221/6222_*`) that were dropped
from the bundle — a dangling alias renders as nothing, so idle avatars had no
nose/mouth (mouths only appeared mid-expression, e.g. while speaking). 48
other bundles had smaller cases of the same defect (~94 dangling aliases
total, mostly clothing frames).

`fix-dangling-sources.py` remaps every dangling `source` to the closest real
sprite with the same size/part/part-id/direction (action priority: std, spk,
sml, sad, agr, wlk). Run it after (re)importing any asset pack, after the
compression fix:

    python3 docker/nitro/fix-dangling-sources.py nitro/assets

Furniture bundles use a different key format and are intentionally left
untouched (reported as "unresolved"). Hard-refresh the browser afterwards —
the old bundles are cached for a week.

## Catalog & badge images

Two of the three trees `renderer-config.json` points at were still empty
after the initial import (see "Known gaps" above): `dcr/hof_furni/icons/`
(furni catalog/inventory grid icons) and `c_images/` (catalog category tree
icons, catalog promo/teaser art, badge art). Both are populated by scripts
here rather than by hand — the produced images themselves stay git-ignored
(`nitro/assets/` is excluded in `.gitignore`), only the scripts are committed.

### `extract-furni-icons.py` — furni grid icons, extracted offline from our own bundles

The Nitro client requests furni icons from
`furni.asset.icon.url` = `${hof.furni.url}/icons/%libname%%param%_icon.png`
(see the config table above). Rather than scraping these from Sulake, they're
cropped directly out of the `.nitro` furniture bundles we already have under
`nitro/assets/bundled/furniture/`.

Each `.nitro` bundle is a small custom container (big-endian): `int16`
fileCount, then per file `[int16 nameLen][name][int32 blobLen][zlib blob]`.
Furniture bundles contain a `<lib>.json` (a pixi spritesheet description,
itself zlib-compressed once decoded from the container) and a `<lib>.png`
sprite sheet. The JSON's `spritesheet.frames` map has one or more icon
frames keyed like `<lib>_<lib>_icon_a` (the default icon) and occasionally
`..._icon_b` etc. (alternate state icons for togglable furni). The script
crops each icon frame out of the sheet using Pillow and writes:

- `<classname>_icon.png` for the `_a` (default) frame
- `<classname>_<suffix>_icon.png` for any other frame suffix

Per-color catalog variants (`classname*1`, `classname*2`, ... in
`FurnitureData.json`) intentionally share one base icon — colored icons for
those are tinted client-side at render time from the layer/color data already
in the bundle, not fetched as separate static images per color, so a single
`<classname>_icon.png` covers every `*N` variant of a library.

```bash
pip3 install pillow   # if not already available
python3 docker/nitro/extract-furni-icons.py
```

Bundles whose `.json`/`.png` entries fail to parse (missing icon frames, bad
zlib data, etc.) are skipped with a per-bundle reason and counted, not fatal.
The script finishes by computing coverage against every base classname in
`nitro/assets/gamedata/FurnitureData.json` and prints the percentage plus a
sample of misses. Current run: 13,333/13,576 bundles processed cleanly,
13,808 icon files written, **98.0% coverage** (13,240/13,505 base
classnames) — the misses are mostly multi-part sets (`bc_alpha1_*` letter
tiles, `SF_alien`, board games like `Chess`/`Poker`) whose bundles don't ship
a dedicated icon frame at all, not a parsing failure.

### `mirror-c-images.sh` — c_images, mirrored from Sulake against what the DB actually references

`c_images/` (catalog tree icons, catalog promo/teaser art, badge art) never
existed in any bundle — it's Sulake's raw web-image tree, so this genuinely
has to be fetched from `images.habbo.com`. The script only mirrors what our
own database references (plus a small numeric sweep for catalog icons),
rather than scraping the whole tree:

1. **Catalog tree icons** (`c_images/catalogue/icon_<N>.png`): `N` is the
   union of every `catalog_pages.icon_image` value in the DB and a `1..250`
   sweep (covers icon ids used by older/edited catalog trees that may not be
   wired into `catalog_pages` yet).
2. **Catalog promo/teaser images**: `catalog_promotions.image` already
   stores the full relative path (e.g.
   `catalogue/feature_cata_vert_hween16bun1.png`) — fetched verbatim, with a
   `.png`⇄`.gif` extension fallback if the first attempt 404s.
3. **Badge art** (`c_images/album1584/<code>.gif`): the deduplicated union of
   `badge_definitions.code`, `user_badges.badge_id`, and
   `client_external_badge_texts.badge_code`.

All fetches are `curl -f` (so a 404 is just a failed, non-fatal command),
capped at 4 concurrent requests, and idempotent — files that already exist
locally are skipped on a re-run (pass `--force` to refetch everything).

```bash
docker/nitro/mirror-c-images.sh          # normal run, skips existing files
docker/nitro/mirror-c-images.sh --force  # refetch everything
```

Latest run against the local DB: catalog icons 254 fetched / 11 404
(258 files on disk incl. 4 promo images sharing the same directory),
promo/teaser images 4/4 fetched, badges 5,334 fetched / 380 404 (5,714 unique
codes attempted — `badge_definitions` includes codes from other emulator
badge packs that were never mirrored to Sulake's CDN, hence the 404s).

### Verification

```bash
$ curl -s -o /dev/null -w '%{http_code} %{content_type}\n' \
    http://localhost:8080/nitro-assets/assets/c_images/catalogue/icon_2.png
200 image/png
$ curl -s -o /dev/null -w '%{http_code} %{content_type}\n' \
    http://localhost:8080/nitro-assets/assets/c_images/album1584/ACH_AvatarLooks1.gif
200 image/gif
$ curl -s -o /dev/null -w '%{http_code} %{content_type}\n' \
    http://localhost:8080/nitro-assets/assets/dcr/hof_furni/icons/anna_sofa_icon.png
200 image/png
```

nginx needed no config changes — the icons directory sits inside the
already-served `nitro/assets/` tree.

## Hotel view widgets

The promo panels overlaying the hotel landing view (the "Habboon PlusEMU Edit."
article, the untranslated `landing.view.2021NitroPromo.*` container, and the
fame hall-of-fame slot) come from `hotelview.widgets` in the client's
`ui-config.json` — not from the CMS or the emulator. All slots are blanked in
the versioned `nitro/ui-config.json`.

Like `renderer-config.json`, copy it into the built client after any client
rebuild (`nitro/client/` is git-ignored):

    cp nitro/ui-config.json nitro/client/ui-config.json

To bring a slot back, set `slot.N.widget` to a widget name (`promoarticle`,
`widgetcontainer`, `achievementcompetition_hall_of_fame`) and fill its
`slot.N.conf`.

## Wearables render wrong (picked shorts, got a skirt/kilt)

The Nitro client renders avatars from `FigureData.json`, but PlusEMU validates
every saved look against `emulator/Config/figuredata.xml`
(`FigureDataManager.ProcessFigure`). If the XML is an older/smaller revision
than the JSON, any clothing set the client offers but the server doesn't know
is **silently dropped on save**, and the emulator's required-parts loop
substitutes the *first* same-gender set of that type — e.g. a male who picks
modern denim shorts is stored wearing leg set 3017 (a kilt). Symptom: "I chose
X but I'm wearing Y."

The two files must describe the same set universe. Regenerate the XML from the
client JSON after every converter run that rewrites `FigureData.json`:

    python3 docker/nitro/figuredata-json-to-xml.py

then rebuild the emulator image so `Config/figuredata.xml` is baked in. (Our
client offered 163 leg sets vs the emulator's 73 before this was synced.)
