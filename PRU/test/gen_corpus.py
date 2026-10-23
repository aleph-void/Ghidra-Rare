#!/usr/bin/env python3
"""Build the PRU test corpus: structured vectors per encoding class + random words.

Usage: gen_corpus.py <out.bin> [nrandom] [seed]

Writes little-endian 32-bit words.  The structured part enumerates every
opcode/sub-opcode, every register-field selector, IO on/off, every burst and
XFR length encoding, every MVI mode, plus class-biased random fill.
"""
import random
import struct
import sys


def regf(r, sel):
    return (sel << 5) | r


def main():
    out = sys.argv[1]
    nrand = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    rnd = random.Random(seed)
    ws = []

    def R():
        return rnd.getrandbits(5)

    # Format 1 ALU: all subops x io x all dst/src selectors
    for sub in range(16):
        for io in (0, 1):
            for sel in range(8):
                rs2 = regf(R(), sel) if not io else rnd.choice([0, 1, 31, 255, rnd.getrandbits(8)])
                ws.append((sub << 25) | (io << 24) | (rs2 << 16) | (regf(R(), sel) << 8) | regf(R(), 7 - sel))
                ws.append((sub << 25) | (io << 24) | (rs2 << 16) | (regf(R(), 7 - sel) << 8) | regf(R(), sel))
    # pseudo-op forms
    ws += [0x12e0e0e0, 0x13000000 | (regf(5, 7) << 8) | regf(6, 4), 0x10000000, 0x1600e3e3]
    # Format 2: every subop with a spread of field values
    for sub in range(16):
        for _ in range(24):
            ws.append((1 << 29) | (sub << 25) | rnd.getrandbits(25))
    # TSEN (V4 only: exactly 0x32000000 / 0x32800000) and near misses
    ws += [0x32000000, 0x32800000, 0x33000000, 0x32800001, 0x32400000, 0x33800000]
    # JMP/JAL/ret/call specials
    ws += [0x20c30000, 0x21001234, 0x230000c3, 0x228100c3, 0x2300ffc3, 0x2100ffff]
    # XFR: all xsub x S, special device ids, all lengths
    for xsub in range(4):
        for s in (0, 1):
            for wba in (0, 10, 20, 253, 254, 255):
                ws.append((1 << 29) | (7 << 25) | (xsub << 23) | (wba << 15) | (s << 14) |
                          (rnd.getrandbits(7) << 7) | (rnd.getrandbits(2) << 5) | R())
    for ln in range(128):
        ws.append((1 << 29) | (7 << 25) | (1 << 23) | (rnd.getrandbits(8) << 15) | (ln << 7) | R())
    # LOOP / ILOOP
    for i in (0, 1):
        for io in (0, 1):
            for off in (0, 1, 2, 5, 255):
                ws.append((1 << 29) | (8 << 25) | (io << 24) | (rnd.getrandbits(8) << 16) |
                          (i << 15) | off)
    # MVI: every size x src mode x dst mode with plausible operands
    for sz in range(4):
        for sm in range(4):
            for dm in range(4):
                for _ in range(2):
                    rs1 = regf(1, rnd.getrandbits(2)) if sm else regf(R(), rnd.getrandbits(3))
                    rdf = regf(1, rnd.getrandbits(2)) if dm else regf(R(), rnd.getrandbits(3))
                    ws.append((1 << 29) | (6 << 25) | ((dm >> 1) << 24) | ((dm & 1) << 23) |
                              (sm << 21) | (sz << 16) | (rs1 << 8) | rdf)
    # Format 4 QB: all compare codes, io, positive/negative offsets
    for c in range(8):
        for io in (0, 1):
            for off in (0, 1, 0x1ff, 0x200, 0x3ff, rnd.getrandbits(10)):
                ws.append((1 << 30) | (c << 27) | ((off >> 8) << 25) | (io << 24) |
                          (rnd.getrandbits(8) << 16) | (regf(R(), rnd.getrandbits(3)) << 8) | (off & 0xff))
    # Format 5 QBBS/QBBC (incl. WBS/WBC offset 0, invalid 00/11 codes)
    for bb in range(4):
        for io in (0, 1):
            for off in (0, 1, 0x3ff, rnd.getrandbits(10)):
                ws.append((6 << 29) | (bb << 27) | ((off >> 8) << 25) | (io << 24) |
                          (rnd.getrandbits(8) << 16) | (regf(R(), rnd.getrandbits(3)) << 8) | (off & 0xff))
    # Format 6: all burst lengths for LBBO/SBBO/LBCO/SBCO
    for top in (7, 4):
        for ls in (0, 1):
            for v in range(128):
                ws.append((top << 29) | (ls << 28) | ((v >> 4) << 25) | (rnd.getrandbits(1) << 24) |
                          (rnd.getrandbits(8) << 16) | (((v >> 1) & 7) << 13) | (R() << 8) |
                          ((v & 1) << 7) | (rnd.getrandbits(2) << 5) | R())
    # undefined top-level class 101
    for _ in range(16):
        ws.append((5 << 29) | rnd.getrandbits(29))
    # class-biased random fill
    for top in range(8):
        for _ in range(500):
            ws.append((top << 29) | rnd.getrandbits(29))
    # fully random
    for _ in range(nrand):
        ws.append(rnd.getrandbits(32))
    with open(out, "wb") as f:
        for x in ws:
            f.write(struct.pack("<I", x & 0xffffffff))
    print("%d words" % len(ws))


if __name__ == "__main__":
    main()
