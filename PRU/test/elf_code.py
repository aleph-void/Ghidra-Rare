#!/usr/bin/env python3
"""Extract the executable sections of a PRU ELF into a flat code image.

Usage: elf_code.py <file.elf> <out.bin> <out.ranges>

out.bin   code memory image starting at code address 0 (gaps zero-filled),
          so offsets in it are code byte addresses (what Ghidra, objdump and
          dispru print).  GNU ld links .text at 0x20000000; the address is
          taken mod 0x40000 (16-bit word PC), as Ghidra's code space does.
out.ranges  one "start end name" line (hex, end exclusive) per section.
"""
import struct
import sys

SHF_EXECINSTR = 4
SHT_PROGBITS = 1


def main():
    data = open(sys.argv[1], "rb").read()
    assert data[:4] == b"\x7fELF" and data[4] == 1 and data[5] == 1, "need ELF32 LE"
    shoff, = struct.unpack_from("<I", data, 0x20)
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x2E)
    secs = [struct.unpack_from("<IIIIIIIIII", data, shoff + i * shentsize) for i in range(shnum)]
    stro = secs[shstrndx][4]

    def name(s):
        return data[stro + s[0]:data.index(b"\0", stro + s[0])].decode(errors="replace")

    img = bytearray()
    ranges = []
    for s in secs:
        if s[1] != SHT_PROGBITS or not s[2] & SHF_EXECINSTR or s[5] == 0:
            continue
        addr = s[3] % 0x40000
        body = data[s[4]:s[4] + s[5]]
        if len(img) < addr + len(body):
            img.extend(b"\0" * (addr + len(body) - len(img)))
        img[addr:addr + len(body)] = body
        ranges.append((addr, addr + len(body), name(s)))
    img.extend(b"\0" * (-len(img) % 4))
    open(sys.argv[2], "wb").write(img)
    with open(sys.argv[3], "w") as f:
        for a, e, n in ranges:
            f.write("%x %x %s\n" % (a, e, n))


if __name__ == "__main__":
    main()
