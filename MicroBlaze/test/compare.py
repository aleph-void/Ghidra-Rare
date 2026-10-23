#!/usr/bin/env python3
"""Normalize and compare Ghidra and objdump MicroBlaze disassembly.

  compare.py <bits:32|64> <endian:be|le> <ghidra.txt> <objdump.txt> [maxshow]

Normalization:
  * objdump "// target" comments are dropped; ".long" and empty mnemonics mean "invalid";
    Ghidra "BAD" means invalid.
  * Ghidra's leading '_' (delay slot marker) is removed.
  * All numbers become integers (objdump prints decimal, Ghidra hex).
  * objdump prints the raw 16-bit field of branches; Ghidra prints the target address.
    The objdump side is converted to the target, combining a preceding imm (32-bit value)
    or imml (40-bit, or 64-bit with two imml) prefix exactly as UG984 describes.
"""
import collections
import re
import sys

bits, endian, gfile, ofile = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
maxshow = int(sys.argv[5]) if len(sys.argv) > 5 else 40
MASK = (1 << bits) - 1

PCREL = set("bri brid brlid breai breaid brealid".split())
for cc in "eq ne lt le gt ge".split():
    PCREL |= {"b%si" % cc, "b%sid" % cc, "bea%si" % cc, "bea%sid" % cc}
ABSB = set("brai braid bralid brki".split())


def sext(v, n):
    v &= (1 << n) - 1
    return v - (1 << n) if v >> (n - 1) else v


def num(tok):
    t = tok.strip()
    if re.fullmatch(r'-?0x[0-9a-fA-F]+', t):
        return int(t, 16)
    if re.fullmatch(r'-?\d+', t):
        return int(t)
    return t


def opnorm(x):
    x = x.strip()
    m = re.fullmatch(r'rpvr(0x[0-9a-fA-F]+|\d+)', x)
    if m:
        return "rpvr%d" % int(m.group(1), 0)
    return num(x)


def parse_ops(s):
    s = s.strip()
    return [opnorm(x) for x in s.split(",")] if s else []


def read_ghidra(path):
    res = {}
    for line in open(path):
        parts = line.rstrip("\n").split(" ", 2)
        if len(parts) < 3:
            continue
        off = int(parts[0], 16)
        b = bytes.fromhex(parts[1])
        if len(b) != 4:
            continue
        word = int.from_bytes(b, "big" if endian == "be" else "little")
        text = parts[2]
        if text.startswith("BAD"):
            res[off] = (word, ("INVALID",))
            continue
        m = text.split(" ", 1)
        mn = m[0].lstrip("_")
        res[off] = (word, (mn,) + tuple(parse_ops(m[1] if len(m) > 1 else "")))
    return res


def read_objdump(path):
    rows = []
    for line in open(path):
        m = re.match(r'\s*([0-9a-f]+):\t([0-9a-f]{8}) \t(.*)$', line.rstrip("\n"))
        if not m:
            continue
        rows.append((int(m.group(1), 16), int(m.group(2), 16), m.group(3)))
    res = {}
    for i, (off, word, text) in enumerate(rows):
        empty_mn = text.startswith("\t") or text == ""
        text = text.split("//")[0].strip()
        if text.startswith(".long") or not text or empty_mn:
            res[off] = (word, ("INVALID",))
            continue
        m = re.split(r'\s+', text, maxsplit=1)
        mn = m[0]
        ops = parse_ops(m[1] if len(m) > 1 else "")
        if mn in PCREL or mn in ABSB:
            # combine with prefixes (only the immediately preceding words)
            lo = word & 0xffff
            p1 = rows[i - 1][1] if i >= 1 and rows[i - 1][0] == off - 4 else None
            p2 = rows[i - 2][1] if i >= 2 and rows[i - 2][0] == off - 8 else None
            is_imm = lambda w: w is not None and (w & 0xffff0000) == 0xb0000000
            is_imml = lambda w: bits == 64 and w is not None and (w >> 24) == 0xb2
            if is_imml(p1) and is_imml(p2):
                val = sext(((p2 & 0xffffff) << 40) | ((p1 & 0xffffff) << 16) | lo, 64)
            elif is_imml(p1):
                val = sext(((p1 & 0xffffff) << 16) | lo, 40)
            elif is_imm(p1):
                val = sext(((p1 & 0xffff) << 16) | lo, 32)
            else:
                val = sext(lo, 16)
            tgt = (off + val) if mn in PCREL else val
            ops[-1] = tgt & MASK
        res[off] = (word, (mn,) + tuple(ops))
    return res


g = read_ghidra(gfile)
o = read_objdump(ofile)
total = match = 0
both_invalid = 0
groups = collections.Counter()
examples = collections.defaultdict(list)
for off in sorted(o):
    if off not in g:
        continue
    total += 1
    ow, ot = o[off]
    gw, gt = g[off]
    # Ghidra displays an absolute branch target as an address: compare modulo address size
    if gt[0] in ABSB and len(gt) > 1 and isinstance(gt[-1], int):
        gt = gt[:-1] + (gt[-1] & MASK,)
    if ot == gt:
        match += 1
        if ot == ("INVALID",):
            both_invalid += 1
        continue
    key = (ot[0], gt[0])
    groups[key] += 1
    if len(examples[key]) < 3:
        examples[key].append("%08x %08x  objdump: %-40s ghidra: %s" % (
            off, ow, " ".join(map(str, ot)), " ".join(map(str, gt))))

print("compared %d words: %d match (%.3f%%), of which %d both invalid; %d mismatches" % (
    total, match, 100.0 * match / max(total, 1), both_invalid, total - match))
for key, n in groups.most_common(maxshow):
    print("  %6d  objdump=%s ghidra=%s" % (n, key[0], key[1]))
    for e in examples[key]:
        print("            " + e)
