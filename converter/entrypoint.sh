#!/bin/bash
# One-shot conversion run. Exits when done; safe to re-run (the converter
# skips any .nitro that already exists, so interrupted runs simply resume).
set -euo pipefail
cd /conv

FLASH=/flash-assets

# ── The SWF pack is a user artifact — fail loudly, never substitute ────────
if [ -z "$(find "$FLASH" -maxdepth 1 -name '*.swf' 2>/dev/null | head -1)" ]; then
  echo >&2 "converter FATAL: no SWFs found in ./artifacts/flash-assets/"
  echo >&2 "converter FATAL: copy your flash-assets-PRODUCTION-* pack there first"
  echo >&2 "converter FATAL: (see artifacts/README.md), then re-run: make convert-assets"
  exit 1
fi
for f in figuremap.xml effectmap.xml; do
  if [ ! -f "$FLASH/$f" ]; then
    echo >&2 "converter FATAL: $f missing from ./artifacts/flash-assets/ — clothing/effect"
    echo >&2 "converter FATAL: conversion needs it (it ships inside the flash-assets pack)."
    exit 1
  fi
done

# ── Configuration: local pack first, official endpoints only for what a
#    client pack never contains (furnidata/productdata/external texts, and
#    the per-revision furniture SWFs on images.habbo.com/dcr/hof_furni) ─────
cat > configuration.json <<EOF
{
 "flash.client.url": "$FLASH/",
 "flash.dynamic.download.url": "https://images.habbo.com/dcr/hof_furni/",
 "furnidata.load.url": "https://www.habbo.com/gamedata/furnidata_json/1",
 "productdata.load.url": "https://www.habbo.com/gamedata/productdata_json/1",
 "figuredata.load.url": "https://www.habbo.com/gamedata/figuredata/1",
 "figuremap.load.url": "\${flash.client.url}figuremap.xml",
 "effectmap.load.url": "\${flash.client.url}effectmap.xml",
 "dynamic.download.pet.url": "\${flash.client.url}%className%.swf",
 "dynamic.download.figure.url": "\${flash.client.url}%className%.swf",
 "dynamic.download.effect.url": "\${flash.client.url}%className%.swf",
 "dynamic.download.furniture.url": "\${flash.dynamic.download.url}%revision%/%className%.swf",
 "external.variables.url": "https://www.habbo.com/gamedata/external_variables/1",
 "external.texts.url": "https://www.habbo.com/gamedata/external_flash_texts/1",
 "convert.figure": "1",
 "convert.effect": "1",
 "convert.furniture": "1",
 "convert.furniture.floor.only": "0",
 "convert.furniture.wall.only": "0",
 "convert.pet": "1"
}
EOF

echo "converter: starting one-shot run (clothing/effects/pets from the local pack;"
echo "converter: furniture streams from images.habbo.com — first run is long, re-runs resume)"

LOG=/tmp/convert.log
# The converter logs failed SWFs ('Invalid SWF: ...') and continues — exactly
# what we want mid-run; the summary below makes sure none of them go unnoticed.
yarn start 2>&1 | tee "$LOG" || true

# ── Normalize FigureMap (REQUIRED — see comment) ───────────────────────────
# nitro-converter emits library entries with NO `parts` key when the source
# figuremap.xml has a library with no <part> children. nitro-renderer's
# processFigureMap iterates `library.parts` unguarded, so ONE such entry
# throws TypeError and aborts the whole figure-map load — every avatar in the
# hotel then silently fails to render (verified 2026-08: 2 bad entries out of
# 2954 made all avatars invisible). Give partless libraries an empty array.
if [ -f assets/gamedata/FigureMap.json ]; then
  node -e '
    const fs = require("fs");
    const p = "assets/gamedata/FigureMap.json";
    const d = JSON.parse(fs.readFileSync(p, "utf8"));
    let fixed = 0;
    for (const lib of (d.libraries || [])) {
      if (!Array.isArray(lib.parts)) { lib.parts = []; fixed++; }
    }
    if (fixed) fs.writeFileSync(p, JSON.stringify(d));
    console.log(`converter: FigureMap normalized (${fixed} partless librar${fixed === 1 ? "y" : "ies"} given an empty parts array)`);
  '
fi

echo ""
echo "──────────────────────────────────────────────────────"
produced=$(find assets/bundled -name '*.nitro' 2>/dev/null | wc -l | tr -d ' ')
echo "converter: ${produced} .nitro bundles now present in artifacts/nitro-assets/bundled/"

failures=$(grep -E '^(Invalid SWF|Invalid SWF Bundle)' "$LOG" | sort -u || true)
if [ -n "$failures" ]; then
  count=$(printf '%s\n' "$failures" | wc -l | tr -d ' ')
  echo ""
  echo "converter: CONVERSION FAILURES (${count}) — these SWFs did NOT convert:"
  printf '%s\n' "$failures" | sed 's/^/converter:   /'
  echo "converter: (re-running retries only missing outputs; persistent entries are"
  echo "converter:  usually corrupt/legacy SWFs in the source pack)"
else
  echo "converter: no conversion failures reported"
fi

if [ "$produced" -eq 0 ]; then
  echo >&2 "converter FATAL: run produced no bundles at all — see the log above."
  exit 1
fi
echo "converter: done"
