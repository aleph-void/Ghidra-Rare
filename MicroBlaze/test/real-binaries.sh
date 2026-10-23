#!/usr/bin/env bash
# Real-world binary check: import each sample into headless Ghidra with NO -processor flag
# (the ELF opinion must pick the language), auto-analyze, decompile every function
# (RealCheck.java), and diff Ghidra's disassembly of every instruction it found against the
# reference objdump at the same addresses (compare.py).
#
#   test/fetch-real-samples.sh [samples]          # download the pinned public samples once
#   test/real-binaries.sh [samples] [workdir]
#
# Environment (defaults point at the Ghidra-Rare scratch tool builds, as in run-tests.sh):
#   MB_GHIDRA   Ghidra 12.1.4 to test with; the module is symlinked into its Ghidra/Processors
#               and the Java part (relocation handler, ELF extension) is compiled with javac
#               into <module>/lib/MicroBlaze.jar.
#   XOBJDUMP    reference objdump (default: AMD/Xilinx binutils 2.42 build, see
#               build-xlnx-binutils.sh); OBJDUMP (binutils 2.45) is used as a second opinion.
#   DECOMP_TIMEOUT  per-function decompiler timeout in seconds (default 60; 0 skips decompiling)
#   XBU, XLD    AMD/Xilinx binutils build dirs (gas, ld) for the relocation-handler check: the
#               test/elf/mbtest.s object is imported (Ghidra applies its relocations) and must
#               equal the same object linked by ld at the addresses Ghidra chose.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
S=${S:-/tmp/claude-1000/-home-nick-Documents-git-Ghidra-Rare/738fc310-bd10-40da-87e5-b0a8be585382/scratchpad}
export GHIDRA_INSTALL_DIR=${MB_GHIDRA:-$S/tools/ghidra}
OBJDUMP=${OBJDUMP:-$S/tools/bu/build/binutils/objdump}
XOBJDUMP=${XOBJDUMP:-$S/work/microblaze/xlnx/build/binutils/objdump}
XBU=${XBU:-$S/work/microblaze/xlnx/build}
XLD=${XLD:-$S/work/microblaze/xlnx/build-ld}
TMO=${DECOMP_TIMEOUT:-60}
SAMPLES=$(readlink -f "${1:-real-samples}")
W=${2:-$S/work/microblaze/real}
mkdir -p "$W"

echo "== compiling SLEIGH and the relocation handler"
"$GHIDRA_INSTALL_DIR/support/sleigh" -a "$MOD/data/languages" 2>&1 | grep -E "ERROR|successfully" || true
P="$GHIDRA_INSTALL_DIR/Ghidra/Processors/MicroBlaze"
if [[ ! -e $P ]]; then ln -s "$MOD" "$P"; elif [[ $(readlink -f "$P") != "$MOD" ]]; then
	echo "warning: $P exists and is not this module" >&2; fi
# Compile the Java part straight into <module>/lib/MicroBlaze.jar (only that jar is written).
CLS=$W/classes
rm -rf "$CLS" && mkdir -p "$CLS" "$MOD/lib"
CP=$(find "$GHIDRA_INSTALL_DIR/Ghidra/Framework" "$GHIDRA_INSTALL_DIR/Ghidra/Features" \
	-path '*/lib/*.jar' ! -name '*-src.zip' | tr '\n' ':')
javac -nowarn --release 21 -cp "$CP" -d "$CLS" $(find "$MOD/src/main/java" -name '*.java')
jar cf "$MOD/lib/MicroBlaze.jar" -C "$CLS" .

run_one() { # file
	local f=$1 n p
	n=$(basename "$f")
	p=$(mktemp -d "$W/proj.XXXXXX")
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$p" p -import "$f" -scriptPath "$HERE" \
		-postScript RealCheck.java "$W/$n.sum" "$W/$n.lst" "$W/$n.c" "$TMO" \
		-deleteProject >"$W/$n.log" 2>&1 || { tail -20 "$W/$n.log" >&2; }
	rm -rf "$p"
}

files=("$SAMPLES"/zcu102-zynqmp_pmufw.elf "$SAMPLES"/vck190-versal_psmfw.elf
	"$SAMPLES"/vck190-versal_plmfw.elf "$SAMPLES"/libc.so.6)
echo "== headless import + analysis + decompile (${#files[@]} files, in parallel)"
for f in "${files[@]}"; do run_one "$f" & done
wait

echo "== results"
for f in "${files[@]}"; do
	n=$(basename "$f")
	# ELF class/endianness and type straight from the header
	read -r bits e etype < <(python3 -I - "$f" <<'EOF'
import sys
h = open(sys.argv[1], 'rb').read(18)
e = 'le' if h[5] == 1 else 'be'
t = int.from_bytes(h[16:18], 'little' if e == 'le' else 'big')
print(32 if h[4] == 1 else 64, e, t)
EOF
)
	# Ghidra rebases a shared object (link base 0) to its image base
	delta=0
	[[ $etype == 3 ]] && delta=$(sed -n 's/^image base: //p' "$W/$n.sum")
	"$XOBJDUMP" -d "$f" >"$W/$n.xod"
	"$OBJDUMP" -d "$f" >"$W/$n.od" 2>/dev/null || true
	echo "-- $n (ELF$bits $e, e_type $etype)"
	grep -E "^(language|functions|instructions|fallthrough|bad-instruction|error bookmarks|relocations|decompile|functions whose)" "$W/$n.sum" | sed 's/^/   /'
	echo "   vs Xilinx objdump: $(python3 "$HERE/compare.py" "$bits" "$e" "$W/$n.lst" "$W/$n.xod" 10 "$delta" | tee "$W/$n.cmpx" | head -2 | tr '\n' ';')"
	echo "   vs binutils 2.45:  $(python3 "$HERE/compare.py" "$bits" "$e" "$W/$n.lst" "$W/$n.od" 10 "$delta" | tee "$W/$n.cmp" | sed -n 2,3p | tr '\n' ';')"
done

echo "== relocation handler: relocatable objects vs ld"
if [[ -x $XBU/gas/as-new && -x $XLD/ld/ld-new ]]; then
	for e in be le; do
		m=elf32microblaze ef=-mbig-endian
		[[ $e == le ]] && m=elf32microblazeel ef=-mlittle-endian
		o=$W/mbtest_$e.o
		"$XBU/gas/as-new" $ef "$HERE/elf/mbtest.s" -o "$o"
		TMO=0 run_one "$o"
		# link at the section addresses Ghidra used
		args=()
		for b in $(sed -n 's/^blocks: //p' "$W/mbtest_$e.o.sum"); do
			args+=("--section-start=${b%@*}=0x${b#*@}")
		done
		"$XLD/ld/ld-new" -m $m -e _start "${args[@]}" "$o" -o "$W/mbtest_$e.ld.elf"
		"$XBU/binutils/objdump" -d "$W/mbtest_$e.ld.elf" >"$W/mbtest_$e.ld.od"
		echo "-- mbtest_$e.o: $(grep '^relocations' "$W/mbtest_$e.o.sum");" \
			"$(python3 "$HERE/rawcmp.py" $e "$W/mbtest_$e.o.lst" "$W/mbtest_$e.ld.od" | tail -1)"
	done
else
	echo "   (skipped: no Xilinx gas/ld at $XBU / $XLD)"
fi
echo "(full outputs: $W/<file>.{sum,lst,c,cmp,cmpx})"
