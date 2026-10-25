#!/usr/bin/env python3
"""Compare Ghidra 65816 decodes with MAME's g65816 disassembler, record by record.

  compare.py <ghidra.txt> <mame.txt> [--label L] [--show N]

Both files have one line per record: "<addr-hex> <bytes-hex> <text>".
exact    : identical length and identical normalized text
semantic : same length and same operands after alias folding (see ALIASES/QUIRKS below)
Differences are bucketed by opcode byte and difference class.
"""
import argparse
import collections
import re

ap = argparse.ArgumentParser()
ap.add_argument("ghidra")
ap.add_argument("mame")
ap.add_argument("--label", default="")
ap.add_argument("--show", type=int, default=3)
a = ap.parse_args()


def load(path):
    recs = {}
    for line in open(path):
        p = line.rstrip("\n").split(" ", 2)
        if len(p) < 2 or not re.fullmatch(r"[0-9a-f]{6}", p[0]):
            continue
        recs[int(p[0], 16)] = (p[1], p[2] if len(p) > 2 else "")
    return recs


from g65816norm import norm_ghidra, norm_mame, semantic  # noqa: E402


G, M = load(a.ghidra), load(a.mame)
n = exact = sem = 0
buckets = collections.defaultdict(list)
for addr in sorted(M):
    if addr not in G:
        continue
    n += 1
    gb, gt = G[addr]
    mb, mt = M[addr]
    op = int(mb[:2], 16)
    gn = norm_ghidra(gt)
    mn = norm_mame(mt, mb)
    if gt.startswith("BAD"):
        buckets[("ghidra-undecoded", "%02x" % op)].append((addr, mb, gt, mt))
        continue
    if gb != mb:
        buckets[("length", "%02x" % op)].append((addr, mb, gb + " " + gt, mt))
        continue
    if gn == mn:
        exact += 1
        sem += 1
    elif semantic(gn, mn, op, addr):
        sem += 1
        buckets[("alias", "%02x" % op)].append((addr, mb, gt, mt))
    else:
        buckets[("text", "%02x" % op)].append((addr, mb, gt, mt))

print(f"{a.label}: {n} records, exact {exact} ({100*exact/max(n,1):.2f}%), "
      f"semantic {sem} ({100*sem/max(n,1):.2f}%)")
bycls = collections.Counter()
for (cls, op), v in buckets.items():
    bycls[cls] += len(v)
for cls, c in bycls.most_common():
    print(f"  {cls}: {c}")
for (cls, op), v in sorted(buckets.items(), key=lambda kv: (kv[0][0] == "alias", -len(kv[1]))):
    if cls == "alias" and a.show < 1000:
        print(f"  [{cls} op={op}] {len(v)}  e.g. {v[0][2]!r} vs {v[0][3]!r}")
        continue
    print(f"  [{cls} op={op}] {len(v)}")
    for addr, b, gt, mt in v[: a.show]:
        print(f"      {addr:06x} {b:10s} ghidra={gt!r} mame={mt!r}")
