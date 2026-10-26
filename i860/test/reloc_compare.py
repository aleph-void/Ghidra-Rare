#!/usr/bin/env python3
"""Compare the words Ghidra relocated (I860RelocDump output) with GNU ld's link of the same
object at the same addresses.  reloc_compare.py <reloc.ghidra> <reloc.elf> <readelf-r.txt>"""
import re
import struct
import sys


def elf_sections(path):
    d = open(path, "rb").read()
    shoff, = struct.unpack_from("<I", d, 0x20)
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 0x2e)
    hdrs = [struct.unpack_from("<IIIIIIIIII", d, shoff + i * shentsize) for i in range(shnum)]
    strtab = hdrs[shstrndx]
    names = {}
    for h in hdrs:
        n = d[strtab[4] + h[0]:].split(b"\0", 1)[0].decode()
        names[n] = (h[3], h[4], h[5])          # addr, offset, size
    return d, names


ghidra_secs, ghidra_words = {}, {}
for line in open(sys.argv[1]):
    f = line.split()
    if f[0] == "section":
        ghidra_secs[f[1]] = int(f[2], 16)
    else:
        ghidra_words[int(f[1], 16)] = int(f[2], 16)
data, ld_secs = elf_sections(sys.argv[2])
sec = None
n = bad = 0
for line in open(sys.argv[3]):
    m = re.match(r"Relocation section '\.rela(\S+)'", line)
    if m:
        sec = m.group(1)
        continue
    m = re.match(r"^([0-9a-f]{8})\s+[0-9a-f]{8}\s+(R_860_\w+)", line)
    if not m:
        continue
    off, typ = int(m.group(1), 16), m.group(2)
    addr = ghidra_secs[sec] + off
    la, lo, _ = ld_secs[sec]
    assert la == ghidra_secs[sec], (sec, la, ghidra_secs[sec])
    ld_word, = struct.unpack_from("<I", data, lo + off)
    g = ghidra_words.get(addr)
    n += 1
    if g != ld_word:
        bad += 1
        print(f"  {sec}+{off:#06x} {typ:14s} ghidra {g:#010x}  ld {ld_word:#010x}")
print(f"relocations: {n - bad}/{n} words identical to GNU ld")
sys.exit(1 if bad else 0)
