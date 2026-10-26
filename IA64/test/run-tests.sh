#!/usr/bin/env bash
# IA-64 module test suite:  test/run-tests.sh [--real <workdir>] [<workdir>]
#   1. the generator reproduces data/languages/ia64_gen.sinc, ia64_gen32.sinc, ia64_regs.sinc
#   2. all three languages compile with this install's SLEIGH compiler (.sla < 16 MB)
#   3. emulator cases pass in all three languages (and a deliberately broken expectation fails)
#   4. every SLEIGH constructor is reached (every-entry test)
#   5. decode differential vs GNU objdump: 0 unexplained differences
#   6. with --real: fetch the pinned Debian ia64 packages, analyse them headless and compare the
#      disassembly with objdump (test/real/run-real.sh)
# GHIDRA_INSTALL_DIR must point at Ghidra with this module installed or linked
# (tools/link-modules.sh) and lib/IA64.jar built (test/build-jar.sh or gradle buildExtension).
# The emulator cases are recorded in test/emu/cases.txt; cases.py regenerates them with the
# ia64-linux-gnu assembler (IA64_AS), but only --check (no assembler) runs here.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
REAL=
if [[ ${1:-} == --real ]]; then REAL=$(readlink -m "$2"); shift 2; fi
W=$(readlink -m "${1:-${TMPDIR:-/tmp}/ia64-tests}")
mkdir -p "$W/gen"
fail=0
step() { echo; echo "== $*"; }

step "generator"
python3 "$MOD/tools/gen_ia64.py" "$W/gen"
for f in ia64_gen.sinc ia64_gen32.sinc ia64_regs.sinc; do
	cmp -s "$W/gen/$f" "$MOD/data/languages/$f" && echo "$f up to date" \
		|| { echo "$f differs from the generator output"; fail=1; }
done

step "SLEIGH compile"
for s in "$MOD"/data/languages/*.slaspec; do
	"$GHIDRA_INSTALL_DIR/support/sleigh" "$s" 2>&1 | grep -E "^(ERROR|Error)" && fail=1
	sz=$(stat -c %s "${s%.slaspec}.sla")
	echo "$(basename "$s" .slaspec).sla $sz bytes"
	((sz < 16000000)) || { echo "sla too large"; fail=1; }
done

step "emulator"
python3 "$HERE/emu/cases.py" --check "$HERE/emu/cases.txt" || { echo "emu/cases.txt is stale"; fail=1; }
"$HERE/emu-test.sh" "$HERE/emu/cases.txt" "$W/emu" || fail=1
python3 - "$HERE/emu/cases.txt" > "$W/broken.txt" <<'PY'
import sys
# the first expectation of the first case, plus one
lines = open(sys.argv[1]).read().splitlines()
for i, l in enumerate(lines):
    if l.startswith('expect '):
        k, v = l.split()[1:]
        lines[i] = 'expect %s 0x%x' % (k, (int(v, 0) + 1) & (2**64 - 1))
        break
print('\n'.join(lines))
PY
if "$HERE/emu-test.sh" "$W/broken.txt" "$W/emu-broken" >/dev/null 2>&1; then
	echo "a broken expectation was NOT reported"; fail=1
else
	echo "broken expectation reported as a failure (expected)"
fi

step "every entry"
for lang in IA64:LE:64:default IA64:BE:64:default IA64:BE:32:default; do
	"$HERE/every-entry.sh" "$lang" "$W/every-${lang//:/_}" > "$W/every-${lang//:/_}.txt"
	tail -1 "$W/every-${lang//:/_}.txt"
	grep -q " 0 not reached" "$W/every-${lang//:/_}.txt" || fail=1
done

step "decode differential vs GNU objdump"
"$HERE/run-decode.sh" "$W/decode" 100000 1 || fail=1

if [[ -n $REAL ]]; then
	step "real binaries (Debian 7 ia64)"
	"$HERE/real/run-real.sh" "$REAL" || fail=1
fi

echo
((fail)) && echo "FAILED" || echo "all tests passed"
exit $fail
