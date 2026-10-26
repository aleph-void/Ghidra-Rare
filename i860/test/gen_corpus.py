#!/usr/bin/env python3
"""Decode corpora for the i860 differential tests (little-endian 32-bit words, one per 8-byte slot).

  gen_corpus.py low  <out.bin>   every op6 x every value of bits 10-0 (opcode, size, FP
                                 P/D/S/R and core-escape fields), two register settings each
  gen_corpus.py regs <out.bin>   every op6 x 4096 register-field combinations (bits 25-11),
                                 low bits from a small set of typical values
  gen_corpus.py rand <out.bin> [n] n uniformly random words (default 65536)
Seeds are fixed, so the corpora are reproducible.
"""
import random
import struct
import sys


NOP = 0xa0000000      # shl r0,r0,r0


def write(path, words):
    # Each test word is followed by a nop, so the delay slot of a branch under test is a nop
    # and every word decodes independently of its neighbours: test words sit at 8k, nops at
    # 8k + 4.
    with open(path, "wb") as f:
        f.write(b"".join(struct.pack("<II", w, NOP) for w in words))
    print(f"{path}: {len(words)} words")


def low():
    rnd = random.Random(860)
    words = []
    for op in range(64):
        for lo in range(2048):
            for k in range(2):
                regs = (2 << 10) | (3 << 5) | 4 if k == 0 else rnd.getrandbits(15)
                words.append((op << 26) | (regs << 11) | lo)
    return words


def regs():
    rnd = random.Random(8600)
    lows = [0x000, 0x001, 0x002, 0x003, 0x004, 0x005, 0x006, 0x007, 0x200, 0x400, 0x600,
            0x030, 0x430, 0x0b0, 0x1b0, 0x5b0, 0x180, 0x580]
    words = []
    for op in range(64):
        for i in range(4096):
            if i < 1024:     # src1 = i % 32, src2 = i / 32, dest = 7i % 32
                r = (i & 31) | ((i >> 5) << 10) | (((i * 7) & 31) << 5)
            else:
                r = rnd.getrandbits(15)
            words.append((op << 26) | (r << 11) | rnd.choice(lows))
    return words


def rand(n):
    rnd = random.Random(86000)
    return [rnd.getrandbits(32) for _ in range(n)]


if __name__ == "__main__":
    kind, path = sys.argv[1], sys.argv[2]
    if kind == "low":
        write(path, low())
    elif kind == "regs":
        write(path, regs())
    else:
        write(path, rand(int(sys.argv[3]) if len(sys.argv) > 3 else 65536))
