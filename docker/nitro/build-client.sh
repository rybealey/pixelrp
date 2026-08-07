#!/usr/bin/env bash
#
# build-client.sh — build the Nitro client from the `client/` submodule
# (rybealey/nitro-react @ branch pixelrp) and install it to nitro/client/.
#
# The client SOURCE is the tracked `client/` submodule; commit UI changes
# there (on the pixelrp branch) and push. The BUILD OUTPUT lives at
# nitro/client/ (git-ignored) and is what nginx serves at /nitro-assets/client/.
#
# Usage:
#   docker/nitro/build-client.sh            # local build (localhost config)
#   docker/nitro/build-client.sh --prod     # install the prod (wss) config
#
# Requires: Node 22 + yarn (the submodule pins the toolchain via its lockfile).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROD=0
[ "${1:-}" = "--prod" ] && PROD=1

if [ ! -e "$REPO_ROOT/client/package.json" ]; then
    echo "client/ submodule not checked out — run: git submodule update --init client" >&2
    exit 1
fi

echo "== Building client from client/ submodule =="
cd "$REPO_ROOT/client"
yarn install --immutable 2>/dev/null || yarn install
# --base sets the subpath the bundle is served under; the committed index.html
# patch already makes config.urls relative so they resolve under it.
npx vite build --base=/nitro-assets/client/

echo "== Installing to nitro/client/ =="
cd "$REPO_ROOT"
rm -rf nitro/client/assets nitro/client/index.html nitro/client/src
cp -R client/dist/. nitro/client/

if [ "$PROD" = "1" ]; then
    cp nitro/renderer-config.prod.json nitro/client/renderer-config.json
    echo "  installed PROD renderer-config (wss://pixelrp.co:2096)"
else
    cp nitro/renderer-config.json nitro/client/renderer-config.json
    echo "  installed local renderer-config (ws://localhost:2096)"
fi
cp nitro/ui-config.json nitro/client/ui-config.json

echo "Done. nginx serves nitro/client/ at /nitro-assets/client/."
