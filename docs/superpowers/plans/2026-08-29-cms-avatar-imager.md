# CMS Avatar Imager (nitro-imager) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render CMS avatars (Online Friends widget + all other avatar spots) with their real clothing by self-hosting a nitro-native imager fed by our own gamedata, instead of habbo.com which drops PixelRP's custom figure sets.

**Architecture:** Add `billsonnn/nitro-imager` (Node/TS, wraps nitro-renderer's avatar code) as a new internal compose service. It pulls `FigureData`/`FigureMap`/`EffectMap`/`HabboAvatarActions` + `.nitro` figure/effect bundles over HTTP from the existing `web` service, renders PNGs, and is reverse-proxied by the web nginx at `/imaging/`. The only CMS change is repointing the `avatar_imager` DB setting.

**Tech Stack:** Node 18, TypeScript, `node-canvas@2.x`, Express, Docker Compose, nginx. Source vendored as a git submodule from an org fork of `billsonnn/nitro-imager`.

## Global Constraints

- **Node 18** in the imager image — `node-canvas@^2.8.0` (upstream dep) does not build cleanly on newer Node. Copy verbatim: base image `node:18-bookworm`.
- **Avatars only** — no furni/room/badge imaging in scope.
- **Beta-first** — everything lands on the `beta` branch and is validated on beta before any prod rollout (prod is a documented follow-up, not in this plan).
- **No CMS template changes** — the imager already accepts the CMS's habbo-style params (`figure`, `direction`, `head_direction`, `gesture=sml`, `action=wav`, `headonly`, `size=s/l`); verified against upstream source. The only CMS-side change is the `avatar_imager` setting value.
- **Imager is internal-only** — no host port publish; reachable only via the web nginx `/imaging/` proxy.
- **Assets over HTTP, never baked** — the imager reads the same `/nitro-assets/...` the client uses, so it always tracks live figuredata.
- **Data-only DB change is manual per environment** — per the non-git-deploy rule, the running `website_settings.avatar_imager` row is changed by hand on beta (and later prod); the seeder default is updated for fresh installs only.
- Imager listen host **must be `0.0.0.0`** (`API_HOST`), or other containers cannot reach it.
- Imager reads `./config.json` from its working directory at startup — it must be present in the image `WORKDIR`.

---

## Prerequisites captured in Task 1

- **Fork URL** — the org fork of `billsonnn/nitro-imager`, e.g. `https://github.com/<your-org>/nitro-imager.git`. Established in Task 1 and referenced by later tasks as `<FORK_URL>` / `<FORK_HTTPS_URL>`.

---

### Task 1: Fork upstream and add it as the `imager/` submodule

Create a pinned org fork so we don't depend on upstream staying online, and vendor it as a submodule (consistent with `client`/`emulator`). No code changes go in the fork right now — it's pristine upstream; our integration (Dockerfile, compose, nginx) lives in the main repo. The fork exists so future patches, if ever needed, have a home.

**Files:**
- Modify: `.gitmodules` (submodule entry added by `git submodule add`)
- Create: `imager/` (submodule working tree)

**Interfaces:**
- Produces: a checked-out `imager/` directory containing upstream's `package.json`, `tsconfig.json` (`outDir: ./dist`), `index.ts`, `src/`, and `config.json`. Later tasks build from this via `docker/imager/Dockerfile`.

- [ ] **Step 1: Create the fork (manual, one-time)**

Fork `billsonnn/nitro-imager` into your GitHub org and make it **public** (simplest for the VPS submodule pull over https; if it must be private, the VPS deploy key needs read access to it — see Task 6 notes). Using the GitHub CLI on your workstation:

```bash
gh repo fork billsonnn/nitro-imager --org <your-org> --fork-name nitro-imager --clone=false
```

Record the resulting https URL (e.g. `https://github.com/<your-org>/nitro-imager.git`) — later steps refer to it as `<FORK_HTTPS_URL>`.

- [ ] **Step 2: Add the submodule at `imager/`**

From the repo root, on the `beta` branch:

```bash
git submodule add <FORK_HTTPS_URL> imager
git submodule update --init --recursive imager
```

- [ ] **Step 3: Verify the submodule checked out the expected source**

Run:
```bash
test -f imager/package.json && test -f imager/config.json && test -f imager/src/main.ts && echo OK
grep -q '"build": "tsc"' imager/package.json && echo BUILD_OK
```
Expected: `OK` then `BUILD_OK`.

- [ ] **Step 4: Commit**

```bash
git add .gitmodules imager
git commit -m "build(imager): vendor nitro-imager fork as submodule"
```

---

### Task 2: Dockerfile for the imager, and a standalone render smoke test

Build the imager image and prove it renders a **clothed** PNG for a real PixelRP custom look, before wiring it into compose. For this task the container reads assets from beta's public URL (`https://beta.pixelrp.co/nitro-assets/...`, CORS-open) so no local full stack is needed.

**Files:**
- Create: `docker/imager/Dockerfile`
- Create: `scripts/imager-smoke-test.sh`

**Interfaces:**
- Consumes: `imager/` submodule source from Task 1.
- Produces: image tag `pixelrp-imager:dev`; a smoke-test script `scripts/imager-smoke-test.sh <base_url>` that exits non-zero if the custom-clothed render is not meaningfully larger than the skin-only baseline.

- [ ] **Step 1: Write the Dockerfile**

Create `docker/imager/Dockerfile` (build context is the repo root, so it can COPY the `imager/` submodule):

```dockerfile
# nitro-imager (billsonnn) — Node 18 required for node-canvas@2.x.
FROM node:18-bookworm AS build
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev \
    && rm -rf /var/lib/apt/lists/*
COPY imager/package.json imager/package-lock.json ./
RUN npm ci
COPY imager/ ./
RUN npm run build

FROM node:18-bookworm AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
      libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libjpeg62-turbo libgif7 librsvg2-2 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY --from=build /app/config.json ./config.json
ENV AVATAR_SAVE_PATH=/cache
RUN mkdir -p /cache
CMD ["node", "dist/index.js"]
```

- [ ] **Step 2: Write the smoke-test script**

Create `scripts/imager-smoke-test.sh`. It renders a real custom-clothed look and the same look stripped to skin only, and asserts the clothed PNG is meaningfully larger (proves clothing layers rendered, not a naked default):

```bash
#!/usr/bin/env bash
# Usage: scripts/imager-smoke-test.sh http://localhost:3030
# Exits non-zero unless the custom-clothed render is clearly larger than the
# skin-only baseline (i.e. clothing actually rendered).
set -euo pipefail
BASE="${1:?usage: imager-smoke-test.sh <imager_base_url>}"

# ClaudeTest's look: custom sets ch-3059 / lg-3019 / sh-3206 + custom acc ca-80000103
CLOTHED='hr-6084-45-36.hd-6021-1.ch-3059-72.lg-3019-82.sh-3206-73.ca-80000103-1410-77'
NAKED='hd-6021-1'   # same body, skin only

tmp="$(mktemp -d)"
curl -fsS "${BASE}/?figure=${CLOTHED}&size=l&direction=2&head_direction=3&gesture=sml" -o "${tmp}/clothed.png"
curl -fsS "${BASE}/?figure=${NAKED}&size=l&direction=2&head_direction=3&gesture=sml"   -o "${tmp}/naked.png"

# Must be valid PNGs
file "${tmp}/clothed.png" | grep -q 'PNG image data' || { echo "FAIL: clothed not a PNG"; exit 1; }

c=$(wc -c < "${tmp}/clothed.png"); n=$(wc -c < "${tmp}/naked.png")
echo "clothed=${c}B naked=${n}B"
# Clothing adds substantial pixel data; require clothed to exceed naked by >25%.
awk -v c="$c" -v n="$n" 'BEGIN{ if (c > n*1.25) { print "PASS: clothing rendered"; exit 0 } else { print "FAIL: render looks naked"; exit 1 } }'
```

```bash
chmod +x scripts/imager-smoke-test.sh
```

- [ ] **Step 3: Build the image**

Run:
```bash
docker build -f docker/imager/Dockerfile -t pixelrp-imager:dev .
```
Expected: build completes; `npm run build` emits `dist/index.js`. If `node-canvas` fails to compile, this is the known 2022-deps risk — fall back to the `Orion-Server/avatar-imaging` fork source (same engine, newer deps) as the submodule and rebuild.

- [ ] **Step 4: Run the container against beta's public assets**

Run:
```bash
docker run -d --name imager-smoke -p 3030:3030 \
  -e API_HOST=0.0.0.0 -e API_PORT=3030 \
  -e AVATAR_ACTIONS_URL=https://beta.pixelrp.co/nitro-assets/gamedata/HabboAvatarActions.json \
  -e AVATAR_FIGUREDATA_URL=https://beta.pixelrp.co/nitro-assets/gamedata/FigureData.json \
  -e AVATAR_FIGUREMAP_URL=https://beta.pixelrp.co/nitro-assets/gamedata/FigureMap.json \
  -e AVATAR_EFFECTMAP_URL=https://beta.pixelrp.co/nitro-assets/gamedata/EffectMap.json \
  -e AVATAR_ASSET_URL='https://beta.pixelrp.co/nitro-assets/bundled/figure/%libname%.nitro' \
  -e AVATAR_ASSET_EFFECT_URL='https://beta.pixelrp.co/nitro-assets/bundled/effect/%libname%.nitro' \
  pixelrp-imager:dev
sleep 8   # allow gamedata + mandatory dance effect libs to download on init
docker logs imager-smoke 2>&1 | tail -20
```
Expected: logs show `Server Started 0.0.0.0:3030` and `Initialized` with no fatal asset-fetch errors.

- [ ] **Step 5: Run the smoke test (the real gate)**

Run:
```bash
scripts/imager-smoke-test.sh http://localhost:3030
```
Expected: prints `clothed=…B naked=…B` and `PASS: clothing rendered`. If it prints `FAIL: render looks naked`, stop and debug the asset URLs / FigureMap before proceeding — do not continue.

- [ ] **Step 6: Also confirm headonly returns a head crop**

Run:
```bash
curl -fsS "http://localhost:3030/?figure=hd-6021-1.ch-3059-72&headonly=1&size=l" -o /tmp/head.png
python3 -c "import struct;d=open('/tmp/head.png','rb').read();w,h=struct.unpack('>II',d[16:24]);print('dims',w,h);assert h<=w*1.4,'looks full-body not head'"
```
Expected: prints small `dims` with height not much greater than width (a head crop, not a full body).

- [ ] **Step 7: Tear down the smoke container and commit**

```bash
docker rm -f imager-smoke
git add docker/imager/Dockerfile scripts/imager-smoke-test.sh
git commit -m "build(imager): Dockerfile + render smoke test (clothed vs naked)"
```

---

### Task 3: Wire the imager into compose and the web nginx proxy

Add the service to the base compose and beta overlay, mount a cache volume, and expose it at `beta.pixelrp.co/imaging/` through the web container's nginx. Point its asset URLs at the internal `web` service.

**Files:**
- Modify: `compose.yaml` (add `imager-cache` volume + `imager` service)
- Modify: `compose.beta.yaml` (imager static IP on the beta subnet)
- Modify: `docker/web/nginx.conf` (add `location /imaging/`)

**Interfaces:**
- Consumes: image built from `docker/imager/Dockerfile` (Task 2); `web` service serving `/nitro-assets/`.
- Produces: internal service `imager` on port 3030; public path `…/imaging/?figure=…` proxied to it.

- [ ] **Step 1: Add the volume and service to `compose.yaml`**

In `compose.yaml`, add to the top-level `volumes:` map:
```yaml
  # Rendered-avatar PNG cache for the imager (keyed by full figure query).
  imager-cache:
```

Add a new service (place it after `web:`), mirroring the existing build/network conventions:
```yaml
  imager:
    build:
      context: .
      dockerfile: docker/imager/Dockerfile
    environment:
      API_HOST: 0.0.0.0
      API_PORT: "3030"
      AVATAR_SAVE_PATH: /cache
      AVATAR_ACTIONS_URL: http://web/nitro-assets/gamedata/HabboAvatarActions.json
      AVATAR_FIGUREDATA_URL: http://web/nitro-assets/gamedata/FigureData.json
      AVATAR_FIGUREMAP_URL: http://web/nitro-assets/gamedata/FigureMap.json
      AVATAR_EFFECTMAP_URL: http://web/nitro-assets/gamedata/EffectMap.json
      AVATAR_ASSET_URL: http://web/nitro-assets/bundled/figure/%libname%.nitro
      AVATAR_ASSET_EFFECT_URL: http://web/nitro-assets/bundled/effect/%libname%.nitro
    volumes:
      - imager-cache:/cache
    depends_on:
      - web
    networks:
      pixelrp:
        ipv4_address: 172.28.0.50
    restart: unless-stopped
```

- [ ] **Step 2: Add the beta subnet override to `compose.beta.yaml`**

Beta uses the `172.29.0.0/16` subnet, so the base `172.28.0.50` must be overridden. Add under `services:` in `compose.beta.yaml`:
```yaml
  imager:
    networks:
      pixelrp:
        ipv4_address: 172.29.0.50
```

- [ ] **Step 3: Add the nginx proxy route**

In `docker/web/nginx.conf`, inside the same `server { }` block as the other `location`s (near `/nitro-assets/`), add:
```nginx
    # CMS avatar imager (nitro-imager) — renders custom clothing the habbo.com
    # imager can't. Trailing slash on proxy_pass strips /imaging/ so the
    # upstream sees "/?figure=...".
    location /imaging/ {
      proxy_pass http://imager:3030/;
      proxy_set_header Host $host;
      add_header Cache-Control "public, max-age=86400";
      add_header Access-Control-Allow-Origin *;
    }
```

- [ ] **Step 4: Validate the compose files parse and resolve the service**

Run:
```bash
docker compose -p pixelrp-beta -f compose.yaml -f compose.prod.yaml -f compose.beta.yaml config \
  | grep -A2 -E "imager:|172.29.0.50" | head
```
Expected: the merged config shows the `imager` service with `ipv4_address: 172.29.0.50` and the `http://web/...` asset URLs. No YAML errors.

- [ ] **Step 5: Validate the nginx config syntax**

Run (mounts the edited config into a throwaway nginx and runs `nginx -t`; `imager` won't resolve in this bare container, so tolerate an upstream-host warning but require the syntax to be valid):
```bash
docker run --rm -v "$PWD/docker/web/nginx.conf:/etc/nginx/nginx.conf:ro" nginx:1.27-alpine nginx -t 2>&1 | tail -5
```
Expected: `syntax is ok` / `test is successful` (a `host not found in upstream "imager"` line is acceptable here — it resolves at runtime on the compose network).

- [ ] **Step 6: Commit**

```bash
git add compose.yaml compose.beta.yaml docker/web/nginx.conf
git commit -m "feat(imager): add imager service + /imaging/ nginx route (beta)"
```

---

### Task 4: Repoint the CMS setting (seeder default) and changelog

Update the seeder default so fresh installs use the self-hosted imager, and add the changelog entry. The running beta DB row is flipped by hand in Task 5 (per the non-git-deploy rule).

**Files:**
- Modify: `cms/database/seeders/WebsiteSettingsSeeder.php` (the `avatar_imager` default value)
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: the `/imaging/` route from Task 3.
- Produces: seeder default `https://beta.pixelrp.co/imaging/?figure=` (documented as environment-specific).

- [ ] **Step 1: Update the seeder default**

In `cms/database/seeders/WebsiteSettingsSeeder.php`, change the `avatar_imager` value from
`https://www.habbo.com/habbo-imaging/avatarimage?figure=`
to
`https://beta.pixelrp.co/imaging/?figure=`
and add a short comment noting the value is environment-specific (prod uses `https://pixelrp.co/imaging/?figure=`) and that existing installs are updated by hand, since the seeder only runs on fresh installs.

- [ ] **Step 2: Verify the edit**

Run:
```bash
grep -n "imaging/?figure=" cms/database/seeders/WebsiteSettingsSeeder.php
```
Expected: one line showing the new value under the `avatar_imager` key.

- [ ] **Step 3: Add the changelog entry**

Add a bullet to the current unreleased section of `CHANGELOG.md` (match the existing style/tense):
```
- Fixed avatars showing up without clothes across the site (Online Friends, profiles, articles, leaderboards). The site now renders avatars with our own imager, so custom clothing appears correctly.
```

- [ ] **Step 4: Commit**

```bash
git add cms/database/seeders/WebsiteSettingsSeeder.php CHANGELOG.md
git commit -m "feat(cms): point avatar_imager at self-hosted imager + changelog"
```

---

### Task 5: Deploy to beta, flip the beta DB row, and validate live

Ship the branch to beta via the deploy workflow (which handles the update screen / graceful shutdown), then make the manual DB change and confirm the widget renders clothed on the live site.

**Files:** none (deploy + data change)

**Interfaces:**
- Consumes: everything from Tasks 1–4 on the `beta` branch.

- [ ] **Step 1: Push the branch**

```bash
git push origin beta
```

- [ ] **Step 2: Trigger the beta deploy workflow**

```bash
gh workflow run deploy-beta.yml --ref beta
```
Then watch it:
```bash
gh run watch "$(gh run list --workflow=deploy-beta.yml --limit 1 --json databaseId -q '.[0].databaseId')"
```
Expected: green run. The deploy must `git submodule update --init --recursive` so `imager/` is present, and build the new `imager` service. If the run fails on the submodule (private fork), grant the VPS deploy key read access to the fork, or make the fork public, then re-run.

- [ ] **Step 3: Confirm the imager container is up on the VPS**

Verify the beta imager container is running and initialized (via your normal VPS access), e.g. that its logs show `Server Started 0.0.0.0:3030` and `Initialized`. Then confirm the public route renders — from anywhere:
```bash
scripts/imager-smoke-test.sh https://beta.pixelrp.co/imaging
```
Expected: `PASS: clothing rendered`. This proves the proxy + internal asset URLs work end-to-end before touching the DB.

- [ ] **Step 4: Flip the beta `avatar_imager` DB row (manual)**

Update the setting on the **beta** database only (target the beta db container by name to avoid the prod-vs-beta compose trap):
```sql
UPDATE website_settings
SET value = 'https://beta.pixelrp.co/imaging/?figure='
WHERE `key` = 'avatar_imager';
```
Then clear the CMS settings/config cache if the CMS caches settings (e.g. `php artisan config:clear` / cache clear per this app's setting layer), so the new value is served.

- [ ] **Step 5: Validate the Online Friends widget live**

Load the profile page on beta (`https://beta.pixelrp.co/me` while logged in) with online friends present, and confirm the friend avatars now render **with clothing** (and as head crops, since the widget uses `headonly=1`). Spot-check other avatar surfaces (articles, leaderboard) render clothed too.

- [ ] **Step 6: Update project memory / notes**

Record on the beta-rollout notes that the beta `avatar_imager` row was flipped on 2026-08-29 and that **prod still points at habbo.com** — prod rollout is the outstanding follow-up (add the `imager` service to `compose.prod.yaml`, deploy prod, then flip the prod row to `https://pixelrp.co/imaging/?figure=`).

---

## Prod rollout (follow-up, out of scope for this plan)

Once beta is confirmed stable: add the `imager` service override to `compose.prod.yaml` (prod subnet IP `172.28.0.50` is already the base value, so likely no override needed — confirm no collision), deploy prod via `deploy.yml`, verify `https://pixelrp.co/imaging` with the smoke test, then flip the prod `website_settings.avatar_imager` row to `https://pixelrp.co/imaging/?figure=` and clear the CMS cache. Confirm prod currently still uses the habbo.com value before flipping.

---

## Self-Review Notes

- **Spec coverage:** service (T2/T3), asset-over-HTTP config (T3), nginx route (T3), param compat — verified unnecessary in-source, noted in Global Constraints; setting flip + seeder + changelog (T4/T5), beta-first deploy + manual DB change (T5), caching volume (T3), testing (T2 smoke + headonly, T5 live). Fork+submodule (T1).
- **Param compat:** upstream `ProcessExpressionAction` already maps `action=wav`→wave; `GetSizeRequest` maps `s`→0.5/`l`→2/else→1 (so `m`/`b` render medium, never naked); `GetSetTypeRequest` honors `headonly=1`; `ProcessGestureRequest` handles `sml`. Hence no fork code patch.
- **Port consistency:** imager listens on 3030 (`API_PORT`) everywhere — Dockerfile default, smoke run, compose env, nginx `proxy_pass http://imager:3030/`.
- **Naked-baseline test:** compares clothed vs `hd`-only byte size to programmatically prove clothing rendered, rather than eyeballing.
