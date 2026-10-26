#!/usr/bin/env bash
# P-code emulation test: test/emu-test.sh [cases.txt] [out.txt]
# Exit status 0 only if every case passes.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
CASES=$(readlink -f "${1:-$HERE/emu/cases.txt}")
OUT=$(readlink -m "${2:-${TMPDIR:-/tmp}/adsp-emu.txt}")
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/adsp-emu.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
head -c $((65536 * 3)) /dev/zero > "$PROJ/pm.bin"
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$PROJ/pm.bin" \
	-loader BinaryLoader -processor ADSP218x:BE:16:default -noanalysis -scriptPath "$HERE" \
	-postScript ADSPEmuTest.java "$CASES" "$OUT" -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
[[ -s $OUT ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -20 >&2; exit 1; }
grep -v ^PASS "$OUT"
grep -q " 0 failed" "$OUT"
