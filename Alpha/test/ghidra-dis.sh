#!/usr/bin/env bash
# Linear-sweep Ghidra disassembly of a raw Alpha instruction image.
#   test/ghidra-dis.sh <LANG_ID> <raw.bin> <out.txt> [dis|pcode]
set -euo pipefail
LANG_ID=$1; BIN=$(readlink -f "$2"); OUT=$(readlink -m "$3"); MODE=${4:-dis}
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/alpha-dis.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p \
	-import "$BIN" -loader BinaryLoader -processor "$LANG_ID" \
	-noanalysis -scriptPath "$HERE" -postScript DumpDisasm.java "$OUT" "$MODE" \
	-deleteProject >"$PROJ/log.txt" 2>&1 || { tail -40 "$PROJ/log.txt" >&2; exit 1; }
[[ -s $OUT ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -40 >&2; exit 1; }
