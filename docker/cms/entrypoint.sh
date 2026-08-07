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
exec "$@"
