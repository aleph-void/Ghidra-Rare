#!/usr/bin/env python3
"""Decode-test corpus for ST9/ST9+.

    gen_corpus.py <out.bin> [nrandom] [seed]

Also writes <out>.NNN.bin chunks of 5461 records (65532 bytes): the ST9 code space is 64K, so
Ghidra's BinaryLoader can't take the whole image at once.

Writes 12-byte records: 6 instruction bytes followed by six FF (NOP) bytes, so that a linear
sweep (MAME unidasm) resynchronises at every record start whatever length it decoded. Records:
every (opcode, byte 1) pair with random bytes 2-5, then <nrandom> fully random records.
"""
import random
import sys

out = sys.argv[1]
nrand = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
rng = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 1)
recs = []
for op in range(256):
    for b1 in range(256):
        recs.append(bytes([op, b1] + [rng.randrange(256) for _ in range(4)]))
# opcodes whose byte 2 also selects the form (K nibble, flag bits, register pair bit 0): every
# byte 1 with eight random byte-2 values, plus every byte 2 for the PEA/PEAU/PUSHW prefixes
for op in (0x06, 0x07, 0x0F, 0x17, 0x1F, 0x26, 0x27, 0x2F, 0x36, 0x37, 0x47, 0x56, 0x57, 0x60,
           0x67, 0x6F, 0x72, 0x73, 0x7E, 0x7F, 0x86, 0x87, 0x96, 0x97, 0xA6, 0xA7, 0xB4, 0xBE,
           0xC2, 0xC3, 0xD5, 0xE6, 0xE7, 0xEF, 0xF2):
    for b1 in range(256):
        for _ in range(8):
            recs.append(bytes([op, b1] + [rng.randrange(256) for _ in range(4)]))
for b1 in (0x01, 0x03, 0xC1, 0xC3, 0xF1, 0xF3):
    for b2 in range(256):
        recs.append(bytes([0x8F, b1, b2] + [rng.randrange(256) for _ in range(3)]))
for _ in range(nrand):
    recs.append(bytes(rng.randrange(256) for _ in range(6)))
CHUNK = 5461
with open(out, "wb") as f:
    for r in recs:
        f.write(r + b"\xff" * 6)
base = out[:-4] if out.endswith(".bin") else out
for i in range(0, len(recs), CHUNK):
    with open("%s.%03d.bin" % (base, i // CHUNK), "wb") as f:
        for r in recs[i:i + CHUNK]:
            f.write(r + b"\xff" * 6)
