#!/usr/bin/env bash
# DWARF and calling-convention check: builds test/elf/dwarf.c with the sh-elf gcc (-m4al -g -O1,
# as -isa=sh4al-dsp) in both byte orders, imports each (auto-detected, DWARF applied) and checks
# the language the ELF opinion picks, the recovered prototypes and the parameter storage.
# (After aleph-void/ghidra-sh test/dwarf-check.sh, MIT.)
#   SH_TOOLS=<sh-elf bin dir> test/dwarf-check.sh <workdir>
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "$1"); mkdir -p "$W"
CC=${SH_TOOLS:-$HOME/.cache/ghidra-rare-scratch/tools/x-sh-elf/bin}/sh-elf-gcc
rc=0
expect() { grep -qF -- "$2" "$W/$1.protos.txt" || { echo "MISSING ($1): $2"; rc=1; }; }
for v in "be -mb" "le -ml"; do
	set -- $v
	n=$1; shift
	"$CC" -m4al "$@" -Wa,-isa=sh4al-dsp -g -O1 -nostdlib -nostartfiles -Wl,-e,__start -static \
		-o "$W/dwarf_$n.elf" "$HERE/elf/dwarf.c" -lgcc
	"$HERE/ghidra-elf.sh" "$W/dwarf_$n.elf" DwarfCheck.java "$W/$n.protos.txt" 2>/dev/null
	"$HERE/ghidra-elf.sh" "$W/dwarf_$n.elf" LangId.java "$W/$n.lang.txt" 2>/dev/null
	echo "== $n: $(cat "$W/$n.lang.txt")"; cat "$W/$n.protos.txt"
	want="SH4ALDSP:${n^^}:32:default"
	grep -q "^language: $want " "$W/$n.lang.txt" || { echo "WRONG LANGUAGE (want $want)"; rc=1; }
	expect $n "int add3(int a, int b, int c) | a@R4:4 | b@R5:4 | c@R6:4"
	expect $n "int sum(int * p, int n) | p@R4:4 | n@R5:4"
	expect $n "int field(pt * p) | p@R4:4"
	expect $n "int many(int a, int b, int c, int d, int e, int f) | a@R4:4 | b@R5:4 | c@R6:4 | d@R7:4 | e@Stack[0x0]:4 | f@Stack[0x4]:4"
	expect $n "float fmuladd(float a, float b) | a@R4:4 | b@R5:4"
done
# the opinion keys on EF_SH4AL_DSP only: the same code flagged SH4A-nofpu (e_flags 0x11) or
# SH-4 must stay with Ghidra's SuperH4 (or whichever module claims those flags)
for isa in sh4a-nofpu sh4-nofpu; do
	"$CC" -m4al -mb -Wa,-isa=$isa -g -O1 -nostdlib -nostartfiles -Wl,-e,__start -static \
		-o "$W/dwarf_$isa.elf" "$HERE/elf/dwarf.c" -lgcc
	"$HERE/ghidra-elf.sh" "$W/dwarf_$isa.elf" LangId.java "$W/$isa.lang.txt" 2>/dev/null
	echo "== $isa: $(cat "$W/$isa.lang.txt")"
	grep -q "^language: SH4ALDSP" "$W/$isa.lang.txt" && { echo "OPINION CLAIMS $isa"; rc=1; }
done
exit $rc
