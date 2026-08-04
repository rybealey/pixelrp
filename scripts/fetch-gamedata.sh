#!/usr/bin/env bash
# Regenerates the Nitro gamedata JSONs (FigureData, FurnitureData, ProductData,
# ExternalTexts, EffectMap, FigureMap) into artifacts/nitro-assets/gamedata/
# using the official nitro-converter against Habbo's live gamedata endpoints.
# This is how the gamedata in artifacts/ was produced; rerun whenever you want
# to sync newer official clothing/furni data. SWF→.nitro conversion stays OFF —
# this only refreshes the JSON metadata, in seconds.
set -euo pipefail
cd "$(dirname "$0")/.."

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

echo "fetch-gamedata: cloning the official nitro-converter"
git clone --depth 1 https://github.com/billsonnn/nitro-converter.git "$WORK/conv"

# The flash client base URL rotates per Habbo release — resolve it live.
FLASH_URL=$(curl -fsSL 'https://www.habbo.com/gamedata/external_variables/1' | grep '^flash.client.url=' | cut -d= -f2-)
[ -n "$FLASH_URL" ] || { echo >&2 "fetch-gamedata: could not resolve flash.client.url"; exit 1; }
echo "fetch-gamedata: flash client base = $FLASH_URL"

python3 - "$WORK/conv" "$FLASH_URL" <<'EOF'
import json, sys
conv, flash = sys.argv[1], sys.argv[2]
p = conv + '/configuration.json'
d = json.load(open(p + '.example'))
d.update({
    'flash.client.url': flash,
    'flash.dynamic.download.url': 'https://images.habbo.com/dcr/hof_furni/',
    'furnidata.load.url': 'https://www.habbo.com/gamedata/furnidata_json/1',
    'productdata.load.url': 'https://www.habbo.com/gamedata/productdata_json/1',
    'external.texts.url': 'https://www.habbo.com/gamedata/external_flash_texts/1',
    # gamedata only — the heavy SWF conversions stay off:
    'convert.figure': '0', 'convert.effect': '0', 'convert.furniture': '0', 'convert.pet': '0',
    'convert.figuredata': '1', 'convert.productdata': '1', 'convert.externaltexts': '1',
})
json.dump(d, open(p, 'w'), indent=1)
EOF

docker run --rm -v "$WORK/conv":/conv -w /conv node:20 \
  bash -c 'yarn install --silent && yarn build && yarn start'

mkdir -p artifacts/nitro-assets/gamedata
cp "$WORK"/conv/assets/gamedata/*.json artifacts/nitro-assets/gamedata/
echo "fetch-gamedata: installed into artifacts/nitro-assets/gamedata/:"
ls -la artifacts/nitro-assets/gamedata/
