#!/usr/bin/env bash
# XA module test suite:  test/run-tests.sh [--real <workdir>] [<decode workdir>]
#   1. the generator reproduces data/languages/xa_gen.sinc
#   2. both languages compile with this install's SLEIGH compiler
#   3. emulator cases pass (and a deliberately broken expectation is reported)
#   4. every SLEIGH constructor is reached (both DS context modes, both languages)
#   5. decode differential vs MAME on the slot corpora (0 unexplained differences)
#   6. with --real: build the asxa examples and run the real-code checks (analysis, listing,
#      MAME and assembler-source comparisons)
# GHIDRA_INSTALL_DIR must point at Ghidra with this module installed or linked
# (tools/link-modules.sh), lib/XA.jar built (test/build-jar.sh or gradle buildExtension).
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
REAL=
if [[ ${1:-} == --real ]]; then REAL=$(readlink -m "$2"); shift 2; fi
W=$(readlink -m "${1:-${TMPDIR:-/tmp}/xa-tests}")
mkdir -p "$W"
fail=0
step() { echo; echo "== $*"; }

step "generator"
python3 "$MOD/tools/gen_xa.py" > "$W/xa_gen.sinc"
cmp -s "$W/xa_gen.sinc" "$MOD/data/languages/xa_gen.sinc" && echo "xa_gen.sinc up to date" \
	|| { echo "xa_gen.sinc differs from the generator output"; fail=1; }

step "SLEIGH compile"
for s in "$MOD"/data/languages/*.slaspec; do
	"$GHIDRA_INSTALL_DIR/support/sleigh" "$s" 2>&1 | grep -E "^(ERROR|Error)" && fail=1
	echo "$(basename "$s" .slaspec).sla $(stat -c %s "${s%.slaspec}.sla") bytes"
done

step "emulator"
python3 "$HERE/emu/cases.py" > "$W/cases.txt"
cmp -s "$W/cases.txt" "$HERE/emu/cases.txt" || { echo "emu/cases.txt is stale"; fail=1; }
"$HERE/emu-test.sh" "$HERE/emu/cases.txt" "$W/emu" || fail=1
python3 "$HERE/emu/cases.py" --broken > "$W/broken.txt"
if "$HERE/emu-test.sh" "$W/broken.txt" "$W/emu-broken" >/dev/null 2>&1; then
	echo "a broken expectation was NOT reported"; fail=1
else
	echo "broken expectation reported as a failure (expected)"
fi

step "every entry"
for lang in XA:LE:24:default XA:LE:24:page0; do
	"$HERE/every-entry.sh" "$lang" "$W/every-${lang##*:}.txt" - dsk=0 | tail -1
	grep -q " 0 not reached" "$W/every-${lang##*:}.txt" || fail=1
done

step "decode differential vs MAME"
"$HERE/run-decode.sh" "$W/decode" 65536 1 || fail=1

if [[ -n $REAL ]]; then
	step "real code (asxa examples)"
	"$HERE/real/fetch-and-build.sh" "$REAL" >/dev/null
	B=$REAL/bin E=$REAL/src/asxa-1.12/examples O=$REAL/out
	"$HERE/real-check.sh" --linear --equ "$E/xa-s3.equ" "$B/test.hex" "$B/test.lst" "$O" || fail=1
	for spec in "monxa XA:LE:24:default xa-s3" "monxa_p0 XA:LE:24:page0 xa-s3" \
		"monitor_rom XA:LE:24:page0 xa-s3" "timer_int_rom XA:LE:24:default xa-g49" \
		"uart_int_rom XA:LE:24:default xa-s3" "keybrd XA:LE:24:default xa-s3"; do
		set -- $spec
		ent=(); [[ $1 == keybrd ]] && ent=(--entry 0xb000)
		for mode in "" --seed; do
			echo "-- $1 ${mode:-analysis}"
			"$HERE/real-check.sh" $mode "${ent[@]}" --equ "$E/$3.equ" --equ "$E/monitor.equ" \
				"$B/$1.hex" "$B/$1.lst" "$O" "$2" || fail=1
		done
	done
fi

echo
((fail)) && echo "FAILED" || echo "all tests passed"
exit $fail
