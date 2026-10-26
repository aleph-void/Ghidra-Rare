#!/usr/bin/env bash
# Real-code check: test/real-check.sh <program> <outprefix>
# Imports with auto-analysis (the DXE loader for VisualDSP++ executables, otherwise a raw pm
# image of 24-bit big-endian words at pm:0000), then writes <outprefix>.summary/.dis/.c
# (ADSPRealCheck.java).
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
BIN=$(readlink -f "$1"); OUT=$(readlink -m "$2")
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/adsp-real.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
loader=()
if [[ $(head -c 4 "$BIN" | od -An -tx1 | tr -d ' ') != 7f454c46 ]]; then
	loader=(-loader BinaryLoader -processor ADSP218x:BE:16:default)
fi
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$BIN" "${loader[@]}" \
	-scriptPath "$HERE" -postScript ADSPRealCheck.java "$OUT" 60 -deleteProject \
	>"$PROJ/log.txt" 2>&1 || { tail -40 "$PROJ/log.txt" >&2; exit 1; }
grep -E "ADSP-218x VisualDSP|ERROR" "$PROJ/log.txt" | head -5 || true
cat "$OUT.summary" | grep -v "^bookmark"
