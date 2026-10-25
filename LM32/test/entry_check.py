#!/usr/bin/env python3
"""Every-entry decode test: each binutils opcode-table entry (gen_corpus.py entries.txt) must
decode in Ghidra, with operand bits all 0 and all 1, as the same mnemonic objdump prints for
that word (objdump prints the assembler aliases, e.g. "mv" for or rX,rY,r0). Catches shadowed
or missing constructors that random fuzzing hides ("both undefined" counts as agreement there).

  entry_check.py <entries.txt> <ghidra-table.txt> <objdump-table.txt>
"""
import re
import sys

entries = [l.split() for l in open(sys.argv[1])]
g = {}
for line in open(sys.argv[2]):
    off, hexw, text = line.rstrip("\n").split(" ", 2)
    g[int(off, 16)] = (hexw, text)
o = {}
for line in open(sys.argv[3]):
    m = re.match(r"\s*([0-9a-f]+):\t(?:[0-9a-f]{2} ){4}\s*\t?(.*)$", line)
    if m:
        o[int(m.group(1), 16)] = m.group(2).strip()
bad = 0
for k, (name, mask, val) in enumerate(entries):
    for i in (0, 1):
        off = (42 * k + i) * 4
        hexw, text = g[off]
        ot = o.get(off, "")
        gm = "BAD" if text.startswith("BAD") else text.split()[0]
        om = "*unknown*" if ot.startswith("*unknown*") or not ot else ot.split()[0]
        if gm == om and gm != "BAD":
            continue
        bad += 1
        print(f"FAIL   {name:10s} {hexw}: ghidra {text:30s} objdump {ot}")
print(f"every-entry decode: {len(entries)} entries, {bad} failures")
sys.exit(1 if bad else 0)
