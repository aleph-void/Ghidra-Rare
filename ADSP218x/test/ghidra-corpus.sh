#!/usr/bin/env bash
# Decode a corpus of 24-bit big-endian words with Ghidra, one instruction per word:
#   test/ghidra-corpus.sh <corpus.bin> <out.txt>      (lines: "<word> <text>")
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
BIN=$(readlink -f "$1"); OUT=$(readlink -m "$2")
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/adsp-corpus.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
head -c $((65536 * 3)) /dev/zero > "$PROJ/pm.bin"
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$PROJ/pm.bin" -loader BinaryLoader \
	-processor ADSP218x:BE:16:default -noanalysis -scriptPath "$HERE" \
	-postScript ADSPDumpDisasm.java "$OUT" "$BIN" -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
[[ -s $OUT ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -20 >&2; exit 1; }
