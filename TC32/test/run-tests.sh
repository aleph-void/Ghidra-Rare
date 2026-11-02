#!/usr/bin/env bash
# TC32 module test suite:  test/run-tests.sh [--real <workdir>] [<workdir>]
#   1. the generator reproduces data/languages/tc32_lists.sinc
#   2. the language compiles with this install's SLEIGH compiler
#   3. emulator cases pass (and a deliberately broken expectation is reported)
#   4. every SLEIGH constructor is reached
#   5. decode differential vs tc32-elf-objdump (0 unexplained differences); needs TC32_OBJDUMP
#   6. with --real: build and check the real-code binaries (needs the tc32 toolchain)
# GHIDRA_INSTALL_DIR must point at Ghidra with this module installed or linked
# (tools/link-modules.sh) and lib/TC32.jar built (test/build-jar.sh or gradle buildExtension).
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
REAL=
if [[ ${1:-} == --real ]]; then REAL=$(readlink -m "$2"); shift 2; fi
W=$(readlink -m "${1:-${TMPDIR:-/tmp}/tc32-tests}")
mkdir -p "$W"
fail=0
step() { echo; echo "== $*"; }

step "generator"
python3 "$MOD/tools/gen_tc32_lists.py" > "$W/tc32_lists.sinc"
cmp -s "$W/tc32_lists.sinc" "$MOD/data/languages/tc32_lists.sinc" && echo "tc32_lists.sinc up to date" \
	|| { echo "tc32_lists.sinc differs from the generator output"; fail=1; }

step "SLEIGH compile"
for s in "$MOD"/data/languages/*.slaspec; do
	out=$("$GHIDRA_INSTALL_DIR/support/sleigh" "$s" 2>&1) || { echo "$out"; fail=1; }
	echo "$out" | grep -E "^(ERROR|Error)" && fail=1
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
"$HERE/every-entry.sh" "$W/every.txt" | tail -1
grep -q " 0 not reached" "$W/every.txt" || fail=1

step "decode differential vs tc32-elf-objdump"
if [[ -n ${TC32_OBJDUMP:-} ]]; then
	"$HERE/run-decode.sh" "$W/decode" 50000 1 || fail=1
	step "gas round trip (module text -> tc32-elf-as)"
	python3 "$HERE/gas_roundtrip.py" "$W/decode/all16.gh" "$W/decode/all16.bin" "$W/gas" "$(dirname "$TC32_OBJDUMP")" || fail=1
else
	echo "TC32_OBJDUMP not set: skipped"
fi

if [[ -n $REAL ]]; then
	step "real code"
	"$HERE/real-build.sh" "$REAL" || fail=1
fi

echo
((fail)) && echo "FAILED" || echo "all tests passed"
exit $fail
