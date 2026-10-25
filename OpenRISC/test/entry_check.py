#!/usr/bin/env python3
"""Every-entry decode test: each opcode-table entry (gen_corpus.py entries.txt, binutils 2.45
plus the arch-manual-only instructions) must decode in Ghidra, with operand bits 0 and 1, as an
instruction with the entry's mnemonic. Catches shadowed or missing constructors that random
fuzzing hides ("both undefined" counts as agreement there).

  entry_check.py <entries.txt> <ghidra-table.txt>      (ghidra-table.txt: DumpWords of table_*.bin)
"""
import sys

# binutils encodings that deliberately differ from the module (see README)
KNOWN = {
    ("l.muldu", "e000030d"): "binutils encodes secondary opcode 0xd; the architecture manual "
                             "and QEMU use 0xc (also in the table, must decode)",
}
entries = [l.split() for l in open(sys.argv[1])]
words = {}
for line in open(sys.argv[2]):
    off, hexw, text = line.rstrip("\n").split(" ", 2)
    words[int(off, 16)] = (hexw, text)
# gen_corpus.py writes 42 words per entry: value, value | free bits, 40 random fills
bad = 0
seen = 0
for k, (name, mask, val) in enumerate(entries):
    for i in (0, 1):
        hexw, text = words[(42 * k + i) * 4]
        mn = text.lstrip("_").split()[0] if not text.startswith("BAD") else "BAD"
        if mn == name:
            continue
        if (name, val) in KNOWN:
            print(f"known  {name:12s} {hexw}: {text}  ({KNOWN[(name, val)]})")
            continue
        if i == 1 and name.endswith(".d") and text.startswith("BAD"):
            # all operand bits set selects register pairs r31,r32/r33, which do not exist
            print(f"known  {name:12s} {hexw}: {text}  (register pair beyond r31)")
            continue
        bad += 1
        print(f"FAIL   {name:12s} {hexw}: ghidra {text}")
    seen += 1
print(f"every-entry decode: {seen} entries, {bad} failures")
sys.exit(1 if bad else 0)
