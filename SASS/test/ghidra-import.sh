#!/usr/bin/env bash
# Import a cubin with Ghidra headless (ELF loader + opinion picks the language),
# auto-analyze it and decompile its functions.
#   test/ghidra-import.sh <file.cubin> [decompiled-out.c] [maxFunctions]
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
BIN=$(readlink -f "$1")
OUT=$(readlink -f "${2:-/dev/null}")
MAX=${3:-50}
HERE=$(cd "$(dirname "$0")" && pwd)
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/sass-import.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$BIN" \
	-scriptPath "$HERE" -postScript SassDecompile.java "$OUT" "$MAX" -deleteProject >"$PROJ/log.txt" 2>&1 || true
grep -h "SASS-CHECK\|ERROR\|Exception" "$PROJ/log.txt" | grep -v "^\s*at " | grep -v "SASS-CHECK block" | head -40
