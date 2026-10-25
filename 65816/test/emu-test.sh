#!/usr/bin/env bash
# Run the p-code emulation test (test/emu/emu_cases.txt).   test/emu-test.sh [out.txt]
# If CA65/LD65 are set, emu.bin and emu.lbl are rebuilt from emu.s first.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$(readlink -m "${1:-${TMPDIR:-/tmp}/65816-emu.txt}")
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/65816-emu.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
if [[ -n ${CA65:-} && -n ${LD65:-} ]]; then
	"$CA65" -g -o "$PROJ/emu.o" "$HERE/emu/emu.s"
	"$LD65" -C "$HERE/emu/raw8000.cfg" -Ln "$HERE/emu/emu.lbl" -o "$HERE/emu/emu.bin" "$PROJ/emu.o"
fi
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$HERE/emu/emu.bin" \
	-loader BinaryLoader -loader-baseAddr 0x8000 -processor 65816:LE:16:default -noanalysis \
	-scriptPath "$HERE" -postScript G65816EmuTest.java "$HERE/emu/emu_cases.txt" "$HERE/emu/emu.lbl" "$OUT" \
	-deleteProject >"$PROJ/log.txt" 2>&1 || { tail -40 "$PROJ/log.txt" >&2; exit 1; }
cat "$OUT"
grep -q " 0 failed" "$OUT"
