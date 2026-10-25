#!/usr/bin/env python3
"""Check R_LM32_GPREL16 as Ghidra applied it to elf/relocs_gprel.o (DumpMem.java output):
the 16-bit immediates of the first four instructions must be S + A - _gp, i.e. 0, 4, 8 and
-0x100 (_gp = small_data). GNU ld cannot be the reference here; see relocs_gprel.s.

  gprel_check.py <relocs_gprel.o.mem> <relocs_gprel.o.sum>
"""
import re
import sys

mem = {}
for line in open(sys.argv[1]):
    a, b = line.split()
    mem[int(a, 16)] = int(b, 16)
blocks = dict(re.findall(r"(\.\w+)@([0-9a-f]+)", open(sys.argv[2]).read()))
text = int(blocks[".text"], 16)
want = [0, 4, 8, -0x100 & 0xffff]
got = [(mem[text + 4 * i + 2] << 8) | mem[text + 4 * i + 3] for i in range(4)]
ok = got == want
print(f"GPREL16: immediates {[hex(x) for x in got]}, expected {[hex(x) for x in want]}: "
      f"{'OK' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
