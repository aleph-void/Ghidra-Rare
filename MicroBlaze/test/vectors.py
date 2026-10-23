#!/usr/bin/env python3
"""Hand-built vectors: every Type B instruction with and without imm / imml prefixes,
and branch/return/call forms. gas refuses explicit imm/imml in source, so these are raw words.

  vectors.py <outdir>     -> vec32_{be,le}.bin, vec64_{be,le}.bin
"""
import struct
import sys

out = sys.argv[1]
TYPEB32 = [0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f, 0x18, 0x28, 0x29, 0x2a, 0x2b,
           0x38, 0x39, 0x3a, 0x3c, 0x3d, 0x3e]
TYPEB64 = TYPEB32 + [0x3b, 0x3f]


def enc(op, rd, ra, imm):
    return (op << 26) | (rd << 21) | (ra << 16) | (imm & 0xffff)


def branches(bits):
    w = []
    # bri / brid / brlid / brai / braid / bralid / brki
    for ra, rd in ((0x00, 0), (0x10, 0), (0x14, 15), (0x08, 0), (0x18, 0), (0x1c, 15), (0x0c, 16)):
        for imm in (8, -8, 0x7ffc, -0x8000):
            w += [enc(0x2e, rd, ra, imm), 0x80000000]
    # conditional immediate branches with and without delay
    for c in range(6):
        for d in (0, 1):
            w += [enc(0x2f, (d << 4) | c, 3, -16), 0x80000000]
    # register branches
    for ra, rd in ((0x00, 0), (0x10, 0), (0x14, 15), (0x08, 0), (0x18, 0), (0x1c, 15), (0x0c, 16)):
        w += [(0x26 << 26) | (rd << 21) | (ra << 16) | (5 << 11), 0x80000000]
    for c in range(6):
        for d in (0, 1):
            w += [(0x27 << 26) | (((d << 4) | c) << 21) | (3 << 16) | (4 << 11), 0x80000000]
    # returns
    for rd in (0x10, 0x11, 0x12, 0x14):
        w += [enc(0x2d, rd, 15, 8), 0x80000000]
    # imm-prefixed branches (32-bit targets)
    for ra, rd in ((0x00, 0), (0x10, 0), (0x14, 15), (0x08, 0), (0x18, 0), (0x1c, 15)):
        w += [0xb0000000 | 0x1234, enc(0x2e, rd, ra, 0x5678), 0x80000000]
        w += [0xb0000000 | 0xffff, enc(0x2e, rd, ra, 0xfff0), 0x80000000]
    for c in range(6):
        w += [0xb0000000 | 0x0001, enc(0x2f, c, 3, 0x0010), 0x80000000]
    if bits == 64:
        # extended address branches, with imml prefixes
        for ra, rd in ((0x01, 0), (0x11, 0), (0x15, 15)):
            w += [enc(0x2e, rd, ra, 0x40), 0x80000000]
            w += [0xb2000012, enc(0x2e, rd, ra, 0x3456), 0x80000000]
            w += [0xb2abcdef, 0xb2123456, enc(0x2e, rd, ra, 0x789a), 0x80000000]
            w += [(0x26 << 26) | (rd << 21) | (ra << 16) | (5 << 11), 0x80000000]
        for c in range(6):
            for d in (0, 1):
                w += [enc(0x2f, (d << 4) | 8 | c, 3, -16), 0x80000000]
                w += [0xb2ffffff, enc(0x2f, (d << 4) | 8 | c, 3, -16), 0x80000000]
                for l in (0, 0x100):
                    w += [(0x27 << 26) | (((d << 4) | 8 | c) << 21) | (3 << 16) | (4 << 11) | l, 0x80000000]
    return w


def build(bits):
    w = []
    for op in (TYPEB64 if bits == 64 else TYPEB32):
        for imm in (0, 1, -1, 0x7fff, -0x8000, 0x1234):
            w.append(enc(op, 3, 1, imm))
            w += [0xb0000000 | 0xdead, enc(op, 3, 1, imm)]
            if bits == 64:
                w += [0xb2000000 | 0x123456, enc(op, 3, 1, imm)]
                w += [0xb2800000, enc(op, 3, 1, imm)]
                w += [0xb2fedcba, 0xb2987654, enc(op, 3, 1, imm)]
    if bits == 64:
        for ra in list(range(8)) + [0x10, 0x11, 0x12, 0x13]:
            w += [enc(0x1a, 4, ra, -2), 0xb2000001, enc(0x1a, 4, ra, 0x10)]
    w += branches(bits)
    w.append(0x80000000)
    return w


for bits in (32, 64):
    words = build(bits)
    for e, fmt in (("be", ">I"), ("le", "<I")):
        with open("%s/vec%d_%s.bin" % (out, bits, e), "wb") as f:
            f.write(b"".join(struct.pack(fmt, x) for x in words))
