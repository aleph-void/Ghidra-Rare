#!/usr/bin/env python3
"""Decode differential: Ghidra (tools/DumpDisasm.java output) vs tc32-elf-objdump -D.

  compare.py <objdump.txt> <ghidra.txt> <stride> [--show N]

Both dumps cover the same raw corpus, one test slot every <stride> bytes; only the instruction
that starts each slot is compared. Text is compared twice:
  exact    - identical after removing whitespace and objdump's trailing comments
             ("; 0xfc", "; (0x2c)", "<sym>") and writing every number in hex;
  semantic - additionally ignoring the explained spelling classes listed in EXPLAINED.
Differences are bucketed; every bucket must be in EXPLAINED or the script exits non-zero.
"""
import re
import sys
from collections import Counter, defaultdict

OBJ = re.compile(r'^\s*([0-9a-f]+):\t([0-9a-f ]+?)\s*\t(.*)$')
GH = re.compile(r'^([0-9a-f]+) ([0-9a-f]*) (.*)$')


def num(m):
    s = m.group(0)
    v = int(s, 16) if s.lower().startswith(("0x", "-0x")) else int(s)
    return hex(v & 0xffffffff) if v >= 0 else "-" + hex(-v)


def norm(t):
    t = re.split(r'\s;|\t;', t)[0]
    t = re.sub(r'<[^>]*>', '', t)
    t = re.sub(r'\s+', '', t)
    t = re.sub(r'-?(0x[0-9a-fA-F]+|\d+)', num, t)
    return t


def load_obj(path, stride):
    out = {}
    for line in open(path):
        m = OBJ.match(line)
        if not m:
            continue
        a = int(m.group(1), 16)
        if a % stride:
            continue
        t = m.group(3).strip()
        out[a] = None if t.startswith(("undefined", ".word", ".short", ".byte")) else t
    return out


def load_gh(path, stride):
    out = {}
    for line in open(path):
        m = GH.match(line.rstrip("\n"))
        if not m:
            continue
        a = int(m.group(1), 16)
        if a % stride:
            continue
        t = m.group(3)
        out[a] = None if t.startswith("BAD") else t
    return out


# Explained classes: name -> predicate(objdump_text, ghidra_text, halfword)
def tjlex(o, g, w):
    # 0x90xx prefix + 0xCxxx/0xExxx suffix: objdump prints the ARMv5 BLX-immediate pair as
    # "tjlex". TC32 has no second instruction state, gas does not accept "tjlex", and the
    # Telink compiler never emits it; Ghidra leaves it undecoded.
    return g is None and o is not None and o.startswith("tjlex")


EXPLAINED = {"objdump tjlex (BLX pair, no TC32 state switch)": tjlex}


def main():
    a = sys.argv[1:]
    show = 0
    if "--show" in a:
        i = a.index("--show"); show = int(a[i + 1]); del a[i:i + 2]
    stride = int(a[2], 0)
    o, g = load_obj(a[0], stride), load_gh(a[1], stride)
    keys = sorted(set(o) & set(g))
    c = Counter()
    buckets = defaultdict(list)
    for k in keys:
        ot, gt = o[k], g[k]
        if ot is None and gt is None:
            c["both invalid"] += 1
        elif ot is not None and gt is not None and norm(ot) == norm(gt):
            c["exact"] += 1
        else:
            for name, pred in EXPLAINED.items():
                if pred(ot, gt, k):
                    c["explained"] += 1
                    buckets[name].append((k, ot, gt))
                    break
            else:
                c["unexplained"] += 1
                key = ((ot or "INVALID").split()[0], (gt or "INVALID").split()[0])
                buckets["UNEXPLAINED %s / %s" % key].append((k, ot, gt))
    print("== %d slots: %d exact, %d both invalid, %d explained, %d unexplained" % (
        len(keys), c["exact"], c["both invalid"], c["explained"], c["unexplained"]))
    for name, items in sorted(buckets.items(), key=lambda x: -len(x[1])):
        print("  %6d  %s" % (len(items), name))
        for k, ot, gt in items[:show]:
            print("          %08x  objdump: %s  |  ghidra: %s" % (k, ot, gt))
    sys.exit(1 if c["unexplained"] else 0)


if __name__ == "__main__":
    main()
