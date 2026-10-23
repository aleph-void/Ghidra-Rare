#!/usr/bin/env bash
# Run the p-code emulation semantics test.   test/emu-test.sh [out.txt]
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$(readlink -m "${1:-${TMPDIR:-/tmp}/pru-emu.txt}")
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/pru-emu.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$HERE/emu/emu_test.bin" \
	-loader BinaryLoader -processor PRU:LE:32:v3 -noanalysis -scriptPath "$HERE" \
	-postScript PruEmuTest.java "$OUT" -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
cat "$OUT"
grep -q " 0 failed" "$OUT"
