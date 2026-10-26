#!/usr/bin/env bash
# Full TMS320C2x/C5x test suite.
#   GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC test/run-tests.sh <workdir> [nrandom]
# Needs MAME's unidasm, python3, a C compiler and make (to build c5xasm), and the Macroassembler
# AS (asl) on PATH or in ASL_DIR for the C2x round trip. Large intermediates go to <workdir>.
#  1. decode differential vs MAME unidasm, both families, plus the other byte order (run-decode.sh)
#  2. every-entry: every SLEIGH constructor reached under the context settings below
#  3. round trip: Ghidra's text re-assembled by c5xasm (C5x) and AS (C2x) gives the same words
#  4. emulator: hand-computed p-code results, including one deliberately broken expectation
#  5. real programs (fetch-inputs.sh + real-test.sh)
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "$1"); NR=${2:-32768}
mkdir -p "$W"
rc=0
step() { echo; echo "== $*"; }
step "fetch inputs"
"$HERE/fetch-inputs.sh" "$W/inputs"
step "decode differential vs MAME"
"$HERE/run-decode.sh" "$W/decode" "$NR" 1 || rc=1
step "every-entry"
# every combination of the context-tracked modes (unknown / each known value), plus the repeat,
# block-repeat and ARP/DP-known variants; each setting lists every field so none carries over
ctxs() { # family
	python3 - "$1" <<'PY'
import itertools, sys
c5 = sys.argv[1] == "c5x"
out = []
modes = lambda name, vals: [f"{name}_k=0,{name}_v=0"] + [f"{name}_k=1,{name}_v={v}" for v in vals]
for i, (s, o, p) in enumerate(itertools.product(modes("sxm", (0, 1)), modes("ovm", (0, 1)),
                                                 modes("pm", (0, 1, 2, 3)))):
    rep = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (0, 0, 1), (1, 0, 1)][i % 6]
    k = i % 2
    c = f"{s},{o},{p},arp_k={k},dp_k={k},rpt={rep[0]}"
    if c5:
        c += f",rbe1={rep[1]},rbe2={rep[2]},ndx={k},trm={k},circ={(i // 2) % 2}"
    out.append(c)
print(" ".join(out))
PY
}
"$HERE/every-entry.sh" TMS320C2x:BE:16:default "$W/decode/c2x/chunks" "$W/decode/c2x/ee.txt" $(ctxs c2x) || rc=1
grep -q ' 0 not reached' "$W/decode/c2x/ee.txt" || { grep 'NOT REACHED' "$W/decode/c2x/ee.txt" | head; rc=1; }
"$HERE/every-entry.sh" TMS320C5x:LE:16:default "$W/decode/c5x/chunks" "$W/decode/c5x/ee.txt" $(ctxs c5x) || rc=1
grep -q ' 0 not reached' "$W/decode/c5x/ee.txt" || { grep 'NOT REACHED' "$W/decode/c5x/ee.txt" | head; rc=1; }
step "round trip through independent assemblers"
python3 "$HERE/roundtrip.py" c5x "$W/inputs/c5xtools/tools/c5xasm/c5xasm" "$W/decode/c5x/records.txt" \
	"$W/decode/c5x/g" "$W/decode/c5x/rt" | head -8 || rc=1
ASL_DIR=${ASL_DIR:-$(dirname "$(command -v asl 2>/dev/null || echo /nonexistent/asl)")}
if [[ -x $ASL_DIR/asl ]]; then
	python3 "$HERE/roundtrip.py" c2x "$ASL_DIR" "$W/decode/c2x/records.txt" "$W/decode/c2x/g" \
		"$W/decode/c2x/rt" | head -4 || rc=1
else
	echo "asl not found (set ASL_DIR): C2x round trip skipped"
fi
step "emulator"
"$HERE/emu-test.sh" "$W/emu" || rc=1
step "real programs"
"$HERE/real-test.sh" "$W/inputs" "$W/real" || rc=1
echo
[[ $rc == 0 ]] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $rc
