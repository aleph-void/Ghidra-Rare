#!/usr/bin/env python3
"""Write decode corpora: every 24-bit instruction word in a range, or random words.

  gen_corpus.py <out-prefix> <first-word> <count>        exhaustive range
  gen_corpus.py --random <out-prefix> <count> <seed>     random words

Writes <prefix>.le (32-bit little-endian words, for MAME unidasm) and <prefix>.be (24-bit
big-endian words, for test/ghidra-corpus.sh).
"""
import array
import random
import sys

if sys.argv[1] == "--random":
    prefix, count, seed = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    rnd = random.Random(seed)
    words = [rnd.getrandbits(24) for _ in range(count)]
else:
    prefix, first, count = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0)
    words = range(first, first + count)
a = array.array("I", words)
if sys.byteorder != "little":
    a.byteswap()
open(prefix + ".le", "wb").write(a.tobytes())
open(prefix + ".be", "wb").write(b"".join(w.to_bytes(3, "big") for w in words))
