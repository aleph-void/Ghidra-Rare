#!/usr/bin/env bash
# DSP56000 module test suite:  test/run-tests.sh [--real <workdir>] [<decode workdir>]
#   1. the generators reproduce dsp56000_gen.sinc and dsp56156_gen.sinc
#   2. both languages compile with this install's SLEIGH compiler
#   3. emulator cases pass for both languages, and a deliberately broken expectation is
#      reported; with asl available (ASL=...), the DSP56000 case encodings agree with asl
#   4. every SLEIGH constructor is reached (every-entry images, with and without the DO
#      loop-end context)
#   5. decode differential vs MAME unidasm -arch dsp56000 / dsp56156 (0 unexplained)
#   6. with --real: Motorola's freely distributed DSP56000 programs (shipped LOD files and
#      sources assembled with Motorola's ASM56000) and the DSP56100 manual's benchmark
#      programs assembled with ASM56100: listing-guided disassembly vs the assembler source,
#      MAME at the same addresses, auto-analysis and decompilation
# GHIDRA_INSTALL_DIR must point at Ghidra with this module installed or linked
# (tools/link-modules.sh), lib/DSP56000.jar built (test/build-jar.sh or gradle buildExtension).
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
REAL=
if [[ ${1:-} == --real ]]; then REAL=$(readlink -m "$2"); shift 2; fi
W=$(readlink -m "${1:-${TMPDIR:-/tmp}/dsp56000-tests}")
mkdir -p "$W"
fail=0
step() { echo; echo "== $*"; }

step "generators"
for g in dsp56000 dsp56156; do
	python3 "$MOD/tools/gen_$g.py" > "$W/${g}_gen.sinc"
	cmp -s "$W/${g}_gen.sinc" "$MOD/data/languages/${g}_gen.sinc" && echo "${g}_gen.sinc up to date" \
		|| { echo "${g}_gen.sinc differs from the generator output"; fail=1; }
done

step "SLEIGH compile"
for s in "$MOD"/data/languages/*.slaspec; do
	"$GHIDRA_INSTALL_DIR/support/sleigh" "$s" 2>&1 | grep -E "^(ERROR|Error)" && fail=1
	echo "$(basename "$s" .slaspec).sla $(stat -c %s "${s%.slaspec}.sla") bytes"
done

step "emulator"
for spec in "cases DSP56000:BE:16:default" "cases156 DSP56000:BE:16:DSP56156"; do
	set -- $spec
	python3 "$HERE/emu/$1.py" > "$W/$1.txt"
	cmp -s "$W/$1.txt" "$HERE/emu/$1.txt" || { echo "emu/$1.txt is stale"; fail=1; }
	"$HERE/emu-test.sh" "$2" "$HERE/emu/$1.txt" "$W/emu-$1.txt" || fail=1
	tail -1 "$W/emu-$1.txt"
	python3 "$HERE/emu/$1.py" --broken > "$W/$1-broken.txt"
	if "$HERE/emu-test.sh" "$2" "$W/$1-broken.txt" "$W/emu-$1-broken.txt" >/dev/null 2>&1; then
		echo "$1: a broken expectation was NOT reported"; fail=1
	else
		echo "$1: broken expectation reported as a failure (expected)"
	fi
done
if [[ -n ${ASL:-} ]]; then
	"$HERE/check-encodings.sh" "$ASL" "$W/enc" | tail -1 || fail=1
fi

step "decode differential vs MAME"
"$HERE/run-decode.sh" "$W/decode" 65536 1 || fail=1

step "every entry"
"$HERE/every-entry.sh" DSP56000:BE:16:default 2 "$W/every-56000.txt" \
	"-/lend=1,laddr=0x10,lstart=0x5" $(cat "$W/decode/56000/list.txt") | tail -1 || fail=1
mkdir -p "$W/every156"
"$HERE/every-entry.sh" DSP56000:BE:16:DSP56156 2 "$W/every-56156.txt" "-/lend=1,laddr=0x10,lstart=0x5" \
	$(python3 "$HERE/gen_corpus156.py" --every "$W/every156/every.bin") | tail -1 || fail=1

if [[ -n $REAL ]]; then
	step "real code: DSP56000 (Motorola BBS programs)"
	"$HERE/real/run-real.sh" "$REAL/56000" || fail=1
	step "real code: DSP56156 (DSP56100 manual benchmarks)"
	"$HERE/real/bench156.sh" "$REAL/56156" || fail=1
fi

echo
((fail)) && echo "FAILED" || echo "all tests passed"
exit $fail
