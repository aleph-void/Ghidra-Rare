#!/usr/bin/env python3
"""XA decode corpus: one instruction per 16-byte slot, padded with NOPs (00h). XA instructions
are at most 6 bytes (user guide 3.5.1), so a linear disassembler resynchronises at every slot
however it decodes the bytes after a test instruction.

    gen_corpus.py <outprefix> [nrandom] [seed]
        -> <outprefix>_op1.bin   every first/second byte pair, tail 12 34 56 78
           <outprefix>_op2.bin   every first/second byte pair, tail 00 41 FF 80 (SFR/DS
                                 addresses, negative offsets)
           <outprefix>_op3.bin   every first/second byte pair, tail 07 80 00 7F (flag bits)
           <outprefix>_rnd.bin   random 6-byte instructions
    gen_corpus.py --every <out.bin>   8-byte slots: every byte pair with 16 tail patterns
Prints the file names.
"""
import random
import sys

SLOT = 16
TAILS = {"op1": b"\x12\x34\x56\x78", "op2": b"\x00\x41\xff\x80", "op3": b"\x07\x80\x00\x7f"}
EVERY_TAILS = [0x00, 0x01, 0x02, 0x03, 0x04, 0x06, 0x07, 0x08, 0x10, 0x18, 0x40, 0x41, 0x42, 0x43,
               0x7f, 0x80, 0xc8, 0xff]


def slot(ins, size=SLOT):
    return ins + bytes(size - len(ins))


def main():
    if sys.argv[1] == "--every":
        buf = bytearray()
        for t in EVERY_TAILS:
            for w in range(65536):
                buf += slot(bytes([w >> 8, w & 0xff, t, t, t, t]), 8)
        open(sys.argv[2], "wb").write(buf)
        print(sys.argv[2])
        return
    out = sys.argv[1]
    nrand = int(sys.argv[2]) if len(sys.argv) > 2 else 65536
    rnd = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 1)
    names = []
    for name, tail in TAILS.items():
        buf = bytearray()
        for w in range(65536):
            buf += slot(bytes([w >> 8, w & 0xff]) + tail)
        fn = f"{out}_{name}.bin"
        open(fn, "wb").write(buf)
        names.append(fn)
    buf = bytearray()
    for _ in range(nrand):
        buf += slot(bytes(rnd.randrange(256) for _ in range(6)))
    fn = f"{out}_rnd.bin"
    open(fn, "wb").write(buf)
    names.append(fn)
    print(" ".join(names))


if __name__ == "__main__":
    main()
