#!/usr/bin/env python3
"""Compare Ghidra's disassembly of a VisualDSP++ executable with the program's assembler source:

  src_compare.py <program.dxe> <program.asm> <include.h> <prefix.dis>

Every instruction statement of the source's program-memory sections is placed at its address
(section base from the DXE, one 24-bit word per statement), its symbols, #defines and
LENGTH() are replaced by the values the linker used (DXE symbol table), and the statement is
compared with the instruction auto-analysis created there (ADSPRealCheck .dis), using the
normalisation of test/compare.py.  Statements at addresses analysis did not reach are counted
as "not reached".  Exit status 1 if any reached statement differs.
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import compare  # noqa: E402


def dxe(path):
    d = open(path, "rb").read()
    shoff, = struct.unpack_from("<I", d, 32)
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 46)
    secs = []
    for i in range(shnum):
        secs.append(struct.unpack_from("<10I", d, shoff + i * shentsize))
    so = secs[shstrndx][4]

    def cstr(base, o):
        e = d.index(b"\0", base + o)
        return d[base + o:e].decode("latin1")
    names = [cstr(so, s[0]) for s in secs]
    syms = {}
    for s in secs:
        if s[1] != 2:
            continue
        stro = secs[s[6]][4]
        for o in range(s[4], s[4] + s[5], s[9] or 16):
            nm, value, size, info, other, shndx = struct.unpack_from("<IIIBBH", d, o)
            if nm and shndx < len(secs):
                try:
                    syms[cstr(stro, nm).lower()] = (value, size)
                except ValueError:
                    pass
    sections = {names[i]: s[3] for i, s in enumerate(secs) if s[1] == 1}
    return sections, syms


def strip_comments(t):
    t = re.sub(r"/\*.*?\*/", " ", t, flags=re.S)
    return re.sub(r"//[^\n]*", " ", t)


def defines(text):
    out = {}
    for m in re.finditer(r"^[ \t]*#[ \t]*define[ \t]+(\w+)[ \t]+(\S+)", text, flags=re.M):
        out[m.group(1).lower()] = m.group(2)
    return out


def number(tok):
    t = tok.lower()
    if t.startswith("b#"):
        return int(t[2:], 2)
    if t.startswith("h#"):
        return int(t[2:], 16)
    if t.startswith("0x"):
        return int(t, 16)
    return int(t)


def resolve(stmt, defs, syms):
    s = stmt
    s = re.sub(r"(?i)\bLENGTH\s*\(\s*(\w+)\s*\)", lambda m: str(syms[m.group(1).lower()][1]), s)
    for _ in range(3):
        s = re.sub(r"\b[A-Za-z_]\w*\b", lambda m: str(defs.get(m.group(0).lower(), m.group(0))), s)
    regs = set("AX0 AX1 MX0 MX1 AY0 AY1 MY0 MY1 SI SE AR MR0 MR1 MR2 SR0 SR1 AF MF SB PX MR SR "
               "ASTAT MSTAT SSTAT IMASK ICNTL CNTR IFC OWRCNTR RX0 TX0 RX1 TX1 PMOVLAY DMOVLAY "
               "TOPPCSTACK".split() + [f"{c}{i}" for c in "IML" for i in range(8)])

    def sym(m):
        w = m.group(0)
        if w.upper() in regs or w.lower() not in syms:
            return w
        return str(syms[w.lower()][0])
    s = re.sub(r"\b[A-Za-z_]\w*\b", sym, s)
    s = re.sub(r"(-?)(\d*\.\d+)[rR]\b", lambda m: str(int(float(m.group(1) + m.group(2)) * 32768)), s)
    s = re.sub(r"(?<![\w#])(b#[01]+|h#[0-9a-fA-F]+|0x[0-9a-fA-F]+|\d+)\b", lambda m: str(number(m.group(0))), s)
    s = re.sub(r"(?i)\bBY\s*\(\s*(-?\d+)\s*\)", r"BY \1", s)
    # constant arithmetic inside DM(...) / IO(...) and immediate expressions
    s = re.sub(r"(?<![\w])(\d+)\s*([+-])\s*(\d+)\b(?!\s*\+\s*C)", lambda m: str(int(m.group(1)) + (1 if m.group(2) == "+" else -1) * int(m.group(3))), s)
    return s


def norm_src(s):
    s = s.upper()
    cl = compare.clauses(s)
    if cl and all(re.match(r"(ENA|DIS) ", c) for c in cl):
        cl = [" ".join(cl)]
    if cl and all(re.match(r"(POP|PUSH) ", c) for c in cl):
        cl = [" ".join(cl)]
    t = ", ".join(cl)
    t = re.sub(r"\bPASS ", "", t)
    return compare.finish(compare.clauses(t))


def variants(s):
    """the source's negative immediates as the 16- and 14-bit fields hold them"""
    yield s
    neg = re.compile(r"(?<!BY )(?<![\w(])-(\d+)")
    if neg.search(s):
        yield neg.sub(lambda m: str(-int(m.group(1)) & 0xffff), s)
        yield neg.sub(lambda m: str(-int(m.group(1)) & 0x3fff), s)


def main():
    prog, src, inc, disf = sys.argv[1:5]
    sections, syms = dxe(prog)
    text = open(src, encoding="latin1").read()
    defs = defines(open(inc, encoding="latin1").read())
    defs.update(defines(text))
    text = strip_comments(re.sub(r"^\s*#.*$", "", text, flags=re.M))
    dis = {}
    for line in open(disf):
        a, w, t = line.rstrip("\n").split(" ", 2)
        dis[int(a, 16)] = t
    # place each program-memory section of the source: from the first label it defines (linker
    # symbol value minus the label's statement index), or at 0 for the interrupt vector table
    base = {}
    sec, idx = None, 0
    for stmt in text.split(";"):
        stmt = stmt.strip()
        m = re.match(r"(?is)\.SECTION\s*/\s*(\w+)\s+(\w+)", stmt)
        if m:
            sec = m.group(2) if m.group(1).upper() == "PM" else None
            idx = base.get(("n", sec), 0)
            continue
        if sec is None:
            continue
        while True:
            m = re.match(r"(?s)^([A-Za-z_]\w*)\s*:(?!=)\s*(.*)$", stmt)
            if not m:
                break
            if sec not in base and m.group(1).lower() in syms:
                base[sec] = syms[m.group(1).lower()][0] - idx
            stmt = m.group(2)
        if stmt and not stmt.startswith("."):
            idx += 1
            base[("n", sec)] = idx
    for k in list(base):
        if isinstance(k, tuple) and k[1] not in base and k[1] and re.search("(?i)int|vect", k[1]):
            base[k[1]] = 0
    sections = {k: v for k, v in base.items() if not isinstance(k, tuple)}
    addr = None
    stats = {"identical": 0, "different": 0, "not reached": 0}
    diffs = []
    for stmt in text.split(";"):
        stmt = stmt.strip()
        m = re.match(r"(?is)\.SECTION\s*/\s*(\w+)\s+(\w+)", stmt)
        if m:
            addr = sections.get(m.group(2)) if m.group(1).upper() == "PM" else None
            continue
        while True:
            m = re.match(r"(?s)^([A-Za-z_]\w*)\s*:(?!=)\s*(.*)$", stmt)
            if not m:
                break
            stmt = m.group(2)
        if not stmt or stmt.startswith(".") or addr is None:
            continue
        r = resolve(" ".join(stmt.split()), defs, syms)
        g = dis.get(addr)
        if g is None:
            stats["not reached"] += 1
            if os.environ.get("SHOW_UNREACHED"):
                print(f"   not reached {addr:04x} {stmt!r}")
        else:
            gn = compare.norm_ghidra(g)
            if any(norm_src(v) == gn for v in variants(r)):
                stats["identical"] += 1
            else:
                stats["different"] += 1
                diffs.append(f"{addr:04x}  source {stmt!r} -> {r!r}  ghidra {g!r}")
        addr += 1
    print(f"{os.path.basename(src)}: " + ", ".join(f"{v} {k}" for k, v in stats.items()))
    for d in diffs:
        print("   " + d)
    return 1 if stats["different"] else 0


if __name__ == "__main__":
    sys.exit(main())
