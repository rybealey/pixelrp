# PixelRP — Phase 0 local dev stack

Local-only Docker environment for a Habbo retro roleplay server. **Not
production**: every port binds 127.0.0.1, no SSL, no hardening.

| Piece | What | Where |
|---|---|---|
| Emulator | Arcturus Morningstar 4.0.x (Java 21) | `ws://localhost:2096` (websocket) |
| Database | MariaDB 11 — game DB (accounts, economy, progression) | `127.0.0.1:3310` (debug access) |
| CMS | AtomCMS (Laravel 11) — register/housekeeping | http://localhost:8080 |
| Client | Nitro (nitro-react) + game assets | http://localhost:3000 |

## Prerequisites

- Docker Desktop (Compose v2+). ~4 GB free RAM for builds, ~10 GB disk.
- `make`, `git`, `curl`, `openssl` (all standard on macOS).
- The user-supplied artifacts — **see [artifacts/README.md](artifacts/README.md)**:
  emulator jar, NitroWebsockets plugin (`make fetch-ws-plugin`), three SQL
  files, Nitro asset pack.

## First run

    make env              # writes .env with generated secrets (once)
    make fetch-ws-plugin  # downloads the websocket plugin jar (once)
    #  → drop the emulator jar, SQL files, and nitro assets per artifacts/README.md
    make up               # clones AtomCMS source (once), builds, starts everything

Then watch `make logs` until the emulator reports the database connection and
finishes loading. Reachable endpoints: CMS http://localhost:8080 (register
there), client http://localhost:3000 (open via the CMS play button so it gets
an SSO ticket — opened bare it sits on the loading screen).

Missing artifacts fail loudly and name the file: db init aborts (then:
`make reset` before retrying), the emulator exits naming the jar or plugin,
nitro warns about an empty asset folder.

## Proving persistence (acceptance check)

1. Register an account at http://localhost:8080.
2. `make down` — stops containers. **Never deletes data.**
3. `make up`, wait for healthy, then:

       make shell-db
       SELECT id, username, mail FROM users;

   Your account is still there. All state lives in `./data/` bind mounts —
   `ls data/db` shows the database files directly.

## The ONLY way to wipe data

    make reset   # prints exactly what dies, requires typing: yes-destroy-my-data

`docker compose down`, image rebuilds, `docker system prune` — none of those
touch `./data`.

## Day-to-day

| Command | Does |
|---|---|
| `make up` / `make down` | start / stop (data safe) |
| `make logs` / `make ps` | tail logs / status |
| `make shell-db` | root MariaDB shell into the game DB |
| `make reset` | ⚠ destroy ./data after typed confirmation |

## Wiring facts worth knowing

- One database for everything: AtomCMS migrates its `website_*` tables into the
  Arcturus DB and ALTERs some emulator tables — order is guaranteed by the db
  healthcheck + init.
- Emulator config: generated once to `data/emulator/config.ini`, then yours to
  edit (restarts never overwrite; delete it to regenerate from `.env`). Do NOT
  add a `DB_HOSTNAME` env var to the emulator service — Arcturus 4.0.x then
  ignores config.ini entirely.
- RCON: `emulator:3001`, internal-only; the whitelist matches the CMS's static
  container IP `172.28.0.30` exactly (no CIDR — hence static IPs in compose).
- Websockets come from the NitroWebsockets plugin (4.0.x has none built in);
  its settings live in the `emulator_settings` DB rows seeded at init.
- CMS config is real container env in `docker-compose.yml` — change `.env` and
  `docker compose up -d` again; there is no `.env` file inside the container.
- Client configs (`/renderer-config.json`, `/ui-config.json`) are re-rendered
  from `.env`-derived URLs every nitro container start.

## Troubleshooting

- **cms build fails resolving GitHub repos** → tokenless builds clone the six
  AtomCMS VCS repos anonymously over https; if GitHub throttles those clones,
  set `GITHUB_TOKEN=<your token>` in `.env` and `docker compose build cms`
  (switches composer to the faster authenticated API path).
- **cms build fails on laravel/nova (Bitbucket)** → AtomCMS's committed
  `auth.json` credentials are the fragile link; check the AtomCMS repo/Discord.
- **db logs `pixelrp-init FATAL`** → a required SQL file is missing/misnamed;
  fix per artifacts/README.md, then `make reset` && `make up` (aborted first
  init leaves a partial datadir on purpose — nothing valuable is in it yet;
  the db healthcheck stays failing until you reset).
- **db unhealthy but its logs look clean** → a previous first-boot init failed
  or was interrupted and the container has since been recreated. The marker
  `data/db/.pixelrp-init-incomplete` holds the explanation (also shown in
  `docker inspect pixelrp-db-1` health logs). Remedy is the same: fix the
  cause, `make reset`, `make up`.
- **`02-…` SQL fails as already-applied** → your base dump is newer than 3.5.4;
  remove the redundant update file(s), `make reset`, `make up`.
- **Client stuck loading** → assets missing (`docker compose logs nitro`), or
  opened without an SSO ticket — enter through the CMS play button.
