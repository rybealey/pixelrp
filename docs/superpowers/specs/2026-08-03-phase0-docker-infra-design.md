# Phase 0: Local Docker Infrastructure — Design

**Date:** 2026-08-03
**Status:** Approved
**Scope:** Bare-bones local development infrastructure for a Habbo retro roleplay server. Infrastructure only — no roleplay or combat systems. Local only — no SSL, no public exposure, no production hardening.

## Goal

`docker compose up` brings the full stack online locally. All persistent data (accounts, economy, currencies, progression) survives `docker compose down` → `docker compose up`. Only an explicit, clearly-named reset command destroys data.

## Stack

| Component | Choice | Version |
|---|---|---|
| Emulator | Arcturus Morningstar (Krews release, user-supplied jar) | 4.0.1+ beta, Java 21 |
| Database | MariaDB | 11 |
| CMS | AtomCMS (Laravel) | PHP 8.3+ |
| Client | Nitro HTML5 (`billsonnn/nitro-react`), built from source in Docker | pinned ref |

## Topology decision

**Port-per-service, no front router.** A central nginx was considered and rejected: path-routing the CMS, client, and assets behind one port adds a service, rewrite rules, and Laravel/Vite base-path complexity with no local-dev payoff. The `nitro` service is already an `nginx:alpine` serving static files, so it doubles as the game-asset host under `/assets`.

### Ports

| Endpoint | URL |
|---|---|
| CMS (registration, housekeeping) | `http://localhost:8080` |
| Nitro client | `http://localhost:3000` |
| Game assets | `http://localhost:3000/assets/` |
| Emulator websocket | `ws://localhost:2096` |
| MariaDB (debugging) | `127.0.0.1:3310` |
| RCON | **not exposed to host** — internal only, `emulator:3001` from the CMS |

Ports are overridable via `.env`.

## Project layout

```
pixelrp/
├── docker-compose.yml
├── .env.example            # committed template, every variable documented
├── .env                    # gitignored; `make env` generates it with real secrets
├── .gitignore              # excludes .env, data/, artifacts contents, cms/src
├── Makefile
├── README.md
├── artifacts/              # user-supplied inputs (gitignored, README committed)
│   ├── README.md           # exact drop-in instructions per file
│   ├── arcturus/           # exactly one Habbo-*.jar from the Krews 4.0.1+ release
│   │   └── plugins/        # NitroWebsockets-3.2.jar — REQUIRED for Nitro (`make fetch-ws-plugin`)
│   ├── sql/                # 01-base.sql, 02-3_5_4-to-3_5_5.sql, 03-3_5_5-to-4_0_0.sql
│   └── nitro-assets/       # .nitro bundles + gamedata (furnidata, figuredata, …)
├── db/
│   ├── conf/my.cnf         # local tuning, mounted read-only
│   └── init/               # 01-arcturus.sh (ordered SQL apply + inline websocket overrides)
├── emulator/               # Dockerfile, entrypoint.sh
├── cms/                    # Dockerfile, entrypoint.sh, apache vhost; src/ auto-cloned
├── nitro/                  # Dockerfile, nginx.conf, config templates, entrypoint.sh
└── data/                   # ALL persistent state (gitignored, created on first up)
    ├── db/                 # MariaDB datadir
    ├── emulator/           # config.ini + logs
    └── cms/storage/        # Laravel storage/
```

## Persistence — the load-bearing requirement

Bind mounts under `./data/`, chosen over named volumes so persistence is visible with `ls`:

| Host path | Container path | Holds |
|---|---|---|
| `./data/db` | `db:/var/lib/mysql` | every account, currency, item, progression row |
| `./data/emulator` | `emulator:/app` | `config.ini`, emulator logs |
| `./data/cms/storage` | `cms:/var/www/html/storage` | Laravel storage, seed marker, logs |

Properties:

- `docker compose down` (no `-v`) never touches bind mounts. Restart-safe by construction.
- MariaDB's init directory only runs when the datadir is empty — repeated `up` never re-applies SQL, so no corruption from re-runs.
- `make reset` is the **only** destructive path: it prints exactly what it will delete and requires typing `yes-destroy-my-data` before running `docker compose down -v` and removing `./data`.

## Database bootstrap

User drops three SQL files into `artifacts/sql/` under prescribed names so ordering is unambiguous:

1. `01-base.sql` — Arcturus base schema
2. `02-3_5_4-to-3_5_5.sql` — first migration (must not be skipped)
3. `03-3_5_5-to-4_0_0.sql` — second migration

`db/init/01-arcturus.sh` (in MariaDB's `/docker-entrypoint-initdb.d`, with `artifacts/sql` mounted read-only) verifies **all three exist by exact name before applying any of them**; if one is missing it aborts init with a message naming the missing file (and the message notes that an aborted first init requires `make reset` before retrying, since MariaDB will otherwise skip the init directory on the next boot). No substitutes, ever. It then applies them in order, then any optional `04-`…`09-` prefixed extras (for the 4.0.2/4.0.3-beta updates), then an inline heredoc of local overrides (authored in this repo — not a user artifact) that pre-seeds the NitroWebsockets plugin's `emulator_settings` rows for local use: `websockets.whitelist = *` (local-only throwaway value), `ws.nitro.host = 0.0.0.0`, `ws.nitro.port = 2096` — written as `INSERT … ON DUPLICATE KEY UPDATE` since the plugin also registers these rows on first boot. Research note (verified against 4.0.x source, branch ms3-upgrade): RCON is configured in `config.ini`, **not** `emulator_settings`, so RCON overrides live in the emulator's generated config instead.

AtomCMS's own tables come from `php artisan migrate --force` in the CMS entrypoint on every boot (idempotent via Laravel's migrations table). Seeding runs once, guarded by a marker file in persisted `storage/`.

## Services

### `db` — `mariadb:11`
- Credentials from `.env` (`MARIADB_ROOT_PASSWORD`, `MARIADB_DATABASE`, `MARIADB_USER`, `MARIADB_PASSWORD`).
- Mounts: datadir bind mount; `db/conf/my.cnf` → `/etc/mysql/conf.d/` (read-only); `db/init/` → `/docker-entrypoint-initdb.d` (read-only); `artifacts/sql/` → `/artifacts/sql` (read-only).
- Healthcheck: MariaDB's bundled `healthcheck.sh --connect --innodb_initialized`.
- `my.cnf`: small `innodb_buffer_pool_size` (256M), sane `max_connections` (100), utf8mb4 server defaults. Comments note the *client-side* pool is HikariCP, sized in Arcturus `config.ini` (`db.pool.maxsize`), and must stay below `max_connections`.

### `emulator` — built on `eclipse-temurin:21-jre`
- Jar bind-mounted read-only from `artifacts/arcturus/`; entrypoint requires **exactly one** `*.jar` there (Krews 4.0.x builds are named like `Habbo-4.0.1-beta-jar-with-dependencies.jar`), exits with a clear named-path error if absent or ambiguous.
- **Websockets via plugin (research-verified):** 4.0.x has no built-in WS support; the NitroWebsockets plugin jar must be in `artifacts/arcturus/plugins/` (fetched knowingly via `make fetch-ws-plugin` from the official Krews repo). Entrypoint copies plugin jars into the persisted `/app/plugins/` and exits with a clear error if none are present.
- On first run, entrypoint generates `config.ini` in `/app` (persisted) from env — DB host `db`, credentials, `game.host=0.0.0.0`, `rcon.host=0.0.0.0`, `rcon.allowed` = the CMS container's static IP (Arcturus matches whitelist IPs exactly — no CIDR). If `config.ini` already exists it is left untouched (hand edits survive).
- **Env-var naming trap (research-verified):** if `DB_HOSTNAME` is set in the emulator's environment, Arcturus ignores `config.ini` entirely and switches to env-only config. All compose-provided variables therefore use an `ARC_` prefix so the emulator never sees `DB_HOSTNAME`.
- Working directory `/app` so logs land in the persisted mount.
- `depends_on: db: condition: service_healthy`, plus a belt-and-braces TCP wait in the entrypoint.
- Exposes `2096` (websocket) to localhost. RCON (`3001`) and raw-TCP `game.port` (`3000`, Flash-era, unused by Nitro) stay internal.
- Services get static IPs on a dedicated compose network (subnet `172.28.0.0/24`) so the exact-match RCON whitelist stays stable.

### `cms` — multi-stage build → `php:8.3-apache`
- Source: `make up` clones `https://github.com/atom-retros/atomcms` into `./cms/src` if absent (host-side, gitignored, so the source stays visible and editable); Dockerfile COPYs from there.
- Stages: `node:22-alpine` for the Vite 6 asset build (`yarn install --frozen-lockfile && yarn build:atom` — repo ships `yarn.lock`, no `package-lock.json`); final `php:8.3-apache` with the research-verified extensions beyond image defaults: `pdo_mysql`, `gd`, `sockets` (required by the AtomCMS RCON package), `zip`, `opcache`; composer binary copied from `composer:2`; docroot at `public/`, `mod_rewrite` on. Laravel 11 / PHP `^8.2` per composer.json.
- **Fragility note (research-verified):** AtomCMS pulls six first-party packages as VCS repos plus `laravel/nova` from a Bitbucket repo authenticated by the `auth.json` committed in the AtomCMS repo itself. The build needs network; an optional `GITHUB_TOKEN` build arg mitigates GitHub API rate limits.
- Config comes as **real container environment** in compose (Laravel's Dotenv never overrides real env, and real env works without a `.env` file) — zero templating code, one source of truth. `DB_HOST=db`, `DB_CONNECTION=mariadb`, `SESSION_DRIVER=database`, `RCON_HOST=emulator`, `RCON_PORT=3001`, `APP_KEY` from the project `.env`.
- Entrypoint: ensures the `storage/` skeleton exists inside the bind mount and is writable by `www-data`; waits for db; `php artisan migrate --force` (AtomCMS migrations run against the **same DB as the emulator** and ALTER emulator tables — so the Arcturus schema must exist first, which the dependency chain guarantees); seeds once behind a storage marker; `storage:link` if missing; then `apache2-foreground`.
- `depends_on: db: condition: service_healthy`.

### `nitro` — multi-stage build → `nginx:alpine`
- Build stage: `node:20-alpine` clones `billsonnn/nitro-react` at a pinned commit (default `75ff874b73d5fc5672a38c536444efa0f0d27e8f`, current main — the 2.1.1 tag is 3.5 years stale; overridable via build arg), `yarn install --frozen-lockfile`, then plain `yarn build` (not `build:prod`, whose only addition is a network-dependent browserslist update). Output: `dist/`.
- Runtime: nginx serves the client at `/`; `artifacts/nitro-assets/` bind-mounted read-only at `/usr/share/nginx/html/assets` (same origin as the client → no CORS needed).
- Config (research-verified): the built app fetches `/renderer-config.json` and `/ui-config.json` at **runtime** from the web root. A container-start script rewrites only our keys (`socket.url`, `asset.url`, `image.library.url`, `hof.furni.url`, `url.prefix`) into the pinned ref's `.example` configs using `jq` — safe against the configs' internal `${key}` interpolation syntax, and upstream config evolution never requires re-vendoring a 31 KB file.
- No DB dependency.

## Configuration & secrets

- One root `.env` is the single source of truth: DB credentials, all host ports, `APP_KEY`, pinned nitro-react ref.
- `.env.example` documents every variable. `make env` copies it and fills secrets (`openssl rand`). `.env` is gitignored.
- Compose interpolates `.env`; entrypoints template service-level configs from container env.

## Failure handling

Every missing-artifact path fails loudly and specifically, never inventing substitutes:

| Missing | Behavior |
|---|---|
| Any of the three SQL files | DB init aborts, message names the missing file + the `make reset` retry requirement |
| Arcturus jar | Emulator container exits, message names the expected path |
| NitroWebsockets plugin jar | Emulator container exits, message names `make fetch-ws-plugin` |
| Nitro assets | Client serves, container logs a warning that `/assets` is empty |

## Makefile targets

`up` (clone CMS source if needed, `docker compose up -d --build`), `down`, `logs`, `ps`, `shell-db` (mariadb client in the db container), `env` (generate `.env`), `fetch-ws-plugin` (explicit one-command download of the NitroWebsockets jar from the official Krews repo), `reset` (typed-confirmation destroy, the only data-destroying path).

## Acceptance criteria (from the brief)

1. `docker compose up` starts all services with no fatal errors; emulator log shows DB connection and finished loading.
2. CMS reachable at `http://localhost:8080`; test account registration works.
3. Nitro client reachable at `http://localhost:3000` and connects to the emulator websocket.
4. Persistence proof: register account → `docker compose down` → `docker compose up` → account still in `users` table.
5. `make reset` is the only path that wipes data and warns (typed confirmation) first.

Full end-to-end verification requires the user-supplied artifacts; everything buildable without them (images, compose config, CMS/nitro clones) is verified independently, and each missing artifact is flagged the moment it blocks.

## Out of scope

Roleplay/combat systems, SSL, public domains, reverse-proxy hardening, production tuning, backups/replication.
