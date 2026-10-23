#!/usr/bin/env python3
"""Normalize and compare PRU disassembly from Ghidra, GNU objdump and TI dispru.

Usage:
  compare.py --gnu gnu.txt --ghidra g_v3.txt [--ti ti_v3.txt] [--version 3]
             [--mismatches N] [--report out.txt]

All three listings are reduced to a canonical form:
  * lower case, operands separated by ", ", no '&'
  * registers as rN / rN.bK / rN.wK (binutils' sp/ra/fp -> r2/r3/r4)
  * immediates in decimal, constant-table operands as cN
  * code addresses as absolute *byte* addresses ("@<dec>"), so Ghidra's
    word-addressed targets, objdump's byte targets and TI's "$+off" agree
  * undecodable words as "UNDEF"
"Exact" compares that form directly; "semantic" additionally expands the
pseudo-ops (nop, mov, ret, call, wbs, wbc, zero, fill) into their base
instructions so a pseudo-op choice difference is not counted.
"""
import argparse
import collections
import re
import sys

ALIAS = {"sp": "r2", "ra": "r3", "fp": "r4"}
CODE_BYTES = 0x40000  # 16-bit word PC
ADDR_FIRST = {"jmp", "call", "qbgt", "qbge", "qblt", "qble", "qbeq", "qbne", "qba",
              "qbbs", "qbbc", "loop", "iloop"}
BURSTS = {"lbbo", "sbbo", "lbco", "sbco", "xin", "xout", "xchg", "sxin", "sxout",
          "sxchg", "zero", "fill"}


def load(path):
    """offset(int) -> (word(int), raw text)"""
    d = {}
    for line in open(path, errors="replace"):
        p = line.rstrip("\n").split(None, 2)
        if len(p) < 2:
            continue
        try:
            off = int(p[0].rstrip(":"), 16)
            word = int(p[1], 16)
        except ValueError:
            continue
        d[off] = (word, p[2] if len(p) > 2 else "")
    return d


def load_gnu(path):
    d = {}
    for line in open(path, errors="replace"):
        m = re.match(r"\s*([0-9a-f]+):\s+([0-9a-f]{8})\s+(.*)$", line)
        if not m:
            continue
        b = bytes.fromhex(m.group(2))
        # objdump -b binary prints the bytes in file order
        word = int.from_bytes(b, "little")
        d[int(m.group(1), 16)] = (word, m.group(3).strip())
    return d


def reg(tok):
    t = tok.lower().lstrip("&")
    m = re.fullmatch(r"(r\d+|sp|ra|fp)((?:\.[bw]\d)?)", t)
    if not m:
        return None
    return ALIAS.get(m.group(1), m.group(1)) + m.group(2)


def num(tok):
    t = tok.strip().lower()
    try:
        return int(t, 0)
    except ValueError:
        return None


def canon(src, text, off):
    text = text.strip()
    if not text or text.startswith("BAD") or text.startswith(".word") or \
            re.fullmatch(r"0x[0-9a-f]+", text) or text == "(bad)":
        return "UNDEF"
    parts = text.split(None, 1)
    mn = parts[0].lower()
    if mn == "loopi":          # TI dispru spelling of ILOOP
        mn = "iloop"
    ops = [o.strip() for o in parts[1].split(",")] if len(parts) > 1 else []
    if src == "ti" and mn in ("jal", "jmp") and ops and ops[-1] == "":
        ops[-1] = "0"          # dispru prints the (empty) section symbol at address 0
    ops = [o for o in ops if o != ""]
    res = []
    for i, o in enumerate(ops):
        lo = o.lower().strip()
        if i == 0 and mn in ADDR_FIRST or (mn in ("jal",) and i == 1):
            # code address operand?
            if src == "ti" and lo.startswith("$"):
                rel = int(lo[1:].replace("+", ""), 0)
                if rel >= 1 << 63:
                    rel -= 1 << 64
                res.append("@%d" % ((off + rel) % CODE_BYTES))
                continue
            n = num(lo.split()[0]) if lo else None
            if n is not None:
                res.append("@%d" % (n % CODE_BYTES))
                continue
        r = reg(lo)
        if r is not None:
            res.append(r)
            continue
        m = re.fullmatch(r"c(\d+)", lo)
        if m and mn in ("lbco", "sbco"):
            res.append("c%d" % int(m.group(1)))
            continue
        if src == "gnu" and mn in ("lbco", "sbco") and i == 1:
            res.append("c%d" % int(lo))
            continue
        if lo.startswith("b") and re.fullmatch(r"b[0-3]", lo):   # TI "bn" count
            res.append("r0." + lo)
            continue
        n = num(lo)
        if n is not None:
            res.append(str(n))
            continue
        res.append(lo)
    # TI quirks
    if src == "ti":
        if mn == "qba":
            res = res[:1]
        if mn == "not":
            res = res[:2]
        if mn in BURSTS and res and res[-1].isdigit() and 125 <= int(res[-1]) <= 128:
            res[-1] = "r0.b%d" % (int(res[-1]) - 125)
    return mn + (" " + ", ".join(res) if res else "")


def expand(c, off):
    """Expand pseudo-ops into their base instruction (canonical form in/out)."""
    if c == "UNDEF":
        return c
    p = c.split(" ", 1)
    mn = p[0]
    ops = p[1].split(", ") if len(p) > 1 else []
    if mn == "nop":
        return "or r0, r0, r0"
    if mn == "mov":
        return "or %s, %s, 0" % (ops[0], ops[1])
    if mn == "ret":
        return "jmp r3.w2"
    if mn == "call":
        return "jal r3.w2, %s" % ops[0]
    if mn in ("wbc", "wbs"):
        return "%s @%d, %s" % ("qbbs" if mn == "wbc" else "qbbc", off % CODE_BYTES, ", ".join(ops))
    if mn in ("zero", "fill"):
        return "xin %d, %s" % (255 if mn == "zero" else 254, ", ".join(ops))
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gnu")
    ap.add_argument("--ghidra", required=True)
    ap.add_argument("--ti")
    ap.add_argument("--version", default="3")
    ap.add_argument("--mismatches", type=int, default=15)
    ap.add_argument("--label", default="")
    a = ap.parse_args()

    g = load(a.ghidra)
    lines = []
    summary = {}

    def cmp(refname, ref, refsrc):
        exact = sem = tot = 0
        ref_undef_g_def = collections.Counter()
        g_undef_ref_def = collections.Counter()
        mism = collections.Counter()
        examples = {}
        for off, (word, rt) in sorted(ref.items()):
            if off not in g:
                continue
            gw, gt = g[off]
            if gw != word:
                print("word mismatch at %x: %08x vs %08x" % (off, gw, word), file=sys.stderr)
                continue
            rc = canon(refsrc, rt, off)
            gc = canon("ghidra", gt, off)
            if rc == "UNDEF" and gc == "UNDEF":
                continue
            if rc == "UNDEF":
                ref_undef_g_def[gc.split()[0]] += 1
                examples.setdefault(("extra", gc.split()[0]), "%08x  %s=%s | ghidra=%s" % (word, refname, rt, gt))
                continue
            tot += 1
            if gc == "UNDEF":
                g_undef_ref_def[rc.split()[0]] += 1
                examples.setdefault(("missing", rc.split()[0]), "%08x  %s=%s | ghidra=%s" % (word, refname, rt, gt))
                continue
            if rc == gc:
                exact += 1
                sem += 1
            elif expand(rc, off) == expand(gc, off):
                sem += 1
                mism[("pseudo", rc.split()[0], gc.split()[0])] += 1
                examples.setdefault(("pseudo", rc.split()[0], gc.split()[0]),
                                    "%08x  %s=%s | ghidra=%s" % (word, refname, rt, gt))
            else:
                k = ("diff", rc.split()[0], gc.split()[0])
                mism[k] += 1
                examples.setdefault(k, "%08x  %s=%s | ghidra=%s\n      canon: %s | %s" % (
                    word, refname, rt, gt, rc, gc))
        lines.append("== %s v%s vs %s: %d words both decode-or-ref-decodes" % (a.label, a.version, refname, tot))
        if tot:
            lines.append("   exact match    : %d / %d  (%.2f%%)" % (exact, tot, 100.0 * exact / tot))
            lines.append("   semantic match : %d / %d  (%.2f%%)" % (sem, tot, 100.0 * sem / tot))
        miss = sum(g_undef_ref_def.values())
        lines.append("   %s decodes, Ghidra UNDEF: %d %s" % (refname, miss, dict(g_undef_ref_def)))
        lines.append("   Ghidra decodes, %s UNDEF: %d %s" % (refname, sum(ref_undef_g_def.values()), dict(ref_undef_g_def)))
        for k, n in mism.most_common(a.mismatches):
            lines.append("   %-7s %-6s->%-6s x%-5d e.g. %s" % (k[0], k[1], k[2], n, examples[k]))
        shown = 0
        for k, v in examples.items():
            if k[0] in ("missing", "extra") and shown < a.mismatches:
                lines.append("   %-7s %-6s e.g. %s" % (k[0], k[1], v))
                shown += 1
        summary[refname] = (exact, sem, tot)

    if a.gnu:
        cmp("gnu", load_gnu(a.gnu), "gnu")
    if a.ti:
        cmp("ti", load(a.ti), "ti")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
