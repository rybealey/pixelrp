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
