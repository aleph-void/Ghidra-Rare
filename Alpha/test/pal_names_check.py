#!/usr/bin/env python3
"""Compare the module's CALL_PAL function names with MAME unidasm's per-OS tables.

  pal_names_check.py <ghidra-dump.txt> <unidasm-output.txt> <os>

Both disassemble pal.bin (CALL_PAL 0x00-0x3f and 0x80-0xbf). MAME prints
"call_pal <name>" or "unknown call_pal"; the module prints the name as the mnemonic or
"CALL_PAL 0x..". GNU spellings used for UNIX (rduniq/wruniq) count as MAME's rdunique/wrunique.
"""
import re, sys

SAME = {("rduniq", "rdunique"), ("wruniq", "wrunique")}
g = {}
for line in open(sys.argv[1]):
    off, w, text = line.split(None, 2)
    g[int(w, 16)] = text.strip().lower()
m = {}
for line in open(sys.argv[2]):
    mm = re.match(r"\s*[0-9a-f]+:\s+([0-9a-f]{8})\s+(.*)$", line)
    if mm:
        m[int(mm.group(1), 16)] = mm.group(2).strip()
ok = bad = 0
for w in sorted(g):
    gt, mt = g[w], m.get(w, "")
    gname = None if gt.startswith("call_pal") else gt
    mname = mt.split()[-1] if mt.startswith("call_pal") else None
    if gname == mname or (gname, mname) in SAME:
        ok += 1
    else:
        bad += 1
        print(f"  0x{w:02x}: ghidra {gt!r} mame {mt!r}")
print(f"{sys.argv[3]} CALL_PAL names: {ok} agree, {bad} differ")
