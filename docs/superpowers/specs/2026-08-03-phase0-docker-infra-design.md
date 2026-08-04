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
│   ├── arcturus/           # Habbo-*.jar from the Krews 4.0.1+ release
│   ├── sql/                # 01-base.sql, 02-3_5_4-to-3_5_5.sql, 03-3_5_5-to-4_0_0.sql
│   └── nitro-assets/       # .nitro bundles + gamedata (furnidata, figuredata, …)
├── db/
│   ├── conf/my.cnf         # local tuning, mounted read-only
│   └── init/               # 01-arcturus.sh + local-overrides.sql
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

`db/init/01-arcturus.sh` (in MariaDB's `/docker-entrypoint-initdb.d`, with `artifacts/sql` mounted read-only) verifies **all three exist by exact name before applying any of them**; if one is missing it aborts init with a message naming the missing file. No substitutes, ever. It then applies them in order, followed by `db/init/local-overrides.sql` (authored in this repo — not a user artifact): sets RCON bind host to `0.0.0.0` in `emulator_settings` so the CMS can reach it over the Docker network, plus any websocket/whitelist settings needed for localhost. Exact setting keys to be verified against the Arcturus 4.x settings table during implementation.

AtomCMS's own tables come from `php artisan migrate --force` in the CMS entrypoint on every boot (idempotent via Laravel's migrations table). Seeding runs once, guarded by a marker file in persisted `storage/`.

## Services

### `db` — `mariadb:11`
- Credentials from `.env` (`MARIADB_ROOT_PASSWORD`, `MARIADB_DATABASE`, `MARIADB_USER`, `MARIADB_PASSWORD`).
- Mounts: datadir bind mount; `db/conf/my.cnf` → `/etc/mysql/conf.d/` (read-only); `db/init/` → `/docker-entrypoint-initdb.d` (read-only); `artifacts/sql/` → `/artifacts/sql` (read-only).
- Healthcheck: MariaDB's bundled `healthcheck.sh --connect --innodb_initialized`.
- `my.cnf`: small `innodb_buffer_pool_size` (256M), sane `max_connections` (100), utf8mb4 server defaults. Comments note the *client-side* pool is HikariCP, sized in Arcturus `config.ini` (`db.pool.maxsize`), and must stay below `max_connections`.

### `emulator` — built on `eclipse-temurin:21-jre`
- Jar bind-mounted read-only from `artifacts/arcturus/`; entrypoint globs `Habbo-*.jar`/`*.jar`, exits with a clear named-file error if absent.
- On first run, entrypoint generates `config.ini` in `/app` (persisted) from `.env` values — DB host `db`, port `3306`, credentials. If `config.ini` already exists it is left untouched (hand edits survive).
- Working directory `/app` so logs land in the persisted mount.
- `depends_on: db: condition: service_healthy`, plus a belt-and-braces TCP wait in the entrypoint.
- Exposes `2096` (websocket) to localhost. RCON (`3001`) stays internal.

### `cms` — multi-stage build → `php:8.3-apache`
- Source: `make up` clones `https://github.com/atom-retros/atomcms` into `./cms/src` if absent (host-side, gitignored, so the source stays visible and editable); Dockerfile COPYs from there.
- Stages: `composer:2` for `composer install`; `node:20` for the Vite asset build; final `php:8.3-apache` with required extensions (`pdo_mysql`, `gd`, `zip`, `intl`, `bcmath`, `exif`, `opcache` — final list verified against AtomCMS's composer.json during implementation), docroot at `public/`, `mod_rewrite` on.
- Entrypoint: templates Laravel `.env` from container env on first run; ensures the `storage/` skeleton exists inside the bind mount and is writable by `www-data`; runs `migrate --force`; seeds once behind a storage marker; then `apache2-foreground`.
- Laravel `.env` points `DB_HOST=db`, RCON at `emulator:3001`. `APP_KEY` comes from the project `.env` (generated by `make env`), not from runtime magic.
- `depends_on: db: condition: service_healthy`.

### `nitro` — multi-stage build → `nginx:alpine`
- Build stage: `node:20-alpine` clones `billsonnn/nitro-react` at a pinned ref (overridable via build arg) and produces the production bundle.
- Runtime: nginx serves the client at `/`; `artifacts/nitro-assets/` bind-mounted read-only at `/assets`.
- Nitro's runtime config files (renderer/ui config JSON — exact filenames verified during implementation) are generated at **container start** from `.env` via a template, so the websocket URL (`ws://localhost:2096`) and asset URL (`http://localhost:3000/assets`) are not baked into the image.
- No DB dependency.

## Configuration & secrets

- One root `.env` is the single source of truth: DB credentials, all host ports, `APP_KEY`, pinned nitro-react ref.
- `.env.example` documents every variable. `make env` copies it and fills secrets (`openssl rand`). `.env` is gitignored.
- Compose interpolates `.env`; entrypoints template service-level configs from container env.

## Failure handling

Every missing-artifact path fails loudly and specifically, never inventing substitutes:

| Missing | Behavior |
|---|---|
| Any of the three SQL files | DB init aborts, message names the missing file |
| Arcturus jar | Emulator container exits, message names the expected path |
| Nitro assets | Client serves, container logs a warning that `/assets` is empty |

## Makefile targets

`up` (clone CMS source if needed, `docker compose up -d --build`), `down`, `logs`, `ps`, `shell-db` (mariadb client in the db container), `env` (generate `.env`), `reset` (typed-confirmation destroy, the only data-destroying path).

## Acceptance criteria (from the brief)

1. `docker compose up` starts all services with no fatal errors; emulator log shows DB connection and finished loading.
2. CMS reachable at `http://localhost:8080`; test account registration works.
3. Nitro client reachable at `http://localhost:3000` and connects to the emulator websocket.
4. Persistence proof: register account → `docker compose down` → `docker compose up` → account still in `users` table.
5. `make reset` is the only path that wipes data and warns (typed confirmation) first.

Full end-to-end verification requires the user-supplied artifacts; everything buildable without them (images, compose config, CMS/nitro clones) is verified independently, and each missing artifact is flagged the moment it blocks.

## Out of scope

Roleplay/combat systems, SSL, public domains, reverse-proxy hardening, production tuning, backups/replication.
