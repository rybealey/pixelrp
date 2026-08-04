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
  # Triage before advising: `make reset` is only correct when the Arcturus
  # schema never made it in. If the schema IS there, a migration wedged
  # mid-way (MariaDB DDL commits outside transactions) — resetting would
  # destroy a healthy, populated database over a fixable migration.
  if php -r 'new PDO(sprintf("mysql:host=%s;port=%s;dbname=%s", getenv("DB_HOST"), getenv("DB_PORT"), getenv("DB_DATABASE")), getenv("DB_USERNAME"), getenv("DB_PASSWORD"))->query("SELECT 1 FROM users LIMIT 1");' >/dev/null 2>&1; then
    echo >&2 "cms FATAL: a migration failed but the Arcturus schema IS present."
    echo >&2 "cms FATAL: do NOT 'make reset' — your data is fine. Read the error above,"
    echo >&2 "cms FATAL: check 'php artisan migrate:status' (docker compose run --rm cms bash),"
    echo >&2 "cms FATAL: and fix the wedged migration manually (often: a half-applied"
    echo >&2 "cms FATAL: ALTER already exists — mark it run or drop the added column)."
  else
    echo >&2 "cms FATAL: migrations failed — the Arcturus schema is missing."
    echo >&2 "cms FATAL: (did db init abort? check: docker compose logs db) — see artifacts/README.md."
  fi
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
