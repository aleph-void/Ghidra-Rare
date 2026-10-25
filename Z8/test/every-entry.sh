#!/usr/bin/env bash
# Every-entry test: test/every-entry.sh <lang-id> <raw.bin> <out.txt> <ctx>...
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
LANG_ID=$1; BIN=$(readlink -f "$2"); OUT=$(readlink -m "$3"); shift 3
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/z8-ee.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$BIN" -loader BinaryLoader \
	-loader-baseAddr 0x1000 -processor "$LANG_ID" -noanalysis -scriptPath "$HERE" \
	-postScript EveryEntry.java "$OUT" "$@" -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
cat "$OUT"
