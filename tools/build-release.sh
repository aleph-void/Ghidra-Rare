#!/usr/bin/env bash
# Build release zips of every module against one Ghidra install:
#   tools/build-release.sh /path/to/ghidra_X.Y_PUBLIC [outdir]     (default outdir: ./dist)
# SLEIGH specs are compiled with that install's compiler first, so each zip ships .sla files in
# the format its Ghidra version reads. This overwrites the .sla files in the working tree.
# Community modules are git submodules (community/modules.tsv); check them out first with
# `git submodule update --init`.
set -euo pipefail
GHIDRA=${1:?usage: build-release.sh <ghidra install dir> [outdir]}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=${2:-dist}

for manifest in "$ROOT"/*/Module.manifest; do
	"$ROOT/tools/build-module.sh" "$GHIDRA" "$(dirname "$manifest")" "$OUT"
done
grep -v '^#' "$ROOT/community/modules.tsv" | while IFS=$'\t' read -r name path sub; do
	"$ROOT/tools/build-module.sh" --standard --name "$name" "$GHIDRA" "$ROOT/$path/$sub" "$OUT"
done
