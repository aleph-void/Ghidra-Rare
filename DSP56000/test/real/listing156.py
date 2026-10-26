#!/usr/bin/env python3
"""Listing-guided check for the DSP56156 language against Motorola ASM56100 listings.

    listing156.py image <file.lst> <out.bin>         P-memory image (16-bit BE words, base 0)
    listing156.py compare <file.lst> <ghidra.txt>    compare Ghidra's linear disassembly

'compare' takes every listing statement that produced code without an assembler error and
checks that Ghidra decodes an instruction at the same address with the same length, and that
the instruction text matches the source statement after normalization: case, spacing,
MOVE(C)/(M)/(I) spelled MOVE, symbols replaced by their values (appendix equates and labels),
numbers compared by value, and the assembler's optional parentheses/force operators removed.
Statements whose text still differs are listed for review."""
import re
import struct
import sys

LINE = re.compile(r"^(\d+)\s+P:([0-9A-F]{4}) ([0-9A-F]{4})\s+(.*)$")
CONT = re.compile(r"^\s{10,}([0-9A-F]{4})\s*$")


def parse(path):
    import os
    src_lines = []
    asm = os.path.splitext(path)[0] + ".asm"
    if os.path.exists(asm):
        src_lines = open(asm, errors="replace").read().split("\n")
    stmts, errline, cur = [], False, None
    labels = {}
    srcpos = 0
    plabels = []
    for raw in open(path, errors="replace"):
        line = raw.rstrip("\n")
        if line.startswith("****"):
            errline = True
            continue
        m = LINE.match(line)
        if m:
            # the listing truncates long statements: find the full line in the source, in order
            want = re.sub(r"\s+", " ", re.sub(r"^\[[^]]*\]", "", m.group(4)).strip())[:40]
            src = m.group(4)
            for j in range(srcpos, len(src_lines)):
                if re.sub(r"\s+", " ", src_lines[j].strip()).startswith(want):
                    src, srcpos = src_lines[j], j + 1
                    break
            cur = {"addr": int(m.group(2), 16), "words": [int(m.group(3), 16)], "src": src,
                   "err": errline}
            for lab in plabels:          # a label on its own line names the next statement
                labels[lab] = cur["addr"]
            plabels = []
            stmts.append(cur)
            errline = False
            continue
        m = CONT.match(line)
        if m and cur is not None:
            cur["words"].append(int(m.group(1), 16))
            continue
        m = re.match(r"^(\d+)\s+P:([0-9A-F]{4})\s+([A-Za-z_]\w*)", line)
        if m:
            labels[m.group(3)] = int(m.group(2), 16)
        m = re.match(r"^(\d+)\s{5,}([A-Za-z_]\w*):?\s*$", line)
        if m:
            plabels.append(m.group(2))
    if stmts:
        for lab in plabels:
            labels[lab] = stmts[-1]["addr"] + len(stmts[-1]["words"])
    parse.labels = labels
    # a later ORG over the same addresses shadows the earlier statements: skip those
    owner = {}
    for i, st in enumerate(stmts):
        if st["err"]:
            continue
        for k in range(len(st["words"])):
            prev = owner.get(st["addr"] + k)
            if prev is not None:
                stmts[prev]["shadowed"] = True
            owner[st["addr"] + k] = i
    return stmts


def symbols(path, stmts):
    import os
    sym = {}
    asm = os.path.splitext(path)[0] + ".asm"
    if os.path.exists(asm):
        for raw in open(asm, errors="replace"):
            m = re.match(r"^([A-Za-z_]\w*)\s+equ\s+([^\s;]+)", raw, re.I)
            if m:
                sym.setdefault(m.group(1), m.group(2))
    pending = []
    for raw in open(path, errors="replace"):
        # data labels: "N  d  X:0120 0100   name   dc ..." or a label line before the data line
        m = re.match(r"^\d+\s+(?:\w\s+)?X:([0-9A-F]{4})(?:\s+[0-9A-F]{4})?\s*(\S*)", raw)
        if m:
            for name in pending:
                sym[name] = "$" + m.group(1)
            pending = []
            lab = re.match(r"^([A-Za-z_]\w*)\s+(ds|dc|bsc)\b", m.group(2) + raw[m.end():], re.I)
            if lab:
                sym[lab.group(1)] = "$" + m.group(1)
            continue
        m = re.match(r"^\d+\s+\w?\s{5,}([A-Za-z_]\w*):?\s*$", raw.rstrip())
        if m:
            pending.append(m.group(1))
        elif re.match(r"^\d+\s", raw):
            pending = []
    for s in stmts:
        m = re.match(r"^([A-Za-z_]\w*)\s", s["src"])
        if m and m.group(1).lower() not in ("move", "movec", "movem", "movep", "moves"):
            sym[m.group(1)] = "$%x" % s["addr"]
    for k, v in getattr(parse, "labels", {}).items():
        sym.setdefault(k, "$%x" % v)
    return sym


def num(tok, sym):
    t = tok
    for name in sorted(sym, key=len, reverse=True):
        t = re.sub(r"(?<![\w$])%s(?!\w)" % re.escape(name), sym[name], t)
    t = re.sub(r"\$([0-9a-f]+)", lambda m: str(int(m.group(1), 16)), t, flags=re.I)
    t = t.replace("<", "").replace(">", "")
    try:
        if re.fullmatch(r"[-+*/()0-9 .]+", t):
            v = eval(t if "." in t else t.replace("/", "//"))
            if isinstance(v, float):
                v = int(round(v * 32768))
            return str(int(v) & 0xffff)
    except Exception:
        pass
    return tok


REGS = set("x0 x1 y0 y1 a b a0 a1 a2 b0 b1 b2 x y sr omr sp ssh ssl la lc mr ccr ab ba".split()) | \
    {"%s%d" % (c, i) for c in "rnm" for i in range(4)}


def norm_src(src, sym, addr):
    s = re.sub(r"\[[^]]*\]", "", src.split(";")[0])
    s = re.sub(r"^[A-Za-z_]\w*\s+(?=[a-zA-Z])", "", s) if not re.match(
        r"^(move\w*|nop|rts|rti|[a-z]+\d*)\s", s, re.I) or re.match(r"^\S+\s+(move|mac|add|sub|tfr|do|rep|j|b|nop)", s, re.I) else s
    s = s.strip()
    parts = s.split()
    if parts:
        parts[0] = parts[0].lower()
    if not parts:
        return ""
    mn = parts[0]
    mn = {"movec": "move", "movem": "move", "movei": "move", "move(c)": "move", "move(m)": "move",
          "move(i)": "move", "move(s)": "moves", "move(p)": "movep"}.get(mn, mn)
    ops = " ".join(parts[1:])
    ops = ops.replace("*", "%d" % addr) if "*" in ops and mn[0] in "bj" else ops
    out = []
    for grp in ops.split():
        elems = []
        for e in grp.split(","):
            low = e.lower()
            m = re.match(r"^([xpXP]):(.*)$", e)
            if e.startswith("#"):
                e = "#" + num(e[1:], sym)
            elif m and not m.group(2).startswith("("):
                e = m.group(1).lower() + ":" + num(m.group(2), sym)
            elif "(" not in e and low not in REGS:
                e = num(e, sym)
            elif low.startswith("(r2") and ("+" in e or "-" in e) and not e.endswith("n2)"):
                mm = re.match(r"^\([rR]2([+-].*)\)$", e)
                if mm:
                    v = int(num("0" + mm.group(1), sym)) & 0xffff
                    v = v - 0x10000 if v & 0x8000 else v
                    e = "(r2%+d)" % v
            elems.append(e.lower())
        out.append(",".join(elems))
    return (mn + " " + " ".join(out)).strip()


def norm_gh(t):
    t = t.lower().strip()
    t = t.replace("<<", "").replace("<", "").replace(">", "")
    t = re.sub(r"0x([0-9a-f]+)", lambda m: str(int(m.group(1), 16)), t)
    t = re.sub(r"-(\d+)", lambda m: str((-int(m.group(1))) & 0xffff) if True else m.group(0), t)
    return re.sub(r"\s+", " ", t)


def canon(t):
    """assembler-level equivalences: MOVE(P)/MOVE(S) may be written MOVE; multiply sources are
    commutative; spacing is free"""
    t = re.sub(r"\s+", " ", t.strip())
    parts = t.split(" ")
    if parts[0] in ("movep", "moves"):
        parts[0] = "move"
    if parts[0] == "lua":
        parts[0] = "lea"
    if parts[0] in ("mpy", "mpyr", "mac", "macr", "mpyuu", "macuu", "dmacss", "dmacuu", "impy", "imac") and len(parts) > 1:
        ops = parts[1].split(",")
        if len(ops) == 3:
            sign = "-" if ops[0].startswith("-") else ""
            pair = sorted([ops[0].lstrip("-+"), ops[1]])
            parts[1] = sign + ",".join(pair + [ops[2]])
    r2 = [re.sub(r"\(r2\+?(-?)(\d+)\)", lambda m: "(r2%s%s)" % ("-" if m.group(1) else "+", m.group(2)), p) for p in parts]
    return "".join(r2)


def main():
    cmd, lst = sys.argv[1], sys.argv[2]
    stmts = parse(lst)
    if cmd == "image":
        mem = [0] * 0x800
        for s in stmts:
            if s["err"] or s.get("shadowed"):
                continue
            for i, w in enumerate(s["words"]):
                mem[s["addr"] + i] = w
        open(sys.argv[3], "wb").write(b"".join(struct.pack(">H", w) for w in mem))
        return
    gh = {}
    for line in open(sys.argv[3]):
        p = line.rstrip("\n").split(" ")
        a = int(p[0], 16)
        i = 1
        while i < len(p) and re.fullmatch(r"[0-9a-f]{4}", p[i]):
            i += 1
        gh[a] = (i - 1, " ".join(p[i:]))
    sym = symbols(lst, stmts)
    ok = bad = boundary = 0
    shadowed = 0
    for s in stmts:
        if s["err"]:
            continue
        if s.get("shadowed"):
            shadowed += 1
            continue
        g = gh.get(s["addr"])
        if g is None or g[0] != len(s["words"]) or g[1] == "BAD":
            boundary += 1
            print("BOUNDARY %04x %s | %s" % (s["addr"], s["src"], g))
            continue
        a, b = norm_src(s["src"], sym, s["addr"]), norm_gh(g[1])
        a2 = re.sub(r"(\d+)", lambda m: str(int(m.group(1)) & 0xffff), a)
        if canon(a2) == canon(b):
            ok += 1
        else:
            bad += 1
            print("DIFF %04x %-50s | %s" % (s["addr"], s["src"].split(";")[0].strip(), g[1]))
    print("%s: %d statements, %d identical, %d text differences, %d boundary/invalid, %d shadowed by a later ORG"
          % (lst, ok + bad + boundary, ok, bad, boundary, shadowed))


if __name__ == "__main__":
    main()
