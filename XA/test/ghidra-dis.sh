#!/usr/bin/env bash
# Disassemble a raw XA image with Ghidra (no analysis):
#   ghidra-dis.sh <lang-id> <raw.bin> <out.txt> [base] [stride] [ctx]
# stride 0 = linear sweep, n = one instruction per n-byte slot; ctx e.g. "dsk=0".
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
LANG_ID=$1; BIN=$(readlink -f "$2"); OUT=$(readlink -m "$3"); BASE=${4:-0}; STRIDE=${5:-0}; CTX=${6:--}
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/xa-dis.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$BIN" -loader BinaryLoader \
	-loader-baseAddr "$BASE" -processor "$LANG_ID" -noanalysis -scriptPath "$HERE" \
	-postScript XADumpDisasm.java "$OUT" "$STRIDE" "$CTX" -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
[[ -s $OUT ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -20 >&2; exit 1; }
