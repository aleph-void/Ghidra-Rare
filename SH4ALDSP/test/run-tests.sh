#!/usr/bin/env bash
# SH4AL-DSP module test suite.  Exits non-zero on any failure.
#   GHIDRA_INSTALL_DIR=<ghidra with this module linked under Ghidra/Processors/SH4ALDSP>
#       test/run-tests.sh [--real <workdir>]
# Steps: 1 tools/gen_pops.py reproduces data/languages/sh4aldsp_pops.sinc; 2 both specs compile
# (each .sla under 16 MB); 3 the hand-computed emulator cases pass in both byte orders and a
# deliberately broken expectation is reported; 4 every SLEIGH constructor is reached; 5 decode
# differential against GNU objdump -m sh4al-dsp (every 16-bit word, the 32-bit P-op fields,
# random words, both byte orders) with 0 unexplained differences; 6 DWARF / calling convention /
# ELF opinion (needs the sh-elf gcc); with --real, 7 zlib and Lua built with gcc -m4al (plus a
# DSP routine) in both byte orders and four third-party fx-CG add-ins: import, analysis,
# decompilation, objdump comparison.
# Tools: SH_TOOLS (dir with sh-elf-gcc/as/objdump 2.45 built with the sh target), OBJDUMP.
set -uo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
REAL=""
[[ ${1:-} == --real ]] && REAL=$(readlink -m "${2:?--real needs a workdir}")
export SH_TOOLS=${SH_TOOLS:-$HOME/.cache/ghidra-rare-scratch/tools/x-sh-elf/bin}
export OBJDUMP=${OBJDUMP:-$SH_TOOLS/sh-elf-objdump}
W=$(mktemp -d "${TMPDIR:-/tmp}/sh4al-tests.XXXXXX")
trap 'rm -rf "$W"' EXIT
fail=0
step() { echo; echo "### $*"; }
check() { if "$@"; then echo "ok"; else echo "FAILED: $*"; fail=1; fi; }

step "1 generator reproduces the checked-in P-op table"
python3 -I "$MOD/tools/gen_pops.py" > "$W/pops.sinc"
check cmp "$W/pops.sinc" "$MOD/data/languages/sh4aldsp_pops.sinc"

step "2 SLEIGH compile"
for f in sh4aldsp sh4aldsp_le; do
	"$GHIDRA_INSTALL_DIR/support/sleigh" "$MOD/data/languages/$f.slaspec" "$W/$f.sla" >"$W/$f.log" 2>&1 \
		|| { grep -E "ERROR" "$W/$f.log"; echo "FAILED: $f.slaspec"; fail=1; }
	sz=$(stat -c %s "$W/$f.sla" 2>/dev/null || echo 0)
	echo "$f.sla $sz bytes"
	(( sz > 0 && sz < 16000000 )) || { echo "FAILED: $f.sla size"; fail=1; }
done

step "3 emulator cases"
if [[ -x $SH_TOOLS/sh-elf-as ]]; then
	# the case file is regenerated (GNU as encodes the programs) and must match the checked-in one
	python3 -I "$HERE/emu/cases.py" > "$W/cases.txt"
	check cmp "$W/cases.txt" "$HERE/emu/cases.txt"
fi
check "$HERE/emu-test.sh" "$W/emu"
check "$HERE/emu-test.sh" --broken "$W/emu"

step "4 every constructor reached"
check "$HERE/every-entry.sh" "$W/every"

step "5 decode differential vs objdump"
check "$HERE/run-decode.sh" "$W/dec"

step "6 DWARF / ABI / ELF opinion"
if [[ -x $SH_TOOLS/sh-elf-gcc ]]; then
	check "$HERE/dwarf-check.sh" "$W/dwarf"
else
	echo "skipped: no sh-elf-gcc in $SH_TOOLS"
fi

if [[ -n $REAL ]]; then
	step "7 real code"
	mkdir -p "$REAL"
	check "$HERE/build-samples.sh" "$REAL"
	for f in zlib_be lua_be zlib_le lua_le; do
		E=BE; [[ $f == *le ]] && E=LE
		echo "== $f"
		check "$HERE/real-check.sh" "$REAL/elf/$f.elf" "$REAL/out" "SH4ALDSP:$E:32:default" sh4al-dsp 20
	done
	check "$HERE/fetch-samples.sh" "$REAL"
	for g in racing nesizm BadApple BACG50; do
		echo "== $g.g3a"
		check "$HERE/real-g3a.sh" "$REAL/g3a/$g.g3a" "$REAL/out" 20
	done
fi

echo
if [[ $fail -ne 0 ]]; then echo "FAILED"; exit 1; fi
echo "ALL TESTS PASSED"
