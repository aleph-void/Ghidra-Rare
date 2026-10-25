#!/usr/bin/env python3
"""Generate LM32 decode corpora.

  gen_corpus.py <binutils lm32-opc.c> <outdir> [seed]

Writes (each as BE and LE raw images, one 32-bit word per instruction):
  table_{be,le}.bin   every binutils opcode-table entry, with its operand bits all 0, all 1
                      and 40 random fills
  fuzz_{be,le}.bin    50,000 uniformly random words
  entries.txt         <mnemonic> <mask> <value> for the every-entry decode test
"""
import random
import re
import struct
import sys

opc, out = sys.argv[1], sys.argv[2]
rnd = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 1)

s = open(opc).read()
fmts = {m.group(1): int(m.group(2), 16) for m in re.finditer(
    r'static const CGEN_IFMT (\w+) ATTRIBUTE_UNUSED = \{\s*32, 32, (0x[0-9a-f]+)', s)}
entries = []
for m in re.finditer(r'/\* (\S+) [^*]*\*/\s*\n\s*\{\s*\{[^}]*\},\s*\{ \{[^}]*\} \},\s*& (\w+), \{ (0x[0-9a-f]+) \}', s):
    entries.append((m.group(1), fmts[m.group(2)], int(m.group(3), 16)))
assert len(entries) > 60, len(entries)

table = []
for name, mask, val in sorted(set(entries), key=lambda e: (e[2], e[1], e[0])):
    free = ~mask & 0xffffffff
    table.append(val)
    table.append(val | free)
    for _ in range(40):
        table.append(val | (rnd.getrandbits(32) & free))
fuzz = [rnd.getrandbits(32) for _ in range(50000)]

for tag, words in (("table", table), ("fuzz", fuzz)):
    for e, fmt in (("be", ">I"), ("le", "<I")):
        with open(f"{out}/{tag}_{e}.bin", "wb") as f:
            f.write(b"".join(struct.pack(fmt, w) for w in words))
with open(f"{out}/entries.txt", "w") as f:
    for name, mask, val in sorted(set(entries), key=lambda e: (e[2], e[1], e[0])):
        f.write(f"{name} {mask:08x} {val:08x}\n")
print(f"table: {len(table)} words from {len(set(entries))} entries; fuzz: {len(fuzz)} words")
