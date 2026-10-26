#!/usr/bin/env bash
# RX module test suite:  test/run-tests.sh [--real <workdir>] [<decode workdir>]
#   1. the generator reproduces data/languages/rx_tokens.sinc and rx_gen.sinc
#   2. the three languages compile with this install's SLEIGH compiler
#   3. emulator cases pass in each language (and a deliberately broken expectation is reported)
#   4. every SLEIGH constructor is reached (each language)
#   5. decode differential vs GNU objdump -m rx / rx:v2 / rx:v3 (0 unexplained differences)
#   6. with --real: build the real-code test binaries (test/real/fetch-and-build.sh) and check
#      each one (ELF import, language choice, analysis, decompiler, objdump comparison)
# GHIDRA_INSTALL_DIR must point at Ghidra with this module installed or linked
# (tools/link-modules.sh), lib/RX.jar built (test/build-jar.sh or gradle buildExtension).
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
REAL=
if [[ ${1:-} == --real ]]; then REAL=$(readlink -m "$2"); shift 2; fi
W=$(readlink -m "${1:-${TMPDIR:-/tmp}/rx-tests}")
mkdir -p "$W"
fail=0
step() { echo; echo "== $*"; }

step "generator"
python3 "$MOD/tools/gen_rx.py" tokens > "$W/rx_tokens.sinc"
python3 "$MOD/tools/gen_rx.py" > "$W/rx_gen.sinc"
for f in rx_tokens.sinc rx_gen.sinc; do
	cmp -s "$W/$f" "$MOD/data/languages/$f" && echo "$f up to date" \
		|| { echo "$f differs from the generator output"; fail=1; }
done

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
for lang in RX:LE:32:RXv1 RX:LE:32:RXv2 RX:LE:32:RXv3; do
	"$HERE/every-entry.sh" "$lang" "$W/every-${lang##*:}.txt" - | tail -1
	grep -q " 0 not reached" "$W/every-${lang##*:}.txt" || fail=1
done

step "decode differential vs GNU objdump"
"$HERE/run-decode.sh" "$W/decode" 65536 1 || fail=1
grep -h "^==" "$W"/decode/*.cmp

if [[ -n $REAL ]]; then
	step "real code"
	"$HERE/real/fetch-and-build.sh" "$REAL" >/dev/null
	for f in "$REAL"/bin/*.elf "$REAL"/bin/obj/*.o; do
		echo "-- $(basename "$f")"
		"$HERE/real-check.sh" "$f" "$REAL/out" | grep -E "^(language|functions|decompile|==|relocatable)" \
			|| fail=1
		grep -q "decompile: .* 0 failed, 0 timeouts" "$REAL/out/$(basename "${f%.elf}").summary" || fail=1
	done
fi

echo
((fail)) && echo "FAILED" || echo "all tests passed"
exit $fail
