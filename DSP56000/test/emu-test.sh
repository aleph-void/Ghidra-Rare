#!/usr/bin/env bash
# P-code emulation test: test/emu-test.sh <lang-id> <cases.txt> [outfile]
# Exit status 0 only if every case passes.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
LANG_ID=$1; CASES=$(readlink -f "$2"); OUT=$(readlink -m "${3:-${TMPDIR:-/tmp}/dsp56k-emu.txt}")
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/dsp56k-emu.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
head -c 12288 /dev/zero > "$PROJ/zero.bin"
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$PROJ/zero.bin" \
	-loader BinaryLoader -processor "$LANG_ID" -noanalysis -scriptPath "$HERE" \
	-postScript DspEmuTest.java "$CASES" "$OUT" -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
[[ -s $OUT ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -20 >&2; exit 1; }
grep -v ^PASS "$OUT"
grep -q " 0 failed" "$OUT"
