#!/usr/bin/env bash
# Decode differential against GNU objdump -m sh4al-dsp, both byte orders:
#   every 16-bit word; every B field under 8 A fields; every A field under 10 B fields; 50,000
#   random 32-bit words.  Exits non-zero on any difference that no class in decode-explained.txt
#   covers.
#   test/run-decode.sh <workdir>
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
W=$(readlink -m "$1"); mkdir -p "$W"
OBJDUMP=${OBJDUMP:-$HOME/.cache/ghidra-rare-scratch/tools/x-sh-elf/bin/sh-elf-objdump}
rc=0
for e in BE:big:EB LE:little:EL; do
	IFS=: read -r E end eo <<<"$e"
	for k in w16 bfield afield random; do
		slot=8; [[ $k == w16 ]] && slot=4
		le=""; [[ $E == LE ]] && le="--le"
		python3 -I "$HERE/gen_corpus.py" $k "$W/$k.$E.bin" $end
		"$OBJDUMP" -D -b binary -m sh4al-dsp -$eo "$W/$k.$E.bin" >"$W/$k.$E.od.txt"
		"$ROOT/tools/ghidra-dis.sh" "SH4ALDSP:$E:32:default" "$W/$k.$E.bin" 2 "$W/$k.$E.gh.txt"
		echo "== $k $E"
		python3 -I "$HERE/compare.py" "$W/$k.$E.gh.txt" "$W/$k.$E.od.txt" "$HERE/decode-explained.txt" --slot $slot $le \
			>"$W/$k.$E.cmp.txt" || rc=1
		awk '/^  [A-Za-z]/{print; n=0; next} /^slots/{print} /^      /{if (n++ < 1) print}' "$W/$k.$E.cmp.txt" | head -40
	done
done
exit $rc
