#!/usr/bin/env bash
# Builds the Arcturus Morningstar emulator jar from the OFFICIAL source and
# drops it into artifacts/arcturus/. This is how the jar in artifacts/ was
# produced — run it again any time to rebuild reproducibly.
#
# One local patch is applied before building: Arcturus BETA builds contain an
# interactive 'Press "ENTER" if you agree' gate (Emulator.java promptEnterKey)
# that blocks forever in a container — feeding stdin does not reliably clear
# it, so like the wider community (e.g. Gurkengewuerz/nitro-docker) we comment
# the call out. The beta warning itself still prints in the emulator log.
set -euo pipefail
cd "$(dirname "$0")/.."

REPO=https://git.krews.org/morningstar/Arcturus-Community.git
BRANCH="${ARC_BRANCH:-ms3-upgrade}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "build-emulator: cloning $REPO @ $BRANCH"
git clone --depth 1 -b "$BRANCH" "$REPO" "$WORK/src"

echo "build-emulator: patching out the interactive beta gate"
# BSD (macOS) and GNU sed differ on -i; write via a temp file to stay portable.
f="$WORK/src/src/main/java/com/eu/habbo/Emulator.java"
sed 's#promptEnterKey();#/* promptEnterKey(); — pixelrp: interactive beta gate skipped for containers */#' "$f" > "$f.tmp"
mv "$f.tmp" "$f"
grep -q 'pixelrp: interactive beta gate skipped' "$f" || { echo "patch failed"; exit 1; }

echo "build-emulator: building with maven:3.9-eclipse-temurin-21 (same image as upstream CI)"
docker run --rm -v "$WORK/src":/build -w /build maven:3.9-eclipse-temurin-21 mvn -DskipTests -q package

jar=$(ls "$WORK"/src/target/*jar-with-dependencies*.jar)
mkdir -p artifacts/arcturus
# Exactly-one-jar contract: remove any previous emulator jar first.
rm -f artifacts/arcturus/*.jar
cp "$jar" artifacts/arcturus/
echo "build-emulator: installed $(basename "$jar") into artifacts/arcturus/"
