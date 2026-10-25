#!/usr/bin/env bash
# p-code check against SingleStepTests/65816 (fetched by test/fetch-singlestep.py, never committed).
#   test/singlestep-test.sh <tests.json> <out.txt>
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
TESTS=$(readlink -f "$1"); OUT=$(readlink -m "$2")
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/65816-sst.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$HERE/emu/emu.bin" \
	-loader BinaryLoader -loader-baseAddr 0x8000 -processor 65816:LE:16:default -noanalysis \
	-scriptPath "$HERE" -postScript G65816SingleStep.java "$TESTS" "$OUT" \
	-deleteProject >"$PROJ/log.txt" 2>&1 || { tail -40 "$PROJ/log.txt" >&2; exit 1; }
tail -1 "$OUT"
