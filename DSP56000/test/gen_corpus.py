#!/usr/bin/env python3
"""Slot corpora for the DSP56000 decode differential (two words per slot: the instruction and
an extension word). Writes <dir>/<name>.bin (the Ghidra image) and <dir>/<name>.m.bin (the
MAME unidasm -arch dsp56000 image), both 4 bytes per word, big-endian, high byte zero, and
prints the .bin paths.

    gen_corpus.py <dir> [nrandom] [seed]
    gen_corpus.py --every <file.bin>      every-entry image (Ghidra format only)

Corpora:
  np00..npf1 every word with bits 23..16 = 00h..0Fh (the non-parallel instructions, MOVEP
             and the class II moves), 32,768 slots per file (P memory holds 64K words)
  pm00..pm11 every parallel-move field (bits 23..8 = 1000h..FFFFh) with two different data ALU
             opcodes each
  alu        every data ALU opcode with 32 representative move fields
  rnd        random instruction words and extension words
"""
import random
import struct
import sys

EXTS = [0x00a5c3, 0x000031, 0x001234, 0x00ffc5]


def write(d, name, slots):
    with open("%s/%s.bin" % (d, name), "wb") as g, open("%s/%s.m.bin" % (d, name), "wb") as m:
        for w, e in slots:
            g.write(struct.pack(">II", w, e))
            m.write(struct.pack(">II", w, e))
    return "%s/%s.bin" % (d, name)


def main():
    if sys.argv[1] == "--every":
        # several images of at most 32,768 slots: <file>.0.bin, <file>.1.bin, ...
        slots = [((hb << 16) | lo, EXTS[lo & 3]) for hb in range(16) for lo in range(65536)]
        slots += [((m << 8) | ((m * 13 + 7) & 0xff), 0x001234) for m in range(0x1000, 0x10000)]
        slots += [((m << 8) | ((m * 29 + 101) & 0xff), 0x001234) for m in range(0x1000, 0x10000)]
        slots += [((m << 8) | a, 0x001234) for a in range(256) for m in (0x2000, 0x2400, 0x44f4, 0xf098)]
        base = sys.argv[2][:-4] if sys.argv[2].endswith(".bin") else sys.argv[2]
        for k in range(0, len(slots), 32768):
            with open("%s.%d.bin" % (base, k // 32768), "wb") as g:
                for w, e in slots[k:k + 32768]:
                    g.write(struct.pack(">II", w, e))
            print("%s.%d.bin" % (base, k // 32768))
        return
    d = sys.argv[1]
    nr = int(sys.argv[2]) if len(sys.argv) > 2 else 65536
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    import os
    os.makedirs(d, exist_ok=True)
    files = []
    for hb in range(16):
        for half in (0, 1):
            files.append(write(d, "np%x%d" % (hb, half), [((hb << 16) | lo, EXTS[(lo >> 4) & 3])
                                                         for lo in range(half * 32768, half * 32768 + 32768)]))
    for k, (mul, add) in enumerate(((13, 7), (29, 101))):
        ms = list(range(0x1000, 0x10000))
        for part in range(2):
            chunk = ms[part * 30720:(part + 1) * 30720]
            files.append(write(d, "pm%d%d" % (k, part), [((m << 8) | ((m * mul + add) & 0xff), EXTS[(m >> k) & 3]) for m in chunk]))
    reps = [0x2000, 0x2400, 0x2104, 0x204b, 0x44f4, 0x4458, 0x5470, 0x4cb0, 0x4858, 0x4a92,
            0x149a, 0x135c, 0x0918, 0x089c, 0xf098, 0xc098, 0xd080, 0xb131, 0xebbd, 0x8094,
            0x2a33, 0x3312, 0x223a, 0x56f4, 0x5ef0, 0x10b0, 0x1bf4, 0x2041, 0x6a00, 0x7930,
            0x9fff, 0x0880]
    files.append(write(d, "alu", [((m << 8) | a, 0x001234) for a in range(256) for m in reps]))
    rnd = random.Random(seed)
    for part in range(0, nr, 32768):
        files.append(write(d, "rnd%d" % (part // 32768), [(rnd.getrandbits(24), rnd.getrandbits(24)) for _ in range(min(32768, nr - part))]))
    print("\n".join(files))


if __name__ == "__main__":
    main()
