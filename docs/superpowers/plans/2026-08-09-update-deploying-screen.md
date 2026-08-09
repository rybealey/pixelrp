# Update-deploying screen — implementation plan

Spec: `docs/superpowers/specs/2026-08-09-update-deploying-screen-design.md`

## Task 1 — Emulator: graceful shutdown on SIGTERM

1. `emulator/PlusEnvironment.cs`: add an `Interlocked`-guarded entry to
   `PerformShutDown()` so signal + crash paths can't run it twice.
2. `emulator/Program.cs`: register `PosixSignalRegistration` for SIGTERM and
   SIGINT → cancel default handling, call `PlusEnvironment.PerformShutDown()`.
3. `compose.yaml`: `stop_grace_period: 60s` on the emulator service.
4. Verify: `dotnet build emulator`.

## Task 2 — Deploy workflow

1. `.github/workflows/deploy.yml` (plus repo): `workflow_dispatch`,
   concurrency `deploy-production`; runner steps (checkout w/ submodules,
   node setup, client build) then SSH steps named exactly:
   `Backing up city data`, `Uploading new assets`,
   `Applying database patches`, `Restarting districts`, `Polishing pixels`.
2. DB patches: replay `emulator/Resources/SQLs/Updates/*.sql` not yet in a
   `_applied_updates` tracking table (create if missing).
3. Readiness gate: poll `docker compose logs emulator` since container
   start for `EMULATOR -> READY!`, 300 s deadline.
4. Secrets documented in the workflow header; inert until the user sets
   them (`DEPLOY_SSH_KEY/HOST/USER/PORT/HOST_KEY/PATH`).

## Task 3 — CMS: `/api/deploy-status`

1. `compose.yaml` + `compose.prod.yaml`: mount `./CHANGELOG.md` read-only
   at `/var/www/html/CHANGELOG.md`.
2. `cms/app/Services/Deploy/DeployStatusService.php`: GitHub runs+jobs
   fetch (ETag + `Cache`), pct/step/ETA computation, `done` window,
   `failed` mapping; `ChangelogParser` for the newest release section.
3. Controller method + `DeployStatusResource` + route
   `GET /api/deploy-status` (`throttle:60,1`).
4. Pest tests: changelog parser (fixture with comment block, multiple
   same-date releases, category mapping) and status computation (idle /
   in-progress pct+ETA / done window / failed) with `Http::fake`.

## Task 4 — Client: DeploymentView

1. Fonts: add Press Start 2P 400, Silkscreen 400+700, Barlow 400 woff2 to
   `src/assets/webfonts`, `@font-face` in `src/assets/styles/fonts.scss`.
2. Assets: `scene-terrace` (lossless webp if smaller, else png) and
   `logo-animated.gif` under `src/assets/images/deployment/`.
3. `src/components/deployment/DeploymentView.tsx` + `DeploymentView.scss`
   (registered in `components/index.scss`; z-index var in `App.scss`):
   markup + styles surgically per spec; internal 4 s poller; changelog
   markdown bold/`code` rendering; Reconnect → `window.location.reload()`.
4. `App.tsx`: on CONNECTION_CLOSED / CONNECTION_ERROR /
   CONNECTION_HANDSHAKE_FAILED → check `/api/deploy-status` (1 retry, 3 s);
   deploying/done → show view, suppress `HabboWebTools.send`; else existing
   behavior. DEV-only `?deploy-preview=` hook.
5. Config key `deployment.status.url` in `ui-config.json`(+example) with
   default `/api/deploy-status`; add to `nitro/ui-config*.json` at deploy.

## Task 5 — Verify

1. `dotnet build` (emulator), Pest (cms, via docker php if needed),
   `vite build` (client).
2. Dev server + `?deploy-preview=62` and `?deploy-preview=done` at
   390×844: screenshot vs the design render (already captured).

## Task 6 — Ship

1. Player-facing `CHANGELOG.md` entry (new 2026-08-09 section content).
2. Commits: client submodule, then plus root (docs, workflow, compose,
   cms submodule bump if cms committed separately, changelog).
