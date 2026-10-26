#!/usr/bin/env bash
# Decode differential: test/run-decode.sh <workdir> [binutils-bin-dir]
#  1. the three word corpora (test/gen_corpus.py) decoded by MAME unidasm and by Ghidra in both
#     languages; every difference must be explained by test/compare.py (manual rules and
#     confirmed MAME limitations)
#  2. with a binutils 2.30 i860 bin directory (GNU as, run as a black box): the assembler-
#     enumerated corpus (test/gen_asm.py), which must decode identically to its source on the
#     XP (and on the XR, except for the XP-only forms), and whose MAME differences must be
#     explained too.
# Exit status 0 only if nothing is unexplained.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "$1"); BU=${2:-}
mkdir -p "$W"
rc=0
for k in low regs rand; do
	python3 "$HERE/gen_corpus.py" "$k" "$W/$k.bin" >/dev/null
	unidasm "$W/$k.bin" -arch i860 | awk 'NR % 2 == 1' > "$W/$k.mame.txt"
	for v in XR XP; do
		"$HERE/ghidra-dis.sh" "i860:LE:32:$v" "$W/$k.bin" "$W/$k.$v.txt" 0 8
		xp=; [[ $v == XP ]] && xp=--xp
		echo "-- $k corpus, $v"
		python3 "$HERE/compare.py" "$W/$k.mame.txt" "$W/$k.$v.txt" --explain $xp --show 2 > "$W/$k.$v.cmp.txt" || rc=1
		head -1 "$W/$k.$v.cmp.txt"; tail -1 "$W/$k.$v.cmp.txt"
	done
done
if [[ -n $BU ]]; then
	python3 "$HERE/gen_asm.py" "$W/asm.s" "$W/asm.lst"
	"$BU/i860-stardent-sysv4-as" -mxp "$W/asm.s" -o "$W/asm.o" 2>/dev/null
	"$BU/i860-stardent-sysv4-objcopy" -O binary -j .text "$W/asm.o" "$W/asm.bin"
	unidasm "$W/asm.bin" -arch i860 | awk 'NR % 2 == 1' > "$W/asm.mame.txt"
	for v in XP XR; do
		"$HERE/ghidra-dis.sh" "i860:LE:32:$v" "$W/asm.bin" "$W/asm.$v.txt" 0 8
	done
	echo "-- assembler corpus, XP vs source"
	python3 "$HERE/asm_compare.py" "$W/asm.lst" "$W/asm.XP.txt" | tail -1 || rc=1
	echo "-- assembler corpus, XR vs source (XP-only forms must be rejected)"
	n=$(python3 "$HERE/asm_compare.py" "$W/asm.lst" "$W/asm.XR.txt" --all | grep -c "ghidra: None$" || true)
	m=$(grep -cE "^(ldio|stio|ldint|scyc|pfld\.q)|%(bear|ccr|p[0-3])\b" "$W/asm.lst" || true)
	echo "$n rejected, $m XP-only forms"; [[ $n == "$m" ]] || rc=1
	echo "-- assembler corpus, XP vs MAME"
	python3 "$HERE/compare.py" "$W/asm.mame.txt" "$W/asm.XP.txt" --explain --xp --show 2 > "$W/asm.cmp.txt" || rc=1
	head -1 "$W/asm.cmp.txt"; tail -1 "$W/asm.cmp.txt"
fi
exit $rc
