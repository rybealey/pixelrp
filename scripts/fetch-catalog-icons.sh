#!/usr/bin/env bash
# Downloads the catalog images that no local source can provide, from Habbo's
# public image CDN. Everything here is SCOPED to what your own database and
# furnidata actually reference — never a blanket mirror — and every file is
# skipped if already present, so re-running is cheap and safe.
#
# Two gaps are covered:
#   A. category tab icons        c_images/catalogue/icon_<id>.png
#   B. page headline/teaser art  c_images/catalogue/<name>.{png,gif}
#
# Furni icons are deliberately NOT fetched here: images.habbo.com no longer
# serves /dcr/hof_furni/icons/ at all (every request 404s, including icons we
# know exist). Modern Habbo renders those from the bundles, which is exactly
# what `make convert-assets` extracts — don't re-add a CDN fetch for them.
set -euo pipefail
cd "$(dirname "$0")/.."

CAT_OUT=artifacts/nitro-assets/c_images/catalogue
CAT_BASE=https://images.habbo.com/c_images/catalogue
PARALLEL=8

mkdir -p "$CAT_OUT"

[ -f .env ] || { echo >&2 "fetch-catalog-icons: no .env — run 'make env' first."; exit 1; }
set -a; . ./.env; set +a

if [ -z "$(docker compose ps -q db 2>/dev/null)" ]; then
  echo >&2 "fetch-catalog-icons: the db service must be running ('make up')."
  exit 1
fi

dbq() { docker compose exec -T db mariadb -uroot -p"$DB_ROOT_PASSWORD" "${DB_DATABASE:-arcturus}" -N -B -e "$1" 2>/dev/null; }

# Downloads "<url> <destination>" pairs from stdin, in parallel, skipping
# existing files. Missing-on-CDN is normal for retro-only content, so it is
# counted rather than treated as an error.
fetch_pairs() {
  local label="$1" tmp; tmp=$(mktemp)
  cat > "$tmp"
  local total; total=$(wc -l < "$tmp" | tr -d ' ')
  if [ "$total" -eq 0 ]; then echo "fetch-catalog-icons: ${label}: nothing to do"; rm -f "$tmp"; return; fi
  echo "fetch-catalog-icons: ${label}: ${total} candidate(s), downloading with ${PARALLEL} workers…"
  local before after
  before=$(find artifacts/nitro-assets/c_images -type f 2>/dev/null | wc -l | tr -d ' ')
  # shellcheck disable=SC2016
  # The temp name must be unique per WORKER, not per destination: two
  # candidate URLs can target the same file (exact path + flattened
  # fallback), and a shared .part means the 404 worker deletes the other
  # worker's finished download.
  xargs -P "$PARALLEL" -n 2 sh -c '
    [ -s "$2" ] && exit 0
    tmp="$2.$$.part"
    curl -fsS --max-time 20 -o "$tmp" "$1" 2>/dev/null && mv "$tmp" "$2" || rm -f "$tmp"
  ' sh < "$tmp"
  after=$(find artifacts/nitro-assets/c_images -type f 2>/dev/null | wc -l | tr -d ' ')
  echo "fetch-catalog-icons: ${label}: +$((after - before)) file(s) (the rest were already present or not on the CDN)"
  rm -f "$tmp"
}

# ── A. category tab icons ──────────────────────────────────────────────────
dbq "SELECT DISTINCT icon_image FROM catalog_pages
     WHERE icon_image REGEXP '^[0-9]+\$';" \
| while read -r id; do [ -n "$id" ] && printf '%s %s\n' "$CAT_BASE/icon_${id}.png" "$CAT_OUT/icon_${id}.png"; done \
| fetch_pairs "category icons"

# ── B. page headline / teaser artwork ──────────────────────────────────────
# The client appends the extension, and the CDN carries a mix of png and gif,
# so try both — whichever exists wins, the other simply 404s.
dbq "SELECT DISTINCT page_headline FROM catalog_pages WHERE page_headline <> ''
     UNION SELECT DISTINCT page_teaser FROM catalog_pages WHERE page_teaser <> '';" \
| while read -r name; do
    [ -n "$name" ] || continue
    mkdir -p "$CAT_OUT/$(dirname "$name")"
    printf '%s %s\n' "$CAT_BASE/${name}.png" "$CAT_OUT/${name}.png"
    printf '%s %s\n' "$CAT_BASE/${name}.gif" "$CAT_OUT/${name}.gif"
  done \
| fetch_pairs "page headline/teaser art"

# ── C. front-page artwork referenced by path in the database ───────────────
# These columns store a path relative to c_images/ (e.g.
# "catalogue/feature_cata/foo.png", "web_promo_small/bar.png"). Habbo has
# since FLATTENED some of these directories, so when the exact path 404s we
# also try the same filename one directory up — that recovers the catalog
# feature tiles, which are otherwise gone.
{
  dbq "SELECT DISTINCT image FROM catalog_featured_pages WHERE image <> ''
       UNION SELECT DISTINCT image FROM hotelview_news WHERE image <> ''
       UNION SELECT DISTINCT image FROM catalog_target_offers WHERE image <> '';"
  # Hardcoded in nitro's stock ui-config hotelview widget, not in any table:
  echo "web_promo_small/spromo_Canal_Bundle.png"
} | while read -r rel; do
    [ -n "$rel" ] || continue
    dest="artifacts/nitro-assets/c_images/$rel"
    mkdir -p "$(dirname "$dest")"
    printf '%s %s\n' "https://images.habbo.com/c_images/$rel" "$dest"
    flat="$(dirname "$(dirname "$rel")")/$(basename "$rel")"
    flat="${flat#./}"
    [ "$flat" != "$rel" ] && printf '%s %s\n' "https://images.habbo.com/c_images/$flat" "$dest"
  done \
| fetch_pairs "front-page artwork"

echo "fetch-catalog-icons: done"
echo "fetch-catalog-icons: restart nitro to serve them: docker compose restart nitro"
