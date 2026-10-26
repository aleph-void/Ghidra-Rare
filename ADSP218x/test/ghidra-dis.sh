#!/usr/bin/env bash
# Disassemble a raw ADSP-218x pm image (24-bit big-endian words) with Ghidra, no analysis:
#   test/ghidra-dis.sh <raw.bin> <out.txt> [base-word-address]
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
BIN=$(readlink -f "$1"); OUT=$(readlink -m "$2"); BASE=${3:-0}
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/adsp-dis.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$BIN" -loader BinaryLoader \
	-loader-baseAddr "$BASE" -processor ADSP218x:BE:16:default -noanalysis -scriptPath "$HERE" \
	-postScript ADSPDumpDisasm.java "$OUT" -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
[[ -s $OUT ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -20 >&2; exit 1; }
