#!/usr/bin/env bash
# ADSP-218x module test suite:  test/run-tests.sh [--real <dir>] [<workdir>]
#   1. the generator reproduces data/languages/adsp218x_gen.sinc
#   2. the language compiles with this install's SLEIGH compiler
#   3. emulator cases pass (and a deliberately broken expectation is reported)
#   4. every SLEIGH constructor is reached
#   5. decode differential vs MAME on all 16,777,216 instruction words (0 unexplained)
#   6. with --real: fetch the freely licensed ADSP-2181 programs (test/real/fetch.sh), import
#      them with the DXE loader and auto-analysis, compare with MAME and with their sources
# GHIDRA_INSTALL_DIR must point at Ghidra with this module installed or linked
# (tools/link-modules.sh in the repository root), lib/ADSP218x.jar built (test/build-jar.sh or
# gradle buildExtension).  MAME's unidasm must be on PATH.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
REAL=
if [[ ${1:-} == --real ]]; then REAL=$(readlink -m "$2"); shift 2; fi
W=$(readlink -m "${1:-${TMPDIR:-/tmp}/adsp218x-tests}")
mkdir -p "$W"
fail=0
step() { echo; echo "== $*"; }

step "generator"
python3 "$MOD/tools/gen_adsp218x.py" > "$W/adsp218x_gen.sinc"
cmp -s "$W/adsp218x_gen.sinc" "$MOD/data/languages/adsp218x_gen.sinc" && echo "adsp218x_gen.sinc up to date" \
	|| { echo "adsp218x_gen.sinc differs from the generator output"; fail=1; }

step "SLEIGH compile"
for s in "$MOD"/data/languages/*.slaspec; do
	"$GHIDRA_INSTALL_DIR/support/sleigh" "$s" 2>&1 | grep -E "^(ERROR|Error)" && fail=1
	echo "$(basename "$s" .slaspec).sla $(stat -c %s "${s%.slaspec}.sla") bytes"
done

step "emulator"
python3 "$HERE/emu/cases.py" > "$W/cases.txt"
cmp -s "$W/cases.txt" "$HERE/emu/cases.txt" || { echo "emu/cases.txt is stale"; fail=1; }
"$HERE/emu-test.sh" "$HERE/emu/cases.txt" "$W/emu.txt" || fail=1
python3 "$HERE/emu/cases.py" --broken > "$W/broken.txt"
if "$HERE/emu-test.sh" "$W/broken.txt" "$W/emu-broken.txt" >/dev/null 2>&1; then
	echo "a broken expectation was NOT reported"; fail=1
else
	echo "broken expectation reported as a failure (expected)"
fi

step "every entry"
"$HERE/every-entry.sh" "$W/every.txt" | tail -1
grep -q " 0 not reached" "$W/every.txt" || fail=1

step "decode differential vs MAME (exhaustive)"
"$HERE/run-decode.sh" "$W/decode" --exhaustive || fail=1

if [[ -n $REAL ]]; then
	step "real code (MIT-licensed ADSP-2181 programs)"
	"$HERE/real/fetch.sh" "$REAL" >/dev/null
	for p in meter pftest; do
		echo "-- $p"
		"$HERE/real-check.sh" "$REAL/$p.dxe" "$W/$p" | grep -E "^(functions|instructions|decompile|bookmarks)" || fail=1
		grep -q "0 failed, 0 timeouts" "$W/$p.summary" || fail=1
		python3 "$HERE/real/real_compare.py" "$W/$p.dis" || fail=1
		python3 "$HERE/real/src_compare.py" "$REAL/$p.dxe" "$REAL/$p.asm" "$REAL/def2181.h" "$W/$p.dis" || fail=1
	done
fi

echo
((fail)) && echo "FAILED" || echo "all tests passed"
exit $fail
