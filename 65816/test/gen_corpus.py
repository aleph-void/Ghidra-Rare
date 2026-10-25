#!/usr/bin/env python3
"""65816 decode corpus: fixed 4-byte records, one instruction decoded per record.

  gen_corpus.py <out.bin> <nrandom> [seed]

Part 1 (structured): every opcode 0x00-0xff with operand bytes drawn from edge values
(00, 01, 7f, 80, ff, fe) and random bytes, 16 records per opcode.
Part 2 (random): <nrandom> records of 4 random bytes.
The same corpus is decoded under every M/X/E combination.
"""
import random
import sys

out, nrand = sys.argv[1], int(sys.argv[2])
rng = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 1)
edges = [0x00, 0x01, 0x7f, 0x80, 0xff, 0xfe]
recs = []
for op in range(256):
    for k in range(16):
        if k < len(edges):
            e = edges[k]
            recs.append(bytes([op, e, e, e]))
        else:
            recs.append(bytes([op] + [rng.randrange(256) for _ in range(3)]))
for _ in range(nrand):
    recs.append(bytes(rng.randrange(256) for _ in range(4)))
with open(out, "wb") as f:
    f.write(b"".join(recs))
print(f"{len(recs)} records ({256 * 16} structured, {nrand} random)")
