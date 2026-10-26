#!/usr/bin/env python3
"""Compare the instructions auto-analysis created (ADSPRealCheck .dis file) with MAME
unidasm -arch adsp21xx at the same addresses:  real_compare.py <prefix.dis>
Uses the normalisation and difference buckets of test/compare.py."""
import os
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import compare  # noqa: E402

rows = []
for line in open(sys.argv[1]):
    addr, word, text = line.rstrip("\n").split(" ", 2)
    rows.append((int(addr, 16), int(word, 16), text))
with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
    f.write(b"".join(struct.pack("<I", w) for _, w, _ in rows))
    name = f.name
out = subprocess.run(["unidasm", name, "-arch", "adsp21xx"], capture_output=True, text=True).stdout
os.unlink(name)
mame = [l.split(":", 1)[1].strip() for l in out.splitlines()]
same = 0
buckets = {}
for (addr, w, gt), ml in zip(rows, mame):
    mt = ml.split("  ", 1)[1] if "  " in ml else ""
    mn, gn = compare.norm_mame(mt), compare.norm_ghidra(gt)
    if mn == gn:
        same += 1
        continue
    b = compare.explain(w, mt, gt, mn, gn)
    buckets.setdefault(b, []).append(f"{addr:04x} {w:06x} mame {mt!r} ghidra {gt!r}")
print(f"{sys.argv[1]}: {len(rows)} instructions, {same} identical to MAME")
bad = 0
for b, l in buckets.items():
    print(f"  {len(l):5d}  {b}")
    for e in l[:5]:
        print("         " + e)
    bad += len(l) if b.startswith("UNEXPLAINED") else 0
sys.exit(1 if bad else 0)
