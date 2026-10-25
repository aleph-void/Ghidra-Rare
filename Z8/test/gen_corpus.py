#!/usr/bin/env python3
"""Z8 decode corpus: every opcode with every first operand byte, every 3-byte opcode with every
second operand byte, plus random instructions. Instruction length depends only on the opcode
(UM0016 op code map), so the stream stays aligned for a linear disassembler.

    gen_corpus.py <outprefix> [nrandom] [seed]   -> <outprefix>_<n>.bin, each <= 0xe000 bytes
                                                    (the code space is 64K; images load at 0x1000)
"""
import random
import sys

ILLEGAL = {0x0f, 0x1f, 0x2f, 0x3f, 0x84, 0x85, 0x86, 0x87, 0x94, 0x95, 0x96, 0x97,
           0xc4, 0xc5, 0xc6, 0xd5, 0xe2, 0xf2, 0xf4, 0xf6, 0xf7}


def length(op):
    lo = op & 15
    if op in ILLEGAL or lo in (0xe, 0xf):
        return 1
    if op == 0xd4:
        return 2
    if lo in (4, 5, 6, 7, 0xd):
        return 3
    return 2


# operand byte classes: ports, ERF-able 00-0F, GPRs, working registers (incl. the FLAGS/SP
# working slots), control registers and the FLAGS/RP/SPH/SPL addresses
CLASSES = list(range(0x10)) + [0x10, 0x3c, 0x7f, 0xdf, 0xe0, 0xe5, 0xec, 0xed, 0xee, 0xef] + \
    list(range(0xf0, 0x100)) + [0xce, 0x5e, 0x1c]


def every():
    """Compact image for the every-entry test: each opcode with each operand-byte class."""
    buf = bytearray()
    for op in range(256):
        for b1 in CLASSES:
            buf.extend(bytes([op, b1, 0x3c])[:length(op)])
        if length(op) == 3:
            for b2 in CLASSES:
                buf.extend(bytes([op, 0xe5, b2]))
    return buf


def main():
    if sys.argv[1] == "--every":
        open(sys.argv[2], "wb").write(every())
        return
    out = sys.argv[1]
    nrand = int(sys.argv[2]) if len(sys.argv) > 2 else 50000
    rnd = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 1)
    chunks = [bytearray()]

    def emit(op, b1, b2):
        n = length(op)
        if len(chunks[-1]) + n > 0xe000:
            chunks.append(bytearray())
        chunks[-1].extend(bytes([op, b1, b2])[:n])

    for op in range(256):
        if length(op) == 1:
            emit(op, 0, 0)
            continue
        for b1 in range(256):
            emit(op, b1, rnd.randrange(256))
    for op in range(256):
        if length(op) == 3:
            for b2 in range(256):
                emit(op, rnd.randrange(256), b2)
    for _ in range(nrand):
        emit(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
    for i, c in enumerate(chunks):
        open(f"{out}_{i}.bin", "wb").write(c)
        print(f"{out}_{i}.bin")


if __name__ == "__main__":
    main()
