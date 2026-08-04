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

jq --arg ws "$NITRO_WS_URL" \
   --arg asset "$NITRO_ASSET_URL" \
   --arg imglib "$IMAGE_LIBRARY_URL" \
   --arg hof "$HOF_FURNI_URL" \
   '."socket.url" = $ws
    | ."asset.url" = $asset
    | ."image.library.url" = $imglib
    | ."hof.furni.url" = $hof' \
   "$HTML/renderer-config.base.json" > "$HTML/renderer-config.json"

jq --arg cms "$NITRO_CMS_URL" \
   '."url.prefix" = $cms' \
   "$HTML/ui-config.base.json" > "$HTML/ui-config.json"

echo "pixelrp-nitro: rendered renderer-config.json (socket.url=$NITRO_WS_URL, asset.url=$NITRO_ASSET_URL)"

# Assets are a user artifact — warn (don't block) when absent.
# (! -name '.*' so the repo's .gitkeep placeholder doesn't count as content.)
if [ -z "$(find "$HTML/assets" -mindepth 1 -maxdepth 1 ! -name '.*' 2>/dev/null | head -1)" ]; then
  echo "pixelrp-nitro WARNING: ./artifacts/nitro-assets is empty — the client will" >&2
  echo "pixelrp-nitro WARNING: load forever without game assets. See artifacts/README.md." >&2
fi
