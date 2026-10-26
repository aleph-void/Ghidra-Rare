#!/usr/bin/env bash
# P-code emulation test: test/emu-test.sh [cases.txt] [outdir]
# Runs every case in test/emu/cases.txt with each RX language.
# Exit status 0 only if every case passes.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
CASES=$(readlink -f "${1:-$HERE/emu/cases.txt}")
OUTD=$(readlink -m "${2:-${TMPDIR:-/tmp}/rx-emu}")
mkdir -p "$OUTD"
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/rx-emu.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
head -c 65536 /dev/zero > "$PROJ/zero.bin"
rc=0
for lang in RX:LE:32:RXv1 RX:LE:32:RXv2 RX:LE:32:RXv3; do
	out="$OUTD/${lang##*:}.txt"
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$PROJ/zero.bin" \
		-loader BinaryLoader -processor "$lang" -noanalysis -scriptPath "$HERE" \
		-postScript RXEmuTest.java "$CASES" "$out" -deleteProject >"$PROJ/log.txt" 2>&1 \
		|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
	[[ -s $out ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -20 >&2; exit 1; }
	grep -v ^PASS "$out"
	grep -q " 0 failed" "$out" || rc=1
done
exit $rc
