#!/usr/bin/env bash
# Slot-by-slot disassembly of a raw bundle image with Ghidra (no analysis):
#   ghidra-dis.sh <lang-id> <raw.bin> <out.txt> [cfm_sol cfm_out cfm_sor]
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
LANG_ID=$1; BIN=$(readlink -f "$2"); OUT=$(readlink -m "$3"); shift 3
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/ia64-dis.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$BIN" -loader BinaryLoader \
	-loader-baseAddr 0 -processor "$LANG_ID" -noanalysis -scriptPath "$HERE" \
	-postScript IA64DumpSlots.java "$OUT" "$@" -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
[[ -s $OUT ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -20 >&2; exit 1; }
