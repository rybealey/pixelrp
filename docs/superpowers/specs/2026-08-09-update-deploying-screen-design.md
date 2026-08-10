# Update-deploying screen — design

**Date:** 2026-08-09
**Source design:** Claude Design project "Game update deployment screen"
(`Update Deploying.dc.html`) — implement surgically accurate to that design.

## Problem

When the emulator restarts for a deploy, players get the CMS's generic
"Whoops! It seems like you have been disconnected" overlay. It says nothing
about why, how long, or what's new. Worse, `docker compose up -d emulator`
SIGKILLs the process without running `PerformShutDown()` — no goodbye
broadcast, no inventory save, stale `server_status`.

## Goal

When a deployment starts:

1. All players are disconnected *gracefully* (broadcast, inventory save,
   clean socket close).
2. Instead of the generic disconnect overlay, the client shows the
   full-screen **Update in progress** design: animated logo over the terrace
   scene, pixel progress bar with live step text and ETA, and a Patch Notes
   card fed by the newest `CHANGELOG.md` release.
3. Progress/ETA reflect the *real* deployment: the GitHub Actions
   "Deploy to VPS" run currently in progress.
4. When the run succeeds, the screen flips to the done state
   ("All districts back online. See you in the city!") with a ▶ Reconnect
   button that reloads the client.

## Architecture

```
GitHub Actions "Deploy to VPS" run (workflow_dispatch)
        │  runs list + jobs API (server-side, cached, ETag)
        ▼
CMS GET /api/deploy-status  ──── also parses CHANGELOG.md (ro mount,
        │                        raw.githubusercontent fallback)
        ▼  same-origin fetch, like /api/online-count
Client DeploymentView (inside the nitro iframe)
```

### Deploy workflow (`.github/workflows/deploy.yml`, plus repo)

- Trigger: `workflow_dispatch` only — pushes to `main` (docs, changelog)
  must not restart the hotel. Concurrency group `deploy-production`.
- Runner phase (players still online, screen not yet visible): checkout with
  submodules, build the nitro client (`build-client.sh --prod` equivalent —
  the VPS has no Node).
- VPS phase over SSH; step names are **exactly** the design's phase strings
  so the status endpoint can pass them through:
  1. `Backing up city data` — `docker compose stop emulator` → SIGTERM →
     graceful `PerformShutDown()` (broadcast + save + disconnect) + DB dump.
  2. `Uploading new assets` — rsync built client (preserving prod configs),
     `git pull` + submodule update on the VPS.
  3. `Applying database patches` — replay any new
     `emulator/Resources/SQLs/Updates/*.sql` (tracked via an applied-set
     table, idempotent).
  4. `Restarting districts` — compose build + up for emulator (and cms/web
     when their code changed).
  5. `Polishing pixels` — poll emulator logs for `EMULATOR -> READY!`
     (scoped to the container's current start) before declaring success.
- Secrets: `DEPLOY_SSH_KEY`, `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PORT`,
  `DEPLOY_HOST_KEY`, `DEPLOY_PATH` — same set the arcturus-legacy workflow
  used. The user must set these; the workflow is inert until then.

### Emulator graceful shutdown

`Program.Main` registers `PosixSignalRegistration` for SIGTERM + SIGINT →
`PlusEnvironment.PerformShutDown()` (with an `Interlocked` re-entrancy guard
also honored by the crash handler). `compose.yaml` gains
`stop_grace_period: 60s` on the emulator so the save completes before
Docker escalates to SIGKILL.

### CMS `GET /api/deploy-status`

Response (Laravel resource, `{ data: … }` like `/api/online-count`):

```json
{
  "data": {
    "status": "idle | deploying | done | failed",
    "progress": 62,
    "step": "Applying database patches…",
    "etaSeconds": 95,
    "changelog": {
      "date": "2026-08-09",
      "title": "The hotel found its tannoy",
      "sections": [
        { "category": "Added", "entries": ["**Hotel-wide announcements.** …"] }
      ]
    }
  }
}
```

- GitHub source: `GET /repos/rybealey/pixelrp/actions/runs?…` filtered to
  the Deploy workflow; when a run is `in_progress`/`queued`, also
  `GET /runs/{id}/jobs` for the current step. Repo is public: unauthenticated
  works; ETag conditional requests (304s are free) + a short computed-status
  cache (5 s active / 30 s idle) keep us under the 60/hr IP budget; an
  optional `GITHUB_DEPLOY_TOKEN` env raises the ceiling.
- `progress` = elapsed ÷ average duration of the last ≤5 successful runs
  (fallback 300 s), clamped to 3–97 while running; 100 on success.
  `etaSeconds` = remaining estimate, floor 30 s while running.
- `step`: current in-progress step name if it's one of the five design
  strings (ellipsis appended client-side); other steps (checkout, node
  setup, client build) map to the first phase text.
- `done` is reported for a short window (~2 min) after a successful run so
  late pollers see the reconnect state; after that, `idle`.
- A failed/cancelled run reports `failed`: the client then falls back to the
  standard disconnect overlay rather than showing a lying progress bar.
- Changelog: newest `## YYYY-MM-DD — Title` section of `CHANGELOG.md`
  (skipping the maintainer HTML comment), split into
  `### Added/Changed/Fixed/Known issues` with `- ` entries (markdown left
  intact; the client renders bold lead-ins). Read from the compose-mounted
  file, falling back to `raw.githubusercontent.com/rybealey/pixelrp/main`.

### Client `DeploymentView`

- New `components/deployment/DeploymentView.tsx` + SCSS registered in
  `components/index.scss`; rendered from `App.tsx` above `LoadingView`.
- Trigger: on `CONNECTION_CLOSED`, `CONNECTION_ERROR`, or
  `CONNECTION_HANDSHAKE_FAILED`, fetch `/api/deploy-status` (one retry ~3 s
  later to dodge cache staleness right at deploy start). If
  `deploying`/`done` → show the view and **skip**
  `HabboWebTools.send(-1, 'client.init.handshake.fail')` so the CMS
  "Whoops" overlay never covers it. Otherwise → previous behavior.
- While visible: poll every 4 s. `deploying` → live pct/step/ETA;
  `done` → done state + ▶ Reconnect (`window.location.reload()`);
  `failed` → fall back to the standard overlay.
- Dev preview: `?deploy-preview=<pct|done>` (DEV builds only) renders the
  view with simulated data for visual verification.

## Visual spec (surgical)

Everything from `Update Deploying.dc.html` + the design-system bundle:

- Tokens: the pixelrp design-system CSS variables (colors, spacing,
  typography, effects) scoped under the view's root class.
- Fonts: Press Start 2P (display), Silkscreen 400/700 (pixel UI), Barlow
  400 (body) — self-hosted woff2 in `src/assets/webfonts` (the client
  bundles fonts; no Google Fonts runtime dependency).
- Layout: `min-height 100dvh`, gradient-over-terrace background
  (`rgba(26,10,20,.45)→.78` over `scene-terrace.png`, pixelated,
  cover/center), column, `max-width 430px` content, gap 20, padding
  `30px 16px 44px`; fixed 8px `--orange-500` strip at the bottom with 2px
  ink top border.
- Logo: `logo-animated.gif`, `width min(230px, 62%)`, centered, pixelated.
- Status card: `rgba(26,10,20,.9)`, 2px ink border, `--shadow-pixel-brand`,
  padding `16px 16px 18px`, gap 12. Header row: 10×10 `--warning` square
  (2px ink border) blinking `1.1s steps(1)` + Silkscreen 700 13px uppercase
  cream heading ("Update in progress" / "Update deployed").
- ProgressBar (per `ProgressBar.jsx`): Silkscreen label row
  (label + right-aligned N%), 20 flex cells gap 2 in a `--plum-900` track,
  3px padding, 2px ink border, `--bevel-sunken`, height 24; filled cells
  `--grad-cta` with `inset 0 2px 0 rgba(255,255,255,.4)`.
- Not-done row: Barlow 14 `--orange-200` step text + Silkscreen 11
  `--mauve-300` uppercase `est. ~N min`, space-between.
- Done state: centered column, Barlow 14 `--orange-200` "All districts back
  online. See you in the city!", primary lg Button (per `Button.jsx`:
  grad-cta face, ink border, `shadow-pixel + bevel-raised`, Silkscreen 700
  16px uppercase, press = translate(2px,2px) + bevel only, hover
  brightness 1.12) labeled "▶ Reconnect".
- Patch notes card: `--surface-card` (white), ink border, `--shadow-pixel`;
  header `--grad-cta`, 2px ink bottom border, padding `12px 14px`,
  "PATCH NOTES" in Press Start 2P 13px white with 2px ink text-shadow,
  right side Silkscreen 700 12px cream uppercase — shows the release date
  (this hotel has no version numbers).
- Body: `max-height min(42dvh, 380px)` scroll, padding 16, gap 18 between
  category groups, gap 8 within; Badge (per `Badge.jsx`: Silkscreen 700
  11px uppercase, 3px 8px, ink border, `--shadow-pixel-sm`) then entries as
  `▶` (Silkscreen 10px `--magenta-500`, margin-top 4) + Barlow 14.5px
  `--leading-body` text with the changelog's bold lead-ins rendered bold.
- Category → badge: Added → "New" (success), Fixed → "Fixes" (info),
  Changed → "Changed" (warning), Known issues → "Known issues" (danger).
- Footer: centered Barlow 13 `--mauve-300` "Your progress is safe — you'll
  reconnect right where you left off."

## Pre-disconnect countdown (added same day)

The shutdown warning is a Platform toast, not the legacy modal:
`PerformShutDown()` broadcasts `hotel.alert` / BUBBLE with
"A software update has been pushed. PixelRP is restarting in…
%countdown:15% seconds." and waits 15 s before stopping the game loop.
`NotificationPlatformBubbleView` recognizes the `%countdown:N%` token and
ticks it down once per second (singularizing "seconds" at 1). The token is
generic — any `:ha` message may carry one.

## Out of scope

- Auto-deploy on push (deliberate `workflow_dispatch` only).
- Failure-state artwork (failed deploys fall back to the classic overlay).
