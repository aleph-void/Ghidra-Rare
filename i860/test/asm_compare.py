#!/usr/bin/env python3
"""Compare Ghidra's disassembly of the assembler-enumerated corpus with its source.

  asm_compare.py <all.lst> <ghidra.txt>
Test instruction k is at address 8k; branch targets L_back = 0, L_fwd = 8 * count,
".+n"/".-n" relative to the instruction. fnop / d.fnop are the shrd r0,r0,r0 pseudo-ops.
"""
import re
import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from compare import norm_ops, GH_RE  # noqa: E402


def expected(i, src, count):
    mn, _, ops = src.partition(" ")
    if mn in ("fnop", "d.fnop"):
        return mn.replace("fnop", "shrd") + " r0,r0,r0"
    addr = 8 * i

    def tgt(m):
        s = m.group(0)
        if s == "L_back":
            return str(0)
        if s == "L_fwd":
            return str(8 * count)
        return str((addr + int(s[1:].replace("+", ""), 0)) & 0xffffffff)
    ops = re.sub(r"L_back|L_fwd|\.[+-]0x[0-9a-f]+|\.[+-]\d+", tgt, ops)
    return mn + " " + norm_ops(ops)


def main():
    src = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    gh = {}
    for line in open(sys.argv[2]):
        m = GH_RE.match(line.rstrip("\n"))
        if m:
            text = m.group(3).strip()
            if text.startswith("BAD"):
                gh[int(m.group(1), 16)] = None
            else:
                mn, _, ops = text.partition(" ")
                gh[int(m.group(1), 16)] = mn + " " + norm_ops(ops)
    bad = 0
    for i, s in enumerate(src):
        e = expected(i, s, len(src))
        g = gh.get(8 * i)
        if g != e:
            bad += 1
            if bad <= 40 or "--all" in sys.argv:
                print(f"  {8 * i:06x}  source: {s:32s} expected: {e:32s} ghidra: {g}")
    print(f"assembler corpus: {len(src) - bad}/{len(src)} instructions identical to the source")
    sys.exit(1 if bad else 0)


main()
