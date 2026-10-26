#!/usr/bin/env python3
"""Compare Ghidra's analysed disassembly of a real i860 ELF with GNU objdump (binutils 2.30,
run as a black box) and MAME unidasm at the same addresses.

  real_compare.py <ghidra.dis> <objdump.txt> <mame.txt> [--show N]
ghidra.dis: "<addr> <bytes> <text>" for every instruction auto-analysis created.
Differences with MAME are explained with test/compare.py's rules; objdump's spellings are
normalized the same way (its branch-target comments are dropped).
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import compare  # noqa: E402

OD_RE = re.compile(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} ){4})\s*(.*)$")


def norm_od(text):
    text = text.split("//")[0].strip()
    if not text or text.startswith(".long"):
        return None
    mn, _, ops = text.partition("\t")
    if not ops:
        mn, _, ops = text.partition(" ")
    return mn.strip() + " " + compare.norm_ops(ops)


def main():
    a = sys.argv[1:]
    show = int(a[a.index("--show") + 1]) if "--show" in a else 5
    gh = compare.load(a[0], compare.GH_RE, compare.norm_ghidra)
    od = {}
    for line in open(a[1]):
        m = OD_RE.match(line.rstrip("\n"))
        if m:
            od[int(m.group(1), 16)] = norm_od(m.group(3))
    mame = compare.load(a[2], compare.MAME_RE, compare.norm_mame)
    compare.XP = True
    n = same_od = same_mame = expl = 0
    bad_od, bad_mame = [], []
    for addr, (word, gt) in sorted(gh.items()):
        n += 1
        if od.get(addr) == gt:
            same_od += 1
        else:
            bad_od.append((addr, gt, od.get(addr)))
        mt = mame.get(addr, (None, None))[1]
        if mt == gt:
            same_mame += 1
        else:
            w = int(word[6:8] + word[4:6] + word[2:4] + word[0:2], 16)
            if compare.mame_quirk(w, gt, mt) or (mt and not gt):
                expl += 1
            else:
                bad_mame.append((addr, gt, mt))
    print(f"instructions: {n}; identical to objdump: {same_od}; identical to MAME: {same_mame}"
          f" (+{expl} explained MAME differences); unexplained: objdump {len(bad_od)}, MAME {len(bad_mame)}")
    for addr, g, o in bad_od[:show]:
        print(f"  objdump {addr:08x}  ghidra: {g}   objdump: {o}")
    for addr, g, m in bad_mame[:show]:
        print(f"  MAME    {addr:08x}  ghidra: {g}   mame: {m}")
    sys.exit(1 if bad_od or bad_mame else 0)


main()
