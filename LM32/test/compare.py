#!/usr/bin/env python3
"""Compare Ghidra linear-sweep output (DumpDisasm.java) with objdump -D on the same raw image.

  compare.py <ghidra.txt> <objdump.txt> [max-examples-per-class] [--delta N] [--listing]

--delta N   subtract N from objdump addresses (shared objects Ghidra rebased: N = -image base)
--listing   <ghidra.txt> is an analysis listing (RealCheck.java): compare only the addresses
            Ghidra disassembled; objdump words Ghidra did not reach are counted separately

Exact: identical text after whitespace/case normalization.
Semantic: identical after numbers are reduced to their value (hex/decimal, sign) and the
known equivalent spellings below are applied. Words both tools reject count as agreement
("both undefined"); they are reported separately.
"""
import collections
import re
import sys

import argparse
ap = argparse.ArgumentParser()
ap.add_argument("gfile")
ap.add_argument("ofile")
ap.add_argument("maxex", nargs="?", type=int, default=10)
ap.add_argument("--delta", type=lambda x: int(x, 0), default=0)
ap.add_argument("--listing", action="store_true")
a = ap.parse_args()
gfile, ofile, maxex, delta = a.gfile, a.ofile, a.maxex, a.delta


def load_ghidra(p):
    d = {}
    for line in open(p):
        parts = line.rstrip("\n").split(" ", 2)
        if len(parts) < 3:
            continue
        off = int(parts[0], 16)
        # Ghidra marks an instruction in a delay slot with a leading "_"
        text = parts[2].lstrip("_")
        d[off] = (parts[1], None if text.startswith("BAD") else text)
    return d


def load_objdump(p):
    d = {}
    for line in open(p):
        m = re.match(r"\s*([0-9a-f]+):\t((?:[0-9a-f]{2} )+)\s*\t?(.*)$", line)
        if not m:
            continue
        off = int(m.group(1), 16) - delta
        text = m.group(3).strip()
        if text.startswith("*unknown*") or text == "":
            text = None
        else:
            # objdump -d on a linked file prints branch targets as bare hex plus <symbol>
            text = re.sub(r"\s*<[^>]*>", "", text)
            text = re.sub(r"^((?:bi|calli) |(?:be|bg|bge|bgeu|bgu|bne) \w+,\w+,)([0-9a-f]+)$", r"\g<1>0x\2", text)
            # rebased image: move absolute branch targets by the same delta
            m2 = re.match(r"^((?:bi|calli) |(?:be|bg|bge|bgeu|bgu|bne) \w+,\w+,)0x([0-9a-f]+)$", text)
            if m2 and delta:
                text = f"{m2.group(1)}0x{(int(m2.group(2), 16) - delta) & 0xffffffff:x}"
        d[off] = (m.group(2).replace(" ", ""), text)
    return d


def norm_exact(t):
    t = t.strip().lower()
    t = re.sub(r"\s*,\s*", ",", t)
    t = re.sub(r"\s+", " ", t)
    return t


def num(m):
    v = m.group(0)
    neg = v.startswith("-")
    v = v.lstrip("-")
    n = int(v, 16) if v.startswith("0x") else int(v)
    n = -n if neg else n
    return str(n & 0xffffffff)


def norm_sem(t):
    t = norm_exact(t)
    # objdump appends <symbol> annotations on linked images
    t = re.sub(r"\s*<[^>]*>", "", t)
    t = re.sub(r"-?(0x[0-9a-f]+|\d+)(?![0-9a-z])", num, t)
    return t


# Known, explained difference classes (see README "Decode results"): (name, test(ghidra, objdump))
EXPLAINED = [
    ("gp-relative load/store: objdump prints only the offset, Ghidra (gp+offset)",
     lambda gt, ot: gt is not None and ot is not None and "(gp+" in gt and "(" not in ot and
     norm_sem(gt.replace("(gp+", "").replace(")", "")) == norm_sem(ot)),
    ("CSR number without a name: objdump prints ???, Ghidra csrN",
     lambda gt, ot: gt is not None and ot is not None and "???" in ot and
     re.sub(r"csr\d+", "???", gt).replace(" ", "") == ot.replace(" ", "")),
    ("div/mod (manual opcodes 0x27/0x35) not in binutils",
     lambda gt, ot: ot is None and gt is not None and gt.split()[0] in ("div", "mod")),
]
explained = collections.Counter()


g = load_ghidra(gfile)
o = load_objdump(ofile)
counts = collections.Counter()
classes = collections.defaultdict(list)
for off in sorted(o):
    if off not in g:
        counts["not disassembled by ghidra" if a.listing else "missing in ghidra"] += 1
        continue
    obytes, ot = o[off]
    gbytes, gt = g[off]
    if ot is None and gt is None:
        counts["both undefined"] += 1
        continue
    for name, test in EXPLAINED:
        if test(gt, ot):
            explained[name] += 1
            break
    if ot is None:
        key = "ghidra decodes, objdump rejects: " + gt.split()[0]
        counts["ghidra only"] += 1
        classes[key].append((off, obytes, gt, "*unknown*"))
        continue
    if gt is None:
        key = "objdump decodes, ghidra rejects: " + ot.split()[0]
        counts["objdump only"] += 1
        classes[key].append((off, obytes, "BAD", ot))
        continue
    if norm_exact(gt) == norm_exact(ot):
        counts["exact"] += 1
    elif norm_sem(gt) == norm_sem(ot):
        counts["semantic"] += 1
    else:
        counts["differ"] += 1
        key = "differ: " + ot.split()[0] + " / " + gt.split()[0]
        classes[key].append((off, obytes, gt, ot))

nreach = counts.pop("not disassembled by ghidra", 0)
total = sum(counts.values())
agree = counts["exact"] + counts["semantic"] + counts["both undefined"]
decoded = counts["exact"] + counts["semantic"] + counts["differ"] + counts["ghidra only"] + counts["objdump only"]
print(f"compared {total} words: agreement {agree}/{total} = {100.0 * agree / max(total, 1):.2f}% "
      f"(exact {counts['exact']}, semantic {counts['semantic']}, both undefined {counts['both undefined']}); "
      f"decoded by either: {decoded}, of which exact+semantic {counts['exact'] + counts['semantic']} = "
      f"{100.0 * (counts['exact'] + counts['semantic']) / max(decoded, 1):.2f}%")
if a.listing:
    print(f"  objdump words not disassembled by ghidra: {nreach}")
ndiff = counts["differ"] + counts["ghidra only"] + counts["objdump only"]
print(f"  differences: {ndiff}, explained {sum(explained.values())}, "
      f"unexplained {ndiff - sum(explained.values())}")
for k, v in explained.items():
    print(f"    explained [{v}] {k}")
for k in ("differ", "ghidra only", "objdump only", "missing in ghidra"):
    if counts[k]:
        print(f"  {k}: {counts[k]}")
for key in sorted(classes, key=lambda k: -len(classes[k])):
    print(f"[{len(classes[key])}] {key}")
    for off, b, gt, ot in classes[key][:maxex]:
        print(f"    {off:08x} {b}  ghidra: {gt:40s} objdump: {ot}")
