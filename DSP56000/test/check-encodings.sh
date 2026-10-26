#!/usr/bin/env bash
# Confirm the hand encodings of the DSP56000 emulator cases with the asl assembler (Alfred
# Arnold's AS, run as a black box): test/check-encodings.sh <asl-binary> <workdir>
# Each case's assembler text (cases.py --asm) is assembled at P:$100 and the words compared.
# DSP56002-only instructions (asl targets the 56000) are reported as skipped.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ASL=$1; W=$(readlink -m "$2"); mkdir -p "$W"
python3 "$HERE/emu/cases.py" --asm | python3 -c '
import re, subprocess, sys
asl, w = sys.argv[1], sys.argv[2]
bad = ok = skip = 0
for line in sys.stdin:
    name, asm, words = line.rstrip("\n").split("\t")
    src = ["\tcpu 56000", "\torg $100"]
    for part in [p.strip() for p in asm.split(" / ")]:
        m = re.match(r"^(\w+):\s*(.*)$", part)
        if m:
            src.append("%s:" % m.group(1))
            part = m.group(2)
        if part:
            src.append("\t" + part)
    open("%s/c.asm" % w, "w").write("\n".join(src) + "\n")
    r = subprocess.run([asl, "-L", "-q", "c.asm"], cwd=w, capture_output=True, text=True)
    if "not supported on 56000" in r.stdout + r.stderr:
        skip += 1; print("SKIP %s (DSP56002 instruction)" % name); continue
    got = []
    for l in open("%s/c.lst" % w, errors="replace"):
        m = re.match(r"\s+\d+/\s+[0-9A-F]+ : ((?:[0-9A-F]{6} ?)+)", l)
        if m: got += [x.lower() for x in m.group(1).split()]
    want = words.split()
    if got[:len(want)] != want and got != want:
        bad += 1; print("MISMATCH %s: asl %s, case %s" % (name, " ".join(got), words))
    else:
        ok += 1
print("encodings: %d agree with asl, %d differ, %d skipped" % (ok, bad, skip))
sys.exit(1 if bad else 0)
' "$ASL" "$W"
