#!/usr/bin/env bash
# P-code emulation test: test/emu-test.sh [cases.txt] [outdir]
# Runs every case in test/emu/cases.txt with both languages (internal and external stack).
# Exit status 0 only if every case passes.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
CASES=$(readlink -f "${1:-$HERE/emu/cases.txt}")
OUTD=$(readlink -m "${2:-${TMPDIR:-/tmp}/z8-emu}")
mkdir -p "$OUTD"
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/z8-emu.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
head -c 8192 /dev/zero > "$PROJ/zero.bin"
rc=0
for lang in Z8:BE:16:default Z8:BE:16:extstack; do
	out="$OUTD/${lang##*:}.txt"
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$PROJ/zero.bin" \
		-loader BinaryLoader -processor "$lang" -noanalysis -scriptPath "$HERE" \
		-postScript Z8EmuTest.java "$CASES" "$out" -deleteProject >"$PROJ/log.txt" 2>&1 \
		|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
	[[ -s $out ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -20 >&2; exit 1; }
	grep -v ^PASS "$out"
	grep -q " 0 failed" "$out" || rc=1
done
exit $rc
