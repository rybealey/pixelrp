# Phase 0 Docker Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Docker Compose project where `docker compose up` brings a full local Habbo retro stack online (MariaDB 11 + Arcturus Morningstar 4.0.x + AtomCMS + nitro-react) and all persistent data survives `docker compose down`/`up`; only `make reset` destroys data.

**Architecture:** Four services on a dedicated bridge network with static IPs (the emulator's RCON whitelist matches IPs exactly). Port-per-service on localhost, no front router; the `nitro` nginx doubles as the game-asset host. All state in bind mounts under `./data/`. User-supplied binaries/SQL live in `./artifacts/` and are never fabricated — every missing artifact fails loudly with the exact path and remedy.

**Tech Stack:** Docker Compose v2+, MariaDB 11, eclipse-temurin:21-jre, PHP 8.3 (apache) + Composer 2 + Node 22 (Vite 6), node:20 + Yarn 1 + nginx:alpine, GNU Make, bash.

**Spec:** `docs/superpowers/specs/2026-08-03-phase0-docker-infra-design.md` (read it first).

## Global Constraints

- **Local development only.** Every published port binds `127.0.0.1`. No SSL, no public exposure, no production hardening.
- **Persistence is the top requirement.** `docker compose down` must never lose data; only `make reset` (typed confirmation `yes-destroy-my-data`) wipes `./data`.
- **Never fabricate artifacts.** If a required file under `./artifacts/` is missing, stop with a message naming the exact missing path and where to get it. Test fixtures live only in the session scratchpad, never in `./artifacts/` or the repo.
- **Idempotent:** repeated `make up` must never corrupt anything. MariaDB's init dir only runs on an empty datadir; Laravel migrations are tracked; entrypoints re-render only what is safe to re-render.
- **No roleplay/combat systems.** Infrastructure only.
- **Git:** commit after each task; push to `origin main`. NEVER add Co-Authored-By or any AI-attribution trailer to commits (explicit user instruction).
- **Emulator env naming:** never set `DB_HOSTNAME` (or other bare `DB_*` names) in the emulator container's environment — Arcturus 4.0.x switches to env-only config and silently ignores `config.ini`. All emulator-bound variables use the `ARC_` prefix.
- **Prefer clarity over cleverness.** The user will read this setup often; comment the non-obvious (especially anything research-derived).

## Canonical contract (used by every task)

**Service names / static IPs** (network `pixelrp`, subnet `172.28.0.0/24`, all overridable in `.env`):

| Service | IP | Internal ports | Published (127.0.0.1) |
|---|---|---|---|
| `db` | 172.28.0.10 | 3306 | `${DB_HOST_PORT:-3310}` |
| `emulator` | 172.28.0.20 | 2096 ws, 3001 rcon, 3000 raw tcp | `${WS_PORT:-2096}` → 2096 only |
| `cms` | 172.28.0.30 | 80 | `${CMS_PORT:-8080}` |
| `nitro` | 172.28.0.40 | 80 | `${NITRO_PORT:-3000}` |

**Bind mounts:** `./data/db` → `db:/var/lib/mysql` · `./data/emulator` → `emulator:/app` · `./data/cms/storage` → `cms:/var/www/html/storage` · `./artifacts/sql` → `db:/artifacts/sql:ro` · `./artifacts/arcturus` → `emulator:/artifacts/arcturus:ro` · `./artifacts/nitro-assets` → `nitro:/usr/share/nginx/html/assets:ro`.

**Prescribed artifact names:** `artifacts/sql/01-base.sql`, `02-3_5_4-to-3_5_5.sql`, `03-3_5_5-to-4_0_0.sql` (optional `04-`…`09-` extras run in lexical order); exactly one `artifacts/arcturus/*.jar`; `artifacts/arcturus/plugins/NitroWebsockets-3.2.jar`.

**Root `.env` variables** (full list — `.env.example` in Task 1 is the single source of truth): `DB_ROOT_PASSWORD`, `DB_DATABASE=arcturus`, `DB_USERNAME=arcturus`, `DB_PASSWORD`, `DB_HOST_PORT=3310`, `CMS_PORT=8080`, `NITRO_PORT=3000`, `WS_PORT=2096`, `APP_NAME=PixelRP`, `APP_KEY`, `APP_DEBUG=true`, `GITHUB_TOKEN` (optional), `ARC_JAVA_OPTS=-Xmx1g`, `NITRO_REF=75ff874b73d5fc5672a38c536444efa0f0d27e8f`, `DOCKER_SUBNET=172.28.0.0/24`, `DB_IP=172.28.0.10`, `EMULATOR_IP=172.28.0.20`, `CMS_IP=172.28.0.30`, `NITRO_IP=172.28.0.40`.

**Research-verified facts you must not "correct":** Arcturus 4.0.x has NO built-in websockets (NitroWebsockets plugin required); RCON config lives in `config.ini`, websocket config lives in `emulator_settings` DB rows; `rcon.allowed` is an exact-string IP whitelist (semicolon-separated, no CIDR); AtomCMS uses the SAME database as the emulator and its migrations ALTER emulator tables; AtomCMS needs `ext-sockets`; both AtomCMS and nitro-react ship `yarn.lock` (no `package-lock.json`); nitro-react's two config JSONs are fetched at runtime from the web root.

---

### Task 1: Root scaffolding — `.env.example`, generator, Makefile, artifacts README

**Files:**
- Create: `.env.example`
- Create: `scripts/gen-env.sh` (executable)
- Create: `Makefile`
- Create: `artifacts/README.md`
- Create: `artifacts/arcturus/.gitkeep`, `artifacts/arcturus/plugins/.gitkeep`, `artifacts/sql/.gitkeep`, `artifacts/nitro-assets/.gitkeep`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: the canonical `.env` variable set (table above) consumed by every later task; Makefile targets `up down logs ps shell-db env fetch-ws-plugin reset`; the prescribed artifact filenames.

- [ ] **Step 1: Write `.env.example`**

```bash
# ─── PixelRP Phase 0 — local dev configuration ──────────────────────────────
# Copy via `make env` (fills every __GENERATE__ with a random value).
# This file is committed; the real .env is gitignored.

# ── Database (MariaDB 11) ──
DB_ROOT_PASSWORD=__GENERATE__
DB_DATABASE=arcturus
DB_USERNAME=arcturus
DB_PASSWORD=__GENERATE__
# Host port for debugging with a local client (127.0.0.1 only). 3310 avoids
# colliding with any MySQL already on 3306.
DB_HOST_PORT=3310

# ── Host ports (every port binds to 127.0.0.1 — local only) ──
CMS_PORT=8080
NITRO_PORT=3000
# Emulator websocket (NitroWebsockets plugin listens on 2096 in-container).
WS_PORT=2096

# ── CMS (AtomCMS / Laravel 11) ──
APP_NAME=PixelRP
# Laravel encryption key — must be "base64:..." format. `make env` generates it.
APP_KEY=__GENERATE_APP_KEY__
APP_DEBUG=true
# Optional: a GitHub token avoids composer hitting anonymous API rate limits
# while resolving AtomCMS's six VCS-repo dependencies during `docker compose build`.
GITHUB_TOKEN=

# ── Emulator (Arcturus Morningstar 4.0.x) ──
# JVM flags for the emulator process.
ARC_JAVA_OPTS=-Xmx1g

# ── Nitro client (billsonnn/nitro-react) ──
# Pinned commit for reproducible builds (main @ 2026-02-04; tags are years stale).
NITRO_REF=75ff874b73d5fc5672a38c536444efa0f0d27e8f

# ── Docker network ──
# Static IPs because Arcturus' rcon.allowed whitelist matches IP strings
# EXACTLY (no CIDR) — the emulator must know the CMS container's IP up front.
DOCKER_SUBNET=172.28.0.0/24
DB_IP=172.28.0.10
EMULATOR_IP=172.28.0.20
CMS_IP=172.28.0.30
NITRO_IP=172.28.0.40
```

- [ ] **Step 2: Write `scripts/gen-env.sh`**

```bash
#!/usr/bin/env bash
# Generates .env from .env.example, filling secrets. Never overwrites an
# existing .env (delete it yourself if you truly want fresh secrets — the DB
# keeps the old password in ./data/db, so regenerating breaks a live stack).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  echo ".env already exists — leaving it untouched."
  exit 0
fi

while IFS= read -r line; do
  case "$line" in
    APP_KEY=__GENERATE_APP_KEY__)
      printf 'APP_KEY=base64:%s\n' "$(openssl rand -base64 32)" ;;
    *=__GENERATE__)
      printf '%s=%s\n' "${line%%=*}" "$(openssl rand -hex 16)" ;;
    *)
      printf '%s\n' "$line" ;;
  esac
done < .env.example > .env

echo "Generated .env with fresh secrets."
```

- [ ] **Step 3: Write `Makefile`**

```make
SHELL := /bin/bash
COMPOSE := docker compose
-include .env
export

.PHONY: up down logs ps shell-db env fetch-ws-plugin reset

## Bring the whole stack up (builds images, clones AtomCMS source on first run).
up: .env cms/src
	@mkdir -p data/db data/emulator data/cms/storage
	$(COMPOSE) up -d --build
	@$(COMPOSE) ps

.env:
	@./scripts/gen-env.sh

## Generate .env from .env.example (no-op if it exists).
env: .env

cms/src:
	git clone https://github.com/atom-retros/atomcms.git cms/src

## Stop containers. NEVER touches ./data — safe to run any time.
down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=200

ps:
	$(COMPOSE) ps

## Root MariaDB shell into the game database.
shell-db:
	$(COMPOSE) exec db mariadb -uroot -p$(DB_ROOT_PASSWORD) $(DB_DATABASE)

## Download the NitroWebsockets plugin jar from the official Krews repo.
## Explicit on purpose: it's a compiled binary, so fetching is a knowing act.
## (Built against MS 3.x; the community runs it on 4.0.x — see artifacts/README.md.)
fetch-ws-plugin:
	@mkdir -p artifacts/arcturus/plugins
	curl -fL -o artifacts/arcturus/plugins/NitroWebsockets-3.2.jar \
	  https://git.krews.org/morningstar/nitrowebsockets-for-ms/-/raw/master/target/NitroWebsockets-3.2.jar
	@echo "Saved artifacts/arcturus/plugins/NitroWebsockets-3.2.jar"

## ─── DESTRUCTIVE ─── wipes every account, item, currency, room, upload, log.
reset:
	@echo "!!! DESTRUCTIVE RESET !!!"
	@echo "This will PERMANENTLY DELETE:"
	@echo "  - all pixelrp containers and the docker network"
	@echo "  - ./data/db          (every account, currency, item, room, progression)"
	@echo "  - ./data/emulator    (emulator config.ini and logs)"
	@echo "  - ./data/cms         (CMS storage: uploads, logs, seed marker)"
	@echo "Your ./artifacts files and .env are NOT touched."
	@read -p "Type 'yes-destroy-my-data' to proceed: " confirm && \
	  [ "$$confirm" = "yes-destroy-my-data" ] || { echo "Aborted — nothing deleted."; exit 1; }
	$(COMPOSE) down -v --remove-orphans
	rm -rf ./data
	@echo "Reset complete. Next 'make up' re-initializes the DB from ./artifacts/sql."
```

- [ ] **Step 4: Write `artifacts/README.md`**

```markdown
# artifacts/ — files YOU must supply

Nothing in this folder (except this README and `.gitkeep` markers) is committed
or invented by tooling. If a required file is missing, the stack stops with an
error naming it — it never substitutes anything.

## artifacts/arcturus/ — the emulator build

Place **exactly one** emulator jar here:

    artifacts/arcturus/Habbo-4.0.1-beta-jar-with-dependencies.jar   (name may vary)

Where to get it: Arcturus Morningstar 4.0.x has **no formal GitLab releases** —
jars are distributed as GitLab CI artifacts (2-week expiry) on
https://git.krews.org/morningstar/Arcturus-Community (branch `ms3-upgrade`) and
via the 4.0.x announcement threads (DevBest) / Krews Discord. Any 4.0.1+ build
for Java 21 works. If you drop more than one jar here the emulator refuses to
guess and asks you to keep one.

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
copied into the emulator's `plugins/` directory at start.

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

## artifacts/nitro-assets/ — game assets (served at http://localhost:3000/assets)

Drop your Nitro asset pack here (nitro-converter output, or a prebuilt default
asset pack). Expected layout — this folder IS the client's `asset.url` root:

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

The client preloads and REQUIRES: `bundled/generic/avatar_additions.nitro`,
`bundled/generic/group_badge.nitro`, `bundled/generic/floor_editor.nitro`,
`images/loading_icon.png`, `images/clear_icon.png`, `images/big_arrow.png`.

If your pack nests things differently (e.g. `swf/c_images`), either rearrange it
to match or adjust `NITRO_IMAGE_LIBRARY_URL` / `NITRO_HOF_FURNI_URL` overrides in
docker-compose.yml (see nitro service comments).

An empty folder does not block startup — the nitro container just logs a
warning and the client shows an eternal loading screen until assets exist.
```

- [ ] **Step 5: Create placeholder dirs and make the script executable**

Run: `mkdir -p artifacts/arcturus/plugins artifacts/sql artifacts/nitro-assets scripts && touch artifacts/arcturus/.gitkeep artifacts/arcturus/plugins/.gitkeep artifacts/sql/.gitkeep artifacts/nitro-assets/.gitkeep && chmod +x scripts/gen-env.sh`

- [ ] **Step 6: Verify the generator and Makefile**

Run: `make env && grep -c 'GENERATE' .env; grep '^APP_KEY=base64:' .env && grep -E '^DB_PASSWORD=[0-9a-f]{32}$' .env`
Expected: `0` occurrences of GENERATE left; APP_KEY line printed; DB_PASSWORD is 32 hex chars.
Run: `make env`
Expected: ".env already exists — leaving it untouched."
Run: `make reset` and type `no`
Expected: "Aborted — nothing deleted." and exit code 1 path taken (data untouched; `./data` may not exist yet — that's fine).

- [ ] **Step 7: Commit**

```bash
git add .gitignore .env.example scripts/gen-env.sh Makefile artifacts/README.md artifacts/arcturus/.gitkeep artifacts/arcturus/plugins/.gitkeep artifacts/sql/.gitkeep artifacts/nitro-assets/.gitkeep
git commit -m "Add scaffolding: env template, generator, Makefile, artifacts guide"
git push
```

---

### Task 2: Database service — my.cnf, ordered init script, compose base

**Files:**
- Create: `db/conf/my.cnf`
- Create: `db/init/01-arcturus.sh` (executable)
- Create: `docker-compose.yml` (network + `db` service; later tasks append services)

**Interfaces:**
- Consumes: `.env` variables `DB_*`, `DOCKER_SUBNET`, `DB_IP` (Task 1).
- Produces: a healthy `db` service other services reference by hostname `db`; the `pixelrp` network with static IPs; the emulator_settings websocket rows (`websockets.whitelist`, `ws.nitro.host`, `ws.nitro.port`, `ws.nitro.ip.header`).

- [ ] **Step 1: Write `db/conf/my.cnf`**

```ini
# PixelRP local-dev MariaDB tuning. Deliberately modest — this is a laptop, not prod.
[mysqld]
# Small pool: the whole Arcturus DB is tiny at Phase 0.
innodb_buffer_pool_size = 256M

# Server-side connection cap. The CLIENT pools must stay below this:
#   - Arcturus HikariCP: db.pool.maxsize in data/emulator/config.ini
#     (note: after boot Arcturus resizes the pool to runtime.threads*2 —
#     runtime.threads is an emulator_settings row, default 8 → 16 conns)
#   - AtomCMS: one connection per PHP worker (mpm_prefork default ≤ ~150,
#     but local traffic is single-digit)
max_connections = 100

# UTF8MB4 everywhere — Habbo content includes emoji.
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

[client]
default-character-set = utf8mb4
```

- [ ] **Step 2: Write `db/init/01-arcturus.sh`**

```bash
#!/bin/bash
# Arcturus database bootstrap. MariaDB's entrypoint runs this ONCE, only when
# ./data/db is empty (first boot). Repeated `docker compose up` never re-runs it
# — that is what makes restarts corruption-free.
set -euo pipefail

SQL_DIR=/artifacts/sql
REQUIRED=(01-base.sql 02-3_5_4-to-3_5_5.sql 03-3_5_5-to-4_0_0.sql)

missing=0
for f in "${REQUIRED[@]}"; do
  if [ ! -f "$SQL_DIR/$f" ]; then
    echo >&2 "pixelrp-init FATAL: required SQL artifact missing: ./artifacts/sql/$f"
    missing=1
  fi
done
if [ "$missing" -ne 0 ]; then
  echo >&2 "pixelrp-init: database NOT initialized. See artifacts/README.md for where"
  echo >&2 "pixelrp-init: to get each file. IMPORTANT: this aborted first boot leaves a"
  echo >&2 "pixelrp-init: partial datadir — run 'make reset' before trying 'make up' again."
  exit 1
fi

export MYSQL_PWD="$MARIADB_ROOT_PASSWORD"
apply() {
  echo "pixelrp-init: applying $(basename "$1")"
  mariadb -uroot "$MARIADB_DATABASE" < "$1"
}

for f in "${REQUIRED[@]}"; do
  apply "$SQL_DIR/$f"
done

# Optional extras for 4.0.2/4.0.3-beta jars (see artifacts/README.md).
for f in "$SQL_DIR"/0[4-9]-*.sql; do
  [ -e "$f" ] && apply "$f"
done

echo "pixelrp-init: seeding NitroWebsockets settings for local use"
# The plugin registers these rows itself on first boot; we pre-seed local-dev
# values (ON DUPLICATE keeps ours authoritative either way).
#   websockets.whitelist '*' — Origin whitelist; wildcard is fine LOCALLY ONLY.
#   RCON is NOT set here: Arcturus 4.0.x reads rcon.* from config.ini, not the DB.
mariadb -uroot "$MARIADB_DATABASE" <<'SQL'
INSERT INTO emulator_settings (`key`, `value`) VALUES
  ('websockets.whitelist', '*'),
  ('ws.nitro.host', '0.0.0.0'),
  ('ws.nitro.port', '2096'),
  ('ws.nitro.ip.header', '')
ON DUPLICATE KEY UPDATE `value` = VALUES(`value`);
SQL

echo "pixelrp-init: done — Arcturus schema ready"
```

- [ ] **Step 3: Write `docker-compose.yml`** (base — later tasks append their service blocks)

```yaml
# PixelRP Phase 0 — local dev stack. See README.md.
# Everything binds to 127.0.0.1; all state lives in ./data (see `make reset`).

services:
  db:
    image: mariadb:11
    restart: unless-stopped
    environment:
      MARIADB_ROOT_PASSWORD: ${DB_ROOT_PASSWORD:?run 'make env' first}
      MARIADB_DATABASE: ${DB_DATABASE:-arcturus}
      MARIADB_USER: ${DB_USERNAME:-arcturus}
      MARIADB_PASSWORD: ${DB_PASSWORD:?run 'make env' first}
    ports:
      - "127.0.0.1:${DB_HOST_PORT:-3310}:3306"
    volumes:
      # THE data that must survive everything short of `make reset`:
      - ./data/db:/var/lib/mysql
      - ./db/conf/my.cnf:/etc/mysql/conf.d/99-pixelrp.cnf:ro
      # Init dir runs ONLY when ./data/db is empty (first boot):
      - ./db/init:/docker-entrypoint-initdb.d:ro
      - ./artifacts/sql:/artifacts/sql:ro
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 5s
      timeout: 5s
      retries: 30
      # Generous: the first boot imports the full Arcturus schema.
      start_period: 300s
    networks:
      pixelrp:
        ipv4_address: ${DB_IP:-172.28.0.10}

networks:
  pixelrp:
    driver: bridge
    ipam:
      config:
        # Static IPs because Arcturus' rcon.allowed matches IPs EXACTLY (no CIDR).
        - subnet: ${DOCKER_SUBNET:-172.28.0.0/24}
```

- [ ] **Step 4: Make init script executable; validate compose interpolation**

Run: `chmod +x db/init/01-arcturus.sh && docker compose config --quiet && echo OK`
Expected: `OK` (no interpolation errors).

- [ ] **Step 5: Verify init mechanics with SCRATCHPAD fixtures (never in ./artifacts)**

Create in the scratchpad dir: `sql-fixtures/01-base.sql`:

```sql
-- TEST FIXTURE (not a real Arcturus dump) — proves ordering + override mechanics.
CREATE TABLE fixture_apply_log (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(64));
CREATE TABLE emulator_settings (`key` VARCHAR(100) PRIMARY KEY, `value` TEXT);
INSERT INTO fixture_apply_log (name) VALUES ('01-base');
```

`sql-fixtures/02-3_5_4-to-3_5_5.sql`: `INSERT INTO fixture_apply_log (name) VALUES ('02-mig');`
`sql-fixtures/03-3_5_5-to-4_0_0.sql`: `INSERT INTO fixture_apply_log (name) VALUES ('03-mig');`

And `fixture-override.yml` (scratchpad):

```yaml
services:
  db:
    volumes:
      - <SCRATCHPAD>/db-data:/var/lib/mysql
      - ./db/conf/my.cnf:/etc/mysql/conf.d/99-pixelrp.cnf:ro
      - ./db/init:/docker-entrypoint-initdb.d:ro
      - <SCRATCHPAD>/sql-fixtures:/artifacts/sql:ro
```

(`<SCRATCHPAD>` = absolute scratchpad path; the override replaces BOTH the datadir and the sql mount so real `./data` and `./artifacts` are untouched.)

- [ ] **Step 6: Fixture run — ordering, overrides, health**

Run: `docker compose -f docker-compose.yml -f <SCRATCHPAD>/fixture-override.yml up -d db` then wait for health, then
`docker compose exec db mariadb -uroot -p"$DB_ROOT_PASSWORD" arcturus -e "SELECT GROUP_CONCAT(name ORDER BY id) FROM fixture_apply_log; SELECT \`key\`,\`value\` FROM emulator_settings ORDER BY \`key\`;"`
Expected: `01-base,02-mig,03-mig` in exact order; four `ws`/`websockets` rows with `websockets.whitelist = *`.

- [ ] **Step 7: Fixture run — persistence proof**

Run: `docker compose exec db mariadb -uroot -p"$DB_ROOT_PASSWORD" arcturus -e "INSERT INTO fixture_apply_log (name) VALUES ('persist-proof');"` then `docker compose -f docker-compose.yml -f <SCRATCHPAD>/fixture-override.yml down` then `up -d db` again, wait healthy, and SELECT the log table.
Expected: `persist-proof` row still present; init did NOT re-run (no duplicate `01-base` row).

- [ ] **Step 8: Fixture run — missing-file abort is loud and names the file**

Run: `docker compose ... down`, `rm -rf <SCRATCHPAD>/db-data`, `mv <SCRATCHPAD>/sql-fixtures/02-3_5_4-to-3_5_5.sql <SCRATCHPAD>/02.hidden`, `up -d db`, then `docker compose logs db`.
Expected: log contains `pixelrp-init FATAL: required SQL artifact missing: ./artifacts/sql/02-3_5_4-to-3_5_5.sql` and the `make reset` warning; `.pixelrp-init-failed` marker exists in the datadir; healthcheck never reaches healthy.
(EXECUTION FINDING, fixed: MariaDB restarts an aborted-init datadir as a *healthy empty* database — the init script now drops `.pixelrp-init-failed` in the datadir via an EXIT trap on any failure, and the compose healthcheck requires the marker's absence, so dependents stay blocked until `make reset`.)

- [ ] **Step 9: Fixture cleanup**

Run: `docker compose -f docker-compose.yml -f <SCRATCHPAD>/fixture-override.yml down --remove-orphans && rm -rf <SCRATCHPAD>/db-data <SCRATCHPAD>/sql-fixtures <SCRATCHPAD>/fixture-override.yml <SCRATCHPAD>/02.hidden`
Expected: no pixelrp containers left (`docker compose ps` empty); real `./data` and `./artifacts` untouched.

- [ ] **Step 10: Commit**

```bash
git add db/ docker-compose.yml
git commit -m "Add MariaDB service: local tuning, ordered Arcturus init, ws settings seed"
git push
```

---

### Task 3: Emulator service — Dockerfile, entrypoint, compose wiring

**Files:**
- Create: `emulator/Dockerfile`
- Create: `emulator/entrypoint.sh` (executable)
- Modify: `docker-compose.yml` (append `emulator` service)

**Interfaces:**
- Consumes: `db` hostname + healthcheck (Task 2); `.env` `DB_DATABASE/DB_USERNAME/DB_PASSWORD/WS_PORT/CMS_IP/ARC_JAVA_OPTS`.
- Produces: websocket listener published at `ws://localhost:${WS_PORT}`; RCON at `emulator:3001` (internal) whitelisting the CMS static IP; persisted `./data/emulator/config.ini` the user may hand-edit.

- [ ] **Step 1: Write `emulator/Dockerfile`**

```dockerfile
# Arcturus Morningstar 4.0.x runtime. The jar is NOT baked in — it is a
# user-supplied artifact bind-mounted from ./artifacts/arcturus (see
# artifacts/README.md), so this image builds fine before artifacts exist and
# the entrypoint gives a precise error at runtime instead.
FROM eclipse-temurin:21-jre

COPY entrypoint.sh /usr/local/bin/pixelrp-emulator-entrypoint
RUN chmod +x /usr/local/bin/pixelrp-emulator-entrypoint

# /app is a bind mount of ./data/emulator — config.ini and logs persist there.
WORKDIR /app
ENTRYPOINT ["pixelrp-emulator-entrypoint"]
```

- [ ] **Step 2: Write `emulator/entrypoint.sh`**

```bash
#!/bin/bash
set -euo pipefail

ART=/artifacts/arcturus
cd /app
mkdir -p plugins logs

# ── 1. config.ini: generate ONCE, then it belongs to the user ──────────────
# NOTE: Arcturus 4.0.x switches to env-only config (ignoring this file) if a
# DB_HOSTNAME env var exists — which is why every variable below is ARC_-prefixed.
if [ ! -f config.ini ]; then
  echo "emulator: generating config.ini (first run — values from .env)"
  cat > config.ini <<EOF
## Generated by the pixelrp emulator entrypoint on first run — edit freely,
## restarts never overwrite it. Delete it and restart to regenerate from .env.
db.hostname=${ARC_DB_HOST}
db.port=3306
db.database=${ARC_DB_NAME}
db.username=${ARC_DB_USER}
db.password=${ARC_DB_PASS}
db.params=
## HikariCP client pool. Server cap: max_connections in db/conf/my.cnf.
## After boot Arcturus resizes the pool to runtime.threads*2 (emulator_settings
## row, base DB default 8) — so these mostly matter during startup.
db.pool.minsize=5
db.pool.maxsize=25
## Raw-TCP game server (Flash-era). Nitro uses the websocket plugin instead;
## the plugin re-binds this server's pipeline on ws.nitro.port (2096, in DB).
game.host=0.0.0.0
game.port=3000
## RCON — how the CMS talks to the emulator. rcon.allowed matches IP strings
## EXACTLY (no CIDR), hence the static CMS IP from docker-compose.yml.
rcon.host=0.0.0.0
rcon.port=3001
rcon.allowed=${ARC_RCON_ALLOWED}
## RSA handshake for Flash clients — off for Nitro-only setups.
enc.enabled=false
EOF
else
  echo "emulator: existing config.ini found — leaving it untouched"
fi

# ── 2. The emulator jar (user-supplied, exactly one) ───────────────────────
shopt -s nullglob
jars=("$ART"/*.jar)
shopt -u nullglob
if [ ${#jars[@]} -eq 0 ]; then
  echo >&2 "emulator FATAL: no emulator jar in ./artifacts/arcturus/"
  echo >&2 "emulator FATAL: expected e.g. Habbo-4.0.1-beta-jar-with-dependencies.jar"
  echo >&2 "emulator FATAL: see artifacts/README.md for where to get it."
  exit 1
elif [ ${#jars[@]} -gt 1 ]; then
  echo >&2 "emulator FATAL: multiple jars in ./artifacts/arcturus/ — keep exactly one:"
  printf >&2 '  %s\n' "${jars[@]}"
  exit 1
fi
JAR="${jars[0]}"

# ── 3. NitroWebsockets plugin (required — Nitro cannot connect without it) ─
shopt -s nullglob
pjars=("$ART"/plugins/*.jar)
shopt -u nullglob
if [ ${#pjars[@]} -eq 0 ]; then
  echo >&2 "emulator FATAL: no plugin jars in ./artifacts/arcturus/plugins/"
  echo >&2 "emulator FATAL: the NitroWebsockets jar is REQUIRED for the Nitro client."
  echo >&2 "emulator FATAL: fetch it with:  make fetch-ws-plugin"
  exit 1
fi
cp -f "${pjars[@]}" plugins/

# ── 4. Wait for MariaDB, then hand over to the emulator ────────────────────
echo "emulator: waiting for database at ${ARC_DB_HOST}:3306 ..."
until (echo > "/dev/tcp/${ARC_DB_HOST}/3306") 2>/dev/null; do sleep 2; done
echo "emulator: database reachable — starting $(basename "$JAR")"

# shellcheck disable=SC2086  # ARC_JAVA_OPTS is intentionally word-split
exec java ${ARC_JAVA_OPTS:--Xmx1g} -jar "$JAR"
```

- [ ] **Step 3: Append the `emulator` service to `docker-compose.yml`** (before `networks:`)

```yaml
  emulator:
    build: ./emulator
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      # ARC_ prefix on purpose — see the env-var trap note in emulator/entrypoint.sh.
      ARC_DB_HOST: db
      ARC_DB_NAME: ${DB_DATABASE:-arcturus}
      ARC_DB_USER: ${DB_USERNAME:-arcturus}
      ARC_DB_PASS: ${DB_PASSWORD:?run 'make env' first}
      # Exact-match RCON whitelist: the CMS container's static IP + loopback.
      ARC_RCON_ALLOWED: "${CMS_IP:-172.28.0.30};127.0.0.1"
      ARC_JAVA_OPTS: ${ARC_JAVA_OPTS:--Xmx1g}
    ports:
      # Nitro websocket only. RCON (3001) and raw TCP (3000) stay internal.
      - "127.0.0.1:${WS_PORT:-2096}:2096"
    volumes:
      - ./data/emulator:/app
      - ./artifacts/arcturus:/artifacts/arcturus:ro
    # Arcturus has an interactive console reader; give it a tty so it behaves.
    stdin_open: true
    tty: true
    networks:
      pixelrp:
        ipv4_address: ${EMULATOR_IP:-172.28.0.20}
```

- [ ] **Step 4: Build and validate**

Run: `docker compose build emulator && docker compose config --quiet && echo OK`
Expected: image builds; `OK`.

- [ ] **Step 5: Verify the missing-artifact error path AND config generation in one shot**

Run: `mkdir -p data/emulator && docker compose run --rm --no-deps emulator; echo "exit=$?"`
Expected: prints "generating config.ini (first run)", then the three `emulator FATAL: no emulator jar` lines naming `./artifacts/arcturus/` and artifacts/README.md, `exit=1`.
Run: `grep -E '^(db.hostname=db|rcon.allowed=172.28.0.30;127.0.0.1|game.host=0.0.0.0)$' data/emulator/config.ini | wc -l`
Expected: `3` (config was generated with real values; this file is the real persisted config and stays).
Run: `docker compose run --rm --no-deps emulator; echo "exit=$?"` again
Expected: "existing config.ini found — leaving it untouched" (idempotency), then the same jar FATAL, `exit=1`.

- [ ] **Step 6: Commit**

```bash
git add emulator/ docker-compose.yml
git commit -m "Add emulator service: config generation, artifact checks, ws plugin wiring"
git push
```

---

### Task 4: CMS service — AtomCMS build, entrypoint, compose wiring

**Files:**
- Create: `cms/Dockerfile`
- Create: `cms/.dockerignore`
- Create: `cms/apache-vhost.conf`
- Create: `cms/entrypoint.sh` (executable)
- Modify: `docker-compose.yml` (append `cms` service)

**Interfaces:**
- Consumes: `db` service (healthy) + the Arcturus schema (its migrations ALTER emulator tables); `emulator:3001` RCON; `.env` `APP_*`, `DB_*`, `CMS_PORT`, `NITRO_PORT`, `GITHUB_TOKEN`, `CMS_IP`; `cms/src` clone (Makefile, Task 1).
- Produces: CMS at `http://localhost:${CMS_PORT}` with registration; persisted `./data/cms/storage`.

- [ ] **Step 1: Write `cms/.dockerignore`**

```
src/.git
src/node_modules
src/vendor
```

- [ ] **Step 2: Write `cms/apache-vhost.conf`**

```apache
# Laravel: serve public/ only.
<VirtualHost *:80>
    DocumentRoot /var/www/html/public
    <Directory /var/www/html/public>
        AllowOverride All
        Require all granted
    </Directory>
    ErrorLog /dev/stderr
    CustomLog /dev/stdout combined
</VirtualHost>
```

- [ ] **Step 3: Write `cms/Dockerfile`**

```dockerfile
# AtomCMS (Laravel 11, PHP ^8.2). Source is cloned to ./cms/src on the HOST by
# `make up` so you can read and edit it; this build COPYs from there.

# ── Stage 1: front-end assets (Vite 6 needs Node 20+; repo ships yarn.lock) ──
FROM node:22-alpine AS assets
WORKDIR /build
COPY src/package.json src/yarn.lock ./
RUN yarn install --frozen-lockfile
COPY src/ ./
# The default theme build, same as AtomCMS's own CI.
RUN yarn build:atom
# Replicate `yarn link:atom` (theme images into public/) with a real copy —
# a symlink would dangle across COPY --from.
RUN if [ -d resources/themes/atom/images ]; then \
      rm -rf public/images && cp -r resources/themes/atom/images public/images; \
    fi

# ── Stage 2: PHP runtime ──
FROM php:8.3-apache
# Extensions AtomCMS needs beyond the image defaults (research-verified):
#   sockets  — the AtomCMS RCON package (ext-sockets in composer.json)
#   pdo_mysql, gd — documented requirements; zip — composer dist installs;
#   opcache — cheap speedup. curl/fileinfo/mbstring/openssl ship enabled already.
RUN apt-get update && apt-get install -y --no-install-recommends \
      git unzip libpng-dev libjpeg62-turbo-dev libwebp-dev libfreetype6-dev libzip-dev \
    && docker-php-ext-configure gd --with-jpeg --with-freetype --with-webp \
    && docker-php-ext-install -j"$(nproc)" gd pdo_mysql sockets zip opcache \
    && a2enmod rewrite \
    && rm -rf /var/lib/apt/lists/*

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer
COPY apache-vhost.conf /etc/apache2/sites-available/000-default.conf

WORKDIR /var/www/html
# Full source incl. the repo's committed auth.json (Bitbucket credentials for
# the laravel/nova housekeeping package — the most fragile dependency; see README).
COPY src/ ./

# Optional GitHub token: AtomCMS declares six first-party packages as VCS repos;
# anonymous GitHub API rate limits can fail the resolve step without one.
ARG GITHUB_TOKEN=""
RUN if [ -n "$GITHUB_TOKEN" ]; then composer config -g github-oauth.github.com "$GITHUB_TOKEN"; fi \
    && composer install --no-dev --prefer-dist --no-interaction --no-progress --no-scripts \
    && composer clear-cache

# Built front-end (includes public/build and theme images) over the source copy.
COPY --from=assets /build/public ./public

COPY entrypoint.sh /usr/local/bin/pixelrp-cms-entrypoint
RUN chmod +x /usr/local/bin/pixelrp-cms-entrypoint

ENTRYPOINT ["pixelrp-cms-entrypoint"]
CMD ["apache2-foreground"]
```

- [ ] **Step 4: Write `cms/entrypoint.sh`**

```bash
#!/bin/bash
set -euo pipefail
cd /var/www/html

# ── storage/ is a bind mount (./data/cms/storage) that starts EMPTY — rebuild
# the skeleton Laravel expects, then hand it to www-data.
mkdir -p storage/app/public \
         storage/framework/cache/data storage/framework/sessions storage/framework/views \
         storage/logs bootstrap/cache
chown -R www-data:www-data storage bootstrap/cache
chmod -R 775 storage bootstrap/cache

echo "cms: waiting for database at ${DB_HOST:-db}:${DB_PORT:-3306} ..."
until (echo > "/dev/tcp/${DB_HOST:-db}/${DB_PORT:-3306}") 2>/dev/null; do sleep 2; done

# Build was done with --no-scripts; discover packages now that we have real env.
php artisan package:discover --ansi

# Idempotent: Laravel tracks applied migrations. These ALTER emulator tables,
# so the Arcturus schema must exist (guaranteed by db's init + healthcheck).
if ! php artisan migrate --force; then
  echo >&2 "cms FATAL: migrations failed. Most likely the Arcturus schema is missing"
  echo >&2 "cms FATAL: (did db init abort? check: docker compose logs db) — see artifacts/README.md."
  exit 1
fi

# Seed exactly once; marker lives in persisted storage.
if [ ! -f storage/.pixelrp-seeded ]; then
  php artisan db:seed --force
  touch storage/.pixelrp-seeded
fi

# public/ is image-local (not persisted) — re-link uploads every start.
[ -L public/storage ] || php artisan storage:link

exec "$@"
```

- [ ] **Step 5: Append the `cms` service to `docker-compose.yml`** (before `networks:`)

```yaml
  cms:
    build:
      context: ./cms
      args:
        GITHUB_TOKEN: ${GITHUB_TOKEN:-}
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      # Laravel reads real env vars (they override any .env file) — this block
      # IS the CMS configuration; edit the root .env, not files in the container.
      APP_NAME: ${APP_NAME:-PixelRP}
      APP_ENV: local
      APP_KEY: ${APP_KEY:?run 'make env' first}
      APP_DEBUG: ${APP_DEBUG:-true}
      APP_TIMEZONE: UTC
      APP_URL: "http://localhost:${CMS_PORT:-8080}"
      LOG_CHANNEL: stack
      LOG_LEVEL: debug
      DB_CONNECTION: mariadb
      DB_HOST: db
      DB_PORT: 3306
      DB_DATABASE: ${DB_DATABASE:-arcturus}
      DB_USERNAME: ${DB_USERNAME:-arcturus}
      DB_PASSWORD: ${DB_PASSWORD:?run 'make env' first}
      SESSION_DRIVER: database
      CACHE_STORE: file
      QUEUE_CONNECTION: sync
      MAIL_MAILER: log
      FILESYSTEM_DISK: public
      # RCON — the emulator whitelists this container's static IP (CMS_IP).
      RCON_HOST: emulator
      RCON_PORT: 3001
      MIN_STAFF_RANK: 4
      # Links the CMS renders for the game client + assets:
      NITRO_CLIENT_URL: "http://localhost:${NITRO_PORT:-3000}"
      NITRO_STATIC_URL: "http://localhost:${NITRO_PORT:-3000}/assets"
      # Local dev: external integrations off.
      TURNSTILE_ENABLED: "false"
      IP_API_ENABLED: "false"
      FINDRETROS_ENABLED: "false"
    ports:
      - "127.0.0.1:${CMS_PORT:-8080}:80"
    volumes:
      - ./data/cms/storage:/var/www/html/storage
    networks:
      pixelrp:
        ipv4_address: ${CMS_IP:-172.28.0.30}
```

- [ ] **Step 6: Clone source and build** (network-heavy; the Nova/auth.json resolve is the known fragile point)

Run: `make cms/src && docker compose build cms`
Expected: clone succeeds; build completes. If composer fails on GitHub rate limits: set `GITHUB_TOKEN` in `.env` and rebuild. If it fails fetching `laravel/nova` from Bitbucket: the committed `auth.json` credentials broke — STOP and surface to the user (do not fake a workaround).

- [ ] **Step 7: Verify extensions, artisan, vite output, and web pipeline (no DB yet)**

(These checks override the entrypoint — the real entrypoint waits for the db, which is intentionally not running here.)
Run: `docker compose run --rm --no-deps --entrypoint php cms -m | grep -E '^(sockets|pdo_mysql|gd|zip)$' | wc -l`
Expected: `4`.
Run: `docker compose run --rm --no-deps --entrypoint ls cms public/build`
Expected: a Vite `manifest.json` (in `.vite/` or root) + hashed assets — non-empty.
Run: `docker compose run --rm --no-deps --entrypoint bash cms -c 'ls -d resources/themes/atom >/dev/null && echo theme-ok; php artisan --version'`
Expected: `theme-ok` and a `Laravel Framework 11.x` version line.
Note: full entrypoint (migrate) intentionally NOT tested here — it requires the real Arcturus schema (user artifact). Its failure path prints the `cms FATAL` migration message and exits 1, which the integration dry-run in Task 6 demonstrates.

- [ ] **Step 8: Commit**

```bash
git add cms/Dockerfile cms/.dockerignore cms/apache-vhost.conf cms/entrypoint.sh docker-compose.yml
git commit -m "Add CMS service: AtomCMS multi-stage build, env-driven config, idempotent boot"
git push
```

---

### Task 5: Nitro client service — pinned build, nginx, runtime config render

**Files:**
- Create: `nitro/Dockerfile`
- Create: `nitro/default.conf` (nginx)
- Create: `nitro/render-config.sh` (executable; runs via nginx's `/docker-entrypoint.d/`)
- Modify: `docker-compose.yml` (append `nitro` service)

**Interfaces:**
- Consumes: `.env` `NITRO_REF`, `NITRO_PORT`, `WS_PORT`, `CMS_PORT`; game assets bind mount.
- Produces: client at `http://localhost:${NITRO_PORT}` with `/renderer-config.json` + `/ui-config.json` rendered at container start; assets at `/assets`.

- [ ] **Step 1: Write `nitro/Dockerfile`**

```dockerfile
# nitro-react, built from source at a pinned commit (see NITRO_REF in .env).

# ── Stage 1: build (README: Node >= 18; yarn.lock is Yarn Classic v1) ──
FROM node:20-alpine AS build
RUN apk add --no-cache git
ARG NITRO_REF=75ff874b73d5fc5672a38c536444efa0f0d27e8f
RUN git clone https://github.com/billsonnn/nitro-react.git /src \
    && cd /src && git checkout "$NITRO_REF"
WORKDIR /src
RUN yarn install --frozen-lockfile
# Headroom for vite in memory-capped Docker builds (a cap, not a reservation —
# harmless if unnecessary; community reports occasional OOMs without it).
ENV NODE_OPTIONS=--max-old-space-size=4096
# Plain `yarn build`, NOT build:prod — build:prod merely prepends a
# network-dependent (and upstream-deprecated) browserslist DB update.
RUN yarn build

# ── Stage 2: serve ──
FROM nginx:alpine
# jq powers the runtime config render (render-config.sh).
RUN apk add --no-cache jq
COPY --from=build /src/dist /usr/share/nginx/html
# Keep the pinned ref's config examples as render bases: render-config.sh
# rewrites ONLY our keys into them at container start, so upstream config
# evolution never requires re-vendoring a 31 KB JSON here.
RUN mv /usr/share/nginx/html/renderer-config.json.example /usr/share/nginx/html/renderer-config.base.json \
    && mv /usr/share/nginx/html/ui-config.json.example /usr/share/nginx/html/ui-config.base.json
COPY default.conf /etc/nginx/conf.d/default.conf
# nginx's stock entrypoint runs every /docker-entrypoint.d/*.sh before nginx.
COPY render-config.sh /docker-entrypoint.d/90-pixelrp-render-config.sh
RUN chmod +x /docker-entrypoint.d/90-pixelrp-render-config.sh
```

- [ ] **Step 2: Write `nitro/render-config.sh`**

```sh
#!/bin/sh
# Renders the two runtime configs the built client fetches from the web root.
# jq (not envsubst) on purpose: nitro configs use their own ${key} interpolation
# (e.g. "${gamedata.url}/FurnitureData.json") which envsubst could mangle;
# jq rewrites exactly the keys we own and nothing else.
set -eu

HTML=/usr/share/nginx/html
: "${NITRO_WS_URL:?NITRO_WS_URL must be set (docker-compose.yml)}"
: "${NITRO_ASSET_URL:?NITRO_ASSET_URL must be set (docker-compose.yml)}"
: "${NITRO_CMS_URL:?NITRO_CMS_URL must be set (docker-compose.yml)}"
# SWF-era image trees — override only if your asset pack nests them elsewhere.
IMAGE_LIBRARY_URL="${NITRO_IMAGE_LIBRARY_URL:-$NITRO_ASSET_URL/c_images/}"
HOF_FURNI_URL="${NITRO_HOF_FURNI_URL:-$NITRO_ASSET_URL/dcr/hof_furni}"

jq --arg ws "$NITRO_WS_URL" \
   --arg asset "$NITRO_ASSET_URL" \
   --arg imglib "$IMAGE_LIBRARY_URL" \
   --arg hof "$HOF_FURNI_URL" \
   '."socket.url" = $ws
    | ."asset.url" = $asset
    | ."image.library.url" = $imglib
    | ."hof.furni.url" = $hof' \
   "$HTML/renderer-config.base.json" > "$HTML/renderer-config.json"

jq --arg cms "$NITRO_CMS_URL" \
   '."url.prefix" = $cms' \
   "$HTML/ui-config.base.json" > "$HTML/ui-config.json"

echo "pixelrp-nitro: rendered renderer-config.json (socket.url=$NITRO_WS_URL, asset.url=$NITRO_ASSET_URL)"

# Assets are a user artifact — warn (don't block) when absent.
if [ -z "$(find "$HTML/assets" -mindepth 1 -maxdepth 1 2>/dev/null | head -1)" ]; then
  echo "pixelrp-nitro WARNING: ./artifacts/nitro-assets is empty — the client will" >&2
  echo "pixelrp-nitro WARNING: load forever without game assets. See artifacts/README.md." >&2
fi
```

- [ ] **Step 3: Write `nitro/default.conf`**

```nginx
# Nitro client + game asset host (same origin → no CORS needed).
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    gzip on;
    gzip_types application/json application/javascript text/css image/svg+xml;

    # Runtime-rendered configs must never be cached stale.
    location = /renderer-config.json { add_header Cache-Control "no-store"; }
    location = /ui-config.json      { add_header Cache-Control "no-store"; }

    # ./artifacts/nitro-assets is bind-mounted at html/assets (read-only).
    location /assets/ { }

    # SPA fallback.
    location / { try_files $uri $uri/ /index.html; }
}
```

- [ ] **Step 4: Append the `nitro` service to `docker-compose.yml`** (before `networks:`)

```yaml
  nitro:
    build:
      context: ./nitro
      args:
        NITRO_REF: ${NITRO_REF:-75ff874b73d5fc5672a38c536444efa0f0d27e8f}
    restart: unless-stopped
    environment:
      # Browser-facing URLs (the client runs on the HOST, so localhost + host ports).
      NITRO_WS_URL: "ws://localhost:${WS_PORT:-2096}"
      NITRO_ASSET_URL: "http://localhost:${NITRO_PORT:-3000}/assets"
      NITRO_CMS_URL: "http://localhost:${CMS_PORT:-8080}"
      # Optional overrides if your asset pack layout differs (artifacts/README.md):
      # NITRO_IMAGE_LIBRARY_URL: "http://localhost:3000/assets/swf/c_images/"
      # NITRO_HOF_FURNI_URL: "http://localhost:3000/assets/swf/dcr/hof_furni"
    ports:
      - "127.0.0.1:${NITRO_PORT:-3000}:80"
    volumes:
      - ./artifacts/nitro-assets:/usr/share/nginx/html/assets:ro
    networks:
      pixelrp:
        ipv4_address: ${NITRO_IP:-172.28.0.40}
```

- [ ] **Step 5: Build** (slow: clones + yarn install + vite build, ~5–10 min first time)

Run: `docker compose build nitro`
Expected: completes. If `yarn build` OOMs, raise Docker Desktop memory; the NODE_OPTIONS headroom is already set.

- [ ] **Step 6: Verify serving + rendered configs + empty-assets warning**

Run: `docker compose up -d nitro && sleep 2 && curl -fsS http://localhost:3000/ | grep -ci nitro`
Expected: ≥1 (index.html serves).
Run: `curl -fsS http://localhost:3000/renderer-config.json | jq -r '."socket.url", ."asset.url", ."image.library.url"'`
Expected: `ws://localhost:2096`, `http://localhost:3000/assets`, `http://localhost:3000/assets/c_images/`.
Run: `curl -fsS http://localhost:3000/ui-config.json | jq -r '."url.prefix"'`
Expected: `http://localhost:8080`.
Run: `docker compose logs nitro | grep -c 'pixelrp-nitro WARNING'`
Expected: ≥1 (assets folder is empty → warning fired).
Run: `docker compose stop nitro`

- [ ] **Step 7: Commit**

```bash
git add nitro/ docker-compose.yml
git commit -m "Add nitro service: pinned source build, runtime config render, asset host"
git push
```

---

### Task 6: README, integration dry-run, artifact flag report

**Files:**
- Create: `README.md`
- Modify: (none expected — fix anything the dry-run exposes)

**Interfaces:**
- Consumes: everything above.
- Produces: the documented first-run + persistence-proof procedure; a verified `docker compose config`; an explicit list of missing artifacts for the user.

- [ ] **Step 1: Write `README.md`**

```markdown
# PixelRP — Phase 0 local dev stack

Local-only Docker environment for a Habbo retro roleplay server. **Not
production**: every port binds 127.0.0.1, no SSL, no hardening.

| Piece | What | Where |
|---|---|---|
| Emulator | Arcturus Morningstar 4.0.x (Java 21) | `ws://localhost:2096` (websocket) |
| Database | MariaDB 11 — ALL persistent state | `127.0.0.1:3310` (debug access) |
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

- **cms build fails resolving GitHub repos** → set `GITHUB_TOKEN=` in `.env`,
  `docker compose build cms`.
- **cms build fails on laravel/nova (Bitbucket)** → AtomCMS's committed
  `auth.json` credentials are the fragile link; check the AtomCMS repo/Discord.
- **db logs `pixelrp-init FATAL`** → a required SQL file is missing/misnamed;
  fix per artifacts/README.md, then `make reset` && `make up` (aborted first
  init leaves a partial datadir on purpose — nothing valuable is in it yet).
- **`02-…` SQL fails as already-applied** → your base dump is newer than 3.5.4;
  remove the redundant update file(s), `make reset`, `make up`.
- **Client stuck loading** → assets missing (`docker compose logs nitro`), or
  opened without an SSO ticket — enter through the CMS play button.
```

- [ ] **Step 2: Full-stack validation with whatever exists**

Run: `docker compose config --quiet && echo OK && make up || true; sleep 5; docker compose ps`
Expected without user artifacts: `db` restarting/exited with the `pixelrp-init FATAL` log naming `01-base.sql` (if `artifacts/sql` empty); `emulator`+`cms` created but never started (dependency on healthy db); `nitro` Up. Each failure is the loud, named kind. Then `make reset` (typed) to clear the aborted datadir, leaving the tree clean for the user's real artifact drop.
With artifacts present: all four Up; emulator log shows DB connect + load complete.

- [ ] **Step 3: Report artifact status to the user**

List exactly which of the required artifacts are present/missing at this moment (`artifacts/arcturus/*.jar`, `plugins/NitroWebsockets-3.2.jar`, the three SQL files, nitro-assets contents) and what each missing one blocks. Do not proceed past this without surfacing the list.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "Add README: first run, persistence proof, reset policy, troubleshooting"
git push
```

---

### Task 7: Adversarial review and fixes

**Files:**
- Modify: whatever the review finds (each fix committed separately with a descriptive message).

**Interfaces:**
- Consumes: the complete tree + spec + this plan.
- Produces: verified-or-fixed final state.

- [ ] **Step 1: Run a multi-lens review** (Workflow tool; ultracode session): four parallel finder agents over the repo — (a) compose/mounts/healthcheck vs spec §Persistence and §Services, (b) shell scripts: quoting, `set -e` pitfalls, glob edge cases, first-run vs restart paths, (c) data-safety: any path besides `make reset` that could destroy or orphan `./data`, plus idempotency of every entrypoint, (d) docs accuracy: does every README/`artifacts/README.md` claim match the implementation exactly (ports, filenames, commands)? Each finding then goes to 2 adversarial verifiers prompted to REFUTE it; only confirmed findings survive.

- [ ] **Step 2: Fix confirmed findings** (touch only what the finding requires), re-run the relevant Task verification steps for anything changed.

- [ ] **Step 3: Final commit + push**

```bash
git add -A && git commit -m "Apply review fixes" && git push
```

---

## Execution notes

- Tasks 3/4/5 are independent of each other (all depend on Tasks 1–2). If executing with subagents, they can run in parallel — but their `docker-compose.yml` edits touch the same file: append service blocks in fixed order (emulator, cms, nitro) or merge carefully.
- Docker builds for cms/nitro are network-heavy and slow (5–10 min each first time); run them concurrently where possible.
- The full acceptance criteria (register → down → up → account persists; client connects) can only be exercised once the user drops the artifacts. Everything else above verifies mechanically without them.
```
