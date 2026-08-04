# Deploy Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A push to `main` updates the pixelrp stack on a Vultr VPS with no manual step, taking a database backup first, and can never destroy persistent data.

**Architecture:** GitHub Actions checks out the repo, rsyncs only tracked files to `/opt/pixelrp` (excluding all state), then runs `scripts/deploy.sh` on the box over SSH. That script backs up the database, rebuilds, and health-gates. Client-facing URLs become `PUBLIC_*`-derived so the deployed hotel points browsers at the real domain instead of `localhost`.

**Tech Stack:** GitHub Actions, OpenSSH, rsync, bash, Docker Compose, mysqldump (via the `db` container).

**Spec:** `docs/superpowers/specs/2026-08-04-deploy-pipeline-design.md` (read it first).

## Global Constraints

- **A deploy is code-only.** `data/`, `.env`, `artifacts/`, `cms/src` are never written, deleted, or overwritten by any deploy step. `--delete` must never be able to reach them.
- **Never run `docker compose down -v`** anywhere in deploy tooling. `make reset` remains the only data-destroying path in this repo.
- **Local behaviour must not change.** With `PUBLIC_*` unset, every generated URL must be byte-identical to today's (`http://localhost:8080`, `ws://localhost:2096`, `http://localhost:3000/game-assets`).
- **No secrets in the repo.** The SSH private key lives only in GitHub secrets; the server `.env` is authored on the server. Never commit, echo, or log either.
- **Fail loudly, never half-deploy.** Every precondition failure aborts before containers are touched, naming the exact fix.
- **A failed backup aborts the deploy.** No dump, no migration.
- Deploy scripts are bash with `set -euo pipefail`, and must be runnable by hand on the server, not only from CI.
- **Git:** commit per task; push to `origin main`. NEVER add Co-Authored-By or any AI-attribution trailer (explicit user instruction).

## File structure

| File | Responsibility |
|---|---|
| `docker-compose.yml` (modify) | derive client-facing URLs from `PUBLIC_*` |
| `.env.example` (modify) | document `PUBLIC_*`, `DEPLOY_*`, `BACKUP_KEEP` |
| `scripts/deploy.sh` (create) | server-side: preflight → backup → build → health gate |
| `scripts/sync-assets.sh` (create) | operator-initiated rsync of `artifacts/` |
| `Makefile` (modify) | `sync-assets` target |
| `.github/workflows/deploy.yml` (create) | push-to-main trigger, rsync, invoke deploy |
| `docs/DEPLOYMENT.md` (create) | one-time setup, secrets, restore, hardening checklist |

---

### Task 1: Parameterize client-facing URLs

Without this the pipeline can deploy successfully to a hotel that is broken for every visitor, because their browsers are told to connect to `localhost`.

**Files:**
- Modify: `docker-compose.yml:83`, `:102-103`, `:124`, `:128-129`
- Modify: `.env.example`

**Interfaces:**
- Produces: `PUBLIC_SCHEME` (default `http`), `PUBLIC_HOST` (default `localhost`), `PUBLIC_WS_SCHEME` (default `ws`), and the optional full overrides `PUBLIC_CMS_URL`, `PUBLIC_NITRO_URL`, `PUBLIC_WS_URL`. Consumed by Task 4's docs and by the server `.env`.

- [ ] **Step 1: Capture today's rendered URLs as the regression baseline**

Run:
```bash
docker compose config | grep -E 'APP_URL|NITRO_CLIENT_URL|NITRO_STATIC_URL|NITRO_WS_URL|NITRO_ASSET_URL|NITRO_CMS_URL' | sort > /tmp/urls-before.txt
cat /tmp/urls-before.txt
```
Expected: six lines, all containing `localhost`. Keep this file — Step 4 diffs against it.

- [ ] **Step 2: Add the `PUBLIC_*` block to `.env.example`**

Insert after the `NITRO_SHOW_PROMO_ARTICLES` line:

```bash
# ── Public identity (deployment) ──
# What the VISITOR'S BROWSER should connect to. Defaults reproduce the local
# setup exactly; a deployed hotel MUST set PUBLIC_HOST to its real domain or
# every visitor's browser tries to reach their own machine.
PUBLIC_SCHEME=http
PUBLIC_HOST=localhost
# Websocket scheme: ws for plain http, wss when TLS terminates at your proxy.
PUBLIC_WS_SCHEME=ws
# Full-URL overrides for when a reverse proxy serves things on standard ports
# (e.g. https://pixelrp.example with no :3000). Leave blank to build the URL
# from the parts above plus the published port.
PUBLIC_CMS_URL=
PUBLIC_NITRO_URL=
PUBLIC_WS_URL=

# ── Deployment ──
# How many pre-deploy database dumps to keep in data/backups/.
BACKUP_KEEP=10
```

- [ ] **Step 3: Rewrite the six URL lines in `docker-compose.yml`**

`cms` service — replace line 83:
```yaml
      APP_URL: "${PUBLIC_CMS_URL:-${PUBLIC_SCHEME:-http}://${PUBLIC_HOST:-localhost}:${CMS_PORT:-8080}}"
```

`cms` service — replace lines 102-103:
```yaml
      NITRO_CLIENT_URL: "${PUBLIC_NITRO_URL:-${PUBLIC_SCHEME:-http}://${PUBLIC_HOST:-localhost}:${NITRO_PORT:-3000}}"
      NITRO_STATIC_URL: "${PUBLIC_NITRO_URL:-${PUBLIC_SCHEME:-http}://${PUBLIC_HOST:-localhost}:${NITRO_PORT:-3000}}/game-assets"
```

`nitro` service — replace the comment on line 123 and line 124:
```yaml
      # Browser-facing URLs. PUBLIC_HOST defaults to localhost for local dev;
      # a deployed hotel sets it to the real domain (see docs/DEPLOYMENT.md).
      NITRO_WS_URL: "${PUBLIC_WS_URL:-${PUBLIC_WS_SCHEME:-ws}://${PUBLIC_HOST:-localhost}:${WS_PORT:-2096}}"
```

`nitro` service — replace lines 128-129:
```yaml
      NITRO_ASSET_URL: "${PUBLIC_NITRO_URL:-${PUBLIC_SCHEME:-http}://${PUBLIC_HOST:-localhost}:${NITRO_PORT:-3000}}/game-assets"
      NITRO_CMS_URL: "${PUBLIC_CMS_URL:-${PUBLIC_SCHEME:-http}://${PUBLIC_HOST:-localhost}:${CMS_PORT:-8080}}"
```

- [ ] **Step 4: Verify local output is byte-identical**

Run:
```bash
docker compose config | grep -E 'APP_URL|NITRO_CLIENT_URL|NITRO_STATIC_URL|NITRO_WS_URL|NITRO_ASSET_URL|NITRO_CMS_URL' | sort > /tmp/urls-after.txt
diff /tmp/urls-before.txt /tmp/urls-after.txt && echo "IDENTICAL — local behaviour preserved"
```
Expected: `IDENTICAL — local behaviour preserved`. Any diff means a default is wrong; fix before continuing.

- [ ] **Step 5: Verify a public host renders correctly**

Run:
```bash
PUBLIC_SCHEME=https PUBLIC_HOST=pixelrp.example PUBLIC_WS_SCHEME=wss \
  docker compose config | grep -E 'NITRO_WS_URL|NITRO_CMS_URL|APP_URL'
```
Expected: `wss://pixelrp.example:2096`, and CMS/APP URLs on `https://pixelrp.example:8080`.

Run:
```bash
PUBLIC_CMS_URL=https://pixelrp.example PUBLIC_WS_URL=wss://ws.pixelrp.example \
  docker compose config | grep -E 'NITRO_WS_URL|NITRO_CMS_URL'
```
Expected: exactly those overrides, with no port suffix — proving the proxy case works.

- [ ] **Step 6: Confirm the running stack still works**

Run: `docker compose up -d nitro && sleep 4 && curl -s http://localhost:3000/renderer-config.json | jq -r '."socket.url", ."asset.url"'`
Expected: `ws://localhost:2096` and `http://localhost:3000/game-assets` — unchanged.

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "Derive client-facing URLs from PUBLIC_* so remote deploys work"
git push
```

---

### Task 2: Server-side deploy script

**Files:**
- Create: `scripts/deploy.sh` (executable)

**Interfaces:**
- Consumes: `PUBLIC_*`/`BACKUP_KEEP` from Task 1's `.env`; the repo checked out at `/opt/pixelrp` on the server.
- Produces: `scripts/deploy.sh`, invoked by Task 3's workflow as `bash scripts/deploy.sh` from the deploy directory. Exit 0 = healthy stack; non-zero = deploy failed.

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# Server-side deploy. Runs on the VPS from the deploy directory; also safe to
# run by hand when debugging (it is the same path CI takes).
#
# A deploy is CODE-ONLY. This script must never write to data/, .env or
# artifacts/, and must never run `docker compose down -v` — `make reset` stays
# the single data-destroying path in this repo.
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose"
say() { printf 'deploy: %s\n' "$*"; }
die() { printf >&2 'deploy FATAL: %s\n' "$*"; exit 1; }

# ── 1. Preflight — abort before touching containers ────────────────────────
[ -f .env ] || die $'no .env on this server.\n  The server keeps its own secrets; it is never deployed.\n  Create it once:  cp .env.example .env  then edit PUBLIC_HOST, passwords, APP_KEY.'

set -a; . ./.env; set +a

[ -n "$(find artifacts/sql -name '*.sql' 2>/dev/null | head -1)" ] \
  || die $'artifacts/sql is empty — the database schema is missing.\n  Sync assets from your workstation:  make sync-assets'
[ -n "$(find artifacts/arcturus -maxdepth 1 -name '*.jar' 2>/dev/null | head -1)" ] \
  || die $'artifacts/arcturus has no emulator jar.\n  Sync assets from your workstation:  make sync-assets'

# ── 2. Pre-deploy database backup ──────────────────────────────────────────
# The CMS entrypoint runs `artisan migrate --force` on every boot. Those
# migrations are upstream AtomCMS code: normally additive, but a future one
# could alter or drop a column. Never migrate without a dump.
if [ -n "$($COMPOSE ps -q db 2>/dev/null)" ]; then
  mkdir -p data/backups
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  dest="data/backups/pixelrp-${stamp}.sql.gz"
  say "backing up the database to ${dest}"
  if ! $COMPOSE exec -T db mariadb-dump -uroot -p"$DB_ROOT_PASSWORD" \
        --single-transaction --routines --events "${DB_DATABASE:-arcturus}" \
        2>/dev/null | gzip > "$dest.part"; then
    rm -f "$dest.part"
    die "database backup FAILED — deploy aborted before any migration ran."
  fi
  # A dump that produced nothing is a failed dump, whatever the exit code said.
  [ -s "$dest.part" ] || { rm -f "$dest.part"; die "database backup was empty — deploy aborted."; }
  mv "$dest.part" "$dest"
  say "backup complete ($(du -h "$dest" | cut -f1))"

  keep="${BACKUP_KEEP:-10}"
  # shellcheck disable=SC2012  # filenames are timestamped and shell-safe
  ls -1t data/backups/pixelrp-*.sql.gz 2>/dev/null | tail -n +$((keep + 1)) | while read -r old; do
    say "pruning old backup $(basename "$old")"
    rm -f "$old"
  done
else
  say "db container not running (first deploy?) — nothing to back up"
fi

# ── 3. Build and start ─────────────────────────────────────────────────────
say "building and starting services"
$COMPOSE up -d --build

# ── 4. Health gate — a green deploy must mean a working stack ──────────────
say "waiting for services to become healthy"
deadline=$(( $(date +%s) + 300 ))
check() { # name, command
  until eval "$2" >/dev/null 2>&1; do
    [ "$(date +%s)" -lt "$deadline" ] || {
      printf >&2 '\ndeploy FATAL: %s did not come up. Last 30 log lines:\n' "$1"
      $COMPOSE logs --tail 30 "$1" >&2 || true
      exit 1
    }
    sleep 5
  done
  say "$1 OK"
}

check db  "[ \"\$(docker inspect --format '{{.State.Health.Status}}' \$($COMPOSE ps -q db))\" = healthy ]"
check cms "curl -fsS -o /dev/null http://127.0.0.1:${CMS_PORT:-8080}/"
check nitro "curl -fsS -o /dev/null http://127.0.0.1:${NITRO_PORT:-3000}/"
check emulator "$COMPOSE logs emulator 2>&1 | grep -q 'successfully loaded'"

say "deploy complete — stack healthy"
```

- [ ] **Step 2: Make executable and syntax-check**

Run: `chmod +x scripts/deploy.sh && bash -n scripts/deploy.sh && echo "syntax OK"`
Expected: `syntax OK`

- [ ] **Step 3: Prove the preflight aborts without `.env`**

Run:
```bash
mkdir -p /tmp/deploytest && cd /tmp/deploytest
mkdir -p scripts artifacts/sql artifacts/arcturus
cp /Users/rybealey/Documents/Personal/pixelrp/scripts/deploy.sh scripts/
bash scripts/deploy.sh; echo "exit=$?"
```
Expected: `deploy FATAL: no .env on this server.` plus the remedy, `exit=1`, and no docker command attempted.

- [ ] **Step 4: Prove the preflight aborts on missing artifacts**

Run (still in `/tmp/deploytest`):
```bash
printf 'DB_ROOT_PASSWORD=x\nDB_DATABASE=arcturus\n' > .env
bash scripts/deploy.sh; echo "exit=$?"
```
Expected: `deploy FATAL: artifacts/sql is empty` naming `make sync-assets`, `exit=1`.

- [ ] **Step 5: Prove a real deploy is data-safe on the live local stack**

Run from the repo:
```bash
source .env
docker compose exec db mariadb -uroot -p"$DB_ROOT_PASSWORD" arcturus \
  -e "SELECT COUNT(*) AS users_before FROM users;"
bash scripts/deploy.sh
docker compose exec db mariadb -uroot -p"$DB_ROOT_PASSWORD" arcturus \
  -e "SELECT COUNT(*) AS users_after FROM users;"
ls -la data/backups/
```
Expected: `deploy complete — stack healthy`; identical before/after counts; exactly one `.sql.gz` present and non-empty.

- [ ] **Step 6: Prove backup retention prunes**

Run:
```bash
for i in 1 2 3; do touch -d "-$i day" "data/backups/pixelrp-2020010${i}T000000Z.sql.gz"; done
BACKUP_KEEP=2 bash scripts/deploy.sh >/dev/null
ls -1 data/backups/*.sql.gz | wc -l | tr -d ' '
```
Expected: `2` — older dumps pruned, newest kept.

- [ ] **Step 7: Clean up and commit**

```bash
rm -rf /tmp/deploytest
rm -f data/backups/pixelrp-2020*.sql.gz
git add scripts/deploy.sh
git commit -m "Add server-side deploy script with pre-deploy DB backup and health gate"
git push
```

---

### Task 3: Asset sync

**Files:**
- Create: `scripts/sync-assets.sh` (executable)
- Modify: `Makefile`

**Interfaces:**
- Consumes: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH`, `DEPLOY_PORT` from the local `.env`.
- Produces: `make sync-assets`, referenced by Task 2's error messages and Task 5's docs.

- [ ] **Step 1: Write `scripts/sync-assets.sh`**

```bash
#!/usr/bin/env bash
# Pushes ./artifacts (game assets, emulator jar, SQL) to the server.
#
# Deliberately SEPARATE from the deploy pipeline: assets are ~570 MB and
# change only when you re-convert, while code deploys should stay seconds
# long. Run this after `make convert-assets`, or once when setting up a box.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo >&2 "sync-assets: no .env — run 'make env' first."; exit 1; }
set -a; . ./.env; set +a

: "${DEPLOY_HOST:?set DEPLOY_HOST in .env (the server hostname or IP)}"
: "${DEPLOY_USER:?set DEPLOY_USER in .env (the ssh user)}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/pixelrp}"
DEPLOY_PORT="${DEPLOY_PORT:-22}"

echo "sync-assets: $(du -sh artifacts | cut -f1) -> ${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/artifacts"
echo "sync-assets: first run over a slow link can take a while; it resumes if interrupted."

# --delete keeps the server's artifacts identical to yours (a jar you removed
# locally must not linger there). It is scoped to artifacts/ ONLY — data/ and
# .env live outside this path and are never considered.
rsync -az --info=progress2 --partial --delete \
  -e "ssh -p ${DEPLOY_PORT}" \
  artifacts/ "${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/artifacts/"

echo "sync-assets: done. Restart the stack there to pick up new assets:"
echo "  ssh -p ${DEPLOY_PORT} ${DEPLOY_USER}@${DEPLOY_HOST} 'cd ${DEPLOY_PATH} && docker compose restart nitro'"
```

- [ ] **Step 2: Add the Makefile target**

Add to `.PHONY` and insert before the `reset` target:

```make
## Push ./artifacts (assets, jar, SQL) to the server. Separate from deploys on
## purpose: ~570MB that only changes when you re-convert.
sync-assets:
	./scripts/sync-assets.sh
```

- [ ] **Step 3: Add deployment variables to `.env.example`**

Append to the `# ── Deployment ──` block created in Task 1:

```bash
# Where `make sync-assets` pushes assets. Leave blank until you have a server.
DEPLOY_HOST=
DEPLOY_USER=root
DEPLOY_PATH=/opt/pixelrp
DEPLOY_PORT=22
```

- [ ] **Step 4: Verify it fails cleanly with no server configured**

Run: `chmod +x scripts/sync-assets.sh && bash -n scripts/sync-assets.sh && ./scripts/sync-assets.sh; echo "exit=$?"`
Expected: `set DEPLOY_HOST in .env (the server hostname or IP)`, `exit=1`. No rsync attempted.

- [ ] **Step 5: Verify the rsync command is correct without transferring**

Run:
```bash
DEPLOY_HOST=example.invalid DEPLOY_USER=root rsync -azn --delete \
  -e "ssh -p 22 -o BatchMode=yes -o ConnectTimeout=2" \
  artifacts/ root@example.invalid:/opt/pixelrp/artifacts/ 2>&1 | tail -2
```
Expected: an SSH connection failure (the host is intentionally unresolvable) — proving the command is well-formed and that `-n` would otherwise have dry-run it.

- [ ] **Step 6: Commit**

```bash
git add scripts/sync-assets.sh Makefile .env.example
git commit -m "Add make sync-assets for pushing game assets to the server"
git push
```

---

### Task 4: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

**Interfaces:**
- Consumes: `scripts/deploy.sh` (Task 2); GitHub secrets `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, optional `DEPLOY_PORT`, `DEPLOY_PATH`.
- Produces: the push-to-main trigger documented in Task 5.

- [ ] **Step 1: Write the workflow**

```yaml
name: Deploy to VPS

on:
  push:
    branches: [main]
  workflow_dispatch:        # lets you redeploy the current main by hand

# One deploy at a time; a newer push supersedes an in-flight one rather than
# racing it onto the same server.
concurrency:
  group: deploy-production
  cancel-in-progress: true

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Load SSH key
        env:
          DEPLOY_SSH_KEY: ${{ secrets.DEPLOY_SSH_KEY }}
        run: |
          [ -n "$DEPLOY_SSH_KEY" ] || { echo "::error::DEPLOY_SSH_KEY secret is not set — see docs/DEPLOYMENT.md"; exit 1; }
          mkdir -p ~/.ssh && chmod 700 ~/.ssh
          printf '%s\n' "$DEPLOY_SSH_KEY" > ~/.ssh/id_deploy
          chmod 600 ~/.ssh/id_deploy
          ssh-keyscan -p "${{ secrets.DEPLOY_PORT || 22 }}" -H "${{ secrets.DEPLOY_HOST }}" >> ~/.ssh/known_hosts 2>/dev/null

      - name: Sync code to the server
        env:
          DEPLOY_PATH: ${{ secrets.DEPLOY_PATH || '/opt/pixelrp' }}
        run: |
          # Code only. Every exclude below is state that belongs to the server:
          # data/ is the database and uploads, .env is its secrets, artifacts/
          # is synced separately by `make sync-assets`, cms/src is cloned there.
          # --delete keeps tracked files honest but can never reach an exclude.
          rsync -az --delete --info=stats2 \
            --exclude '.git/' \
            --exclude 'data/' \
            --exclude '.env' \
            --exclude 'artifacts/' \
            --exclude 'cms/src/' \
            -e "ssh -i ~/.ssh/id_deploy -p ${{ secrets.DEPLOY_PORT || 22 }} -o StrictHostKeyChecking=yes" \
            ./ "${{ secrets.DEPLOY_USER }}@${{ secrets.DEPLOY_HOST }}:${DEPLOY_PATH}/"

      - name: Run deploy script
        env:
          DEPLOY_PATH: ${{ secrets.DEPLOY_PATH || '/opt/pixelrp' }}
        run: |
          ssh -i ~/.ssh/id_deploy -p "${{ secrets.DEPLOY_PORT || 22 }}" \
            -o StrictHostKeyChecking=yes \
            "${{ secrets.DEPLOY_USER }}@${{ secrets.DEPLOY_HOST }}" \
            "cd ${DEPLOY_PATH} && bash scripts/deploy.sh"

      - name: Remove SSH key
        if: always()
        run: rm -f ~/.ssh/id_deploy
```

- [ ] **Step 2: Validate the YAML parses**

Run: `python3 -c "import yaml,sys; d=yaml.safe_load(open('.github/workflows/deploy.yml')); print('jobs:', list(d['jobs'])); print('steps:', len(d['jobs']['deploy']['steps']))"`
Expected: `jobs: ['deploy']` and `steps: 5`.

- [ ] **Step 3: Verify every state path is excluded**

Run: `for p in "data/" ".env" "artifacts/" "cms/src/" ".git/"; do grep -q -- "--exclude '$p'" .github/workflows/deploy.yml && echo "excluded: $p" || echo "MISSING EXCLUDE: $p"; done`
Expected: five `excluded:` lines, no `MISSING`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "Add push-to-main deploy workflow"
git push
```

Note: this push triggers the workflow, which will fail at "Load SSH key" until the secrets exist. That failure is expected and is itself the check that the guard works — Task 5 documents the setup.

---

### Task 5: Deployment documentation

**Files:**
- Create: `docs/DEPLOYMENT.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.
- Produces: the operator runbook.

- [ ] **Step 1: Write `docs/DEPLOYMENT.md`**

````markdown
# Deploying to a VPS

Push to `main` → GitHub Actions syncs the code → the server rebuilds and
health-checks itself. Assets are sent separately with `make sync-assets`.

**A deploy is code-only.** `data/` (database, uploads, emulator config),
`.env`, and `artifacts/` on the server are never written or deleted by a
deploy, and a database dump is taken before every one.

## One-time server setup

1. **Provision.** ~4 GB RAM and ~10 GB disk minimum. Install Docker Engine +
   the compose plugin, `git`, `make`, `rsync`, `curl`.

2. **Create a deploy keypair** on your workstation (no passphrase — CI cannot
   type one):

       ssh-keygen -t ed25519 -f ~/.ssh/pixelrp_deploy -C "pixelrp deploy" -N ""
       ssh-copy-id -i ~/.ssh/pixelrp_deploy.pub USER@SERVER

3. **Add GitHub repo secrets** (Settings → Secrets and variables → Actions):

   | Secret | Value |
   |---|---|
   | `DEPLOY_HOST` | server hostname or IP |
   | `DEPLOY_USER` | ssh user |
   | `DEPLOY_SSH_KEY` | contents of `~/.ssh/pixelrp_deploy` (the PRIVATE key) |
   | `DEPLOY_PORT` | optional, defaults to 22 |
   | `DEPLOY_PATH` | optional, defaults to `/opt/pixelrp` |

4. **Prepare the directory** on the server:

       sudo mkdir -p /opt/pixelrp && sudo chown "$USER" /opt/pixelrp

5. **Author the server `.env`.** It is never deployed — the server keeps its
   own. Copy `.env.example` there and set, at minimum:

       PUBLIC_HOST=your-domain.example     # NOT localhost
       PUBLIC_SCHEME=https                 # if you terminate TLS
       PUBLIC_WS_SCHEME=wss                # must match the page's scheme
       APP_DEBUG=false                     # true leaks stack traces publicly
       # fresh DB_ROOT_PASSWORD / DB_PASSWORD / APP_KEY — not your local ones

6. **Send the assets** from your workstation (set `DEPLOY_*` in your local
   `.env` first):

       make sync-assets

7. **First deploy:** push to `main`, or run the workflow by hand from the
   Actions tab (`workflow_dispatch`).

## Everyday use

| You want to | Do this |
|---|---|
| Ship code/config | push to `main` |
| Ship new game assets | `make sync-assets`, then restart nitro on the server |
| Redeploy without a code change | Actions tab → Deploy to VPS → Run workflow |
| Deploy by hand from the box | `cd /opt/pixelrp && bash scripts/deploy.sh` |

## Restoring a database backup

Every deploy leaves a dump in `data/backups/` (the newest `BACKUP_KEEP`, default
10 are kept). Restore is manual on purpose — an automatic restore over a live
database is more dangerous than the failure it guards against.

```bash
cd /opt/pixelrp
docker compose stop emulator cms          # stop writers; leave db running
gunzip -c data/backups/pixelrp-<STAMP>.sql.gz \
  | docker compose exec -T db mariadb -uroot -p"$DB_ROOT_PASSWORD" arcturus
docker compose start cms emulator
```

This is a deploy-time safety net, **not a backup strategy**: it lives on the
same disk and only runs when you deploy. Schedule off-box backups separately.

## Before you let real players in

This repo was built for local development. The pipeline deploys it faithfully
— it does not harden it. These are yours to do, and a green deploy does not
imply any of them:

- [ ] **Ports are bound to `127.0.0.1`.** Nothing is publicly reachable until
      you front it with a reverse proxy. That is intentional — decide what to
      expose rather than exposing everything.
- [ ] **TLS.** If the site is `https://`, the websocket must be `wss://`, which
      means the proxy has to terminate TLS for the emulator port too. A plain
      `ws://` from an `https://` page is blocked by browsers.
- [ ] **Keep the database port off the public interface.**
- [ ] **`APP_DEBUG=false`** in the server `.env`.
- [ ] **Firewall** — allow only what the hotel needs.
- [ ] **Off-box backups** and monitoring.
````

- [ ] **Step 2: Link it from `README.md`**

Add after the "Day-to-day" table:

```markdown
## Deploying

Pushing to `main` deploys to a VPS; game assets go separately via
`make sync-assets`. Setup, secrets, backup restore, and the
pre-public hardening checklist: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
```

- [ ] **Step 3: Verify the docs match the implementation**

Run:
```bash
grep -q 'BACKUP_KEEP' docs/DEPLOYMENT.md && grep -q 'sync-assets' docs/DEPLOYMENT.md \
  && grep -q 'scripts/deploy.sh' docs/DEPLOYMENT.md && echo "docs reference real targets"
for s in DEPLOY_HOST DEPLOY_USER DEPLOY_SSH_KEY; do
  grep -q "$s" .github/workflows/deploy.yml && grep -q "$s" docs/DEPLOYMENT.md \
    && echo "$s documented and used" || echo "MISMATCH: $s"
done
```
Expected: `docs reference real targets` and three `documented and used` lines.

- [ ] **Step 4: Commit**

```bash
git add docs/DEPLOYMENT.md README.md
git commit -m "Document VPS deployment, backup restore, and hardening checklist"
git push
```

---

### Task 6: End-to-end verification

Only runs once the user has a server and has added the secrets. If there is no
server yet, stop here and tell them exactly what is needed (Task 5 steps 1-6).

**Files:** none — this task verifies.

- [ ] **Step 1: Confirm prerequisites with the user**

Ask whether the VPS exists and the five GitHub secrets are set. Do not guess,
and never ask them to paste a private key into the chat.

- [ ] **Step 2: Watch the first deploy**

Run: `gh run watch $(gh run list --workflow="Deploy to VPS" --limit 1 --json databaseId -q '.[0].databaseId')`
Expected: all five steps green; the deploy step ends with `deploy complete — stack healthy`.

- [ ] **Step 3: Prove data survives a deploy (acceptance criterion 3)**

Register an account on the deployed CMS, then push a trivial change (e.g. a
comment) to `main` and wait for the deploy. Then on the server:

```bash
cd /opt/pixelrp && source .env
docker compose exec db mariadb -uroot -p"$DB_ROOT_PASSWORD" arcturus \
  -e "SELECT username FROM users ORDER BY id DESC LIMIT 3;"
ls -la data/backups/
```
Expected: the account still exists; a new timestamped dump was added.

- [ ] **Step 4: Report**

Summarise: deploy duration, health-gate result, backup count, and any
hardening checklist items still outstanding.
