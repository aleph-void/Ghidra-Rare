#!/usr/bin/env python3
"""Compare the raw instruction words of a Ghidra listing (RealCheck.java) with objdump -d.

  rawcmp.py <be|le> <ghidra.lst> <objdump.txt>

Used to check the ELF relocation handler: a relocatable object imported into Ghidra (which
applies the relocations at the addresses it chose) must have the same words as the object
linked by ld at those addresses.
"""
import re
import sys

endian, gfile, ofile = sys.argv[1:4]
g = {}
for line in open(gfile):
    p = line.split()
    if len(p) >= 2:
        g[int(p[0], 16)] = bytes.fromhex(p[1])
n = bad = 0
for line in open(ofile):
    m = re.match(r'\s*([0-9a-f]+):\t([0-9a-f]{8}) ', line)
    if not m or int(m.group(1), 16) not in g:
        continue
    w = g[int(m.group(1), 16)]
    w = w if endian == "be" else w[::-1]
    n += 1
    if w.hex() != m.group(2):
        bad += 1
        if bad <= 10:
            print("  %s: ghidra %s ld %s" % (m.group(1), w.hex(), m.group(2)))
print("compared %d words with the ld-linked object: %d differ" % (n, bad))
