#!/usr/bin/env bash
# Import real OpenRISC binaries headless (no -processor: the ELF opinion picks the language),
# run auto-analysis, decompile every function, and diff every instruction Ghidra found against
# objdump at the same address.
#
#   test/real-binaries.sh [samples-dir] [workdir]        (samples: test/fetch-real-samples.sh)
#
# Environment: GHIDRA_INSTALL_DIR (Ghidra 12.1.x with this module in Ghidra/Processors),
#   OBJDUMP (binutils 2.45 built with or1k), DECOMP_TIMEOUT (seconds per function, default 60)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
OBJDUMP=${OBJDUMP:-objdump}
TMO=${DECOMP_TIMEOUT:-60}
SAMPLES=$(readlink -f "${1:-real-samples}")
W=$(readlink -f "${2:-real-work}")
mkdir -p "$W"
"$HERE/build-jar.sh"

files=()
for n in ldconfig ld-linux-or1k.so.1 libc.so.6 libm.so.6 vmlinux-or1k ${EXTRA_SAMPLES:-}; do
	[[ -s $SAMPLES/$n ]] && files+=("$SAMPLES/$n")
done

run_one() { # file
	local f=$1 n p
	n=$(basename "$f")
	p=$(mktemp -d "${TMPDIR:-/tmp}/or1k-real.XXXXXX")
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$p" p -import "$f" -scriptPath "$HERE" \
		-postScript RealCheck.java "$W/$n.sum" "$W/$n.lst" "$W/$n.c" "$TMO" \
		-deleteProject >"$W/$n.log" 2>&1 || { tail -20 "$W/$n.log" >&2; }
	rm -rf "$p"
}
echo "== headless import + analysis + decompile (${#files[@]} files, in parallel)"
for f in "${files[@]}"; do run_one "$f" & done
wait

echo "== results"
for f in "${files[@]}"; do
	n=$(basename "$f")
	etype=$(python3 -I -c 'import sys; h=open(sys.argv[1],"rb").read(18); print(int.from_bytes(h[16:18], "little" if h[5]==1 else "big"))' "$f")
	delta=0
	# Ghidra rebases a shared object (link base 0) to its image base
	[[ $etype == 3 ]] && delta=$(sed -n 's/^image base: //p' "$W/$n.sum")
	"$OBJDUMP" -d "$f" >"$W/$n.od"
	# objdump -d output -> same per-address form; compare.py reads objdump lines directly
	echo "-- $n (e_type $etype)"
	grep -E "^(language|functions|instructions|fallthrough|bad-instruction|error bookmarks|relocations|decompile|functions whose)" "$W/$n.sum" | sed 's/^/   /'
	python3 "$HERE/compare.py" --listing "$W/$n.lst" "$W/$n.od" 10 --delta=$((-delta)) >"$W/$n.cmp"
	echo "   vs objdump: $(head -1 "$W/$n.cmp")"
done
echo "(full outputs: $W/<file>.{sum,lst,c,cmp,log})"
