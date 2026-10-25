#!/usr/bin/env python3
"""Compare Ghidra slot disassembly (DumpSlots.java) with GNU objdump slot disassembly (slotdis).

  compare.py <ghidra.txt> <objdump.txt> [examples-per-class]

Both files have one line per slot: "<offset-hex> <length> <text>"; length 0 means rejected.

  exact:    same length and same text after lower-casing, removing blanks and writing every
            number as hex (objdump prints decimal below 1000, Ghidra hex)
  semantic: additionally, memory-mapped register names are replaced by their addresses (Ghidra
            names saddr/sfr operands that hit a register, e.g. 0xffef1 is RB1_A), addresses are
            taken modulo 2^20 (objdump prints negative branch targets as 64-bit values and keeps
            the unused top nibble of !!addr20), "+0]" is dropped and ei/di are set1/clr1 psw.7.
"""
import re
import sys
from collections import Counter, defaultdict

NUM = re.compile(r"(?<![\w])(0x[0-9a-f]+|\d+)(?![\w])")

# memory-mapped registers (RL78: register banks at FFEE0-FFEFF, CPU registers at FFFF8-FFFFF)
R8 = ["x", "a", "c", "b", "e", "d", "l", "h"]
RP = ["ax", "bc", "de", "hl"]
REGADDR = {}
for bank, base in [(0, 0xFFEF8), (1, 0xFFEF0), (2, 0xFFEE8), (3, 0xFFEE0)]:
    pre = "" if bank == 0 else "rb%d_" % bank
    for i, n in enumerate(R8):
        REGADDR[pre + n] = base + i
    for i, n in enumerate(RP):
        REGADDR[pre + n] = base + 2 * i
    REGADDR[pre + "bcax"] = base
    REGADDR[pre + "hlde"] = base + 4
REGADDR.update({"sp": 0xFFFF8, "spl": 0xFFFF8, "sph": 0xFFFF9, "psw": 0xFFFFA, "cs": 0xFFFFC,
                "es": 0xFFFFD, "pmc": 0xFFFFE, "mem": 0xFFFFF,
                "macr": 0xFFFF0, "macrl": 0xFFFF0, "macrh": 0xFFFF2})
REGRE = re.compile(r"(?<![\w$])(%s)(?![\w:])" % "|".join(sorted(REGADDR, key=len, reverse=True)))


def load(path):
    d = {}
    for line in open(path):
        p = line.rstrip("\n").split(" ", 2)
        if len(p) < 2:
            continue
        d[int(p[0], 16)] = (int(p[1]), p[2] if len(p) > 2 else "")
    return d


def canon_num(m):
    return hex(int(m.group(1), 0))


def exact_norm(t):
    t = t.lower().replace("\t", " ").strip()
    m, _, ops = t.partition(" ")
    t = m + " " + ops.replace(" ", "")
    return NUM.sub(canon_num, t)


def sem_norm(t):
    t = exact_norm(t).strip()
    t = re.sub(r"^ei$", "set1 psw.0x7", t)
    t = re.sub(r"^di$", "clr1 psw.0x7", t)
    t = NUM.sub(lambda m: hex(int(m.group(1), 0) & 0xFFFFF), t)
    t = t.replace("+0x0]", "]")
    # "divwu <old-encoding>" (objdump's text for the CE FB 04 alias)
    t = t.replace("<old-encoding>", "").strip()
    t = REGRE.sub(lambda m: hex(REGADDR[m.group(1)]), t)
    # ror/rol/rorc/rolc/rolwc print the implicit count
    return t


def mnem(t):
    return t.split(" ")[0].lower() if t else "-"


def main():
    g = load(sys.argv[1])
    o = load(sys.argv[2])
    nex = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    cnt = Counter()
    classes = defaultdict(list)
    for off in sorted(o):
        gl, gt = g.get(off, (0, "BAD"))
        ol, ot = o[off]
        gbad = gl == 0
        obad = ol == 0 or ot.startswith("(bad)") or ot.startswith(".byte") or "*unknown*" in ot
        cnt["total"] += 1
        if gbad and obad:
            cnt["both_reject"] += 1
            continue
        if gbad:
            cnt["ref_only"] += 1
            classes["ref only: " + mnem(ot)].append((off, gt, ot, ol))
            continue
        if obad:
            cnt["ghidra_only"] += 1
            classes["ghidra only: " + mnem(gt)].append((off, gt, ot, gl))
            continue
        cnt["both_decode"] += 1
        if gl == ol and exact_norm(gt) == exact_norm(ot):
            cnt["exact"] += 1
            cnt["semantic"] += 1
        elif gl == ol and sem_norm(gt) == sem_norm(ot):
            cnt["semantic"] += 1
            classes["~ " + mnem(ot)].append((off, gt, ot, gl))
        else:
            key = ("LEN " if gl != ol else "DIFF ") + mnem(ot) + " / " + mnem(gt)
            classes[key].append((off, gt, ot, "%d/%d" % (gl, ol)))
    bd = cnt["both_decode"] or 1
    print("compared %d slots: both decode %d, exact %d (%.2f%%), semantic %d (%.2f%%), "
          "ghidra-only %d, ref-only %d, both reject %d"
          % (cnt["total"], cnt["both_decode"], cnt["exact"], 100.0 * cnt["exact"] / bd,
             cnt["semantic"], 100.0 * cnt["semantic"] / bd, cnt["ghidra_only"], cnt["ref_only"],
             cnt["both_reject"]))
    for k in sorted(classes, key=lambda k: (k.startswith("~"), -len(classes[k]))):
        v = classes[k]
        print("  [%d] %s" % (len(v), k))
        for off, gt, ot, ln in v[:nex]:
            print("      %08x len %s  ghidra: %-34s objdump: %s" % (off, ln, gt, ot))


if __name__ == "__main__":
    main()
