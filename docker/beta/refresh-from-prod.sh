#!/usr/bin/env bash
# Refresh the beta hotel's database (and optionally its game assets) from the
# live hotel. Run ON the VPS as root:
#
#   bash /opt/pixelrp-beta/docker/beta/refresh-from-prod.sh          # DB only
#   bash /opt/pixelrp-beta/docker/beta/refresh-from-prod.sh --assets # DB + assets
#
# The beta emulator/cms are stopped during the import so nothing caches stale
# rows; prod is only READ (a mysqldump), never touched.
set -euo pipefail

PROD=/opt/pixelrp
BETA=/opt/pixelrp-beta
PROD_COMPOSE="docker compose -f compose.yaml -f compose.prod.yaml"
BETA_COMPOSE="docker compose -p pixelrp-beta -f compose.yaml -f compose.prod.yaml -f compose.beta.yaml"

echo "== Dumping the live database =="
dump=$(mktemp /tmp/pixelrp-prod-XXXXXX.sql)
trap 'rm -f "$dump"' EXIT
(cd "$PROD" && $PROD_COMPOSE exec -T db \
  sh -c 'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction "$MYSQL_DATABASE"') > "$dump"
echo "dump size: $(du -h "$dump" | cut -f1)"

echo "== Stopping beta emulator/cms =="
(cd "$BETA" && $BETA_COMPOSE stop emulator cms bot 2>/dev/null || true)

# A fresh db container spends minutes seeding the base SQL before the real
# server listens on TCP; dropping the schema mid-init corrupts the data
# dictionary (MySQL error 3681). The healthcheck pings over TCP, so healthy
# means init is genuinely done.
echo "== Waiting for the beta database to be ready =="
deadline=$((SECONDS + 600))
until [ "$(docker inspect -f '{{.State.Health.Status}}' pixelrp-beta-db-1 2>/dev/null)" = "healthy" ]; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "beta db did not become healthy within 10 minutes" >&2
    exit 1
  fi
  sleep 5
done

echo "== Importing into the beta database =="
(cd "$BETA" && $BETA_COMPOSE exec -T db \
  sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -e "DROP DATABASE IF EXISTS \`$MYSQL_DATABASE\`; CREATE DATABASE \`$MYSQL_DATABASE\` CHARACTER SET utf8mb4;"')
(cd "$BETA" && $BETA_COMPOSE exec -T db \
  sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot "$MYSQL_DATABASE"') < "$dump"

# The import overwrote grants-independent data only; the app user's grants
# live in mysql.* and survive. Reset transient state prod wrote mid-dump.
(cd "$BETA" && $BETA_COMPOSE exec -T db \
  sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot "$MYSQL_DATABASE"' \
  <<< "UPDATE users SET online = '0', auth_ticket = ''; UPDATE server_status SET users_online = 0;") || true

# Camera URLs come over pointing at prod: repoint the base setting and every
# stored photo URL (camera_web rows + photo-furni extra_data) at the beta
# host, or the phone's Photos app / photo furni render broken images.
(cd "$BETA" && $BETA_COMPOSE exec -T db \
  sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot "$MYSQL_DATABASE"' \
  <<< "UPDATE server_settings SET value = REPLACE(value, '//pixelrp.co/', '//beta.pixelrp.co/') WHERE \`key\` = 'camera.url.base';
UPDATE camera_web SET url = REPLACE(url, '//pixelrp.co/', '//beta.pixelrp.co/');
UPDATE items SET extra_data = REPLACE(extra_data, '//pixelrp.co/', '//beta.pixelrp.co/') WHERE extra_data LIKE '%c_images/camera%';") || true

if [ "${1:-}" = "--assets" ]; then
  echo "== Syncing game assets (prod -> beta) =="
  # nitro/assets only — nitro/client (the built client + its VPS-only
  # configs) belongs to the beta deploy workflow, never to this refresh.
  rsync -a --delete "$PROD/nitro/assets/" "$BETA/nitro/assets/"
fi

echo "== Restarting beta =="
(cd "$BETA" && $BETA_COMPOSE up -d)
echo "Done. Beta now mirrors prod's data as of this dump."
