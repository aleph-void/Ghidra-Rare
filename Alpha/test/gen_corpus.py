#!/usr/bin/env python3
"""Build the Alpha decode corpora.

  gen_corpus.py <alpha-opc.txt> <outdir> [seed]

alpha-opc.txt is GNU binutils' alpha_opcodes[] table dumped by tools/dumpopc.c
(name opcode mask flags operands...). Writes:
  table.bin  every table entry, 16 words each with random operand bits (fields that the
             entry fixes to R31 or to Ra are set accordingly)
  fuzz.bin   50,000 uniformly random 32-bit words
Little-endian 32-bit words. Deterministic for a given seed.
"""
import random, struct, sys

opc, out = sys.argv[1], sys.argv[2]
rng = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 1)
# binutils operand indices that constrain other fields: ZA/ZB/ZC must be 31, RBA/RCA must
# equal Ra (alpha-opc.c alpha_operands[]).
ZA, ZB, ZC, RBA, RCA = 7, 8, 9, 12, 13

def constrain(w, operands):
    ra = (w >> 21) & 31
    for o in operands:
        if o == ZA:
            w |= 31 << 21
        elif o == ZB:
            w |= 31 << 16
        elif o == ZC:
            w |= 31
        elif o == RBA:
            w = (w & ~(31 << 16)) | (ra << 16)
        elif o == RCA:
            w = (w & ~31) | ra
    return w

words = []
for line in open(opc):
    f = line.split()
    op, mask = int(f[1], 16), int(f[2], 16)
    operands = [int(x) for x in f[4:]]
    words.append(constrain(op, operands))
    for _ in range(15):
        w = op | (rng.getrandbits(32) & ~mask & 0xffffffff)
        words.append(constrain(w, operands) & 0xffffffff)
with open(f"{out}/table.bin", "wb") as fh:
    fh.write(b"".join(struct.pack("<I", w) for w in words))
with open(f"{out}/fuzz.bin", "wb") as fh:
    fh.write(b"".join(struct.pack("<I", rng.getrandbits(32)) for _ in range(50000)))
print(f"table.bin: {len(words)} words; fuzz.bin: 50000 words")
