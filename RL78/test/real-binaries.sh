#!/usr/bin/env bash
# Real-binary check: import each ELF built by fetch-real-samples.sh into headless Ghidra with NO
# -processor flag (the ELF opinion picks the language), auto-analyze, decompile every function
# (RealCheck.java) and compare the disassembly of every instruction Ghidra found with
# rl78-elf-objdump -d at the same addresses (real_compare.py).
#
#   test/real-binaries.sh <samples-dir> [workdir]
# Environment: GHIDRA_INSTALL_DIR (Ghidra with this module installed or symlinked into
# Ghidra/Processors), RL78_OBJDUMP (default rl78-elf-objdump), DECOMP_TIMEOUT (default 60).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
OD=${RL78_OBJDUMP:-rl78-elf-objdump}
TMO=${DECOMP_TIMEOUT:-60}
SAMPLES=$(readlink -f "$1")
W=$(readlink -f "${2:-real-out}")
mkdir -p "$W"
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/rl78-real.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT

run_one() {
	local f=$1 n p
	n=$(basename "$f")
	p=$(mktemp -d "$PROJ/p.XXXXXX")
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$p" p -import "$f" -scriptPath "$HERE" \
		-postScript RealCheck.java "$W/$n.sum" "$W/$n.lst" "$W/$n.c" "$TMO" \
		-deleteProject >"$W/$n.log" 2>&1 || tail -20 "$W/$n.log" >&2
	rm -rf "$p"
}

mapfile -t files < <(find "$SAMPLES" -maxdepth 1 -name '*.elf' | sort)
echo "== headless import + analysis + decompile (${#files[@]} files, 4 at a time)"
i=0
for f in "${files[@]}"; do
	run_one "$f" &
	i=$((i + 1))
	(( i % 4 == 0 )) && wait
done
wait

echo "== results"
for f in "${files[@]}"; do
	n=$(basename "$f")
	"$OD" -d -z "$f" >"$W/$n.od"
	echo "-- $n"
	grep -E "^(language|functions|instructions|bad-instruction|error bookmarks|decompile|functions whose)" "$W/$n.sum" | sed 's/^/   /'
	echo "   vs objdump: $(python3 "$HERE/real_compare.py" "$W/$n.lst" "$W/$n.od" 10 | tee "$W/$n.cmp" | head -1)"
done
echo "(full outputs: $W/<file>.{sum,lst,c,cmp})"
