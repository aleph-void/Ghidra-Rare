#!/usr/bin/env bash
# i860 module test suite:  test/run-tests.sh [--real <workdir>] [<test workdir>]
#   1. the generator reproduces data/languages/i860_gen.sinc
#   2. both languages compile with this install's SLEIGH compiler
#   3. emulator cases pass on both languages (and a deliberately broken expectation is reported)
#   4. decode differential vs MAME on the word corpora (0 unexplained differences)
#   5. every SLEIGH constructor is reached (both languages, all dual-mode contexts)
#   6. with --real <workdir> (toolchain from test/real/build-toolchain.sh; programs are fetched
#      and built if missing): the assembler-enumerated corpus vs its source and MAME, the ELF
#      relocation check vs GNU ld, the hand-written pipeline/dual-mode kernels in the emulator,
#      and the real-code checks of the GCC-built programs (analysis, objdump/MAME agreement,
#      decompilation).
# GHIDRA_INSTALL_DIR must point at Ghidra with this module installed or linked
# (tools/link-modules.sh), lib/i860.jar built (test/build-jar.sh or gradle buildExtension).
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
REAL=
if [[ ${1:-} == --real ]]; then REAL=$(readlink -m "$2"); shift 2; fi
W=$(readlink -m "${1:-${TMPDIR:-/tmp}/i860-tests}")
mkdir -p "$W"
fail=0
step() { echo; echo "== $*"; }

step "generator"
python3 "$MOD/tools/gen_i860.py" > "$W/i860_gen.sinc"
cmp -s "$W/i860_gen.sinc" "$MOD/data/languages/i860_gen.sinc" && echo "i860_gen.sinc up to date" \
	|| { echo "i860_gen.sinc differs from the generator output"; fail=1; }

step "SLEIGH compile"
for s in "$MOD"/data/languages/*.slaspec; do
	"$GHIDRA_INSTALL_DIR/support/sleigh" "$s" 2>&1 | grep -E "^(ERROR|Error)" && fail=1
	echo "$(basename "$s" .slaspec).sla $(stat -c %s "${s%.slaspec}.sla") bytes"
done

step "emulator"
(cd "$HERE/emu" && python3 cases.py) > "$W/cases.txt"
cmp -s "$W/cases.txt" "$HERE/emu/cases.txt" || { echo "emu/cases.txt is stale"; fail=1; }
"$HERE/emu-test.sh" "$HERE/emu/cases.txt" "$W/emu" || fail=1
(cd "$HERE/emu" && python3 cases.py --broken) > "$W/broken.txt"
if "$HERE/emu-test.sh" "$W/broken.txt" "$W/emu-broken" >/dev/null 2>&1; then
	echo "a broken expectation was NOT reported"; fail=1
else
	echo "broken expectation reported as a failure (expected)"
fi

BU=
[[ -n $REAL ]] && BU=$REAL/tc/inst/bin
step "decode differential vs MAME${BU:+ (and the assembler corpus)}"
"$HERE/run-decode.sh" "$W/decode" $BU || fail=1

step "every entry"
for v in XR XP; do
	imgs=("$W/decode/low.bin" "$W/decode/regs.bin")
	[[ -n $BU ]] && imgs+=("$W/decode/asm.bin")
	"$HERE/every-entry.sh" "i860:LE:32:$v" "$W/every-$v.txt" "${imgs[@]}"
	grep -q " 0 not reached" "$W/every-$v.txt" || fail=1
done

if [[ -n $REAL ]]; then
	step "ELF relocations vs GNU ld"
	"$HERE/reloc-check.sh" "$BU" "$W/reloc" || fail=1
	step "pipeline / dual-mode kernels (assembled), emulated"
	"$HERE/real/kernel-emu.sh" "$BU" "$W/kernels" || fail=1
	step "real code (GCC 4.0.4: zlib 1.3.1, Embench-IoT 1.0)"
	[[ -d $REAL/real/src/zlib-1.3.1 ]] || "$HERE/real/fetch-sources.sh" "$REAL" >/dev/null
	ls "$REAL"/real/bin/*.elf >/dev/null 2>&1 || "$HERE/real/build-programs.sh" "$REAL" >/dev/null
	"$HERE/real/run-real.sh" "$REAL" | tail -1 || fail=1
fi

echo
((fail)) && echo "FAILED" || echo "all tests passed"
exit $fail
