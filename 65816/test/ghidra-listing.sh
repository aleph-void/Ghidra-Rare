#!/usr/bin/env bash
# Flow disassembly of a raw image with the context tracking of the module.
#   test/ghidra-listing.sh <raw.bin> <out.txt> <base-hex> <entry-hex>[:MXE] ...
set -euo pipefail
BIN=$(readlink -f "$1"); OUT=$(readlink -m "$2"); BASE=$3; shift 3
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/65816-lst.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p \
	-import "$BIN" -loader BinaryLoader -loader-baseAddr "0x$BASE" -processor 65816:LE:16:default \
	-noanalysis -scriptPath "$HERE" -postScript G65816Listing.java "$OUT" "$@" \
	-deleteProject >"$PROJ/log.txt" 2>&1 || { tail -40 "$PROJ/log.txt" >&2; exit 1; }
[[ -s $OUT ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -40 >&2; exit 1; }
