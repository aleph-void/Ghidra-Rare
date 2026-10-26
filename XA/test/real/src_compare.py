#!/usr/bin/env python3
"""Compare Ghidra's instruction text with the asxa source statements in an assembler listing.

    src_compare.py <ghidra.dis> <assembler.lst> [label] [symbols.equ ...]

Both sides are reduced to a canonical form: case and spacing ignored, size suffixes (.b/.w/.d)
dropped, numbers as integers, immediates masked to the operand size, and bit operands as
10-bit bit addresses (user guide 6.2.7) unless they name a register bit. Source symbols come
from the listing (labels, and "equ"/"bit" lines shown as ":=value") and from the .equ files
given; "$", "low", "high" and + - * / expressions are evaluated. Statements the assembler
expanded into two instructions, statements with character constants, symbols that cannot be
resolved, and the XCH Rd,[Rs] statements asxa encodes wrongly are skipped and counted.
Character constants are evaluated as asxa packs them ('xy' = x | y << 8).
"""
import re
import sys

LST_RE = re.compile(r"^([0-9A-Fa-f]+):((?: [0-9A-Fa-f]{2})*)\s*\t+\s*(\d+)>?\t?(.*)$")
EQU_RE = re.compile(r"^([0-9A-Fa-f]+):=(\S+)\s+\t*\s*\d+>?\t?([A-Za-z_]\w*)")
DIRECTIVES = ("db", "dw", "ds", "resb", "resw", "org", "equ", "bit", "segment")
REGS = {f"R{i}" for i in range(8)} | {f"R{i}{h}" for i in range(8) for h in "LH"} | \
    {"USP", "A", "DPTR", "PC", "C", "AC", "V", "N", "Z", "PSWL", "PSWH", "PSW51", "SSEL",
     "SCR", "DS", "ES", "CS"}
CORE = {"PSWL": 0x400, "PSWH": 0x401, "PSW51": 0x402, "SSEL": 0x403, "SCR": 0x440, "DS": 0x441,
        "ES": 0x442, "CS": 0x443}
BITOPS = {"CLR", "SETB", "ANL", "ORL", "JB", "JNB", "JBC"}


def ival(s):
    s = s.strip()
    if s.lower().startswith("0x"):
        return int(s, 16)
    if s.startswith("$") and len(s) > 1:
        return int(s[1:], 16)
    if s.lower().endswith("h") and re.match(r"^[0-9][0-9a-f]*h$", s.lower()):
        return int(s[:-1], 16)
    return int(s)


def bitaddr(byte, bit):
    if 0x20 <= byte <= 0x3f:
        return 0x100 + (byte - 0x20) * 8 + bit
    if 0x400 <= byte <= 0x43f:
        return 0x200 + (byte - 0x400) * 8 + bit
    return None


def load_equ(path, syms):
    for line in open(path, errors="replace"):
        line = re.sub(r";.*", "", line).strip()
        m = re.match(r"^([A-Za-z_]\w*):?\s+(equ|bit|=)\s+(\S+)", line, re.I)
        if not m:
            continue
        name, kind, val = m.group(1).upper(), m.group(2).lower(), m.group(3)
        try:
            if kind == "bit":
                b, n = val.rsplit(".", 1)
                base = syms[b.upper()] if b.upper() in syms else ival(b)
                syms[name] = ("bit", bitaddr(base, int(n)))
            else:
                syms[name] = ival(val)
        except (ValueError, KeyError):
            pass


class Unresolved(Exception):
    pass


def evaluate(expr, syms, here):
    # character constants: asxa packs 'xy' as x | y << 8 (listing: #'dw' assembles to 7764h)
    def chars(m):
        txt = m.group(1).encode().decode("unicode_escape")
        return str(sum(ord(c) << (8 * i) for i, c in enumerate(txt)))
    e = re.sub(r"'((?:\\.|[^'\\]){1,2})'", chars, expr)
    e = e.upper()
    e = re.sub(r"\$([0-9A-F]+)", lambda m: str(int(m.group(1), 16)), e)
    e = e.replace("$", f" {here} ")
    e = re.sub(r"0X([0-9A-F]+)", lambda m: str(int(m.group(1), 16)), e)

    def sym(m):
        w = m.group(0)
        if w in ("LOW", "HIGH"):
            return w
        v = syms.get(w)
        if v is None:
            raise Unresolved(w)
        return str(v[1] if isinstance(v, tuple) else v)
    e = re.sub(r"[A-Z_][A-Z0-9_]*", sym, e)
    e = re.sub(r"\bHIGH\s+(\d+)", r"((\1 >> 8) & 255)", e)
    e = re.sub(r"\bLOW\s+(\d+)", r"(\1 & 255)", e)
    if not re.match(r"^[\s\d+\-*/()&>]*$", e):
        raise Unresolved(expr)
    e = re.sub(r"\b0+(\d)", r"\1", e)
    return int(eval(e.replace("/", "//")))


def canon_ghidra(text):
    t = text.upper()
    m = re.match(r"^(\S+?)(?:\.([BWD]))?(?:\s+(.*))?$", t)
    mn, size, ops = m.group(1), m.group(2), m.group(3) or ""
    out = []
    for op in [o.strip() for o in ops.split(",")] if ops else []:
        bm = re.match(r"^(/?)0X([0-9A-F]+)\.(\d)$", op)
        if bm:
            out.append(f"{bm.group(1)}BIT{bitaddr(int(bm.group(2), 16), int(bm.group(3)))}")
            continue
        op = re.sub(r"0X([0-9A-F]+)", lambda mm: str(int(mm.group(1), 16)), op)
        out.append(op)
    return mn, size, out


def split_ops(ops):
    """Split an operand list on commas outside character constants."""
    out, cur, q = [], "", False
    i = 0
    while i < len(ops):
        ch = ops[i]
        if ch == "\\" and q and i + 1 < len(ops):
            cur += ops[i:i + 2]
            i += 2
            continue
        if ch == "'":
            q = not q
        if ch == "," and not q:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
        i += 1
    if cur.strip():
        out.append(cur.strip())
    return out


def canon_source(src, syms, here, mn, size):
    t = src.strip()
    parts = t.split(None, 1)
    ops = parts[1] if len(parts) > 1 else ""
    out = []
    for op in split_ops(ops):
        u = op.upper()
        if u in REGS:
            out.append(u if u not in CORE or mn in BITOPS else u)
            continue
        neg = ""
        if u.startswith("/"):
            neg, u, op = "/", u[1:], op[1:]
        # register bits: Rn.b (word register), RnL.b, RnH.b
        rb = re.match(r"^(R[0-7])([LH]?)\.(\d+)$", u)
        if rb:
            b = int(rb.group(3))
            half = rb.group(2) or ("L" if b < 8 else "H")
            out.append(f"{neg}{rb.group(1)}{half}.{b % 8}")
            continue
        sb = re.match(r"^([A-Z_]\w*|\$?[0-9A-F]+H?|0X[0-9A-F]+)\.(\d)$", u)
        if sb:
            base = sb.group(1)
            if base in CORE:
                out.append(f"{neg}{base}.{sb.group(2)}" if base != "PSWL" else
                           neg + {"7": "C", "6": "AC", "2": "V", "1": "N", "0": "Z"}.get(sb.group(2), f"PSWL.{sb.group(2)}"))
                continue
            v = syms.get(base) if base in syms else ival(base.replace("0X", "0x"))
            if v is None:
                raise Unresolved(base)
            out.append(f"{neg}BIT{bitaddr(v, int(sb.group(2)))}")
            continue
        if u in syms and isinstance(syms[u], tuple):
            out.append(f"{neg}BIT{syms[u][1]}")
            continue
        im = re.match(r"^#(.*)$", op)
        if im:
            v = evaluate(im.group(1), syms, here)
            out.append("#" + str(v & {"B": 0xff, "W": 0xffff}.get(size, 0xffffffff)))
            continue
        ind = re.match(r"^\[(R[0-7])(\+?)\]$", u)
        if ind or u in ("[A+DPTR]", "[A+PC]") or re.match(r"^\[\[R[0-7]\+\]\]$", u):
            out.append(u)
            continue
        io = re.match(r"^\[(R[0-7])\s*([+-])\s*(.+)\]$", op.upper())
        if io:
            v = evaluate(io.group(3), syms, here)
            if io.group(2) == "-":
                v = -v
            out.append(f"[{io.group(1)}{'+' if v >= 0 else '-'}{abs(v)}]")
            continue
        lo = re.match(r"^(R[0-7])\s*([+-])\s*(.+)$", op.upper())
        if lo and mn == "LEA":
            v = evaluate(lo.group(3), syms, here)
            if lo.group(2) == "-":
                v = -v
            out.append(f"{lo.group(1)}{'+' if v >= 0 else '-'}{abs(v)}")
            continue
        out.append(str(evaluate(op, syms, here)))
    return out


def main():
    dis, lst = sys.argv[1:3]
    label = sys.argv[3] if len(sys.argv) > 3 else dis
    syms = {}
    for f in sys.argv[4:]:
        load_equ(f, syms)
    ghid = {}
    for line in open(dis):
        a, b, t = (line.rstrip("\n").split(" ", 2) + ["", ""])[:3]
        ghid[int(a, 16)] = (b, t)
    stmts = []
    for line in open(lst, errors="replace"):
        line = line.rstrip("\n")
        m = EQU_RE.match(line)
        if m:
            name = m.group(3).upper()
            v = int(m.group(2), 16) if m.group(2).lower().startswith("0x") else int(m.group(2))
            syms[name] = ("bit", v) if re.search(r"\bbit\b", line, re.I) else v
            continue
        m = LST_RE.match(line)
        if not m:
            continue
        a = int(m.group(1), 16)
        src = re.sub(r";.*", "", m.group(4)).strip()
        lm = re.match(r"^([A-Za-z_]\w*):?\s*(.*)$", src)
        if lm and (src.split()[0].endswith(":") or
                   (len(src.split()) > 1 and src.split()[1].lower() in DIRECTIVES)):
            syms.setdefault(lm.group(1).upper(), a)
            src = lm.group(2)
        if m.group(2).strip() and src and not src.startswith("$") and \
                src.split()[0].lower() not in DIRECTIVES:
            stmts.append((a, len(m.group(2).split()), src))
    from collections import Counter
    agree, skipped, bad, why = 0, 0, [], Counter()
    for a, n, src in stmts:
        if a not in ghid:
            skipped += 1
            why["not disassembled"] += 1
            continue
        if "\"" in src or re.match(r"(?i)^xch\s+\w+\s*,\s*\[", src):
            skipped += 1
            why["string or asxa XCH bug"] += 1
            continue
        gb, gt = ghid[a]
        if len(gb) // 2 != n:
            skipped += 1           # the assembler expanded the statement
            continue
        gm, size, go = canon_ghidra(gt)
        sm = re.sub(r"\.(B|W|D)$", "", src.split()[0].upper())
        try:
            so = canon_source(src, syms, a, gm, size)
        except (Unresolved, SyntaxError, ValueError, ZeroDivisionError) as ex:
            skipped += 1
            why[str(ex)[:20]] += 1
            continue
        if gm in ("PUSH", "POP", "PUSHU", "POPU") and all(o in REGS for o in so):
            so = sorted(so, key=lambda r: (int(r[1]), r[2:]))
        if sm == gm and so == go:
            agree += 1
        else:
            bad.append(f"{a:06x} {gb}: source '{src}' ghidra '{gt}'  [{so} | {go}]")
    print(f"{label}: {len(stmts)} source statements, {agree} agree with the assembler source, "
          f"{len(bad)} differ, {skipped} skipped")
    if __import__("os").environ.get("VERBOSE"):
        print("    skipped:", dict(why))
    for x in bad[:40]:
        print("   ", x)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
