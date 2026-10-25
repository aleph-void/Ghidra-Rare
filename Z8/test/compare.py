#!/usr/bin/env python3
"""Compare Ghidra's Z8 disassembly with MAME unidasm (-arch z8).

    compare.py <mame.txt> <ghidra.txt> [label]

Text is normalised (case, spaces, MAME "3Ch"/Ghidra "0x3c" numbers). Differences that are
explained are counted separately:
  oracle-d7     MAME prints D7 (LD x(r2),r1, a store) as a load with the nibbles swapped;
                UM0016 and libasm agree on the store (manual example "D7 A0 F0 = LD F0h(R0),R10")
  manual-only   4F WDh, 5F WDT, 6F STOP, 7F HALT: Z86C0x/Z86E0x CMOS opcodes from UM0016
                that MAME's Z8601-era decoder reports as Illegal
"""
import re
import sys
from collections import Counter, defaultdict

MAME_RE = re.compile(r"^([0-9a-f]+): ((?:[0-9a-f]{2} )+)\s*(.*)$")


def norm_num(m):
    return "0X%X" % int(m.group(1), 16)


def norm_mame(t):
    t = t.upper()
    t = re.sub(r"(?<![A-Z0-9])([0-9A-F]+)H(?![A-Z0-9])", norm_num, t)
    return re.sub(r"\s+", "", t)


def norm_ghidra(t):
    t = t.upper()
    t = re.sub(r"0X([0-9A-F]+)", norm_num, t)
    return re.sub(r"\s+", "", t)


def load_mame(path):
    d = {}
    for line in open(path):
        m = MAME_RE.match(line.rstrip("\n"))
        if m:
            d[int(m.group(1), 16)] = (m.group(2).replace(" ", ""), m.group(3).strip())
    return d


def load_ghidra(path):
    d = {}
    for line in open(path):
        a, b, t = (line.rstrip("\n").split(" ", 2) + ["", ""])[:3]
        d[int(a, 16)] = (b, t)
    return d


def classify(by, mt, gt):
    op = int(by[:2], 16)
    if mt == "ILLEGAL" and gt == "BAD":
        return "both-illegal"
    if op in (0x4f, 0x5f, 0x6f, 0x7f) and mt == "ILLEGAL":
        return "manual-only"
    if op == 0xd7:
        m = re.match(r"LD(R\d+),(0X[0-9A-F]+)\((R\d+)\)$", mt)
        if m and gt == f"LD{m.group(2)}({m.group(1)}),{m.group(3)}":
            return "oracle-d7"
    return None


def main():
    mame = load_mame(sys.argv[1])
    ghid = load_ghidra(sys.argv[2])
    label = sys.argv[3] if len(sys.argv) > 3 else sys.argv[2]
    stats = Counter()
    bad = defaultdict(list)
    for a in sorted(mame):
        mb, mtext = mame[a]
        if a not in ghid:
            stats["missing"] += 1
            bad["missing"].append(f"{a:04x} {mb} {mtext}")
            continue
        gb, gtext = ghid[a]
        mt, gt = norm_mame(mtext), norm_ghidra(gtext)
        if mt == "ILLEGAL":
            mb = mb[:2]
        if mt == gt and mb == gb:
            stats["exact"] += 1
            continue
        c = classify(mb, mt, gt)
        if c:
            stats[c] += 1
            if len(bad[c]) < 3:
                bad[c].append(f"{a:04x} {mb}: mame '{mtext}' ghidra '{gtext}'")
            continue
        k = f"op {mb[:2]}"
        stats["mismatch"] += 1
        bad[k].append(f"{a:04x} {mb}/{gb}: mame '{mtext}' ghidra '{gtext}'")
    n = sum(stats.values())
    ok = stats["exact"] + stats["both-illegal"]
    expl = stats["oracle-d7"] + stats["manual-only"]
    print(f"{label}: {n} instructions, {ok} agree ({100.0 * ok / max(n, 1):.2f}%), "
          f"{expl} explained (oracle-d7 {stats['oracle-d7']}, manual-only "
          f"{stats['manual-only']}), {stats['mismatch'] + stats['missing']} unexplained")
    for k, v in sorted(bad.items(), key=lambda kv: -len(kv[1])):
        if k.startswith("op") or k == "missing":
            print(f"  {k}: {len(v)}")
            for s in v[:4]:
                print("     ", s)
    return 0 if stats["mismatch"] + stats["missing"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
