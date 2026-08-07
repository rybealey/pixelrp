#!/usr/bin/env bash
# Builds the Arcturus Morningstar emulator jar from the OFFICIAL source at a
# PINNED commit, applies our patches from emulator/patches/, and drops the jar
# into artifacts/arcturus/. This is how the jar in artifacts/ is produced —
# run it again any time to rebuild reproducibly.
#
# Patches (emulator/patches/*.patch, applied in filename order):
#   0001  skips the interactive 'Press "ENTER"' beta gate that blocks forever
#         in a container (stdin does not reliably clear it),
#   0002  instant first step: a click-to-walk dispatches its first step
#         immediately instead of waiting for the next 500ms room tick.
#         Walking SPEED is unchanged. Runtime kill-switch: emulator_settings
#         key pathfinder.instant.first.step = 0.
set -euo pipefail
cd "$(dirname "$0")/.."

REPO=https://git.krews.org/morningstar/Arcturus-Community.git
BRANCH="${ARC_BRANCH:-ms3-upgrade}"
# Pinned for reproducibility (ms3-upgrade @ 2026-08). Override via ARC_COMMIT.
COMMIT="${ARC_COMMIT:-6cedc536a00da95c00f4674806c609a60bfdb03f}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "build-emulator: cloning $REPO @ $BRANCH"
git clone --depth 1 -b "$BRANCH" "$REPO" "$WORK/src"

if [ "$(git -C "$WORK/src" rev-parse HEAD)" != "$COMMIT" ]; then
  echo "build-emulator: branch head moved — fetching pinned commit $COMMIT"
  git -C "$WORK/src" fetch --depth 1 origin "$COMMIT"
  git -C "$WORK/src" checkout --detach "$COMMIT"
fi

echo "build-emulator: applying emulator/patches/"
for p in emulator/patches/*.patch; do
  # --check first so a stale patch fails loudly BEFORE half-applying anything.
  git -C "$WORK/src" apply --check "$(pwd)/$p"
  git -C "$WORK/src" apply "$(pwd)/$p"
  echo "build-emulator:   applied $(basename "$p")"
done

echo "build-emulator: building with maven:3.9-eclipse-temurin-21 (same image as upstream CI)"
docker run --rm -v "$WORK/src":/build -w /build \
  -v pixelrp-m2-cache:/root/.m2 \
  maven:3.9-eclipse-temurin-21 mvn -DskipTests -q package

jar=$(ls "$WORK"/src/target/*jar-with-dependencies*.jar)
mkdir -p artifacts/arcturus
# Exactly-one-jar contract: remove any previous emulator jar first.
rm -f artifacts/arcturus/*.jar
cp "$jar" artifacts/arcturus/
echo "build-emulator: installed $(basename "$jar") into artifacts/arcturus/"
echo "build-emulator: local restart:  docker compose restart emulator"
echo "build-emulator: deploy:         make sync-assets, then restart emulator on the server"
