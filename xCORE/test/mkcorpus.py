#!/usr/bin/env python3
"""Build raw instruction corpora for the XS1 comparison against llvm-mc / libLLVM.
   mkcorpus.py <outdir>  -> w16.bin (every non-prefix halfword), w32.bin (4-byte items)"""
import os, random, struct, sys
out = sys.argv[1]
os.makedirs(out, exist_ok=True)
words = [w for w in range(65536) if (w >> 11) != 0x1f and (w >> 10) != 0x3c]
open(os.path.join(out, 'w16.bin'), 'wb').write(b''.join(struct.pack('<H', w) for w in words))
items = []
for a in (0xf800, 0xfeee, 0xfefe, 0xf9b5, 0xfd7d, 0xfa2b, 0xf000, 0xf2aa, 0xf3ff, 0xffff, 0xffec):
    items += [(a, b) for b in range(65536)]
rnd = random.Random(1234)
for _ in range(300000):
    a = rnd.randint(0xf000, 0xffff)
    if (a >> 10) == 0x3d:
        a |= 0x800
    items.append((a, rnd.randint(0, 0xffff)))
open(os.path.join(out, 'w32.bin'), 'wb').write(b''.join(struct.pack('<HH', a, b) for a, b in items))
print(len(words), len(items))
