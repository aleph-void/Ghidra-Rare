#!/usr/bin/env python3
"""Compare Ghidra's disassembly of a real binary (RealCheck.java listing) with objdump -d.

  real_compare.py <ghidra.lst> <objdump-d.txt> [examples] [address-delta]

Every instruction Ghidra found is looked up at the same address (minus address-delta, the
image base Ghidra rebased a shared object to) in objdump's output and compared with the
normalization and pseudo-op rules of compare.py.
"""
import os, re, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare as C

gfile, ofile = sys.argv[1], sys.argv[2]
nex = int(sys.argv[3]) if len(sys.argv) > 3 else 5
delta = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0
o = {}
for line in open(ofile):
    m = re.match(r"\s*([0-9a-f]+):\t([0-9a-f ]+)\t(.*)$", line)
    if m:
        text = re.sub(r"\s*<[^>]*>", "", m.group(3).replace("\t", " ")).strip()
        o[int(m.group(1), 16)] = text
BRANCH = {"br", "bsr", "beq", "bne", "blt", "ble", "bgt", "bge", "blbc", "blbs", "fbeq", "fbne",
          "fblt", "fble", "fbgt", "fbge", "jmp", "jsr", "hw_jmp", "hw_jsr"}

def fix_target(text, objdump):
    """objdump prints branch targets (and JMP/JSR hints) as bare hex addresses in ELF mode;
    Ghidra prints rebased 0x-prefixed addresses. Rewrite the last operand of both as decimal."""
    parts = text.split(None, 1)
    if len(parts) < 2 or parts[0].lower().split("/")[0] not in BRANCH:
        return text
    ops = parts[1].rsplit(",", 1)
    last = ops[-1].strip()
    if last.startswith("("):
        return text
    try:
        v = int(last, 16) if objdump else int(last, 0) - delta
    except ValueError:
        return text
    ops[-1] = str(v & 0xffffffffffffffff)
    return parts[0] + " " + ",".join(ops)

cnt = Counter()
classes = defaultdict(list)
for line in open(gfile):
    addr, hexb, text = line.rstrip("\n").split(" ", 2)
    a = int(addr, 16) - delta
    ot = o.get(a)
    if ot is None:
        cnt["not in objdump -d"] += 1
        continue
    if ot.startswith(".long") or re.match(r"pal1[9bdef]\b", ot):
        cnt["objdump undefined"] += 1
        classes[("objdump-undefined", text.split()[0].lower())].append((addr, text, ot))
        continue
    gn, on = C.norm(fix_target(text, False), C.GMAP), C.norm(fix_target(ot, True), C.OMAP)
    if gn == on:
        cnt["exact"] += 1
    elif C.canon(gn, C.GPALNAMES) == C.canon(on):
        cnt["semantic"] += 1
    else:
        cnt["differ"] += 1
        classes[("differ", text.split()[0].lower() + " / " + ot.split()[0])].append((addr, text, ot))
n = cnt["exact"] + cnt["semantic"] + cnt["differ"]
print(f"instructions {n}: exact {cnt['exact']}, semantic {cnt['semantic']}, differ {cnt['differ']} "
      f"({100 * (cnt['exact'] + cnt['semantic']) / max(1, n):.3f}% agree); "
      f"objdump undefined {cnt['objdump undefined']}, not in objdump -d {cnt['not in objdump -d']}")
for k, v in sorted(classes.items(), key=lambda kv: -len(kv[1])):
    print(f"  [{len(v):5d}] {k[0]}: {k[1]}")
    for a, gt, ot in v[:nex]:
        print(f"           {a}  ghidra: {gt:40s} objdump: {ot}")
