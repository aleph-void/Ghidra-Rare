#!/usr/bin/env python3
"""Intel HEX -> raw image from address 0 (gaps filled with FFh, like an erased EPROM).

    ihex2bin.py [--crop] <in.hex> <out.bin>
    --crop: start the image at the lowest address instead and print that address
"""
import sys

crop = sys.argv[1] == "--crop"
args = sys.argv[2:] if crop else sys.argv[1:]
img = bytearray()
lo = None
for line in open(args[0]):
    line = line.strip()
    if not line.startswith(":"):
        continue
    n, a, t = int(line[1:3], 16), int(line[3:7], 16), int(line[7:9], 16)
    if t != 0:
        continue
    data = bytes.fromhex(line[9:9 + 2 * n])
    lo = a if lo is None else min(lo, a)
    if len(img) < a + n:
        img.extend(b"\xff" * (a + n - len(img)))
    img[a:a + n] = data
if crop:
    img = img[lo:]
    print(hex(lo))
open(args[1], "wb").write(img)
