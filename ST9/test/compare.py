#!/usr/bin/env python3
"""Compare MAME unidasm (st9/st9p) with Ghidra on a gen_corpus.py image, record by record.

    compare.py <corpus.bin> <unidasm.txt> <ghidra.txt> [label] [--show N]

Both listings are normalised (numbers to integers, case, spacing); the known oracle bugs listed
in the README are recognised and counted separately (see oracle_bug()). Differences are bucketed
by opcode and kind and printed with examples. Exit status 1 if any unexplained difference.
"""
import collections
import re
import sys

REC = 12

def chunk_files(path, suffix):
    import os
    if not os.path.isdir(path):
        return [(0, path)]
    files = []
    for f in sorted(os.listdir(path)):
        m = re.search(r"\.(\d{3})\.bin" + re.escape(suffix) + "$", f)
        if m:
            files.append((int(m.group(1)) * CHUNK, os.path.join(path, f)))
    return files


def parse_mame(path):
    """unidasm -norawbytes output, or a directory of per-chunk outputs <name>.NNN.bin.mame."""
    res = {}
    for base, f in chunk_files(path, ".mame"):
        lines = []
        for line in open(f):
            line = line.rstrip("\n")
            m = re.match(r"^(?:([0-9a-f]+)\s*:)?([0-9a-f]+): (.*)$", line)
            a = int(m.group(2), 16) + ((int(m.group(1), 16) << 16) if m.group(1) else 0)
            lines.append((a, m.group(3)))
        for i, (a, t) in enumerate(lines):
            if a % REC == 0:
                n = (lines[i + 1][0] if i + 1 < len(lines) else a + 1) - a
                res[base + a // REC] = (n, t)
    return res

CHUNK = 5461

def parse_ghidra(path):
    """A listing file, or a directory of per-chunk listings <name>.NNN.bin.txt."""
    res = {}
    for base, f in chunk_files(path, ".txt"):
        for line in open(f):
            a, n, t = line.rstrip("\n").split(" ", 2)
            a = int(a, 16)
            if a % REC == 0:
                res[base + a // REC] = (int(n), t)
    return res

NUM = re.compile(r"(?<![A-Za-z0-9_])(-?)(0x[0-9a-fA-F]+|[0-9][0-9a-fA-F]*h|\d+)(?![A-Za-z0-9_])")

def num(m):
    s = m.group(2)
    if s.startswith("0x"):
        v = int(s, 16)
    elif s.endswith("h"):
        v = int(s[:-1], 16)
    else:
        v = int(s)
    return str(-v if m.group(1) else v)

def norm(t):
    t = " ".join(t.split()).lower()
    if t.startswith(".byte") or t == "bad":
        return "BAD"
    mn, _, ops = t.partition(" ")
    ops = ops.replace(" ", "")
    ops = NUM.sub(num, ops)
    return (mn + " " + ops).strip()

KOPS = {0x0: "or", 0x1: "and", 0x2: "sbc", 0x3: "adc", 0x4: "add", 0x5: "sub", 0x6: "xor",
        0x8: "tcm", 0x9: "cp", 0xA: "tm", 0xF: "ld"}
XFAM = (0x07, 0x17, 0x27, 0x37, 0x47, 0x57, 0x67, 0x87, 0x97, 0xA7)


def reserved(raw, plus):
    """True if the encoding sets a bit the manual's opcode map fixes (to 0 or to 0001), or uses an
    ST9+ opcode on the ST9. MAME decodes most of these anyway (ignoring the bit)."""
    op, b1, b2 = raw[0], raw[1], raw[2]
    if op in XFAM:
        return (b1 & 1) == 0 and (b2 & 1) == 1
    if op == 0xEF:
        return (b1 & 1) == 1 and b1 not in (0x01, 0x31) or (b1 & 1) == 0 and (b2 & 1) == 1
    if op == 0xBF:
        return (b1 & 1) == 1 and b1 != 0x01
    if op in (0x2F, 0x36):
        return (b1 & 1) == 1 and (b1 & 0xF) != 1
    if op in (0x4F, 0x5F):
        return (b1 & 0x10) != 0
    if op == 0x56:
        return (b1 & 1) == 1 or (b2 & 0x11) != 0
    if op == 0x60:
        return (b1 & 0x10) == 0 and (b2 & 1) == 1
    if op == 0x73:
        return (b1 & 1) == 0 and (b2 & 1) == 1
    if op == 0x7E:
        return (b1 & 1) == 1 or (b2 & 1) == 1
    if op == 0x96:
        return (b1 & 1) == 1
    if op in (0xA6, 0xC3, 0xD5):
        return (b2 & 1) == 1
    if op == 0xBE:
        return (b1 & 1) == 1 and (b2 & 1) == 1
    if op == 0xF3:
        return (b1 & 1) == 1
    if op == 0xF6:
        return b1 != 0x01 and ((b1 & 0x11) != 0)
    if not plus and (op in (0x75, 0xB6, 0xB7, 0xD4) and (b1 & 1) == 1 or op == 0x3F
                     or op == 0x73 and (b1 & 1) == 1 or op == 0xF6 and b1 == 0x01):
        return True
    return False


SYSPAIRS = {0xE8: "RPR", 0xEC: "USPR", 0xEE: "SSPR"}


def pairname(v):
    """Name of a register pair byte (bit 0 ignored) as MAME prints it."""
    if (v >> 4) == 0xD:
        return "rr%d" % (v & 14)
    v &= 0xFE
    return SYSPAIRS.get(v, "RR%02X" % v)


def sb(v):
    return v - 256 if v & 0x80 else v


def oracle_model(raw, g):
    """Ghidra's (manual-conforming) decode rewritten the way MAME's known display bugs print it.
    Returns (category, text) or None."""
    op, b1, b2 = raw[0], raw[1], raw[2]
    mn, _, ops = g.partition(" ")
    parts = ops.split(",") if ops else []
    if op == 0x96:
        # MAME takes the K nibble and the (r) register from byte 1 (the RR byte) instead of byte 2
        k = KOPS.get(b1 >> 4)
        if k is None or b1 & 1:
            return "96 K/r read from byte 1", "BAD"
        return "96 K/r read from byte 1", "%sw (r%d),%s" % (k, b1 & 15, pairname(b1))
    if op == 0xA6:
        # MAME prints the whole K,r byte as the register number: (r<signed byte>)
        return "A6 (r) prints the K,r byte", "%s %s,(r%d)" % (mn, parts[0], sb(b1))
    if op == 0x06:
        # MAME prints only the high byte of the #NN immediate (it still consumes both bytes)
        imm = int(parts[1].lstrip("#"))
        return "06 #NN printed as one byte", "%s %s,#%d" % (mn, parts[0], imm >> 8)
    if op == 0xF2 and mn == "bld":
        # MAME swaps BLD's operands (manual: F2 58 B4 = BLD r4.5,r8.!2)
        d, s_ = parts
        neg = ".!" in s_
        s_ = s_.replace(".!", ".")
        if neg:
            d = d.replace(".", ".!")
        return "BLD operands swapped", "bld %s,%s" % (s_, d)
    if op == 0x8F and b1 in (0xC1, 0xC3):
        imm = int(parts[0].lstrip("#"))
        return "PUSHW #NN printed as one byte", "%s #%d" % (mn, imm >> 8)
    if op == 0x8F and b1 in (0x01, 0x03) and (b2 & 1) == 1:
        # PEA/PEAU NN(RR): both manuals give the offset low byte first; MAME reads it high first
        m = re.match(r"^(-?\d+)\((.*)\)$", parts[0])
        v = int(m.group(1)) & 0xFFFF
        return "PEA NN byte order", "%s %d(%s)" % (mn, ((v & 0xFF) << 8) | (v >> 8), m.group(2))
    if op == 0x73 and (b1 & 1) == 1 and mn in ("calls", "jps"):
        # MAME prints the CSR source register R as a pair name (without clearing bit 0)
        name = "rr%d" % (b2 & 15) if (b2 >> 4) == 0xD else SYSPAIRS.get(b2, "RR%02X" % b2)
        return "CALLS/JPS (R) printed as a pair", "%s (%s),%s" % (mn, name, parts[1])
    return None


def main():
    corpus, mame, ghidra = sys.argv[1:4]
    label = sys.argv[4] if len(sys.argv) > 4 and not sys.argv[4].startswith("--") else ""
    show = int(sys.argv[sys.argv.index("--show") + 1]) if "--show" in sys.argv else 4
    data = open(corpus, "rb").read()
    M, G = parse_mame(mame), parse_ghidra(ghidra)
    buckets = collections.OrderedDict()
    explained = collections.Counter()
    plus = "st9p" in label
    same = diff = 0
    for i in range(len(data) // REC):
        raw = data[i * REC:i * REC + 6]
        mn, mt = M.get(i, (0, "?"))
        gn, gt = G.get(i, (0, "?"))
        a, b = norm(mt), norm(gt)
        if a == b and (mn == gn or a == "BAD"):
            same += 1
            continue
        model = oracle_model(raw, b) if b != "BAD" or raw[0] == 0x96 else None
        if model and model[1] is not None and norm(model[1]) == a:
            explained[model[0]] += 1
            continue
        if b == "BAD" and a != "BAD" and reserved(raw, plus):
            explained["reserved bits set (MAME ignores them)"] += 1
            continue
        if a == "BAD" and b.startswith("eret"):
            explained["ERET (EF 31) missing from MAME"] += 1
            continue
        diff += 1
        kind = ("mame-bad" if a == "BAD" else "ghidra-bad" if b == "BAD" else
                "length" if a == b else "text")
        key = ("%02x" % raw[0], kind, a.split(" ")[0], b.split(" ")[0])
        buckets.setdefault(key, []).append((raw.hex(), mn, mt, gn, gt))
    print("%s: %d records, %d agree, %d explained, %d differ" % (label, same + sum(explained.values()) + diff, same,
                                                             sum(explained.values()), diff))
    for k, v in sorted(explained.items()):
        print("  explained: %-45s x%d" % (k, v))
    for key, ex in buckets.items():
        print("  %s %-10s mame=%-8s ghidra=%-8s x%d" % (key + (len(ex),)))
        for r in ex[:show]:
            print("      %s  mame[%d] %-34s ghidra[%d] %s" % r)
    return 1 if diff else 0

if __name__ == "__main__":
    sys.exit(main())
