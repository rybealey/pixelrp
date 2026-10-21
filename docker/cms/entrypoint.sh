#!/bin/sh
set -e
if [ ! -f /var/www/html/.env ]; then
  cp /var/www/html/.env.example /var/www/html/.env
fi
# Only mint a key when there isn't one. Regenerating on every start would log
# out every session and permanently destroy encrypted-at-rest data (Fortify 2FA
# secrets) — unrecoverable, and staff routes require 2FA.
if ! grep -qE '^APP_KEY=.+' /var/www/html/.env; then
  php artisan key:generate --force --no-interaction || true
fi
# pixelrp: Laravel's config, route, view and event caches (and Filament's)
# before serving. Without them every request re-read every config file and
# re-scanned the routes and Filament's classes. Built here, not in the image:
# the config cache captures the environment, which only exists at run time.
# A failure only means running uncached, so clear any half-built cache and go
# on. The worker processes run as www-data and write into the same places.
# Not locally: there ./cms is bind-mounted, and cached routes and config would
# hide every edit until a manual clear.
if [ "${APP_ENV:-}" != "local" ]; then
  if ! php artisan optimize --no-interaction; then
    echo "entrypoint: artisan optimize failed - serving without Laravel's caches" >&2
    php artisan optimize:clear --no-interaction || true
  fi
  chown -R www-data:www-data bootstrap/cache storage/framework/views 2>/dev/null || true
fi
exec "$@"
