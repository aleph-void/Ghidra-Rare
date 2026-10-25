#!/usr/bin/env python3
"""Build a small original ST9 program for headless analysis and decompiler checks."""
import sys

out = sys.argv[1]
image = bytearray(0x28)


def put(offset, data):
    image[offset:offset + len(data)] = bytes.fromhex(data)


# The three fixed vectors: reset, divide-by-zero, top-level interrupt.
put(0x00, "000c 0027 0027")
# Initialise the system stack, call a function twice, compare its result, then loop.
put(0x0c, "bf ee 1f f0")       # ldw SSPR,#1ff0
put(0x10, "f5 20 05")          # ld R20,#5
put(0x13, "d2 00 23")          # call increment
put(0x16, "d2 00 23")          # call increment
put(0x19, "95 20 07")          # cp R20,#7
put(0x1c, "6b 03")             # jreq done
put(0x1e, "f5 21 ff")          # ld R21,#ff
put(0x21, "8b fe")             # done: jr done
put(0x23, "45 20 01")          # increment: add R20,#1
put(0x26, "46")                # ret
put(0x27, "d3")                # irq: iret

with open(out, "wb") as f:
    f.write(image)
