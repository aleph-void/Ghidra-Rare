#!/usr/bin/env bash
# Import and analyse one ELF file headless, then run IA64RealCheck:
#   real-check.sh <elf> <out-prefix> [project dir]
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
ELF=$(readlink -f "$1"); OUT=$(readlink -m "$2")
PROJ=$(readlink -m "${3:-$(mktemp -d "${TMPDIR:-/tmp}/ia64-real.XXXXXX")}")
mkdir -p "$PROJ" "$(dirname "$OUT")"
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" real -import "$ELF" -overwrite -max-cpu 4 \
	-scriptPath "$HERE" -postScript IA64RealCheck.java "$OUT" 60 -deleteProject >"$OUT.log" 2>&1 \
	|| { tail -30 "$OUT.log" >&2; exit 1; }
cat "$OUT.summary"
