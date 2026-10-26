#!/usr/bin/env python3
"""Slot corpora for the DSP56156 decode differential (two words per slot: the instruction and
an extension word). Writes <dir>/<name>.bin (Ghidra: 16-bit big-endian words) and
<dir>/<name>.m.bin (MAME unidasm -arch dsp56156: 16-bit little-endian words) and prints the
.bin paths. Each image holds 16,384 slots (32,768 words).

    gen_corpus156.py <dir> [nrandom] [seed]
    gen_corpus156.py --every <file.bin>    every-entry images (Ghidra format), prints paths

Corpora:
  t0_0..t0_3  every first word with tail 1234h (R2+xx: parallel ALU form)
  t1_0..t1_3  every first word with tail 3C85h (R2+xx: MOVE(C) form)
  t2_0..t2_3  every first word with tail 9212h (BFCHG upper byte; R2+xx parallel)
  rnd*        random first and second words
"""
import os
import random
import struct
import sys

TAILS = [0x1234, 0x3c85, 0x9212]
SLOTS = 16384


def write(d, name, slots, mame=True):
    with open("%s/%s.bin" % (d, name), "wb") as g:
        for w, e in slots:
            g.write(struct.pack(">HH", w, e))
    if mame:
        with open("%s/%s.m.bin" % (d, name), "wb") as m:
            for w, e in slots:
                m.write(struct.pack("<HH", w, e))
    return "%s/%s.bin" % (d, name)


def main():
    if sys.argv[1] == "--every":
        base = sys.argv[2][:-4] if sys.argv[2].endswith(".bin") else sys.argv[2]
        tails = TAILS + [0x0308, 0x0300, 0x3c00, 0x5000, 0x30f0, 0x1880, 0x7080, 0x0011]
        slots = [(w, t) for t in tails for w in range(65536)]
        # X:(R2+xx) / P:(R2+xx) and bit-field second words: every second word
        slots += [(0x0500 | (t & 0xff), t) for t in range(65536)]
        slots += [(0x1400 | (t & 0xff), t) for t in range(65536)]
        d = os.path.dirname(os.path.abspath(base))
        for k in range(0, len(slots), SLOTS):
            print(write(d, "%s.%d" % (os.path.basename(base), k // SLOTS), slots[k:k + SLOTS], False))
        return
    d = sys.argv[1]
    nr = int(sys.argv[2]) if len(sys.argv) > 2 else 65536
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    os.makedirs(d, exist_ok=True)
    files = []
    for ti, t in enumerate(TAILS):
        for part in range(4):
            files.append(write(d, "t%d_%d" % (ti, part), [(w, t) for w in range(part * SLOTS, (part + 1) * SLOTS)]))
    rnd = random.Random(seed)
    for part in range(0, nr, SLOTS):
        files.append(write(d, "rnd%d" % (part // SLOTS),
                           [(rnd.getrandbits(16), rnd.getrandbits(16)) for _ in range(min(SLOTS, nr - part))]))
    print("\n".join(files))


if __name__ == "__main__":
    main()
