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

echo "sync-assets: $(du -sh artifacts | cut -f1) -> ${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/artifacts"
echo "sync-assets: first run over a slow link can take a while; resumption is safe and never leaves truncated files."

# --delete keeps the server's artifacts identical to yours (a jar you removed
# locally must not linger there). It is scoped to artifacts/ ONLY — data/ and
# .env live outside this path and are never considered.
# --partial-dir and --delay-updates ensure interrupted transfers never leave
# half-written files under their real names: incomplete transfers park in
# .rsync-partial/ and are moved into place only when the full rsync succeeds.
rsync -az --info=progress2 --partial-dir=.rsync-partial --delay-updates --delete \
  --exclude='.rsync-partial/' \
  -e "ssh -p ${DEPLOY_PORT}" \
  artifacts/ "${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/artifacts/"

echo "sync-assets: done. Restart the stack there to pick up new assets:"
echo "  ssh -p ${DEPLOY_PORT} ${DEPLOY_USER}@${DEPLOY_HOST} 'cd ${DEPLOY_PATH} && docker compose restart nitro'"
