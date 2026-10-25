#!/usr/bin/env python3
"""Write a 64-byte SPC700 boot ROM for MAME's snes driver (local tracing only).

MAME's snes machine refuses to start without the SPC700 IPL ROM, which is Sony's copyrighted
code. This is an independent implementation of the documented boot/upload protocol (fullsnes,
"SNES APU Main CPU Communication Port" / boot ROM protocol) written for this test harness, so
the copyrighted ROM is never needed. MAME warns about the checksum and runs it.

  make_ipl.py <out-dir>      -> <out-dir>/snes/spc700.rom
"""
import os
import sys

prog = [
    ("reset", [0xcd, 0xef]),            # mov x,#$ef
    (None, [0xbd]),                     # mov sp,x
    (None, [0x8f, 0xaa, 0xf4]),         # mov $f4,#$aa     ready signature
    (None, [0x8f, 0xbb, 0xf5]),         # mov $f5,#$bb
    ("kick", [0x78, 0xcc, 0xf4]),       # cmp $f4,#$cc     wait for the CPU's $cc
    (None, [0xd0, "kick"]),             # bne kick
    (None, [0x2f, "block"]),            # bra block
    ("data", [0x7e, 0xf4]),             # cmp y,$f4        expected index arrived?
    (None, [0xd0, "other"]),            # bne other
    (None, [0xe4, 0xf5]),               # mov a,$f5
    (None, [0xcb, 0xf4]),               # mov $f4,y        acknowledge
    (None, [0xd7, 0x00]),               # mov [$00]+y,a    store
    (None, [0xfc]),                     # inc y
    (None, [0xd0, "data"]),             # bne data
    (None, [0xab, 0x01]),               # inc $01          next page
    (None, [0x2f, "data"]),             # bra data
    ("other", [0x10, "data"]),          # bpl data         index not reached yet
    (None, [0x7e, 0xf4]),               # cmp y,$f4        re-read (port may be mid-update)
    (None, [0x10, "data"]),             # bpl data
    ("block", [0xba, 0xf6]),            # movw ya,$f6      destination / jump address
    (None, [0xda, 0x00]),               # movw $00,ya
    (None, [0xba, 0xf4]),               # movw ya,$f4      a=port0, y=port1 (command)
    (None, [0xc4, 0xf4]),               # mov $f4,a        acknowledge
    (None, [0xdd]),                     # mov a,y
    (None, [0x5d]),                     # mov x,a
    (None, [0xf0, "jump"]),             # beq jump         command 0: execute
    ("first", [0xeb, 0xf4]),            # mov y,$f4        wait for index 0
    (None, [0xd0, "first"]),            # bne first
    (None, [0x2f, "data"]),             # bra data
    ("jump", [0x1f, 0x00, 0x00]),       # jmp [$0000+x]    (x = 0)
]
BASE = 0xffc0
addr, labels = BASE, {}
for lab, b in prog:
    if lab:
        labels[lab] = addr
    addr += len(b)
out, addr = bytearray(), BASE
for lab, b in prog:
    for i, x in enumerate(b):
        if isinstance(x, str):
            off = labels[x] - (addr + len(b))
            assert -128 <= off < 128, x
            out.append(off & 0xff)
        else:
            out.append(x)
    addr += len(b)
assert len(out) <= 62, len(out)
out += bytes(62 - len(out))
out += bytes([BASE & 0xff, BASE >> 8])     # reset vector
d = os.path.join(sys.argv[1], "snes")
os.makedirs(d, exist_ok=True)
open(os.path.join(d, "spc700.rom"), "wb").write(out)
print("wrote", os.path.join(d, "spc700.rom"), len(out), "bytes")
