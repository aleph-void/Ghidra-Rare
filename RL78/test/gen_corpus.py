#!/usr/bin/env python3
"""RL78 decode corpora, 8-byte slots (the longest RL78 instruction is 6 bytes with the ES: prefix).

  gen_corpus.py <outdir>  ->  enum.bin, fuzz.bin

enum.bin: every first byte x every second byte, and 0x11 (ES:) x every second x every third byte,
each followed by three different operand tails; plus CE FB xx (the RL78-S3 multiply/divide
group) with and without ES:. fuzz.bin: 60,000 random slots (fixed seed).
"""
import os
import random
import sys

out = sys.argv[1]
tails = [bytes([0x34, 0x12, 0x56, 0x78, 0x9a, 0xbc]), bytes([0xfe, 0x80, 0x07, 0x01, 0x02, 0x03]),
         bytes([0x02, 0xf1, 0xff, 0x10, 0x20, 0x30])]
e = bytearray()
for t in tails:
    for b0 in range(256):
        for b1 in range(256):
            e += bytes([b0, b1]) + t
    for b1 in range(256):
        for b2 in range(256):
            e += bytes([0x11, b1, b2]) + t[:5]
for x in range(256):
    e += bytes([0xCE, 0xFB, x]) + tails[0][:5]
    e += bytes([0x11, 0xCE, 0xFB, x]) + tails[0][:4]
open(os.path.join(out, "enum.bin"), "wb").write(e)
rnd = random.Random(1)
f = bytearray()
for _ in range(60000):
    f += bytes(rnd.getrandbits(8) for _ in range(8))
open(os.path.join(out, "fuzz.bin"), "wb").write(f)
print("enum.bin: %d slots, fuzz.bin: %d slots" % (len(e) // 8, len(f) // 8))
