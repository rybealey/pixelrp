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
