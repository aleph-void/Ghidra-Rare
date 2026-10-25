#!/usr/bin/env python3
"""Compare Ghidra's listing of a real binary (RealCheck.java: "<addr> <bytes> <text>") with
`rl78-elf-objdump -d` at the same addresses, normalized as in compare.py.

  real_compare.py <ghidra.lst> <objdump-d.txt> [examples]
"""
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, __import__("os").path.dirname(__file__))
from compare import exact_norm, sem_norm  # noqa: E402

ODLINE = re.compile(r"^\s*([0-9a-f]+):\t([0-9a-f ]+?)\s*\t(.*)$")


def od_fix(t):
    t = re.sub(r"\s*<[^>]*>", "", t)
    # objdump -d prints branch targets and !addr operands as bare hex
    t = re.sub(r"(\$!|\$|!!|!)([0-9a-f]+)(?![0-9a-fx\w])", lambda m: m.group(1) + "0x" + m.group(2), t)
    t = re.sub(r"^(callt\s+\[)([0-9a-f]+)\]", lambda m: m.group(1) + "0x" + m.group(2) + "]", t)
    return t


def main():
    g = {}
    for line in open(sys.argv[1]):
        p = line.rstrip("\n").split(" ", 2)
        g[int(p[0], 16)] = (p[1], p[2] if len(p) > 2 else "")
    o = {}
    for line in open(sys.argv[2]):
        m = ODLINE.match(line)
        if m:
            o[int(m.group(1), 16)] = (m.group(2).replace(" ", ""), od_fix(m.group(3)))
    nex = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    cnt = Counter()
    cls = defaultdict(list)
    for a in sorted(g):
        gb, gt = g[a]
        cnt["ghidra"] += 1
        if a not in o:
            cnt["no_objdump_insn"] += 1
            cls["objdump has no instruction here"].append((a, gt, ""))
            continue
        ob, ot = o[a]
        if gb != ob:
            cnt["bytes_differ"] += 1
            cls["length/bytes differ"].append((a, gt + " [" + gb + "]", ot + " [" + ob + "]"))
            continue
        if exact_norm(gt) == exact_norm(ot):
            cnt["exact"] += 1
            cnt["semantic"] += 1
        elif sem_norm(gt) == sem_norm(ot):
            cnt["semantic"] += 1
        else:
            cls["DIFF " + ot.split(" ")[0]].append((a, gt, ot))
    n = cnt["ghidra"] or 1
    print("ghidra instructions %d: same bytes as objdump %d, exact %d (%.2f%%), semantic %d (%.2f%%), "
          "no objdump instruction %d, different length %d"
          % (cnt["ghidra"], cnt["ghidra"] - cnt["no_objdump_insn"] - cnt["bytes_differ"], cnt["exact"],
             100.0 * cnt["exact"] / n, cnt["semantic"], 100.0 * cnt["semantic"] / n,
             cnt["no_objdump_insn"], cnt["bytes_differ"]))
    for k in sorted(cls, key=lambda k: -len(cls[k])):
        print("  [%d] %s" % (len(cls[k]), k))
        for a, gt, ot in cls[k][:nex]:
            print("      %05x  ghidra: %-36s objdump: %s" % (a, gt, ot))


if __name__ == "__main__":
    main()
