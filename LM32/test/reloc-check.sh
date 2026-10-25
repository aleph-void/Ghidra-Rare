#!/usr/bin/env bash
# ELF relocation handler check: import each relocatable object (Ghidra applies its relocations
# at addresses it chooses), link the same object with GNU ld at those addresses (undefined
# symbols at Ghidra's EXTERNAL addresses) and compare every loaded byte.
#   test/reloc-check.sh <ld|--no-ld> <objdump> <workdir> <object.o>...
# With --no-ld the objects are only imported (memory dump in <workdir>/<object>.mem).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
LD=$1 OD=$2 W=$(readlink -f "$3")
shift 3
mkdir -p "$W"
for o in "$@"; do
	n=$(basename "$o")
	p=$(mktemp -d "${TMPDIR:-/tmp}/lm32-rel.XXXXXX")
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$p" p -import "$(readlink -f "$o")" -scriptPath "$HERE" \
		-postScript RealCheck.java "$W/$n.sum" "$W/$n.lst" "$W/$n.c" 0 \
		-postScript DumpMem.java "$W/$n.mem" -deleteProject >"$W/$n.log" 2>&1 || tail -20 "$W/$n.log"
	rm -rf "$p"
	if [[ $LD == --no-ld ]]; then
		echo "-- $n: $(grep '^relocations' "$W/$n.sum") (imported only)"
		continue
	fi
	args=()
	for b in $(sed -n 's/^blocks: //p' "$W/$n.sum"); do
		[[ ${b%@*} == EXTERNAL ]] || args+=("--section-start=${b%@*}=0x${b#*@}")
	done
	for s in $(sed -n 's/^external symbols: //p' "$W/$n.sum"); do
		args+=("--defsym=${s%@*}=0x${s#*@}")
	done
	"$LD" -e _start --no-warn-rwx-segments "${args[@]}" "$o" -o "$W/$n.ld.elf"
	"$OD" -s "$W/$n.ld.elf" >"$W/$n.ld.s"
	echo "-- $n: $(grep '^relocations' "$W/$n.sum"); $(python3 "$HERE/rawcmp.py" "$W/$n.mem" "$W/$n.ld.s" | tail -1)"
done
