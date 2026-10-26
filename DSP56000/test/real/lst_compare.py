#!/usr/bin/env python3
"""Compare Ghidra's disassembly with a Motorola assembler listing (listing-guided).

    lst_compare.py addrs <listing.lst>                   print the listed P-space code addresses
    lst_compare.py compare <listing.lst> <ghidra.txt> [--mame mame.txt] [--auto auto.txt]

The listing (Motorola asm56000 / asm56100 "-l" output) gives, for every assembled statement, the
P address, the instruction words and the source statement. For each statement that generated
code in P memory (directives such as DC/DS excluded), the Ghidra decode at that address must
have the same number of words and the same text as the source statement after normalization:
lower case, comments dropped, symbols and expressions evaluated (labels, EQUs and the Motorola
'$' hex / '%' binary / fractional constants), force operators '<' '>' dropped, 'N' as offset
register written as Nn, and the two multiplier sources of MPY/MAC compared as a set. With
--mame, the MAME decode of the same words is compared too (through compare.py's normalization
and the explain rules), and with --auto it reports how many statements auto-analysis reached.

Statements are counted identical, different (printed) or skipped (an operand expression the
script cannot evaluate, e.g. a macro argument or an expression with an unknown function).
"""
import importlib.util
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("compare", os.path.join(HERE, "..", "compare.py"))
cmp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cmp)

DIRECTIVES = {"dc", "ds", "dsm", "dsr", "bsc", "bsm", "bsr", "org", "equ", "set", "page", "opt",
              "include", "macro", "endm", "end", "if", "else", "endif", "section", "endsec",
              "xdef", "xref", "global", "local", "nolist", "list", "title", "stitle", "dupf",
              "dup", "endm", "lstcol", "comment", "ident", "radix", "scsreg", "himem", "lomem",
              "buffer", "endbuf", "mode", "cobj", "msg", "warn", "fail", "undef", "dupa",
              "dupc", "exitm", "pmacro", "maclib", "tabs", "rdirect", "baddr", "symobj"}

# overlay listings print the run-time address, then the load address: statements are compared
# at the load address (where the load file puts the words), labels take the run-time address
CODE = re.compile(r"^\s*(\d+)\s+((?:[a-z]\+?|\+)\s+)?(?:[PXYL]:([0-9A-F]{4})\s+)?([PXYL]):([0-9A-F]{4})\s+([0-9A-F]{4}|[0-9A-F]{6})(\s.*)?$")
ADDR = re.compile(r"^\s*(\d+)\s+((?:[a-z]\+?|\+)\s+)?(?:[PXYL]:([0-9A-F]{4})\s+)?([PXYL]):([0-9A-F]{4})(\s.*)?$")
NUMBERED = re.compile(r"^\s*\d+(\s|$)")
CONT = re.compile(r"^\s+([0-9A-F]{6}|[0-9A-F]{4})\s*$")
EQU = re.compile(r"^\s*(\d+)\s+((?:[a-z]\+?|\+)\s+)?([0-9A-F]{6}|[0-9A-F]{4})\s+(\S+)\s+(equ|set)\s+(.*)$", re.I)


HEADER = re.compile(r"^(Motorola DSP|\s*Page \d+\s*$)")
EQU_NOLABEL = re.compile(r"^\s*(\d+)\s+((?:[a-z]\+?|\+)\s+)?([0-9A-F]{6}|[0-9A-F]{4})\s+(equ|set)\s", re.I)
LABEL_ONLY = re.compile(r"^\s*\d+\s+(?:(?:[a-z]\+?|\+)\s+)?([A-Za-z_][A-Za-z0-9_@?]*):?\s*(;.*)?$")


def parse(path):
    """statements [space, addr, words, label, source, scope] and symbols; labels starting
    with '_' are local to the section after the previous global label (stored as
    'scope|_name')."""
    stmts = []
    syms = {}
    cur = None
    scope = ""
    pending = []
    loc = None                           # the location counter after the previous line

    def define(lb, value):
        nonlocal scope
        lb = lb.lower().rstrip(":")
        if lb.startswith("_"):
            syms[scope + "|" + lb] = value
        else:
            scope = lb
            syms[lb] = value

    for raw in open(path, errors="replace"):
        line = raw.rstrip("\n\r").replace("\f", "")
        if not line.strip() or HEADER.match(line):
            continue                     # blank lines and page headers keep the statement open
        m = CODE.match(line)
        if m:
            sp, addr, w0, rest = m.group(4), int(m.group(5), 16), m.group(6), m.group(7) or ""
            run = int(m.group(3), 16) if m.group(3) else addr
            mc = re.match(r"^\s*\[[^\]]*\](.*)$", rest)
            if mc:
                rest = mc.group(1)       # cycle-count column of the -mc option
            label = None
            if len(rest) > 2 and rest[0] == " " and rest[1] == " " and rest[2] != " ":
                label = rest[2:].split()[0]
            elif len(rest) > 1 and rest[0] == " " and rest[1] != " ":
                label = rest[1:].split()[0]
            src = rest
            if label:
                src = rest.split(label, 1)[1]
                pending.append(label)
            for lb in pending:
                define(lb, run)
            pending = []
            cur = [sp, addr, [int(w0, 16)], label, src.strip(), scope]
            stmts.append(cur)
            loc = ("code", cur, run)
            continue
        m = CONT.match(line)
        if m and cur is not None:
            cur[2].append(int(m.group(1), 16))
            continue
        if not NUMBERED.match(line):
            # the listing wraps lines at 80 columns: the rest of the statement's source
            if cur is not None:
                cur[4] += line
            continue
        m = ADDR.match(line)
        if m:
            # an address without code words (DS, ORG, a label): labels take this address
            rest = m.group(6) or ""
            run = int(m.group(3) or m.group(5), 16)
            lab = None
            # the label column follows the (empty) code-word column, and the cycle-count
            # column in listings made with -mc
            for col in (9, 25):
                if len(rest) > col and rest[col] != " " and rest[:col].strip() == "":
                    mm = re.match(r"([A-Za-z_][A-Za-z0-9_@?]*)", rest[col:])
                    if mm and mm.group(1).lower() not in DIRECTIVES:
                        lab = mm.group(1)
                    break
            for lb in pending + ([lab] if lab else []):
                define(lb, run)
            pending = []
            cur = None
            # ORG sets the counter; DS/DSM/DSR/BSC/BSM reserve words
            loc = None
            body = rest.split(";", 1)[0].split()
            ops = [x.lower() for x in body]
            for k, op in enumerate(ops):
                if op == "org":
                    loc = ("addr", run)
                elif op in ("ds", "dsm", "dsr", "bsc", "bsm", "bsr") and k + 1 < len(body):
                    try:
                        loc = ("addr", run + evaluate(body[k + 1].split(",")[0], syms, 24, scope))
                    except Unresolved:
                        loc = None
            continue
        m = EQU.match(line)
        if m:
            syms[m.group(4).lower()] = int(m.group(3), 16)
            cur = None
            continue
        m = EQU_NOLABEL.match(line)
        if m and pending:
            for lb in pending:
                syms[lb.lower().rstrip(":")] = int(m.group(3), 16)
            pending = []
            cur = None
            continue
        m = LABEL_ONLY.match(line)
        if m and m.group(1).lower() not in DIRECTIVES:
            # a label on its own line takes the location counter (when the listing shows it)
            if loc and loc[0] == "code":
                define(m.group(1), loc[2] + len(loc[1][2]))
            elif loc and loc[0] == "addr":
                define(m.group(1), loc[1])
            else:
                pending.append(m.group(1))
        cur = None
    return stmts, syms


def strip_comment(s):
    return s.split(";", 1)[0].strip()


class Unresolved(Exception):
    pass


TOK = re.compile(r"\s*(\$[0-9a-f]+|%[01]+|\d+\.\d*(?:e-?\d+)?|\.\d+(?:e-?\d+)?|\d+|[a-z_][a-z0-9_@?]*|<<|>>|[-+*/()&|^~<>!])")


def evaluate(expr, syms, frac_bits=24, scope=""):
    """Motorola assembler expression: $hex, %bin, decimal, fractional constants (a result
    with a fraction is converted to a signed frac_bits fixed-point word), symbols."""
    toks = []
    pos = 0
    e = expr.lower()
    while pos < len(e):
        m = TOK.match(e, pos)
        if not m:
            raise Unresolved(expr)
        toks.append(m.group(1))
        pos = m.end()
    out = []
    frac = False
    for t in toks:
        if t.startswith("$"):
            out.append(str(int(t[1:], 16)))
        elif t.startswith("%"):
            out.append(str(int(t[1:], 2)))
        elif re.fullmatch(r"\d+\.\d*(e-?\d+)?|\.\d+(e-?\d+)?", t):
            out.append(repr(float(t)))
            frac = True
        elif re.fullmatch(r"\d+", t):
            out.append(str(int(t)))
        elif re.fullmatch(r"[a-z_][a-z0-9_@?]*", t):
            key = scope + "|" + t if t.startswith("_") else t
            if key not in syms:
                raise Unresolved(t)
            out.append(str(syms[key]))
        elif t == "/":
            out.append("/" if frac else "//")
        elif t == "!":
            out.append("~")
        else:
            out.append(t)
    try:
        v = eval(" ".join(out), {"__builtins__": {}})
    except Exception:
        raise Unresolved(expr)
    if frac or isinstance(v, float):
        iv = int(math.floor(v * (1 << (frac_bits - 1)) + 0.5))
        return max(-(1 << (frac_bits - 1)), min(iv, (1 << (frac_bits - 1)) - 1))
    return int(v)


REGS = set("a b x y x0 x1 y0 y1 a0 a1 a2 b0 b1 b2 a10 b10 ab ba sr omr sp ssh ssl la lc mr ccr".split())
REGS |= {"r%d" % i for i in range(8)} | {"n%d" % i for i in range(8)} | {"m%d" % i for i in range(8)}


def norm_operand(op, syms, word_bits, scope=""):
    """one comma-separated operand of the source, made comparable with compare.norm output"""
    o = op.strip().lower().replace("<", "").replace(">", "")
    if o in REGS or o == "" or (o.startswith(("-", "+")) and o[1:] in REGS):
        return o.lstrip("+")
    m = re.fullmatch(r"([xylp]):(.*)", o)
    if m:
        return m.group(1) + ":" + norm_operand(m.group(2), syms, word_bits, scope)
    m = re.fullmatch(r"-\((r\d)\)", o)
    if m:
        return o
    m = re.fullmatch(r"\((r(\d))\)([+-])(n\d?)?", o)
    if m:
        n = m.group(4)
        if n == "n":
            n = "n" + m.group(2)
        return "(%s)%s%s" % (m.group(1), m.group(3), n or "")
    m = re.fullmatch(r"\((r(\d))\+(n\d?)\)", o)
    if m:
        n = m.group(3) if m.group(3) != "n" else "n" + m.group(2)
        return "(%s+%s)" % (m.group(1), n)
    m = re.fullmatch(r"\((r(\d))\)", o)
    if m:
        return o
    if o.startswith("#"):
        return "#" + str(evaluate(o[1:], syms, word_bits, scope) & ((1 << word_bits) - 1))
    return str(evaluate(o, syms, word_bits, scope) & 0xffff if not re.fullmatch(r"\d+", o) else int(o))


def norm_source(src, syms, word_bits, scope=""):
    s = strip_comment(src)
    if not s:
        return None
    fields = s.split()
    mn = fields[0].lower()
    if mn in DIRECTIVES:
        return None
    out = [mn]
    for f in fields[1:]:
        out.append(",".join(norm_operand(x, syms, word_bits, scope) for x in f.split(",")))
    return out


def norm_ghidra(text):
    t = cmp.norm(text)
    return t.split(" ")


def same(src, gh, word_bits):
    """token-wise comparison with the documented equivalences"""
    # the assembler accepts MOVE for MOVEC, MOVEM and MOVEP ("syntax alternatives")
    if src[0] == "move" and gh[0] in ("movec", "movem", "movep"):
        src = [gh[0]] + src[1:]
    if (src[0], gh[0]) in (("and", "andi"), ("or", "ori")):
        src = [gh[0]] + src[1:]
    # the two parts of an XY, X:R or R:Y move may be written in either order
    first = 1 if src[0] == "move" else 2
    if len(src) == len(gh) == first + 2 and sorted(src[first:]) == sorted(gh[first:]):
        src = src[:first] + gh[first:]
    if len(src) != len(gh) or src[0] != gh[0]:
        return False
    for i, (a, b) in enumerate(zip(src, gh)):
        if a == b:
            continue
        pa, pb = a.split(","), b.split(",")
        if i == 1 and src[0] in ("mpy", "mpyr", "mac", "macr") and len(pa) == 3 == len(pb):
            sa = [x.lstrip("-") for x in pa[:2]]
            sb = [x.lstrip("-") for x in pb[:2]]
            if sorted(sa) == sorted(sb) and pa[2] == pb[2] and \
                    (pa[0].startswith("-") or pa[1].startswith("-")) == pb[0].startswith("-"):
                continue
        if len(pa) != len(pb):
            return False
        for x, y in zip(pa, pb):
            if x == y:
                continue
            # immediate short forms: the source value is the full word, Ghidra prints the 8 bits
            mx, my = re.fullmatch(r"#(\d+)", x), re.fullmatch(r"#(\d+)", y)
            if mx and my:
                vx, vy = int(mx.group(1)), int(my.group(1))
                if vy < 256 and (vx == vy or (vx >> (word_bits - 8)) == vy and vx & ((1 << (word_bits - 8)) - 1) == 0
                                 or vx & 0xff == vy):
                    continue
            # P/X/Y address operands: compare the 16-bit address
            mx, my = re.fullmatch(r"([xyp]):(\d+)", x), re.fullmatch(r"([xyp]):(\d+)", y)
            if mx and my and mx.group(1) == my.group(1) and int(mx.group(2)) & 0xffff == int(my.group(2)):
                continue
            mx, my = re.fullmatch(r"(\d+)", x), re.fullmatch(r"(\d+)", y)
            if mx and my and int(x) & 0xffff == int(y):
                continue
            return False
    return True


def load_dump(path):
    d = {}
    for line in open(path):
        p = line.rstrip("\n").split(" ")
        a = int(p[0], 16)
        words = []
        i = 1
        while i < len(p) and re.fullmatch(r"[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8}", p[i]):
            words.append(int(p[i], 16))
            i += 1
        d[a] = (words, " ".join(p[i:]))
    return d


def main():
    if sys.argv[1] == "addrs":
        stmts, syms = parse(sys.argv[2])
        for sp, a, w, label, src, scope in stmts:
            if sp == "P":
                print("%04x" % a)
        return
    lst, gpath = sys.argv[2], sys.argv[3]
    mame = auto = None
    args = sys.argv[4:]
    while args:
        if args[0] == "--mame":
            mame = cmp.load_mame(args[1], 1, 8 if "56000" in args[1] or True else 4)
        elif args[0] == "--auto":
            auto = load_dump(args[1])
        args = args[2:]
    stmts, syms = parse(lst)
    gh = load_dump(gpath)
    word_bits = 24
    for sp, a, w, label, src, scope in stmts:
        if any(x > 0xffff for x in w):
            break
    else:
        word_bits = 16 if stmts else 24
    n = {"identical": 0, "different": 0, "skipped": 0, "directive": 0, "shadowed": 0}
    # a later statement assembled over the same P words wins in the load file
    owner = {}
    for i, (sp, a, w, label, src, scope) in enumerate(stmts):
        if sp == "P":
            for k in range(len(w)):
                owner[a + k] = i
    mdiff = mok = 0
    reached = 0
    diffs = []
    for i, (sp, a, w, label, src, scope) in enumerate(stmts):
        if sp != "P":
            continue
        if any(owner.get(a + k) != i for k in range(len(w))):
            n["shadowed"] += 1
            continue
        try:
            ns = norm_source(src, syms, word_bits, scope)
        except Unresolved as e:
            n["skipped"] += 1
            if os.environ.get("LST_DEBUG"):
                print("    SKIP %04x %s (%s)" % (a, src.strip(), e))
            continue
        if ns is None:
            n["directive"] += 1
            continue
        if a not in gh:
            n["skipped"] += 1
            continue
        gw, gt = gh[a]
        if auto is not None and a in auto:
            reached += 1
        if gt != "BAD" and len(gw) == len(w) and same(ns, norm_ghidra(gt), word_bits):
            n["identical"] += 1
        else:
            n["different"] += 1
            diffs.append("%04x %s | %s | %s" % (a, " ".join("%06x" % x for x in w), src.strip(), gt))
        if mame is not None and a in mame:
            mn, mt, mw = mame[a]
            if not cmp.mame_invalid(mt) and cmp.norm(mt) == cmp.norm(gt):
                mok += 1
            else:
                mdiff += 1
    total = n["identical"] + n["different"]
    print("%s: %d code statements: %d identical, %d different, %d skipped; %d directives in P, %d shadowed"
          % (os.path.basename(lst), total, n["identical"], n["different"], n["skipped"], n["directive"], n["shadowed"]))
    if auto is not None:
        print("    auto-analysis reached %d/%d statements" % (reached, total))
    if mame is not None:
        print("    MAME text identical at %d statements, different at %d" % (mok, mdiff))
    for d in diffs[:40]:
        print("    DIFF " + d)
    sys.exit(1 if n["different"] else 0)


if __name__ == "__main__":
    main()
