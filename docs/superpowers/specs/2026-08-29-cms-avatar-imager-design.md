# CMS Avatar Imager (nitro-imager) — Design

**Date:** 2026-08-29
**Status:** Approved, pending implementation plan
**Scope:** Avatars only, beta-first

## Problem

Avatars across the CMS (the "Online Friends" widget on the profile page, plus
~20 other templates) render **naked** — a body with the correct skin tone but no
clothing.

### Root cause (confirmed)

The CMS renders every avatar through the `avatar_imager` row in
`website_settings`, which on both beta and local dev still points at Habbo's
**official** imaging server:

```
https://www.habbo.com/habbo-imaging/avatarimage?figure=
```

Habbo's imager renders the figure parts it recognizes and **silently drops any
figure set-ID it doesn't have in its own figuredata.** PixelRP is a roleplay
hotel where players wear a lot of **custom-imported clothing** (`.nitro` sets
registered in our `FigureData.json`/`FigureMap.json`). Habbo has none of those
set-IDs, drops them all, and leaves only `hd` (skin) → a naked body with the
right skin tone.

Verified in-browser against the live habbo.com imager:
- A look using set-IDs that overlap Habbo's official range renders clothed
  (e.g. `ClaudeTest`'s look kept its shirt/legs/shoes, but Habbo dropped the
  custom `ca-80000103` accessory).
- A look composed of PixelRP-exclusive sets renders as naked skin.

In-game the client looks correct because Nitro renders avatars locally from our
own gamedata + `.nitro` bundles. The CMS has no such renderer, so it falls back
to an external imager that doesn't know our custom sets.

There is **no self-hosted imager anywhere in the project today** — nothing to
point the setting at. So the fix is to stand one up.

### The naked-headshot detail

The "Online Friends" strip requests `headonly=1`, yet the screenshotted avatars
are tiny full bodies. That is a habbo.com quirk (it ignores `headonly` in the
`size=s&action=wav` combination). The replacement imager honors `headonly`
properly, so headshots will finally render as heads.

## Chosen approach

Deploy **`billsonnn/nitro-imager`** (TypeScript / Node, authored by the
nitro-renderer author) as a new internal compose service, fed by the **same
gamedata + `.nitro` figure bundles the client already uses**, reverse-proxied
through the existing web nginx at `beta.pixelrp.co/imaging/`. The only CMS-side
change is repointing the `avatar_imager` setting.

It wraps the real nitro-renderer avatar generator against our own `.nitro`
bundles (including custom clothing libs), so custom outfits render just like
in-game. Its rendering fidelity tracks the client because it uses the same code
path and the same (already-repaired) `FigureMap.json`.

### Alternatives rejected
- **Orion-Server/avatar-imaging** — same engine, fresher packaging. Kept only as
  a fallback if `node-canvas` won't build on our pinned Node.
- **Build-from-scratch headless nitro-renderer** — that is exactly what
  nitro-imager already is; no reason to reinvent it.
- **Classic PHP `habbo-imaging` / Quackster Avatara** — SWF-asset based;
  dealbreaker, since our custom clothing is `.nitro`.

## Architecture / data flow

```
CMS template  ──►  avatar_imager setting
                   = https://beta.pixelrp.co/imaging/?figure=
                        │
host nginx (:8081) ──►  web container nginx
                        location /imaging/  ──►  imager:8080  (new service)
                                                    │ pulls, over the compose network:
                                                    │   http://web/nitro-assets/gamedata/FigureData.json
                                                    │   …/FigureMap.json, EffectMap.json, HabboAvatarActions.json
                                                    │   http://web/nitro-assets/bundled/figure/%libname%.nitro
                                                    ▼
                                                 renders PNG (nitro-renderer avatar code)
                                                 → in-memory .nitro cache + on-disk PNG cache (named volume)
```

The imager consumes assets **over HTTP from the `web` service** — what it is
built for — so there is **zero asset baking/copying** into the imager image, and
it always sees the same figuredata the live client sees. The web service already
serves `/nitro-assets/` (gamedata + 2,985 figure `.nitro` bundles) with
`Access-Control-Allow-Origin *`.

## Components

### 1. `imager` service (fork + submodule)
- Fork `billsonnn/nitro-imager` into the PixelRP org; add as a git submodule,
  consistent with how `client`/`emulator` are vendored.
- The fork carries our patches (tracked in git, not invisible container tweaks):
  1. A **Dockerfile** (upstream ships none).
  2. **Node 18 pin** for `node-canvas` native build stability.
  3. **Param-compat aliases** (see below).
- New service in `compose.beta.yaml` (later `compose.prod.yaml`), internal-only
  (no host port publish). Reachable as `http://imager:8080` on the compose
  network.
- Config (`.env` / `config.json`) points every asset URL at the web service:
  - `FigureData` / `FigureMap` / `EffectMap` / `HabboAvatarActions` →
    `http://web/nitro-assets/gamedata/...`
  - bundle template → `http://web/nitro-assets/bundled/figure/%libname%.nitro`

### 2. Param compatibility (fork patch)
nitro-imager's param **names** match habbo, but a few **values** differ. CMS
templates emit habbo values, so alias them in the fork — **no CMS template
changes needed**:
- `action=wav` → `wave`
- `size=m` → `n` (medium), `size=b` → `l` (big)
- Already matching: `figure`, `direction`, `head_direction`, `gesture=sml`,
  `headonly`, `size=s`, `size=l`. Stray no-op values (e.g. `action=sml`, which
  isn't a valid habbo action either) fall back to the imager default.

### 3. web nginx route
- Add to `docker/web/nginx.conf`:
  `location /imaging/ { proxy_pass http://imager:8080/; }` with sensible cache
  headers. No host-nginx change: everything under `beta.pixelrp.co/` already
  proxies to the web container.

### 4. CMS setting (data-only)
- Update the `avatar_imager` row in `website_settings`:
  `https://www.habbo.com/habbo-imaging/avatarimage?figure=`
  → `https://beta.pixelrp.co/imaging/?figure=`
- No code/template edits. Per the non-git-deploy rule, this is a **manual DB
  change per environment**, applied to beta first and prod later — not shipped by
  deploy. Update the `WebsiteSettingsSeeder` default too so fresh installs get
  the right value, but the running beta/prod rows must be changed by hand.

## Caching / footprint
- Named volume for the imager's on-disk rendered-PNG cache; document a prune
  approach (the cache grows unbounded otherwise).
- In-memory `.nitro` cache grows with the number of figure libs touched
  (bounded by the library count). Modest Node process overall.
- nginx cache headers on `/imaging/` so repeat CMS page loads don't re-hit the
  renderer.

## Deploy sequencing (beta-first)
1. Fork + submodule + Dockerfile + patches, on the `beta` branch.
2. Add `imager` service + nginx route to beta compose/config; deploy beta.
3. Manually flip the beta `avatar_imager` DB row.
4. Validate on beta (see Testing).
5. Only after beta is confirmed: add the service to prod compose, deploy prod,
   flip the prod DB row.

## Testing
- **Rendering smoke test:** request `/imaging/?figure=<known custom-clothed
  look>&size=l` and assert a clothed PNG comes back — compare byte size /
  non-transparent pixel area against the naked-default baseline for the same
  figure with clothing parts stripped. A naked render must fail the test.
- **Real-figure spot checks:** the figures pulled during investigation
  (`ClaudeTest` with `ca-80000103`, the beta article author's
  `hd-6159…ch-6222…wa-5986` look) render clothed.
- **headonly check:** `headonly=1` returns a head crop, not a full body.
- **Param-compat check:** `action=wav`, `size=m`, `size=b` all render without
  error (aliases applied).
- **Widget check:** load the Online Friends widget on beta after the DB flip and
  confirm clothed headshots.

## Non-goals
- Furni, room, and badge imaging (avatars only).
- Replacing in-game rendering (unchanged; client already correct).
- Any CMS template refactor (the setting flip is the whole CMS change).

## Prerequisites / open items
- Creating the org fork of `billsonnn/nitro-imager` is a manual GitHub step
  (the GitHub MCP is not connected this session). The implementation plan will
  call it out as step 0.
- Confirm prod currently uses the same habbo.com `avatar_imager` value (assumed
  from the seeder default + beta parity; verify before the prod flip).
