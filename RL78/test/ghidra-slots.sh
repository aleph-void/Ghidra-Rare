#!/usr/bin/env bash
# ghidra-slots.sh <language-id> <raw.bin> <slot> <out.txt> [ctx=val ...]   (GHIDRA_INSTALL_DIR set)
set -euo pipefail
LANG_ID=$1; BIN=$(readlink -f "$2"); SLOT=$3; OUT=$(readlink -f "$4"); shift 4
HERE=$(cd "$(dirname "$0")" && pwd)
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/slots.XXXXXX"); trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$BIN" -loader BinaryLoader \
	-processor "$LANG_ID" -noanalysis -scriptPath "$HERE" -postScript DumpSlots.java "$SLOT" "$OUT" "$@" \
	-deleteProject >"$PROJ/log.txt" 2>&1 || { tail -30 "$PROJ/log.txt" >&2; exit 1; }
grep -qE "SCRIPT ERROR|Exception" "$PROJ/log.txt" && { grep -E -A5 "SCRIPT ERROR|Exception" "$PROJ/log.txt" | head -30 >&2; exit 1; }
[[ -s $OUT ]]
