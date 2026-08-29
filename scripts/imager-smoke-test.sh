#!/usr/bin/env bash
# Usage: scripts/imager-smoke-test.sh http://localhost:3030
# Exits non-zero unless the custom-clothed render is clearly larger than the
# skin-only baseline (i.e. clothing actually rendered).
set -euo pipefail
BASE="${1:?usage: imager-smoke-test.sh <imager_base_url>}"

# ClaudeTest's look: custom sets ch-3059 / lg-3019 / sh-3206 + custom acc ca-80000103
CLOTHED='hr-6084-45-36.hd-6021-1.ch-3059-72.lg-3019-82.sh-3206-73.ca-80000103-1410-77'
NAKED='hd-6021-1'   # same body, skin only

tmp="$(mktemp -d)"
curl -fsS "${BASE}/?figure=${CLOTHED}&size=l&direction=2&head_direction=3&gesture=sml" -o "${tmp}/clothed.png"
curl -fsS "${BASE}/?figure=${NAKED}&size=l&direction=2&head_direction=3&gesture=sml"   -o "${tmp}/naked.png"

# Must be valid PNGs
file "${tmp}/clothed.png" | grep -q 'PNG image data' || { echo "FAIL: clothed not a PNG"; exit 1; }

c=$(wc -c < "${tmp}/clothed.png"); n=$(wc -c < "${tmp}/naked.png")
echo "clothed=${c}B naked=${n}B"
# Clothing adds substantial pixel data; require clothed to exceed naked by >25%.
awk -v c="$c" -v n="$n" 'BEGIN{ if (c > n*1.25) { print "PASS: clothing rendered"; exit 0 } else { print "FAIL: render looks naked"; exit 1 } }'
