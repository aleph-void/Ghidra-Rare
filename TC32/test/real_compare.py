#!/usr/bin/env python3
"""Compare Ghidra's analysed instructions (TC32RealCheck .dis) with `tc32-elf-objdump -d` of the
same ELF at the same addresses.  real_compare.py <objdump.txt> <ghidra.dis> [label]
Prints totals and every difference; exit 1 if any instruction differs."""
import re
import sys

from compare import norm


def read_od(path):
    out = {}
    for line in open(path, errors="replace"):
        m = re.match(r"^\s*([0-9a-f]+):\t((?:[0-9a-f]{4} ?|[0-9a-f]{8} ?)+)\s*\t(.*)$", line)
        if not m:
            continue
        txt = m.group(3).strip()
        if txt.startswith((".word", ".short", ".byte", "undefined")):
            continue
        txt = re.sub(r"\s*<[^>]*>\s*$", "", txt)
        # objdump -d prints branch targets as bare hex
        txt = re.sub(r"^(tj\S*)(\s+)([0-9a-f]+)$", r"\1\2 0x\3", txt)
        nbytes = sum(len(x) // 2 for x in m.group(2).split())
        out[int(m.group(1), 16)] = (txt, nbytes)
    return out


def read_ghidra(path):
    out = {}
    for line in open(path):
        p = line.rstrip("\n").split(" ", 2)
        if len(p) == 3:
            out[int(p[0], 16)] = (p[2], len(p[1]) // 2, p[1])
    return out


def main():
    od, gh = read_od(sys.argv[1]), read_ghidra(sys.argv[2])
    label = sys.argv[3] if len(sys.argv) > 3 else ""
    same = diff = missing = 0
    shown = 0
    for a in sorted(gh):
        g_txt, g_len, g_hex = gh[a]
        if a not in od:
            missing += 1
            if shown < 20:
                print(f"  no objdump instruction at {a:08x}: ghidra {g_txt}")
                shown += 1
            continue
        o_txt, o_len = od[a]
        if norm(o_txt) == norm(g_txt) and o_len == g_len:
            same += 1
        else:
            diff += 1
            if shown < 40:
                print(f"  {a:08x} {g_hex:<10} objdump: {o_txt:<36} ghidra: {g_txt}")
                shown += 1
    print(f"== {label}: {same + diff + missing} Ghidra instructions: {same} identical to objdump, "
          f"{diff} different, {missing} at addresses objdump did not decode")
    sys.exit(1 if diff or missing else 0)


if __name__ == "__main__":
    main()
