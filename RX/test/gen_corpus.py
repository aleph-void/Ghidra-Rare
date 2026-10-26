#!/usr/bin/env python3
"""Slot corpora for the RX decode differential and the every-entry test.

    gen_corpus.py <outprefix> [nrandom] [seed]   -> prints the generated .bin files
    gen_corpus.py --every <out.bin>              -> one image with every slot of the corpora

Every slot is 16 bytes: one test instruction (an enumerated prefix followed by pseudo-random tail
bytes, at most 8 bytes in all) and then NOP (03h) padding, so a linear disassembler resynchronises
at every slot start. Corpora:
  c2_<t>      every first/second byte pair, tail set t (t = 0, 1, 2)
  c3_<xx>     every second/third byte after prefix xx (06, 75, 76, F9, FC, FD)
  c3z_<xx>    the same for 06 and FC with the fixed tail 10h 10h ...
  c4_<xxyy>   every third/fourth byte after the two-byte prefixes 7690, FD75, FD76, FD77
  rnd         nrandom random 8-byte instructions
"""
import random
import sys

SLOT = 16


def slot(prefix, rng):
    b = bytes(prefix) + bytes(rng.randrange(256) for _ in range(8 - len(prefix)))
    return b + b"\x03" * (SLOT - 8)


def corpora(nrandom, seed):
    out = {}
    for t in range(3):
        rng = random.Random(seed * 1000 + t)
        out[f"c2_{t}"] = b"".join(slot((a, b), rng) for a in range(256) for b in range(256))
    for p in (0x06, 0x75, 0x76, 0xF9, 0xFC, 0xFD):
        rng = random.Random(seed * 1000 + 100 + p)
        out[f"c3_{p:02x}"] = b"".join(slot((p, a, b), rng) for a in range(256) for b in range(256))
    for p in (0x06, 0xFC):
        # fixed tail 10h: Rd = R1 in a fourth opcode byte, low nibble 0 (DMOV.D, EMUL)
        out[f"c3z_{p:02x}"] = b"".join(bytes((p, a, b)) + b"\x10" * 5 + b"\x03" * (SLOT - 8)
                                       for a in range(256) for b in range(256))
    for p in ((0x76, 0x90), (0xFD, 0x75), (0xFD, 0x76), (0xFD, 0x77)):
        rng = random.Random(seed * 1000 + 200 + p[1])
        out[f"c4_{p[0]:02x}{p[1]:02x}"] = b"".join(slot(p + (a, b), rng) for a in range(256)
                                                   for b in range(256))
    rng = random.Random(seed * 1000 + 999)
    out["rnd"] = b"".join(slot((), rng) for _ in range(nrandom))
    return out


def main():
    if sys.argv[1] == "--every":
        c = corpora(4096, 1)
        open(sys.argv[2], "wb").write(b"".join(c[k] for k in sorted(c)))
        print(sys.argv[2])
        return
    prefix = sys.argv[1]
    nrandom = int(sys.argv[2]) if len(sys.argv) > 2 else 65536
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    for name, data in corpora(nrandom, seed).items():
        fn = f"{prefix}_{name}.bin"
        open(fn, "wb").write(data)
        print(fn)


if __name__ == "__main__":
    main()
