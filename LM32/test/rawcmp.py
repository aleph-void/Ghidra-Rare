#!/usr/bin/env python3
"""Relocation-handler check: compare the bytes Ghidra holds after importing a relocatable
object (DumpMem.java) with the same object linked by ld at Ghidra's addresses (objdump -s).

  rawcmp.py <ghidra-mem.txt> <objdump-s.txt>

Only the sections both sides have are compared (objdump -s prints every loaded section).
"""
import re
import sys

g = {}
for line in open(sys.argv[1]):
    a, b = line.split()
    g[int(a, 16)] = int(b, 16)
n = bad = 0
shown = 0
for line in open(sys.argv[2]):
    m = re.match(r"^ ([0-9a-f]+) ((?:[0-9a-f]{2,8} ){1,4})", line)
    if not m:
        continue
    addr = int(m.group(1), 16)
    hexs = m.group(2).replace(" ", "")
    for i in range(0, len(hexs), 2):
        a = addr + i // 2
        if a not in g:
            continue
        n += 1
        v = int(hexs[i:i + 2], 16)
        if g[a] != v:
            bad += 1
            if shown < 10:
                shown += 1
                print(f"  {a:08x}: ghidra {g[a]:02x} ld {v:02x}")
print(f"compared {n} bytes with the ld-linked object: {bad} differ")
