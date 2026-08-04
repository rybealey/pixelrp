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

# Portable bounded-command runner. `timeout` ships on every Linux server this
# script targets, but isn't guaranteed on every workstation it might be run by
# hand from (e.g. stock macOS), so fall back to perl's alarm. Used by the
# health gate so a hung command (stuck curl, blocked docker inspect) can never
# stall a single check() iteration past `deadline`.
run_timeout() { # seconds, command-string (run via `bash -c`)
  local secs="$1" cmd="$2"
  if command -v timeout >/dev/null 2>&1; then
    timeout "$secs" bash -c "$cmd"
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$secs" bash -c "$cmd"
  else
    command -v perl >/dev/null 2>&1 \
      || die "none of timeout, gtimeout, or perl is available — install one of these (coreutils/perl) so the health gate can bound its checks."
    perl -e 'alarm $ARGV[0]; exec("bash","-c",$ARGV[1]) or die "$!\n"' "$secs" "$cmd"
  fi
}

# ── 1. Preflight — abort before touching containers ────────────────────────
[ -f .env ] || die $'no .env on this server.\n  The server keeps its own secrets; it is never deployed.\n  Create it once:  cp .env.example .env  then edit PUBLIC_HOST, passwords, APP_KEY.'

set -a; . ./.env; set +a

[ -n "$(find artifacts/sql -name '*.sql' 2>/dev/null | head -1)" ] \
  || die $'artifacts/sql is empty — the database schema is missing.\n  Sync assets from your workstation:  make sync-assets'
[ -n "$(find artifacts/arcturus -maxdepth 1 -name '*.jar' 2>/dev/null | head -1)" ] \
  || die $'artifacts/arcturus has no emulator jar.\n  Sync assets from your workstation:  make sync-assets'
[ -n "$(find artifacts/nitro-assets -mindepth 1 -not -name '.git*' 2>/dev/null | head -1)" ] \
  || die $'artifacts/nitro-assets is empty — the game client would load with zero furni/badges/gamedata.\n  Sync assets from your workstation:  make sync-assets'

# cms/src is gitignored (not vendored) and excluded from the deploy sync, so a
# fresh server checkout never has it — only `make up` clones it, and this
# script does not call make. Clone it here so cms/Dockerfile's
# `COPY src/package.json ./` has something to find on a first deploy.
if [ ! -f cms/src/package.json ]; then
  if [ -d cms/src ]; then
    say "cms/src exists but has no package.json — replacing incomplete checkout"
    rm -rf cms/src
  fi
  say "cms/src is missing — cloning AtomCMS source (first deploy on this server)"
  command -v git >/dev/null 2>&1 \
    || die "git is not installed — required to clone cms/src on first deploy."
  git clone https://github.com/atom-retros/atomcms.git cms/src \
    || die "failed to clone cms/src from https://github.com/atom-retros/atomcms.git — check network access and try again."
fi

# ── 2. Pre-deploy database backup ──────────────────────────────────────────
# The CMS entrypoint runs `artisan migrate --force` on every boot. Those
# migrations are upstream AtomCMS code: normally additive, but a future one
# could alter or drop a column. Never migrate without a dump.
#
# Discriminate on the DATADIR, not on `compose ps` — compose v2 `ps` lists
# only RUNNING containers, so a stopped-but-existing db (e.g. after `make
# down`, or a previous deploy left it down) would otherwise take the "first
# deploy" branch, skip the dump, and let `compose up` run `artisan migrate
# --force` against live data with no backup on disk. Only a genuinely
# empty/absent data/db may skip the backup.
if [ -n "$(find data/db -mindepth 1 2>/dev/null | head -1)" ]; then
  # A database already exists — a backup is mandatory. Bring db up if it
  # isn't already, and wait for it to report healthy before dumping.
  if [ -z "$($COMPOSE ps -q db 2>/dev/null)" ] || [ "$(docker inspect --format '{{.State.Running}}' "$($COMPOSE ps -q db)" 2>/dev/null)" != "true" ]; then
    say "db container not running — starting it to take the pre-deploy backup"
    $COMPOSE up -d db
  fi
  db_deadline=$(( $(date +%s) + 600 ))
  until [ -n "$($COMPOSE ps -q db 2>/dev/null)" ] && [ "$(docker inspect --format '{{.State.Health.Status}}' "$($COMPOSE ps -q db)" 2>/dev/null)" = healthy ]; do
    [ "$(date +%s)" -lt "$db_deadline" ] || die "db did not become healthy in time to take the pre-deploy backup — deploy aborted before any migration ran."
    sleep 5
  done

  mkdir -p data/backups
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  dest="data/backups/pixelrp-${stamp}.sql.gz"
  say "backing up the database to ${dest}"
  # Password goes via MYSQL_PWD inside the container's exec environment, never
  # on argv — `-p"$DB_ROOT_PASSWORD"` would be visible to any `ps`/`docker top`
  # for the life of the dump.
  if ! $COMPOSE exec -T -e MYSQL_PWD="$DB_ROOT_PASSWORD" db mariadb-dump -uroot \
        --single-transaction --routines --events "${DB_DATABASE:-arcturus}" \
        2>/dev/null | gzip > "$dest.part"; then
    rm -f "$dest.part"
    die "database backup FAILED — deploy aborted before any migration ran."
  fi
  # A dump that produced nothing is a failed dump, whatever the exit code said.
  [ -s "$dest.part" ] || { rm -f "$dest.part"; die "database backup was empty — deploy aborted before any migration ran."; }
  # mariadb-dump can exit 0 while having written only an error message (e.g. a
  # mid-dump connection drop). Size alone doesn't catch that, so verify the
  # gzip stream is intact AND that the dump actually finished — mariadb-dump
  # writes `-- Dump completed` as its final line on success. Use `gzip -dc`
  # rather than `zcat`: on macOS, `zcat` is BSD `uncompress` and silently
  # fails on real `.gz` input, which would falsely flag every good backup.
  if ! gzip -t "$dest.part" 2>/dev/null || ! gzip -dc "$dest.part" 2>/dev/null | tail -5 | grep -q 'Dump completed'; then
    rm -f "$dest.part"
    die "database backup was corrupt (failed gzip/content check) — deploy aborted before any migration ran."
  fi
  mv "$dest.part" "$dest"
  say "backup complete ($(du -h "$dest" | cut -f1))"

  keep="${BACKUP_KEEP:-10}"
  # shellcheck disable=SC2012  # filenames are timestamped and shell-safe
  ls -1t data/backups/pixelrp-*.sql.gz 2>/dev/null | tail -n +$((keep + 1)) | while read -r old; do
    say "pruning old backup $(basename "$old")"
    rm -f "$old"
  done
else
  say "no existing database — nothing to back up"
fi

# ── 3. Build and start ─────────────────────────────────────────────────────
say "building and starting services"
$COMPOSE up -d --build

# ── 4. Health gate — a green deploy must mean a working stack ──────────────
say "waiting for services to become healthy"
deadline=$(( $(date +%s) + 300 ))
# db's own healthcheck start_period is 300s to allow a first-boot schema
# import; give the db check a longer allowance of its own so a legitimately
# slow first deploy doesn't fail red while the other, faster services keep
# the default 300s budget.
db_check_deadline=$(( $(date +%s) + 600 ))
check() { # name, command, optional-deadline-var (defaults to `deadline`)
  local dl="${3:-$deadline}"
  # Every check is run through run_timeout so a hung service (a stuck curl, a
  # blocked docker inspect) can never stall inside one iteration forever — the
  # loop always gets back to re-testing the deadline.
  until run_timeout 15 "$2" >/dev/null 2>&1; do
    [ "$(date +%s)" -lt "$dl" ] || {
      printf >&2 '\ndeploy FATAL: %s did not come up. Last 30 log lines:\n' "$1"
      $COMPOSE logs --tail 30 "$1" >&2 || true
      exit 1
    }
    sleep 5
  done
  say "$1 OK"
}

check db  "[ \"\$(docker inspect --format '{{.State.Health.Status}}' \$($COMPOSE ps -q db))\" = healthy ]" "$db_check_deadline"
check cms "curl -fsS --max-time 10 --connect-timeout 5 -o /dev/null http://127.0.0.1:${CMS_PORT:-8080}/"
check nitro "curl -fsS --max-time 10 --connect-timeout 5 -o /dev/null http://127.0.0.1:${NITRO_PORT:-3000}/"
# Must require BOTH that the emulator container is actually running (a
# crash-looping container's log can still hold yesterday's success line,
# which survives restarts) AND that the success line appears in logs scoped
# to the CONTAINER'S CURRENT boot via --since, not its entire log history —
# anchoring to the deploy's own start time instead would false-RED whenever
# `compose up -d --build` leaves the container already running (its boot
# line predates the deploy), and a stale --since would equally false-GREEN a
# container that booted successfully once and is now crash-looping. Re-read
# the container id and its StartedAt fresh each iteration (guarding against
# `ps -q emulator` being briefly empty) so both conjuncts always reflect the
# container's current incarnation.
check emulator "cid=\$($COMPOSE ps -q emulator); [ -n \"\$cid\" ] && [ \"\$(docker inspect --format '{{.State.Running}}' \"\$cid\")\" = true ] && $COMPOSE logs --since \"\$(docker inspect --format '{{.State.StartedAt}}' \"\$cid\")\" emulator 2>&1 | grep -q 'successfully loaded'"

say "deploy complete — stack healthy"
