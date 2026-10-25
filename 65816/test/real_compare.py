#!/usr/bin/env python3
"""Compare Ghidra's analysed listing of a real 65816 binary with MAME.

  real_compare.py <ghidra.lst> <mame65816dis> [--trace mame-trace.log] [--label L]

decode : every instruction Ghidra disassembled is re-decoded by MAME's g65816 disassembler with
         Ghidra's M/X for that address; same length and text (after alias folding) = agree.
trace  : every distinct PC in a MAME execution trace (debugger "trace" command; MAME prints
         each instruction with the real M/X flags) is looked up in Ghidra's listing. Reports how
         many executed instructions Ghidra disassembled and how many it decoded identically
         (same length and text = same M/X context).
"""
import argparse
import collections
import os
import re
import subprocess
import tempfile

from g65816norm import norm_ghidra, norm_mame, semantic

ap = argparse.ArgumentParser()
ap.add_argument("lst")
ap.add_argument("dis")
ap.add_argument("--trace")
ap.add_argument("--label", default="")
ap.add_argument("--show", type=int, default=3)
a = ap.parse_args()

G = {}
for line in open(a.lst):
    p = line.rstrip("\n").split(" ", 5)
    if len(p) == 6:
        G[int(p[0], 16)] = (int(p[1]), int(p[2]), int(p[3]), p[4], p[5])

with tempfile.TemporaryDirectory() as td:
    lf = os.path.join(td, "l.txt")
    with open(lf, "w") as f:
        for addr, (m, x, e, b, t) in sorted(G.items()):
            f.write("%x %d %d %s\n" % (addr, m, x, b))
    out = subprocess.run([a.dis, "-list", lf], capture_output=True, text=True).stdout
M = {}
for line in out.splitlines():
    p = line.split(" ", 2)
    M[int(p[0], 16)] = (p[1], p[2] if len(p) > 2 else "")

agree = 0
diff = collections.defaultdict(list)
for addr, (m, x, e, b, t) in sorted(G.items()):
    mb, mt = M[addr]
    gn, mn = norm_ghidra(t), norm_mame(mt, mb)
    op = int(b[:2], 16)
    if mb == b and (gn == mn or semantic(gn, mn, op, addr)):
        agree += 1
    else:
        diff[b[:2]].append((addr, b, t, mt))
print(f"{a.label} decode: {len(G)} Ghidra instructions, MAME agrees on {agree} "
      f"({100 * agree / max(len(G), 1):.2f}%)")
for op, v in sorted(diff.items(), key=lambda kv: -len(kv[1])):
    print(f"  [op={op}] {len(v)}")
    for addr, b, t, mt in v[: a.show]:
        print(f"      {addr:06x} {b} ghidra={t!r} mame={mt!r}")

if a.trace:
    T = {}
    for line in open(a.trace, errors="replace"):
        m = re.match(r"([0-9A-F]{2}):([0-9A-F]{4}): (.*)$", line.strip())
        if m:
            T[int(m.group(1), 16) << 16 | int(m.group(2), 16)] = m.group(3)
    starts = sorted(G)
    import bisect
    same = 0
    cls = collections.Counter()
    ex = collections.defaultdict(list)
    for pc, mt in sorted(T.items()):
        if pc in G:
            m, x, e, b, t = G[pc]
            gn, mn = norm_ghidra(t), norm_mame(mt, "")
            op = int(b[:2], 16)
            if gn == mn or semantic(gn, mn, op, pc):
                same += 1
                continue
            k = "decoded differently"
        else:
            i = bisect.bisect_right(starts, pc) - 1
            if i >= 0 and starts[i] < pc < starts[i] + len(G[starts[i]][3]) // 2:
                k = "inside another Ghidra instruction"
            else:
                k = "not disassembled"
        cls[k] += 1
        ex[k].append((pc, mt, G.get(pc)))
    cov = len(T) - cls["not disassembled"] - cls["inside another Ghidra instruction"]
    print(f"{a.label} trace: {len(T)} executed PCs; Ghidra disassembled {cov} "
          f"({100 * cov / max(len(T), 1):.2f}%), decoded {same} of those identically "
          f"({100 * same / max(cov, 1):.2f}%)")
    for k, c in cls.most_common():
        print(f"  {k}: {c}")
        for pc, mt, g in ex[k][: a.show]:
            print(f"      {pc:06x} mame={mt!r} ghidra={g[4] if g else None!r}"
                  + (f" (M{g[0]} X{g[1]} E{g[2]})" if g else ""))
