#!/usr/bin/env bash
# Fixed-stride Ghidra disassembly of a raw 65816 corpus with a given M/X/E context.
#   test/ghidra-dis.sh <raw.bin> <out.txt> <stride> <MF> <XF> <EF> [dis|pcode] [base-hex]
set -euo pipefail
BIN=$(readlink -f "$1"); OUT=$(readlink -m "$2"); STRIDE=$3; MF=$4; XF=$5; EF=$6
MODE=${7:-dis}; BASE=${8:-8000}
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/65816-dis.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p \
	-import "$BIN" -loader BinaryLoader -loader-baseAddr "0x$BASE" -processor 65816:LE:16:default \
	-noanalysis -scriptPath "$HERE" -postScript G65816DumpDisasm.java "$OUT" "$STRIDE" "$MF" "$XF" "$EF" "$MODE" \
	-deleteProject >"$PROJ/log.txt" 2>&1 || { tail -40 "$PROJ/log.txt" >&2; exit 1; }
[[ -s $OUT ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -40 >&2; exit 1; }
