#!/usr/bin/env bash
# Import a real binary headless (loader and language chosen by Ghidra's opinions), analyse it,
# count functions / bad instructions / error bookmarks / decompile failures and dump the listing.
#   test/real-check.sh <binary> <out-prefix>
set -euo pipefail
BIN=$(readlink -f "$1"); OUT=$(readlink -m "$2")
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/65816-real.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$BIN" \
	-scriptPath "$HERE" -postScript G65816RealCheck.java "$OUT" 30 \
	-deleteProject >"$PROJ/log.txt" 2>&1 || { tail -40 "$PROJ/log.txt" >&2; exit 1; }
[[ -s $OUT.summary ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -40 >&2; exit 1; }
grep -E "Using Loader|Using Language" "$PROJ/log.txt" | sed 's/^INFO *//' > "$OUT.import" || true
