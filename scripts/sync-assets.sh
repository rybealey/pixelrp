#!/usr/bin/env bash
# Pushes ./artifacts (game assets, emulator jar, SQL) to the server.
#
# Deliberately SEPARATE from the deploy pipeline: assets are ~570 MB and
# change only when you re-convert, while code deploys should stay seconds
# long. Run this after `make convert-assets`, or once when setting up a box.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo >&2 "sync-assets: no .env — run 'make env' first."; exit 1; }
set -a; . ./.env; set +a

: "${DEPLOY_HOST:?set DEPLOY_HOST in .env (the server hostname or IP)}"
: "${DEPLOY_USER:?set DEPLOY_USER in .env (the ssh user)}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/pixelrp}"
DEPLOY_PORT="${DEPLOY_PORT:-22}"

# Guard against a fresh/empty local checkout: --delete-after below mirrors
# the server to whatever is here, so an empty artifacts/ (e.g. a clean clone
# with DEPLOY_* already set, before ever running convert-assets or fetching
# the jar) would delete ~570MB of real assets on the server. Mirrors the same
# check scripts/deploy.sh does server-side before it will run at all.
[ -n "$(find artifacts/sql -name '*.sql' 2>/dev/null | head -1)" ] \
  || { echo >&2 $'sync-assets: artifacts/sql is empty locally — refusing to sync.\n  This guard exists so an empty checkout cannot wipe the server via --delete-after.'; exit 1; }
[ -n "$(find artifacts/arcturus -maxdepth 1 -name '*.jar' 2>/dev/null | head -1)" ] \
  || { echo >&2 $'sync-assets: artifacts/arcturus has no emulator jar locally — refusing to sync.\n  This guard exists so an empty checkout cannot wipe the server via --delete-after.'; exit 1; }
[ -n "$(find artifacts/nitro-assets -mindepth 1 -not -name '.git*' 2>/dev/null | head -1)" ] \
  || { echo >&2 $'sync-assets: artifacts/nitro-assets is empty locally — refusing to sync.\n  This guard exists so an empty checkout cannot wipe the server via --delete-after.\n  Convert assets from your workstation:  make convert-assets'; exit 1; }

echo "sync-assets: $(du -sh artifacts | cut -f1) -> ${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/artifacts"
echo "sync-assets: first run over a slow link can take a while; resumption is safe and never leaves truncated files."

# --delete-after keeps the server's artifacts identical to yours (a jar you
# removed locally must not linger there). It is scoped to artifacts/ ONLY —
# data/ and .env live outside this path and are never considered. Deletions
# are deferred to the end so the destination is never left missing assets
# mid-transfer if the sync is interrupted.
# --partial-dir and --delay-updates ensure interrupted transfers never leave
# half-written files under their real names: incomplete transfers park in
# .rsync-partial/ and are moved into place only when the full rsync succeeds.
# flash-assets/ is excluded: it's converter INPUT only (~93MB of source SWFs)
# with no use on the server, which only ever serves the converted output.
rsync -az --info=progress2 --partial-dir=.rsync-partial --delay-updates --delete-after \
  --exclude='.rsync-partial/' \
  --exclude='flash-assets/' \
  -e "ssh -p ${DEPLOY_PORT}" \
  artifacts/ "${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/artifacts/"

echo "sync-assets: done. Restart the stack there to pick up new assets:"
echo "  ssh -p ${DEPLOY_PORT} ${DEPLOY_USER}@${DEPLOY_HOST} 'cd ${DEPLOY_PATH} && docker compose restart nitro'"
