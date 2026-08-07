#!/usr/bin/env bash
#
# mirror-c-images.sh
#
# Mirrors the small set of Sulake "c_images" web assets that our own
# `nitro/assets/` tree never had a copy of, because they were historically
# served straight from images.habbo.com rather than bundled with the client:
#
#   - nitro/assets/c_images/catalogue/icon_<N>.png   (catalog tree icons)
#   - nitro/assets/c_images/catalogue/<name>.png|gif (catalog promo/teaser images)
#   - nitro/assets/c_images/album1584/<code>.gif     (badge art)
#
# We only fetch what our own database actually references (plus a small
# icon_<N> sweep for numbers that show up in older/edited catalog trees),
# so this stays a "mirror what we use" operation rather than a full scrape.
#
# Requires: docker compose (for `db` service), curl, mysql client inside the
# db container (bundled with the mysql:8.0 image), xargs -P for a small
# amount of politely-bounded concurrency.
#
# Usage:
#   docker/nitro/mirror-c-images.sh
#
# Idempotent: re-running only re-fetches files that are still missing
# locally (existing files are left alone) or use --force to refetch all.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# shellcheck disable=SC1091
[ -f .env ] && source .env

DB_NAME="${DB_NAME:-pixelrp}"
DB_USER="${DB_USER:-pixelrp}"
DB_PASSWORD="${DB_PASSWORD:?DB_PASSWORD not set (check .env)}"

OUT_DIR="$REPO_ROOT/nitro/assets/c_images"
CATALOGUE_DIR="$OUT_DIR/catalogue"
ALBUM_DIR="$OUT_DIR/album1584"
BASE_URL="https://images.habbo.com/c_images"
CONCURRENCY=4
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

mkdir -p "$CATALOGUE_DIR" "$ALBUM_DIR"

mysql_query() {
    docker compose exec -T db mysql -N -B -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -e "$1" 2>/dev/null
}

# ---------------------------------------------------------------------------
# 1. Catalog tree icons: nitro/assets/c_images/catalogue/icon_<N>.png
# ---------------------------------------------------------------------------
echo "== Collecting referenced catalog icon ids =="
{
    mysql_query "SELECT DISTINCT icon_image FROM catalog_pages WHERE icon_image IS NOT NULL;"
    seq 1 250
} | sort -n -u > /tmp/mirror_icon_ids.txt
echo "  $(wc -l < /tmp/mirror_icon_ids.txt) candidate icon ids (DB-referenced + 1..250 sweep)"

fetch_icon() {
    local n="$1"
    local out="$CATALOGUE_DIR/icon_${n}.png"
    if [ "$FORCE" -eq 0 ] && [ -s "$out" ]; then
        echo "SKIP icon_${n}.png"
        return
    fi
    if curl -fsS --max-time 15 -o "$out" "$BASE_URL/catalogue/icon_${n}.png"; then
        echo "OK icon_${n}.png"
    else
        rm -f "$out"
        echo "404 icon_${n}.png"
    fi
}
export -f fetch_icon
export CATALOGUE_DIR BASE_URL FORCE

echo "== Fetching catalog icons (icon_<N>.png) =="
ICON_RESULTS=$(cat /tmp/mirror_icon_ids.txt | xargs -P "$CONCURRENCY" -I{} bash -c 'fetch_icon "$@"' _ {})
echo "$ICON_RESULTS" > /tmp/mirror_icon_results.txt
ICON_OK=$(grep -c '^OK' /tmp/mirror_icon_results.txt || true)
ICON_404=$(grep -c '^404' /tmp/mirror_icon_results.txt || true)
ICON_SKIP=$(grep -c '^SKIP' /tmp/mirror_icon_results.txt || true)
echo "  icons: fetched=$ICON_OK 404=$ICON_404 skipped(existing)=$ICON_SKIP"

# ---------------------------------------------------------------------------
# 2. Catalog promo / teaser images referenced from catalog_promotions.image
#    (values already look like "catalogue/feature_cata_vert_hween16bun1.png")
# ---------------------------------------------------------------------------
echo "== Collecting referenced catalog promo/teaser images =="
mysql_query "SELECT DISTINCT image FROM catalog_promotions WHERE image IS NOT NULL AND image <> '';" > /tmp/mirror_teaser_paths.txt
echo "  $(wc -l < /tmp/mirror_teaser_paths.txt) referenced promo/teaser images"

fetch_teaser() {
    local rel="$1"
    [ -z "$rel" ] && return
    local out="$OUT_DIR/$rel"
    mkdir -p "$(dirname "$out")"
    if [ "$FORCE" -eq 0 ] && [ -s "$out" ]; then
        echo "SKIP $rel"
        return
    fi
    if curl -fsS --max-time 15 -o "$out" "$BASE_URL/$rel"; then
        echo "OK $rel"
        return
    fi
    rm -f "$out"
    # try swapping extension .png<->.gif as a fallback
    local alt=""
    case "$rel" in
        *.png) alt="${rel%.png}.gif" ;;
        *.gif) alt="${rel%.gif}.png" ;;
    esac
    if [ -n "$alt" ]; then
        local altout="$OUT_DIR/$alt"
        if curl -fsS --max-time 15 -o "$altout" "$BASE_URL/$alt"; then
            echo "OK $alt (fallback for $rel)"
            return
        fi
        rm -f "$altout"
    fi
    echo "404 $rel"
}
export -f fetch_teaser
export OUT_DIR

echo "== Fetching catalog promo/teaser images =="
TEASER_RESULTS=$(cat /tmp/mirror_teaser_paths.txt | xargs -P "$CONCURRENCY" -I{} bash -c 'fetch_teaser "$@"' _ {})
echo "$TEASER_RESULTS" > /tmp/mirror_teaser_results.txt
TEASER_OK=$(grep -c '^OK' /tmp/mirror_teaser_results.txt || true)
TEASER_404=$(grep -c '^404' /tmp/mirror_teaser_results.txt || true)
TEASER_SKIP=$(grep -c '^SKIP' /tmp/mirror_teaser_results.txt || true)
echo "  teasers: fetched=$TEASER_OK 404=$TEASER_404 skipped(existing)=$TEASER_SKIP"

# ---------------------------------------------------------------------------
# 2b. Catalog page header/teaser images (the banner to the right of the item
#     grid). Each visible catalog_pages.page_strings_1 is a '|'-separated list
#     whose first two tokens are the header (index 0) and teaser (index 1)
#     image NAMES; PageLocalization.getImage() resolves them to
#     c_images/catalogue/<name>.gif (the client always requests .gif). Fetch
#     .gif, falling back to Habbo's .png saved under the .gif name the client
#     asks for (browsers sniff the content, so PNG bytes still render).
#     Legacy/purged or custom-pack names simply 404 and stay blank.
# ---------------------------------------------------------------------------
echo "== Collecting catalog page header/teaser image names =="
mysql_query "SELECT page_strings_1 FROM catalog_pages WHERE visible=1 AND page_strings_1 <> '';" \
  | awk -F'|' '{ if ($1 ~ /^[A-Za-z0-9_]+$/) print $1; if ($2 ~ /^[A-Za-z0-9_]+$/) print $2; }' \
  | sort -u > /tmp/mirror_header_names.txt
echo "  $(wc -l < /tmp/mirror_header_names.txt) header/teaser names"

fetch_header() {
    local name="$1" dest="$CATALOGUE_DIR/$1.gif"
    if [ "$FORCE" != "1" ] && [ -s "$dest" ]; then echo "SKIP"; return; fi
    if curl -fs --max-time 20 "$BASE_URL/catalogue/$name.gif" -o "$dest.tmp" && [ -s "$dest.tmp" ]; then
        mv "$dest.tmp" "$dest"; echo "OK"; return
    fi
    # fall back to the .png source, saved under the .gif name the client requests
    if curl -fs --max-time 20 "$BASE_URL/catalogue/$name.png" -o "$dest.tmp" && [ -s "$dest.tmp" ]; then
        mv "$dest.tmp" "$dest"; echo "OK"; return
    fi
    rm -f "$dest.tmp"; echo "404"
}
export -f fetch_header
export CATALOGUE_DIR BASE_URL FORCE

echo "== Fetching catalog header/teaser images (catalogue/<name>.gif) =="
HEADER_RESULTS=$(cat /tmp/mirror_header_names.txt | xargs -P "$CONCURRENCY" -I{} bash -c 'fetch_header "$@"' _ {})
HEADER_OK=$(grep -c '^OK' <<<"$HEADER_RESULTS" || true)
HEADER_404=$(grep -c '^404' <<<"$HEADER_RESULTS" || true)
HEADER_SKIP=$(grep -c '^SKIP' <<<"$HEADER_RESULTS" || true)
echo "  headers: fetched=$HEADER_OK 404=$HEADER_404 skipped(existing)=$HEADER_SKIP"

# ---------------------------------------------------------------------------
# 3. Badge art: nitro/assets/c_images/album1584/<code>.gif
#    Union of badge_definitions.code, user_badges.badge_id and
#    client_external_badge_texts.badge_code - deduplicated.
# ---------------------------------------------------------------------------
echo "== Collecting referenced badge codes =="
mysql_query "
    SELECT code FROM badge_definitions
    UNION
    SELECT badge_id FROM user_badges
    UNION
    SELECT badge_code FROM client_external_badge_texts;
" | sort -u > /tmp/mirror_badge_codes.txt
echo "  $(wc -l < /tmp/mirror_badge_codes.txt) unique badge codes (badge_definitions + user_badges + client_external_badge_texts)"

fetch_badge() {
    local code="$1"
    [ -z "$code" ] && return
    local out="$ALBUM_DIR/${code}.gif"
    if [ "$FORCE" -eq 0 ] && [ -s "$out" ]; then
        echo "SKIP ${code}.gif"
        return
    fi
    if curl -fsS --max-time 15 -o "$out" "$BASE_URL/album1584/${code}.gif"; then
        echo "OK ${code}.gif"
    else
        rm -f "$out"
        echo "404 ${code}.gif"
    fi
}
export -f fetch_badge
export ALBUM_DIR

echo "== Fetching badge art (album1584/<code>.gif) =="
BADGE_RESULTS=$(cat /tmp/mirror_badge_codes.txt | xargs -P "$CONCURRENCY" -I{} bash -c 'fetch_badge "$@"' _ {})
echo "$BADGE_RESULTS" > /tmp/mirror_badge_results.txt
BADGE_OK=$(grep -c '^OK' /tmp/mirror_badge_results.txt || true)
BADGE_404=$(grep -c '^404' /tmp/mirror_badge_results.txt || true)
BADGE_SKIP=$(grep -c '^SKIP' /tmp/mirror_badge_results.txt || true)
echo "  badges: fetched=$BADGE_OK 404=$BADGE_404 skipped(existing)=$BADGE_SKIP"

echo ""
echo "== Summary =="
echo "  catalog icons : fetched=$ICON_OK   404=$ICON_404   skipped=$ICON_SKIP"
echo "  teasers/promos: fetched=$TEASER_OK 404=$TEASER_404 skipped=$TEASER_SKIP"
echo "  badges        : fetched=$BADGE_OK  404=$BADGE_404  skipped=$BADGE_SKIP"

rm -f /tmp/mirror_icon_ids.txt /tmp/mirror_icon_results.txt /tmp/mirror_teaser_paths.txt \
      /tmp/mirror_teaser_results.txt /tmp/mirror_badge_codes.txt /tmp/mirror_badge_results.txt
