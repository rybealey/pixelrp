#!/usr/bin/env bash
# Downloads the catalog PAGE icons (the little pictures on catalog category
# tabs) into artifacts/nitro-assets/c_images/catalogue/.
#
# Unlike furniture icons — which live inside the converted .nitro bundles and
# are extracted by `make convert-assets` — these are plain web images that no
# flash-assets pack ships. They come from Habbo's public image CDN.
#
# The download is SCOPED to the icon ids your own database actually references
# (catalog_pages.icon_image), not the whole CDN, and it skips files already
# present, so re-running is cheap and safe.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT=artifacts/nitro-assets/c_images/catalogue
BASE=https://images.habbo.com/c_images/catalogue
mkdir -p "$OUT"

[ -f .env ] || { echo >&2 "fetch-catalog-icons: no .env — run 'make env' first."; exit 1; }
set -a; . ./.env; set +a

if [ -z "$(docker compose ps -q db 2>/dev/null)" ]; then
  echo >&2 "fetch-catalog-icons: the db service must be running ('make up')."
  exit 1
fi

echo "fetch-catalog-icons: reading referenced icon ids from catalog_pages"
ids=$(docker compose exec -T db mariadb -uroot -p"$DB_ROOT_PASSWORD" "${DB_DATABASE:-arcturus}" \
        -N -B -e "SELECT DISTINCT icon_image FROM catalog_pages WHERE icon_image IS NOT NULL AND icon_image <> '' AND icon_image REGEXP '^[0-9]+$';" 2>/dev/null)

[ -n "$ids" ] || { echo >&2 "fetch-catalog-icons: no icon ids found — is the catalog seeded?"; exit 1; }

total=0; got=0; have=0; missing=0
for id in $ids; do
  total=$((total + 1))
  f="$OUT/icon_${id}.png"
  if [ -s "$f" ]; then have=$((have + 1)); continue; fi
  if curl -fsS --max-time 20 -o "$f.part" "$BASE/icon_${id}.png" 2>/dev/null; then
    mv "$f.part" "$f"; got=$((got + 1))
  else
    rm -f "$f.part"; missing=$((missing + 1))
    echo "fetch-catalog-icons: not on the CDN: icon_${id}.png"
  fi
done

echo "fetch-catalog-icons: ${total} referenced — downloaded ${got}, already present ${have}, unavailable ${missing}"
echo "fetch-catalog-icons: restart nitro to serve them: docker compose restart nitro"
