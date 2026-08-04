#!/bin/bash
# Arcturus database bootstrap. MariaDB's entrypoint runs this ONCE, only when
# ./data/db is empty (first boot). Repeated `docker compose up` never re-runs it
# — that is what makes restarts corruption-free.
set -euo pipefail

SQL_DIR=/artifacts/sql
DATADIR=/var/lib/mysql
REQUIRED=(01-base.sql 02-3_5_4-to-3_5_5.sql 03-3_5_5-to-4_0_0.sql)

# If init fails for ANY reason, drop a marker the healthcheck looks for.
# Without this, a restart after an aborted init would skip this script (the
# datadir is no longer empty) and report a HEALTHY database with an empty
# schema — the marker keeps db unhealthy so emulator/cms never start against it.
on_exit() {
  if [ "$?" -ne 0 ]; then
    touch "$DATADIR/.pixelrp-init-failed" 2>/dev/null || true
    echo >&2 "pixelrp-init: initialization FAILED — db will stay unhealthy until you"
    echo >&2 "pixelrp-init: fix the cause above and run 'make reset' && 'make up'."
  fi
}
trap on_exit EXIT

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
