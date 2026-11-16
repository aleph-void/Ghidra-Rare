#!/usr/bin/env python3
"""Write the decode corpora as raw images.

    gen_corpus.py <kind> <out.bin> <big|little>

kinds: w16   every 16-bit word w, each in a 4-byte slot [w, 0x0009] (a P-op prefix takes the nop
             as its B field)
       bfield every B field (65536) under each of the A fields in A_SET, as 32-bit P-ops
       afield every A field (1024) with each B field in B_SET, as 32-bit P-ops
       random 50,000 random 32-bit words (fixed seed), each as two halfwords
The 32-bit kinds use 8-byte slots [w0, w1, nop, nop] so that a rejected word cannot shift the
next slot out of step.
"""
import random
import struct
import sys

A_SET = [0x000, 0x00b, 0x008, 0x003, 0x0f3, 0x114, 0x2a1, 0x3ff]
B_SET = [0xb107, 0x0012, 0x7123, 0x4110, 0x8a17, 0x9d17, 0x1f87, 0xa0a8, 0xfd0c, 0x0000]


def main():
    kind, out, end = sys.argv[1], sys.argv[2], sys.argv[3]
    f = ">H" if end == "big" else "<H"
    words = []
    if kind == "w16":
        for w in range(65536):
            words += [w, 0x0009]
    elif kind == "bfield":
        for a in A_SET:
            for b in range(65536):
                words += [0xf800 | a, b, 9, 9]
    elif kind == "afield":
        for b in B_SET:
            for a in range(1024):
                words += [0xf800 | a, b, 9, 9]
    elif kind == "random":
        r = random.Random(20261116)
        for _ in range(50000):
            words += [r.randrange(65536), r.randrange(65536), 9, 9]
    else:
        sys.exit("unknown kind " + kind)
    open(out, "wb").write(b"".join(struct.pack(f, w) for w in words))


if __name__ == "__main__":
    main()
