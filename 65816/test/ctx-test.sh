#!/usr/bin/env bash
# Context-tracking test: flow-disassemble test/ctx/ctx.bin from the reset state and check every
# "; expect <insn><8|16>" comment in ctx.s against the decoded immediate width.
#   test/ctx-test.sh [workdir]       (CA65/LD65 set: rebuild ctx.bin from ctx.s first)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=$(mkdir -p "${1:-${TMPDIR:-/tmp}/65816-ctx}" && cd "${1:-${TMPDIR:-/tmp}/65816-ctx}" && pwd)
if [[ -n ${CA65:-} && -n ${LD65:-} ]]; then
	"$CA65" -l "$WORK/ctx.lst" -o "$WORK/ctx.o" "$HERE/ctx/ctx.s"
	"$LD65" -C "$HERE/ctx/raw8000.cfg" -o "$HERE/ctx/ctx.bin" "$WORK/ctx.o"
fi
"$HERE/ghidra-listing.sh" "$HERE/ctx/ctx.bin" "$WORK/ctx.txt" 8000 8000:111
python3 - "$HERE/ctx/ctx.s" "$WORK/ctx.txt" <<'PY'
import re, sys
src, lst = sys.argv[1], sys.argv[2]
exp = [m.groups() for m in re.finditer(r"^\s*(\w+) #\$([0-9a-f]+)\s*; expect (\w+?)(8|16)\b", open(src).read(), re.M)]
got = {}
for l in open(lst):
    p = l.split()   # addr bytes M X E MNEMONIC operand
    if len(p) > 6 and p[6].startswith("#"):
        got.setdefault((p[5].lower(), int(p[6].lstrip("#$").replace("0x", ""), 16)), l.strip())
ok = bad = 0
for mn, imm, emn, width in exp:
    v = int(imm, 16)
    line = got.get((mn, v))
    want = 2 if width == "8" else 3
    if line and len(line.split()[1]) // 2 == want:
        ok += 1
    else:
        bad += 1
        print(f"FAIL {mn} #${imm} expected {width}-bit: {line}")
print(f"context: {ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
PY
