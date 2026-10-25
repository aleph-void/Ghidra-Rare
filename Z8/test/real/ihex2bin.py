#!/usr/bin/env python3
"""Intel HEX -> raw image from address 0 (gaps filled with FFh, like an erased EPROM).

    ihex2bin.py <in.hex> <out.bin>
"""
import sys

img = bytearray()
for line in open(sys.argv[1]):
    line = line.strip()
    if not line.startswith(":"):
        continue
    n, a, t = int(line[1:3], 16), int(line[3:7], 16), int(line[7:9], 16)
    if t != 0:
        continue
    data = bytes.fromhex(line[9:9 + 2 * n])
    if len(img) < a + n:
        img.extend(b"\xff" * (a + n - len(img)))
    img[a:a + n] = data
open(sys.argv[2], "wb").write(img)
