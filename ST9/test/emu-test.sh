#!/usr/bin/env bash
# Hand-computed p-code checks for ST9 and ST9+.
#   GHIDRA_INSTALL_DIR=... test/emu-test.sh [outdir]
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
OUTD=$(readlink -m "${1:-${TMPDIR:-/tmp}/st9-emu}")
mkdir -p "$OUTD"
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/st9-emu.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
head -c 8192 /dev/zero > "$PROJ/zero.bin"
for lang in ST9:BE:16:default ST9:BE:24:ST9+; do
	out="$OUTD/${lang##*:}.txt"
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p \
		-import "$PROJ/zero.bin" -loader BinaryLoader -processor "$lang" -noanalysis \
		-scriptPath "$HERE" -postScript ST9EmuTest.java "$HERE/emu/cases.txt" "$out" \
		-deleteProject >"$PROJ/log.txt" 2>&1 \
		|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
	[[ -s $out ]] || { grep -E 'ERROR|Exception' "$PROJ/log.txt" | head -20 >&2; exit 1; }
	grep -v '^PASS' "$out"
	grep -q ' 0 failed' "$out"
done
