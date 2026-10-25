#!/usr/bin/env bash
# Build release zips of every module against one Ghidra install:
#   tools/build-release.sh /path/to/ghidra_X.Y_PUBLIC [outdir]     (default outdir: ./dist)
# SLEIGH specs are compiled with that install's compiler first, so each zip ships .sla files in
# the format its Ghidra version reads. This overwrites the .sla files in the working tree.
set -euo pipefail
GHIDRA=$(cd "${1:?usage: build-release.sh <ghidra install dir> [outdir]}" && pwd)
ROOT=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "${2:-dist}"
OUT=$(cd "${2:-dist}" && pwd)
VERSION=$(sed -n 's/^application.version=//p' "$GHIDRA/Ghidra/application.properties")

# Ghidra 12 bundles a Gradle wrapper pinned to a compatible Gradle; fall back to gradle on PATH.
GRADLE=gradle
[[ -x "$GHIDRA/support/gradle/gradlew" ]] && GRADLE="$GHIDRA/support/gradle/gradlew"

for manifest in "$ROOT"/*/Module.manifest; do
	dir=$(dirname "$manifest")
	name=$(basename "$dir")
	echo "== $name (Ghidra $VERSION)"
	# One spec per JVM: compiling several large specs in one run has exhausted memory.
	for spec in "$dir"/data/languages/*.slaspec; do
		"$GHIDRA/support/sleigh" "$spec"
	done
	(cd "$dir" && GHIDRA_INSTALL_DIR="$GHIDRA" "$GRADLE" --no-daemon -q buildExtension)
	zip=$(ls -t "$dir"/dist/ghidra_"${VERSION}"_PUBLIC_*_"$name".zip | head -1)
	cp "$zip" "$OUT/"
	echo "built $(basename "$zip")"
done
