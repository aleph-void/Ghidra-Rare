#!/usr/bin/env python3
"""Decode-test corpus for TMS320C2x/C5x.

    gen_corpus.py <family c2x|c5x> <endian be|le> <outdir> [nrandom] [seed]

Records are 4 words: the instruction word, a second (immediate) word, and two NOP padding words, so
that a linear sweep (MAME unidasm) resynchronises at every record start whatever length it decoded
(instructions are at most 2 words). Records: every 16-bit first word with a random second word,
then <nrandom> fully random records. Writes <outdir>/all.bin plus 16384-record chunks
<outdir>/chunks/cNN.bin (one 64K-word program space each) and <outdir>/records.txt (hex words).
"""
import os
import random
import struct
import sys

fam, end, out = sys.argv[1], sys.argv[2], sys.argv[3]
nrand = int(sys.argv[4]) if len(sys.argv) > 4 else 32768
rng = random.Random(int(sys.argv[5]) if len(sys.argv) > 5 else 1)
nop = 0x5500 if fam == "c2x" else 0x8B00
fmt = ">H" if end == "be" else "<H"
recs = [(w, rng.randrange(65536)) for w in range(65536)]
recs += [(rng.randrange(65536), rng.randrange(65536)) for _ in range(nrand)]
os.makedirs(os.path.join(out, "chunks"), exist_ok=True)


def enc(r):
    return b"".join(struct.pack(fmt, x) for x in (r[0], r[1], nop, nop))


with open(os.path.join(out, "all.bin"), "wb") as f:
    for r in recs:
        f.write(enc(r))
CH = 16384
for i in range(0, len(recs), CH):
    with open(os.path.join(out, "chunks", "c%02d.bin" % (i // CH)), "wb") as f:
        for r in recs[i:i + CH]:
            f.write(enc(r))
with open(os.path.join(out, "records.txt"), "w") as f:
    for r in recs:
        f.write("%04x %04x\n" % r)
