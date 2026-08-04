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
  before=$(find "$CAT_OUT" -type f | wc -l | tr -d ' ')
  # shellcheck disable=SC2016
  xargs -P "$PARALLEL" -n 2 sh -c '
    [ -s "$2" ] && exit 0
    curl -fsS --max-time 20 -o "$2.part" "$1" 2>/dev/null && mv "$2.part" "$2" || rm -f "$2.part"
  ' sh < "$tmp"
  after=$(find "$CAT_OUT" -type f | wc -l | tr -d ' ')
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

echo "fetch-catalog-icons: done"
echo "fetch-catalog-icons: restart nitro to serve them: docker compose restart nitro"
