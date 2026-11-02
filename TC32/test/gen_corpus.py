#!/usr/bin/env python3
"""Decode corpora for the TC32 differential and every-entry tests.

  gen_corpus.py <outdir> [random-count] [seed]

Writes (raw little-endian images, decoded from offset 0):
  all16.bin   every halfword 0000-FFFF, one per 4-byte slot (halfword, 0000 pad)
  pairs.bin   32-bit pairs, one per 8-byte slot (prefix, suffix, 0600 0600 pad):
              every prefix 9000-97FF with suffixes 0000 9800 9FFF 8800 C000 E000 F800 0600,
              prefix 9000 and 97FF with every suffix, plus 4096 random prefix/suffix pairs
  random.bin  <random-count> random 32-bit words, one per 4-byte slot
  every.bin   all16 slots followed by tjl pairs, 4-byte slots (every-entry test)
"""
import os
import random
import struct
import sys


def main():
    out = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 50000
    rnd = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 1)
    os.makedirs(out, exist_ok=True)
    all16 = b"".join(struct.pack("<HH", w, 0) for w in range(65536))
    open(os.path.join(out, "all16.bin"), "wb").write(all16)

    pairs = []
    for p in range(0x9000, 0x9800):
        for s in (0x0000, 0x9800, 0x9FFF, 0x8800, 0xC000, 0xE000, 0xF800, 0x0600):
            pairs.append((p, s))
    for p in (0x9000, 0x97FF):
        pairs += [(p, s) for s in range(65536)]
    pairs += [(rnd.randrange(0x9000, 0x9800), rnd.randrange(65536)) for _ in range(4096)]
    open(os.path.join(out, "pairs.bin"), "wb").write(
        b"".join(struct.pack("<HHHH", p, s, 0x0600, 0x0600) for p, s in pairs))

    open(os.path.join(out, "random.bin"), "wb").write(
        b"".join(struct.pack("<I", rnd.getrandbits(32)) for _ in range(n)))

    tjl = b"".join(struct.pack("<HH", p, s) for p, s in ((0x9000, 0x9800), (0x97FF, 0x9FFF), (0x9400, 0x9C00)))
    open(os.path.join(out, "every.bin"), "wb").write(all16 + tjl)
    print("all16 65536 slots, pairs %d slots, random %d slots" % (len(pairs), n))


if __name__ == "__main__":
    main()
