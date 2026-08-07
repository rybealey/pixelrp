#!/bin/sh
# Renders the two runtime configs the built client fetches from the web root.
# jq (not envsubst) on purpose: nitro configs use their own ${key} interpolation
# (e.g. "${gamedata.url}/FurnitureData.json") which envsubst could mangle;
# jq rewrites exactly the keys we own and nothing else.
set -eu

HTML=/usr/share/nginx/html
: "${NITRO_WS_URL:?NITRO_WS_URL must be set (docker-compose.yml)}"
: "${NITRO_ASSET_URL:?NITRO_ASSET_URL must be set (docker-compose.yml)}"
: "${NITRO_CMS_URL:?NITRO_CMS_URL must be set (docker-compose.yml)}"
# SWF-era image trees — override only if your asset pack nests them elsewhere.
IMAGE_LIBRARY_URL="${NITRO_IMAGE_LIBRARY_URL:-$NITRO_ASSET_URL/c_images/}"
HOF_FURNI_URL="${NITRO_HOF_FURNI_URL:-$NITRO_ASSET_URL/dcr/hof_furni}"

# Cache-bust the gamedata JSONs. `make convert-assets` rewrites them in place
# at a stable URL, and browsers happily serve a months-old cached copy —
# which looks exactly like "the converter didn't work". Stamp = newest
# gamedata mtime, so the query only changes when the data actually changes.
STAMP=$(find "$HTML/game-assets/gamedata" -type f -name '*.json' -exec stat -c %Y {} + 2>/dev/null | sort -n | tail -1)
STAMP=${STAMP:-0}

jq --arg ws "$NITRO_WS_URL" \
   --arg asset "$NITRO_ASSET_URL" \
   --arg imglib "$IMAGE_LIBRARY_URL" \
   --arg hof "$HOF_FURNI_URL" \
   --arg v "?v=$STAMP" \
   '."socket.url" = $ws
    | ."asset.url" = $asset
    | ."image.library.url" = $imglib
    | ."hof.furni.url" = $hof
    | ."furnidata.url" = "${gamedata.url}/FurnitureData.json\($v)"
    | ."productdata.url" = "${gamedata.url}/ProductData.json\($v)"
    | ."avatar.figuredata.url" = "${gamedata.url}/FigureData.json\($v)"
    | ."avatar.figuremap.url" = "${gamedata.url}/FigureMap.json\($v)"
    | ."avatar.effectmap.url" = "${gamedata.url}/EffectMap.json\($v)"
    | ."avatar.actions.url" = "${gamedata.url}/HabboAvatarActions.json\($v)"
    | ."external.texts.url" = ["${gamedata.url}/ExternalTexts.json\($v)", "${gamedata.url}/UITexts.json\($v)"]' \
   "$HTML/renderer-config.base.json" > "$HTML/renderer-config.json"

# The hotel view ships two pieces of stock Habbo demo content: the "What's
# new?" promo articles (seeded into hotelview_news) and a promo box whose
# copy comes from translation keys (2021NitroPromo) that no retro has, so it
# renders as raw "landing.view.…" strings. Blank both slots by default —
# this touches only client config, never the database, so restoring is just
# NITRO_SHOW_PROMO_ARTICLES=1 in .env.
if [ "${NITRO_SHOW_PROMO_ARTICLES:-0}" = "1" ]; then
  PROMO_FILTER='.'
else
  PROMO_FILTER='
    ( [ .hotelview.widgets | to_entries[]
        | select((.key | endswith(".conf")) and (.value.texts? == "2021NitroPromo"))
        | .key | sub("\\.conf$"; "") ] ) as $demo
    | .hotelview.widgets |= with_entries(
        if (.key | endswith(".widget"))
           and ((.value == "promoarticle")
                or ((.key | sub("\\.widget$"; "")) as $s | $demo | index($s)))
        then .value = "" else . end)'
fi

# camera.url: nitro-react builds photo previews as camera.url + '/' + the
# filename the emulator sends, so NO trailing slash here. thumbnails.url is
# the navigator room-thumbnail template in the same tree.
CAMERA_URL="${NITRO_CAMERA_URL:?NITRO_CAMERA_URL must be set (docker-compose.yml)}"

jq --arg cms "$NITRO_CMS_URL" \
   --arg cam "$CAMERA_URL" \
   '."url.prefix" = $cms
    | ."camera.url" = $cam
    | ."thumbnails.url" = "\($cam)/thumbnail/%thumbnail%.png"' \
   "$HTML/ui-config.base.json" \
| jq "$PROMO_FILTER" > "$HTML/ui-config.json"

echo "pixelrp-nitro: rendered renderer-config.json (socket.url=$NITRO_WS_URL, asset.url=$NITRO_ASSET_URL)"

# Assets are a user artifact — warn (don't block) when absent.
# (! -name '.*' so the repo's .gitkeep placeholder doesn't count as content.)
if [ -z "$(find "$HTML/game-assets" -mindepth 1 -maxdepth 1 ! -name '.*' 2>/dev/null | head -1)" ]; then
  echo "pixelrp-nitro WARNING: ./artifacts/nitro-assets is empty — the client will" >&2
  echo "pixelrp-nitro WARNING: load forever without game assets. See artifacts/README.md." >&2
fi
