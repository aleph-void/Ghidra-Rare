#!/usr/bin/env python3
"""Generate data/languages/dsp56156_gen.sinc: the DSP56156 (DSP561xx) instruction tables.

    python3 tools/gen_dsp56156.py > data/languages/dsp56156_gen.sinc

Encodings follow the Motorola DSP56100 Family Manual (Appendix A Opcode sections) for the
instruction set the DSP56156 User's Manual lists (Table C-2). Where the family manual and the
Motorola ASM56100 assembler disagree, the assembler wins (MOVE(C) X:(A1)/X:(B1): Z = 1 selects
A1).

Every instruction with a parallel move evaluates in three phases, as in the DSP56000 tables:
pmR (move sources and effective addresses), the data ALU operation, pmW (move destinations).
Every root constructor ends with 'tail' (the DO loop end, selected by context); REP and REPcc
repeat their delay-slot instruction.

In p-code, inst_start / inst_next are byte offsets (two bytes per word): word addresses are
inst_next >> 1.
"""
import re
import sys

out = []


def emit(s=""):
    out.append(s)


# ------------------------------------------------------------------ registers
D5 = {0: "X0", 1: "Y0", 2: "X1", 3: "Y1", 4: "A", 5: "B", 6: "A0", 7: "B0", 8: "LC", 9: "SR",
      10: "OMR", 11: "SP", 12: "A1", 13: "B1", 14: "A2", 15: "B2", 24: "SSH", 25: "SSL", 26: "LA"}
for i in range(4):
    D5[16 + i] = "R%d" % i
    D5[20 + i] = "M%d" % i
    D5[28 + i] = "N%d" % i
HHH = {0: "X0", 1: "Y0", 2: "X1", 3: "Y1", 4: "A", 5: "B", 6: "A0", 7: "B0"}
HH = {0: "X0", 1: "Y0", 2: "A", 3: "B"}


def q(n):
    return '"%s"' % n


def rd(n, t):
    """read register n onto the 16-bit bus into local t:2"""
    if n in ("X0", "X1", "Y0", "Y1", "A0", "A1", "B0", "B1", "OMR", "LA", "LC") or n[0] in "RNM":
        return "%s = %s;" % (t, n)
    if n in ("A2", "B2"):
        return "%s = sext(%s);" % (t, n)
    if n in ("A", "B"):
        return "busAcc(%s, %s);" % (n, t)
    if n == "SR":
        return "getSR(%s);" % t
    if n == "SP":
        return "%s = zext(SP);" % t
    if n == "SSH":
        return "local sse:4 = *[ss]:4 SP; %s = sse(2); SP = SP - 1;" % t
    if n == "SSL":
        return "local sse:4 = *[ss]:4 SP; %s = sse:2;" % t
    raise ValueError(n)


def wr(n, v):
    """write the 16-bit value in the low bits of v (MVX/MVY) to register n"""
    if n in ("X0", "X1", "Y0", "Y1", "A0", "A1", "B0", "B1", "OMR", "LA", "LC") or n[0] in "RNM":
        return "%s = %s:2;" % (n, v)
    if n in ("A2", "B2"):
        return "%s = %s:1;" % (n, v)
    if n in ("A", "B"):
        return "local wv:2 = %s:2; accWrite16(%s, wv);" % (v, n)
    if n == "SR":
        return "local wv:2 = %s:2; setSR(wv);" % v
    if n == "SP":
        return "SP = %s:1 & 0x3f;" % v
    if n == "SSH":
        return ("SP = SP + 1; local sse:4 = *[ss]:4 SP; "
                "*[ss]:4 SP = (sse & 0xffff) | (zext(%s:2) << 16);" % v)
    if n == "SSL":
        return ("local sse:4 = *[ss]:4 SP; *[ss]:4 SP = (sse & 0xffff0000) | zext(%s:2);" % v)
    raise ValueError(n)


def regtables(name, table, cons, src="MVX"):
    """<name>R exports the 16-bit bus value; <name>W writes it from src"""
    for code, n in sorted(table.items()):
        emit("%sR: %s is %s { local t:2 = 0; %s export t; }" % (name, q(n), cons(code), rd(n, "t")))
    for code, n in sorted(table.items()):
        emit("%sW: %s is %s { %s }" % (name, q(n), cons(code), wr(n, src)))
    emit()


# ------------------------------------------------------------------ AGU helpers
def upd(r, mode):
    """p-code updating register r (R0..R3 name or field) for a post-update mode"""
    n, m = r.replace("R", "N"), r.replace("R", "M")
    return {"+": "aguAdd(%s, 1:2, 0:1, %s, %s);" % (r, m, r),
            "-": "aguAdd(%s, 0xffff:2, 1:1, %s, %s);" % (r, m, r),
            "+N": "aguAdd(%s, %s, 0:1, %s, %s);" % (r, n, m, r),
            "": ""}[mode]


MODEDISP = {"": '"(%s)"', "+": '"(%s)+"', "-": '"(%s)-"', "+N": '"(%s)+%s"'}


def mdisp(r, mode):
    if mode == "+N":
        return '"(%s)+%s"' % (r, r.replace("R", "N"))
    return MODEDISP[mode] % r


# ------------------------------------------------------------------ data ALU (single-move byte)
CC = ["cc", "ge", "ne", "pl", "nn", "ec", "lc", "gt", "cs", "lt", "eq", "mi", "nr", "es", "ls", "le"]
CCX = ["!C", "!(N ^^ V)", "!Z", "!N", "!(Z || (!U && !E))", "!E", "!L", "!(Z || (N ^^ V))",
       "C", "N ^^ V", "Z", "N", "Z || (!U && !E)", "E", "L", "Z || (N ^^ V)"]


def acc_finish(dst="aF", sat=True):
    return (" satAcc(r);" if sat else "") + " ccEUNZ(r); %s = r;" % dst


def alu_entries(T):
    """(constraint, mnemonic, operand display, p-code) for the single-move ALU byte in token
    T ('f' = first word, 'g' = second word)"""
    F = lambda h, l: "%s%d_%d" % (T, h, l)
    b = lambda i: "%s%d" % ("b" if T == "f" else "c", i)
    aF, aFn, aJ, aXY, Q1, Q2 = ("aF", "aFn", "aJ", "aXY", "aQ1", "aQ2") if T == "f" else \
        ("cF", "cFn", "cJ", "cXY", "cQ1", "cQ2")
    E = []

    def e(cons, mn, ops, code):
        code = code.replace("aFn", "@@N").replace("aF", aF).replace("@@N", aFn)
        code = code.replace("aJ", aJ).replace("aXY", aXY).replace("aQ1", Q1).replace("aQ2", Q2)
        ops = ops.replace("aFn", "@@N").replace("aF", aF).replace("@@N", aFn)
        ops = ops.replace("aJ", aJ).replace("aXY", aXY).replace("aQ1", Q1).replace("aQ2", Q2)
        E.append((cons, mn, ops, code))

    g = lambda grp, lo: "%s=0 & %s=%d & %s=%d" % (b(7), F(6, 4), grp, F(2, 0), lo)
    gj = lambda grp: "%s=0 & %s=%d & %s=1" % (b(7), F(6, 4), grp, b(2))
    SACC = "local s:5 = aFn;"
    SXY = "local s:5 = sext(aXY);"
    SJ = "local s:5 = sext(aJ) << 16;"
    xy = lambda grp, lo: "%s=0 & %s=%d & %s=%d" % (b(7), F(6, 4), grp, F(2, 1), lo)
    # group 0: ADD, CLR
    e(g(0, 0), "add", "aFn,aF", SACC + " local r:5; addFlags(aF, s, 0:1, r);" + acc_finish())
    e(g(0, 1), "clr", "aF", "aF = 0; E = 0; U = 1; N = 0; Z = 1; V = 0;")
    e(xy(0, 1), "add", "aXY,aF", SXY + " local r:5; addFlags(aF, s, 0:1, r);" + acc_finish())
    e(gj(0), "add", "aJ,aF", SJ + " local r:5; addFlags(aF, s, 0:1, r);" + acc_finish())
    # group 1: TFR, MOVE
    e(g(1, 0), "tfr", "aFn,aF", "aF = aFn;")
    e(xy(1, 1), "tfr", "aXY,aF", "aF = sext(aXY);")
    e(gj(1), "tfr", "aJ,aF", SJ + " aF = s;")
    # group 2: RND TST INC INC24 OR
    e(g(2, 0), "rnd", "aF", "local r:5; roundAcc(aF, r); V = !(aF s< 0) && (r s< 0); L = L || V;" + acc_finish())
    e(g(2, 1), "tst", "aF", "ccEUNZ(aF); V = 0; C = 0; S = 0;")
    e(g(2, 2), "inc", "aF", "local one:5 = 1; local r:5; addFlags(aF, one, 0:1, r);" + acc_finish())
    e(g(2, 3), "inc24", "aF", "local one:5 = 0x10000; local r:5; addFlags(aF, one, 0:1, r); satAcc(r); ccEUNZ(r); Z = (r & 0xffffff0000) == 0; aF = r;")
    e(gj(2), "or", "aJ,aF", "local m:2 = aF(2) | aJ; setMid(aF, m); ccLogic(m);")
    # group 3: ASR ASL LSR LSL EOR
    e(g(3, 0), "asr", "aF", "C = (aF & 1) != 0; local r:5 = aF s>> 1; V = 0; ccEUNZ(r); aF = r;")
    e(g(3, 1), "asl", "aF", "local r:5 = aF << 1; C = aF s< 0; V = (aF s< 0) != (r s< 0); L = L || V;" + acc_finish())
    e(g(3, 2), "lsr", "aF", "local m:2 = aF(2); C = (m & 1) != 0; m = m >> 1; setMid(aF, m); ccLogic(m);")
    e(g(3, 3), "lsl", "aF", "local m:2 = aF(2); C = (m & 0x8000) != 0; m = m << 1; setMid(aF, m); ccLogic(m);")
    e(gj(3), "eor", "aJ,aF", "local m:2 = aF(2) ^ aJ; setMid(aF, m); ccLogic(m);")
    # group 4: SUB SUBL
    e(g(4, 0), "sub", "aFn,aF", SACC + " local r:5; subFlags(aF, s, 0:1, r);" + acc_finish())
    e(g(4, 1), "subl", "aFn,aF", SACC + " local t:5 = aF << 1; local v1:1 = (aF s< 0) != (t s< 0); local r:5; subFlags(t, s, 0:1, r); V = V || v1; L = L || V;" + acc_finish())
    e(xy(4, 1), "sub", "aXY,aF", SXY + " local r:5; subFlags(aF, s, 0:1, r);" + acc_finish())
    e(gj(4), "sub", "aJ,aF", SJ + " local r:5; subFlags(aF, s, 0:1, r);" + acc_finish())
    # group 5: CMP CLR24 SBC
    e(g(5, 0), "cmp", "aFn,aF", SACC + " local r:5; subFlags(aF, s, 0:1, r); ccEUNZ(r);")
    e(g(5, 1), "clr24", "aF", "local r:5 = aF & 0xffff; ccEUNZ(r); Z = 1; V = 0; aF = r;")
    e(xy(5, 1), "sbc", "aXY,aF", SXY + " local r:5; subFlags(aF, s, C, r);" + acc_finish())
    e(gj(5), "cmp", "aJ,aF", SJ + " local r:5; subFlags(aF, s, 0:1, r); ccEUNZ(r);")
    # group 6: NEG NOT DEC DEC24 AND
    e(g(6, 0), "neg", "aF", "local z:5 = 0; local r:5; subFlags(z, aF, 0:1, r);" + acc_finish())
    e(g(6, 1), "not", "aF", "local m:2 = ~aF(2); setMid(aF, m); ccLogic(m);")
    e(g(6, 2), "dec", "aF", "local one:5 = 1; local r:5; subFlags(aF, one, 0:1, r);" + acc_finish())
    e(g(6, 3), "dec24", "aF", "local one:5 = 0x10000; local r:5; subFlags(aF, one, 0:1, r); satAcc(r); ccEUNZ(r); Z = (r & 0xffffff0000) == 0; aF = r;")
    e(gj(6), "and", "aJ,aF", "local m:2 = aF(2) & aJ; setMid(aF, m); ccLogic(m);")
    # group 7: CMPM ABS ROR ROL
    e(g(7, 0), "cmpm", "aFn,aF", SACC + " local da:5; abs40(aF, da); local sa:5; abs40(s, sa); local r:5; subFlags(da, sa, 0:1, r); ccEUNZ(r);")
    e(g(7, 1), "abs", "aF", "local r:5; abs40(aF, r); V = r s< 0; L = L || V;" + acc_finish())
    e(g(7, 2), "ror", "aF", "local m:2 = aF(2); local co:1 = (m & 1) != 0; m = (m >> 1) | (zext(C) << 15); C = co; setMid(aF, m); ccLogic(m);")
    e(g(7, 3), "rol", "aF", "local m:2 = aF(2); local co:1 = (m & 0x8000) != 0; m = (m << 1) | zext(C); C = co; setMid(aF, m); ccLogic(m);")
    e(gj(7), "cmpm", "aJ,aF", SJ + " local da:5; abs40(aF, da); local sa:5; abs40(s, sa); local r:5; subFlags(da, sa, 0:1, r); ccEUNZ(r);")
    # multiply: 1 k op op F QQQ
    for op, mn in enumerate(["mpy", "mpyr", "mac", "macr"]):
        code = "local prd:5; fmul(aQ1, aQ2, prd); local sg:5 = %s; prd = prd - ((prd << 1) * sg);" % b(6)
        if op & 2:
            code += " local r:5; local cs:1 = C; addFlags(aF, prd, 0:1, r); C = cs;"
        else:
            code += " local r:5 = prd; V = 0;"
        if op & 1:
            code += " local qq:5; roundAcc(r, qq); V = V || (!(r s< 0) && (qq s< 0)); L = L || V; r = qq;"
        code += acc_finish()
        e("%s=1 & %s=%d" % (b(7), F(5, 4), op), mn, "%s^aQ1^\",\"^aQ2^\",\"^aF" % ("msign" if T == "f" else "msign2"), code)
    return E


def alu_tables(T, suf):
    E = alu_entries(T)
    flds = ("aF & aFn & aJ & aXY & aQ1 & aQ2 & msign & b6" if T == "f" else
            "cF & cFn & cJ & cXY & cQ1 & cQ2 & msign2 & c6")
    for cons, mn, ops, code in E:
        emit('aluMn%s: "%s" is %s { }' % (suf, mn, cons))
    for cons, mn, ops, code in E:
        emit("aluOp%s: %s is %s & %s { %s }" % (suf, ops, cons, flds, code))
    emit()


# ------------------------------------------------------------------ main tables
ROOTS = []


def root(disp, pat, code, tail=True):
    ROOTS.append((disp, pat, code, tail))


def build():
    emit("# generated by tools/gen_dsp56156.py; do not edit")
    emit()
    emit('msign: "-" is b6=1 { }')
    emit('msign: "" is b6=0 { }')
    emit('msign2: "-" is c6=1 { }')
    emit('msign2: "" is c6=0 { }')
    alu_tables("f", "")
    alu_tables("g", "2")

    # condition codes
    for fld, nm in (("f3_0", "cc0"), ("f9_6", "cc6"), ("f11_8", "cc8")):
        for i, c in enumerate(CC):
            emit('%s: "%s" is %s=%d { local t:1 = %s; export t; }' % (nm, c, fld, i, CCX[i]))
    emit()
    # register tables
    regtables("hh", HHH, lambda c: "f11_9=%d" % c)                 # 1mRRHHHW / 0101HHHW
    for code, n in sorted(HHH.items()):
        emit("hhD: %s is f11_9=%d { }" % (q(n), code))
        emit("g2hD: %s is g11_9=%d { }" % (q(n), code))
    regtables("hhy", HHH, lambda c: "f11_9=%d" % c, "MVY")
    regtables("g2h", HHH, lambda c: "g11_9=%d" % c)                # (R2+xx) second word
    regtables("t3h", HHH, lambda c: "f2_0=%d" % c)                 # TFR3 D2/S2
    regtables("mmh", HHH, lambda c: "f2_0=%d" % c)                 # MOVE(M) HHH
    regtables("mmh2", HHH, lambda c: "g2_0=%d" % c)                # MOVE(M) (R2+xx)
    regtables("sh", HH, lambda c: "f7_6=%d" % c)                   # MOVE(S)/(P) HH
    regtables("dc", D5, lambda c: "f9_5=%d" % c)                   # MOVE(C) DDDDD (bits 9..5)
    regtables("dc2", D5, lambda c: "g9_5=%d" % c)                  # MOVE(C) (R2+xx)
    regtables("dl", D5, lambda c: "f4_0=%d" % c)                   # DDDDD at 4..0
    regtables("ds", D5, lambda c: "f9_5=%d" % c)                   # MOVE(C) S,D source ddddd

    # ---------------- parallel moves (pmR displayed, pmW write phase)
    P = []

    def pm(cls, pat, d, r, w):
        P.append((cls, pat, d, r, w))

    # X memory move 1 m RR HHH W: m = 0 (Rn)+, 1 (Rn)+Nn
    for m, mode in ((0, "+"), (1, "+N")):
        for rr in range(4):
            R = "R%d" % rr
            dsp = mdisp(R, mode)
            pat = "b15=1 & b14=%d & f13_12=%d" % (m, rr)
            pm("x", pat + " & b8=1 & hhD", '"X:"^%s^","^hhD' % dsp,
               "EAX = %s; %s MVX = zext(*[x]:2 EAX);" % (R, upd(R, mode)), "build hhW;")
            pm("x", pat + " & b8=0 & hhR", 'hhR^",X:"^%s' % dsp,
               "EAX = %s; %s MVX = zext(hhR);" % (R, upd(R, mode)), "*[x]:2 EAX = MVX:2;")
    # X:(F1) move 0101 HHH W, F1 = upper word of the accumulator the ALU op does not use
    pm("f1", "f15_12=5 & b8=1 & hhD & aFn1", '"X:("^aFn1^")"^","^hhD',
       "EAX = aFn1; MVX = zext(*[x]:2 EAX);", "build hhW;")
    pm("f1", "f15_12=5 & b8=0 & hhR & aFn1", 'hhR^",X:("^aFn1^")"',
       "EAX = aFn1; MVX = zext(hhR);", "*[x]:2 EAX = MVX:2;")
    # register to register 0100 IIII
    IIII = {0: ("X0", "F"), 1: ("Y0", "F"), 2: ("X1", "F"), 3: ("Y1", "F"),
            4: ("A", "X0"), 5: ("B", "Y0"), 6: ("A0", "X0"), 7: ("B0", "Y0"),
            8: ("B", "A"), 9: ("A", "B"), 12: ("A", "X1"), 13: ("B", "Y1"), 14: ("A0", "X1"),
            15: ("B0", "Y1")}
    for i, (s, dd) in IIII.items():
        pat = "f15_12=4 & f11_8=%d" % i
        if dd == "F":
            pm("r", pat + " & aFn", '"%s,"^aFn' % s, "MVX = zext(%s);" % s,
               "local wv:2 = MVX:2; accWrite16(aFn, wv);")
        else:
            rdc = rd(s, "t")
            pm("r", pat, '"%s,%s"' % (s, dd), "local t:2 = 0; %s MVX = zext(t);" % rdc, wr(dd, "MVX"))
    pm("r", "f15_12=4 & f11_8=10", '""', "", "")
    # address register update 0011 0 z RR: z = 0 (Rn)-, 1 (Rn)+Nn
    for z, mode in ((0, "-"), (1, "+N")):
        for rr in range(4):
            R = "R%d" % rr
            pm("u", "f15_11=6 & b10=%d & f9_8=%d" % (z, rr), mdisp(R, mode), upd(R, mode), "")
    emit('r2d: "+"^f7_0 is b7=0 & f7_0 { }')
    emit('r2d: "-"^tgt is b7=1 & f7_0 [ tgt = 256 - f7_0; ] { }')
    emit("f7_0s: tgt is f7_0s8 [ tgt = f7_0s8 + 0; ] { export *[const]:2 tgt; }")
    for cls, pat, d, r, w in P:
        emit("pmR_%s: %s is %s { %s }" % (cls, d, pat, r))
    emit()
    for cls, pat, d, r, w in P:
        wpat = pat.split(";")[0] if cls != "r2" else pat
        wpat = re.sub(r" & (g2h|hh)[RD]\b", "", wpat)
        wpat = re.sub(r" & aFn1\b", "", wpat)
        wpat = re.sub(r" & f7_0s\b", "", wpat)
        if "build hhW" in w:
            wpat += " & hhW"
        if "build g2hW" in w:
            wpat += " & g2hW"
        emit("pmW_%s: is %s { %s }" % (cls, wpat, w))
    emit()

    # ---------------- dual X memory read: 011 mm KKK | X rr u F uuu
    # KKK: D1 (first read, R0-R2) / D2 (second read, R3)
    KKK = {0: ("F", "X0"), 1: ("Y0", "X0"), 2: ("X1", "X0"), 3: ("Y1", "X0"),
           4: ("X0", "X1"), 5: ("Y0", "X1"), 6: ("F", "Y0"), 7: ("Y1", "X1")}
    for mm in range(4):
        m1 = "+N" if mm & 2 else "+"
        m2 = "+N" if mm & 1 else "+"
        for rr in range(3):
            R = "R%d" % rr
            for k, (d1, d2) in KKK.items():
                d1d = "dFn" if d1 == "F" else q(d1)
                pat = "f12_11=%d & f6_5=%d & f10_8=%d" % (mm, rr, k)
                if d1 == "F":
                    pat += " & dFn"
                disp = '"X:"^%s^","^%s^" X:"^%s^",%s"' % (mdisp(R, m1), d1d, mdisp("R3", m2), d2)
                rcode = ("EAX = %s; EAY = R3; %s %s MVX = zext(*[x]:2 EAX); MVY = zext(*[x]:2 EAY);"
                         % (R, upd(R, m1), upd("R3", m2)))
                if d1 == "F":
                    wcode = "local wv:2 = MVX:2; accWrite16(dFn, wv); %s = MVY:2;" % d2
                else:
                    wcode = "%s = MVX:2; %s = MVY:2;" % (d1, d2)
                emit("dmR: %s is %s { %s }" % (disp, pat, rcode))
                emit("dmW: is %s { %s }" % (pat, wcode))
    emit()
    # dual-read data ALU byte: X rr u F uuu
    DQ = {0: ("X0", "Y0"), 1: ("X0", "Y1"), 2: ("X1", "Y0"), 3: ("X1", "Y1")}
    DE = []
    J4 = ["X0", "Y0", "X1", "Y1"]
    for k in range(4):
        DE.append(("b7=0 & b4=0 & b2=0 & f1_0=%d" % k, "add", '"%s,"^dF' % J4[k],
                   "local s:5 = sext(%s) << 16; local r:5; addFlags(dF, s, 0:1, r); satAcc(r); ccEUNZ(r); dF = r;" % J4[k]))
        DE.append(("b7=0 & b4=0 & b2=1 & f1_0=%d" % k, "sub", '"%s,"^dF' % J4[k],
                   "local s:5 = sext(%s) << 16; local r:5; subFlags(dF, s, 0:1, r); satAcc(r); ccEUNZ(r); dF = r;" % J4[k]))
        DE.append(("b7=0 & b4=1 & b2=0 & f1_0=%d" % k, "tfr", '"%s,"^dF' % J4[k],
                   "dF = sext(%s) << 16;" % J4[k]))
    DE.append(("b7=0 & b4=1 & f2_0=4", "add", "dFn^\",\"^dF", "local s:5 = dFn; local r:5; addFlags(dF, s, 0:1, r); satAcc(r); ccEUNZ(r); dF = r;"))
    DE.append(("b7=0 & b4=1 & f2_0=5", "sub", "dFn^\",\"^dF", "local s:5 = dFn; local r:5; subFlags(dF, s, 0:1, r); satAcc(r); ccEUNZ(r); dF = r;"))
    DE.append(("b7=0 & b4=1 & f2_0=6", "tfr", "dFn^\",\"^dF", "dF = dFn;"))
    for k1 in (0, 1):
        for k0 in (0, 1):
            mn = [["mpy", "mac"], ["mpyr", "macr"]][k1][k0]
            for qq, (s1, s2) in DQ.items():
                code = "local prd:5; fmul(%s, %s, prd);" % (s1, s2)
                if k0:
                    code += " local r:5; local cs:1 = C; addFlags(dF, prd, 0:1, r); C = cs;"
                else:
                    code += " local r:5 = prd; V = 0;"
                if k1:
                    code += " local qq:5; roundAcc(r, qq); V = V || (!(r s< 0) && (qq s< 0)); L = L || V; r = qq;"
                code += " satAcc(r); ccEUNZ(r); dF = r;"
                DE.append(("b7=1 & b4=%d & b2=%d & f1_0=%d" % (k1, k0, qq), mn,
                           '"%s,%s,"^dF' % (s1, s2), code))
    for cons, mn, ops, code in DE:
        emit('daMn: "%s" is %s { }' % (mn, cons))
    for cons, mn, ops, code in DE:
        emit("daOp: %s is %s & dF & dFn { %s }" % (ops, cons, code))
    emit()

    # ---------------- non-parallel instructions
    JSUB = "local srv:2; getSR(srv); local nx:2 = inst_next >> 1; sspush(nx, srv); "
    root(":nop", "w16=0", "")
    root(":debug", "w16=1", "debugMode();")
    root(":chkaau", "w16=4", "V = AGUW; Z = AGUR == 0; N = AGUR s< 0;")
    root(":swi", "w16=5", "softwareInterrupt();")
    root(":rts", "w16=6", "local e:4 = *[ss]:4 SP; SP = SP - 1; local pc:2 = e(2); return [pc];")
    root(":rti", "w16=7", "local e:4 = *[ss]:4 SP; SP = SP - 1; local sr:2 = e:2; setSR(sr); local pc:2 = e(2); return [pc];")
    root(":reset", "w16=8", "resetPeripherals();")
    root(":enddo", "w16=9",
         "local e:4 = *[ss]:4 SP; SP = SP - 1; local sr:2 = e:2; MR = (MR & 0x3f) | (sr(1) & 0xc0); "
         "e = *[ss]:4 SP; SP = SP - 1; LA = e(2); LC = e:2;")
    root(":stop", "w16=0xa", "stopProcessing();")
    root(":wait", "w16=0xb", "waitForInterrupt();")
    root(":illegal", "w16=0xf", "illegal();")
    root(":debug^cc0", "f15_4=0x005 & cc0", "if (!cc0) goto inst_next; debugMode();")
    root(":brk^cc0", "f15_4=0x011 & cc0",
         "if (!cc0) goto inst_next; local tg:2 = LA + 1; "
         "local e:4 = *[ss]:4 SP; SP = SP - 1; local sr:2 = e:2; MR = (MR & 0x3f) | (sr(1) & 0xc0); "
         "e = *[ss]:4 SP; SP = SP - 1; LA = e(2); LC = e:2; goto [tg];")
    # JSR/JMP/BSR/BRA Rn and xxxx
    root(":jsr f1_0r", "f15_2=0x048 & f1_0r", JSUB + "call [f1_0r];")
    root(":jmp f1_0r", "f15_2=0x049 & f1_0r", "goto [f1_0r];")
    root(":bsr f1_0r", "f15_2=0x04a & f1_0r", JSUB + "local tg:2 = (inst_start >> 1) + f1_0r; call [tg];")
    root(":bra f1_0r", "f15_2=0x04b & f1_0r", "local tg:2 = (inst_start >> 1) + f1_0r; goto [tg];")
    root(":jsr jabs", "f15_2=0x04c; jabs", JSUB + "call jabs;")
    root(":jmp jabs", "f15_2=0x04d; jabs", "goto jabs;")
    root(":bsr jrel", "f15_2=0x04e; jrel", JSUB + "call jrel;")
    root(":bra jrel", "f15_2=0x04f; jrel", "goto jrel;")
    root(":jsr j8", "f15_8=0x0a & j8", JSUB + "call j8;")
    root(":bra j8r", "f15_8=0x0b & j8r", "goto j8r;")
    # Jcc/JScc/Bcc/BScc
    for hb, kind in ((6, "j"), (7, "b")):
        tgt_x = "jabs" if kind == "j" else "jrel"
        root(":%s^cc0 %s" % (kind, tgt_x), "f15_8=%d & f5_4=3 & cc0; %s" % (hb, tgt_x), "if (cc0) goto %s;" % tgt_x)
        root(":%ss^cc0 %s" % (kind, tgt_x), "f15_8=%d & f5_4=1 & cc0; %s" % (hb, tgt_x),
             "if (!cc0) goto inst_next; " + JSUB + "call %s;" % tgt_x)
        if kind == "j":
            root(":j^cc0 f7_6r", "f15_8=6 & f5_4=2 & cc0 & f7_6r", "if (!cc0) goto inst_next; goto [f7_6r];")
            root(":js^cc0 f7_6r", "f15_8=6 & f5_4=0 & cc0 & f7_6r", "if (!cc0) goto inst_next; " + JSUB + "call [f7_6r];")
        else:
            root(":b^cc0 f7_6r", "f15_8=7 & f5_4=2 & cc0 & f7_6r",
                 "if (!cc0) goto inst_next; local tg:2 = (inst_start >> 1) + f7_6r; goto [tg];")
            root(":bs^cc0 f7_6r", "f15_8=7 & f5_4=0 & cc0 & f7_6r",
                 "if (!cc0) goto inst_next; " + JSUB + "local tg:2 = (inst_start >> 1) + f7_6r; call [tg];")
    root(":b^cc6 j6r", "f15_10=0x0b & cc6 & j6r", "if (cc6) goto j6r;")
    # REPcc
    # REPcc: repeat the next (one-word) instruction until cc is true; skip it if cc on entry
    # The repeated instruction runs through delayslot(1) in a loop, so the same instruction
    # reached by a jump runs once (no disassembly context); the condition is re-evaluated
    # after every pass.
    for i, c in enumerate(CC):
        root(":rep^cc0", "f15_4=0x015 & cc0 & f3_0=%d & skip1" % i,
             "if (%s) goto skip1; <rep_top> delayslot(1); if (!(%s)) goto <rep_top>;" % (CCX[i], CCX[i]),
             tail=False)
    # LEA
    for nn in (0, 1):
        for mm, mode in enumerate(["", "+", "-", "+N"]):
            if mm == 0:
                continue        # MM = 00 is not an update mode (the assembler emits MOVE(C) Rn,D)
            for rr in range(4):
                R = "R%d" % rr
                for tt in range(4):
                    dst = ("N%d" if nn == 0 else "R%d") % tt
                    if mode == "":
                        code = "%s = %s;" % (dst, R)
                    else:
                        c = upd(R, mode).replace(", %s);" % R, ", r);")
                        code = "local r:2; %s %s = r;" % (c, dst)
                    root(':lea %s,"%s"' % (mdisp(R, mode), dst),
                         "f15_7=0x003 & b6=%d & f5_4=%d & f3_2=%d & f1_0=%d" % (nn, tt, mm, rr), code)
    # REP / DO
    REPL = "LCSV = LC; LC = %s; <rep_top> delayslot(1); LC = LC - 1; if (LC != 0) goto <rep_top>; LC = LCSV;"
    root(':rep "#"^f7_0', "f15_8=0x0f & f7_0", REPL % "f7_0", tail=False)
    root(":rep dlR", "f15_5=0x021 & dlR", "local n:2 = dlR; " + REPL % "n", tail=False)
    root(':rep "X:("^f1_0r^")"', "f15_5=0x007 & f1_0r",
         "local a:2 = f1_0r; local n:2 = *[x]:2 a; " + REPL % "n", tail=False)
    ctx = ("lend = 1; laddr = inst_start + 1 + es16; lstart = inst_start + 2; "
           "globalset(laAt, lend); globalset(laAt, laddr); globalset(laAt, lstart); "
           "globalset(laPrev, lend); globalset(laPrev, laddr); globalset(laPrev, lstart);")
    dosem = ("local srv:2; getSR(srv); local nx:2 = inst_next >> 1; sspush(LA, LC); sspush(nx, srv); "
             "LA = (inst_start >> 1) + 1 + es16; LC = %s; MR = MR | 0x80;")
    root(':do "#"^f7_0,dolast', "f15_8=0x0e & f7_0; dolast & laAt & laPrev & es16 [ " + ctx + " ]",
         dosem % "f7_0", tail=False)
    root(":do dlR,dolast", "f15_5=0x020 & dlR; dolast & laAt & laPrev & es16 [ " + ctx + " ]",
         dosem % "dlR", tail=False)
    root(':do "X:("^f1_0r^")",dolast', "f15_5=0x006 & f1_0r; dolast & laAt & laPrev & es16 [ " + ctx + " ]",
         "local a:2 = f1_0r; local v:2 = *[x]:2 a; " + dosem % "v", tail=False)
    root(':do "forever",dolast', "w16=2; dolast & laAt & laPrev & es16 [ " + ctx + " ]",
         (dosem % "LC").replace("MR = MR | 0x80;", "MR = MR | 0xc0;"), tail=False)
    # Tcc 0001 00cc ccTT Fh0h
    for h1 in (0, 1):
        for h0 in (0, 1):
            for fb in (0, 1):
                dst = "AB"[fb]
                xfer = True
                if h1:
                    src = ["X0", "Y0"][h0]
                    val = "sext(%s) << 16" % src
                elif h0 == 0:
                    src = "AB"[1 - fb]
                    val = src
                else:
                    xfer = False        # h0h = 001: no data ALU transfer (R0,Rn only)
                pat = "f15_10=4 & cc6 & b3=%d & b2=%d & b1=0 & b0=%d" % (fb, h1, h0)
                acode = "%s = %s;" % (dst, val) if xfer else ""
                if xfer:
                    root(':t^cc6 "%s,%s"' % (src, dst), pat + " & f5_4=0",
                         "if (!cc6) goto inst_next; %s" % acode)
                root((':t^cc6 "%s,%s" "R0,"^f5_4r' % (src, dst)) if xfer else ':t^cc6 "R0,"^f5_4r',
                     pat + (" & f5_4!=0" if xfer else "") + " & f5_4r",
                     "if (!cc6) goto inst_next; local rs:2 = R0; %s f5_4r = rs;" % acode)
    # TFR2 ADC DIV TST2 NORM ASR4 ASL4 ZERO EXT NEGC ASR16 SWAP IMPY IMAC DMAC MPY/MACsu/uu
    P15 = "f15_8=0x15 & "
    root(":tfr2 eF,eXY", P15 + "f7_4=0 & b2=0 & b1=0 & eF & eXY",
         "local hi:8 = sext(eF) s>> 31; local ok:1 = (hi == 0) || (hi == -1); "
         "local satv:4 = 0x7fffffff + zext(eF s< 0); "
         "eXY = eF:4 * zext(ok) + satv * zext(!ok); L = L || !ok;")
    root(":adc eXY,eF", P15 + "f7_4=0 & b2=0 & b1=1 & eF & eXY",
         "local s:5 = sext(eXY); local r:5; addFlags(eF, s, C, r); satAcc(r); ccEUNZ(r); eF = r;")
    root(":div eJ,eF", P15 + "b7=0 & b4=0 & b2=1 & eF & eJ",
         "local sx:1 = (eF s< 0) != (eJ s< 0); local t:5 = (eF << 1) | zext(C); "
         "local hi:3 = t(2); local s:3 = sext(eJ); local r:3 = hi + s * zext(sx) - s * zext(!sx); "
         "local res:5 = (zext(r) << 16) | (t & 0xffff); "
         "V = (eF s< 0) != ((eF << 1) s< 0); L = L || V; C = !(res s< 0); eF = res;")
    root(":tst2 eJ", P15 + "f7_4=1 & b2=1 & eJ",
         "local r:5 = sext(eJ) << 16; ccEUNZ(r); V = 0; C = 0; L = 0; E = 0; U = 0;")
    root(":norm f1_0r,eF", P15 + "f7_4=2 & b2=0 & eF & f1_0r",
         "ccEUNZ(eF); local up:1 = !E && U && !Z; local dn:1 = E; "
         "local r:5 = (eF << 1) * zext(up) + (eF s>> 1) * zext(dn) + eF * zext(!up && !dn); "
         "V = (eF s< 0) != (r s< 0); L = L || V; f1_0r = f1_0r - zext(up) + zext(dn); ccEUNZ(r); eF = r;")
    root(":asr4 eF", P15 + "f7_4=3 & f2_0=0 & eF",
         "C = (eF & 8) != 0; local r:5 = eF s>> 4; V = 0; ccEUNZ(r); eF = r;")
    root(":asl4 eF", P15 + "f7_4=3 & f2_0=1 & eF",
         "C = (eF & 0x1000000000) != 0; local r:5 = eF << 4; local hi:8 = sext(eF) s>> 35; "
         "V = (hi != 0) && (hi != -1); L = L || V; ccEUNZ(r); eF = r;")
    root(":zero eF", P15 + "f7_4=5 & f2_0=0 & eF", "local r:5 = eF & 0xffffffff; ccEUNZ(r); V = 0; eF = r;")
    root(":ext eF", P15 + "f7_4=5 & f2_0=2 & eF", "local w:4 = eF:4; local r:5 = sext(w); ccEUNZ(r); V = 0; eF = r;")
    root(":negc eF", P15 + "f7_4=6 & f2_0=0 & eF",
         "local z:5 = 0; local r:5; subFlags(z, eF, C, r); satAcc(r); ccEUNZ(r); eF = r;")
    root(":asr16 eF", P15 + "f7_4=7 & f2_0=0 & eF",
         "C = (eF & 0x8000) != 0; local r:5 = eF s>> 16; V = 0; ccEUNZ(r); eF = r;")
    root(":swap eF", P15 + "f7_4=7 & f2_0=1 & eF", "local hi:2 = eF(2); local lo:2 = eF:2; eF = (eF & 0xff00000000) | (zext(lo) << 16) | zext(hi);")
    root(":impy eQ1,eQ2,eF", P15 + "f7_4=8 & eF & eQ1 & eQ2",
         "local prd:4 = sext(eQ1) * sext(eQ2); local w:3 = prd:3; eF = (sext(w) << 16) | (eF & 0xffff); "
         "local r:5 = eF; ccEUNZ(r);")
    root(":imac eQ1,eQ2,eF", P15 + "f7_4=10 & eF & eQ1 & eQ2",
         "local prd:4 = sext(eQ1) * sext(eQ2); local hi3:3 = eF(2); local acc:4 = sext(hi3); local sm:4 = prd + acc; local w:3 = sm:3; "
         "eF = (sext(w) << 16) | (eF & 0xffff); local r:5 = eF; ccEUNZ(r);")
    DQ2 = {0: ("Y0", "X0"), 1: ("Y1", "X0"), 2: ("X1", "Y0"), 3: ("X1", "Y1")}
    for name, pat, s1sign, s2sign, acc in (
            ("dmacss", "f7_4=9 & b2=0", 1, 1, "dmac"), ("dmacss", "f7_4=9 & b2=1", 1, 1, "dmac"),
            ("dmacsu", "f7_4=11 & b2=0", 1, 0, "dmac"), ("dmacuu", "f7_4=11 & b2=1", 0, 0, "dmac"),
            ("mpysu", "f7_4=12 & b2=0", 1, 0, "mpy"), ("mpyuu", "f7_4=12 & b2=1", 0, 0, "mpy"),
            ("macsu", "f7_4=14 & b2=0", 1, 0, "mac"), ("macuu", "f7_4=14 & b2=1", 0, 0, "mac")):
        for qq, (s1, s2) in DQ2.items():
            e1 = "sext(%s)" % s1 if s1sign else "zext(%s)" % s1
            e2 = "sext(%s)" % s2 if s2sign else "zext(%s)" % s2
            code = "local prd:5 = (%s * %s) << 1;" % (e1, e2)
            if acc == "dmac":
                code += " local base:5 = eF s>> 16; local r:5; local cs:1 = C; addFlags(base, prd, 0:1, r); C = cs;"
            elif acc == "mac":
                code += " local r:5; local cs:1 = C; addFlags(eF, prd, 0:1, r); C = cs;"
            else:
                code += " local r:5 = prd; V = 0;"
            if name == "dmacss":
                code += " satAcc(r);"
            code += " ccEUNZ(r); eF = r;"
            root(':%s "%s,%s,"^eF' % (name, s1, s2), P15 + pat + " & f1_0=%d & eF" % qq, code)
    # MPY/MAC with X memory write and register move: 0001 011k RR DD F QQQ
    MQ = {0: ("X0", "X0"), 1: ("X1", "X0"), 2: ("A1", "Y0"), 3: ("B1", "X0"),
          4: ("Y0", "X0"), 5: ("Y1", "X0"), 6: ("Y0", "X1"), 7: ("Y1", "X1")}
    DDm = ["X0", "Y0", "X1", "Y1"]
    for k, mn in ((0, "mpy"), (1, "mac")):
        for qqq, (s1, s2) in MQ.items():
            for dd in range(4):
                code = ("local wv:2; busAcc(eFn, wv); EAX = f7_6r; aguAdd(f7_6r, f7_6n, 0:1, f7_6m, f7_6r); "
                        "local mvv:2 = %s; local prd:5; fmul(%s, %s, prd);" % (DDm[dd], s1, s2))
                code += (" local r:5; local cs:1 = C; addFlags(eF, prd, 0:1, r); C = cs;" if k
                         else " local r:5 = prd; V = 0;")
                code += " satAcc(r); ccEUNZ(r); eF = r; *[x]:2 EAX = wv; accWrite16(eFn, mvv);"
                root(':%s "%s,%s,"^eF eFn^",X:("^f7_6r^")+"^f7_6n "%s,"^eFn2' % (mn, s1, s2, DDm[dd]),
                     "f15_9=0x0b & b8=%d & f5_4=%d & f2_0=%d & eF & eFn & eFn2 & f7_6r & f7_6n & f7_6m"
                     % (k, dd, qqq), code)
    # TFR3: 0010 01 m W RR DD F HHH: S1 (A/B by DD) -> D1, X:ea <-> D2/S2
    T3 = {0: ("A", "X0"), 1: ("B", "X0"), 2: ("A", "Y0"), 3: ("B", "Y0")}
    T3b = {0: ("A", "X1"), 1: ("B", "X1"), 2: ("A", "Y1"), 3: ("B", "Y1")}
    for m, mode in ((0, "+"), (1, "+N")):
        for rr in range(4):
            R = "R%d" % rr
            for ddf in range(8):
                dd, fb = ddf >> 1, ddf & 1
                s1, d1 = (T3 if fb == 0 else T3b)[dd]
                s1, d1 = {0: ("A", "X0"), 1: ("B", "X0"), 2: ("A", "Y0"), 3: ("B", "Y0"),
                          4: ("A", "X1"), 5: ("B", "X1"), 6: ("A", "Y1"), 7: ("B", "Y1")}[ddf]
                pre = "local s1:2; busAcc(%s, s1); EAX = %s; %s " % (s1, R, upd(R, mode))
                base = "f15_10=9 & b9=%d & f7_6=%d & f5_4=%d & b3=%d" % (m, rr, dd, fb)
                ddf_pat = "f5_3=%d" % ddf
                base = "f15_10=9 & b9=%d & f7_6=%d & %s" % (m, rr, ddf_pat)
                root(':tfr3 "%s,%s" "X:"^%s^","^t3hW' % (s1, d1, mdisp(R, mode)),
                     base + " & b8=1 & t3hW",
                     pre + "MVX = zext(*[x]:2 EAX); %s = s1; build t3hW;" % d1)
                root(':tfr3 "%s,%s" t3hR^",X:"^%s' % (s1, d1, mdisp(R, mode)),
                     base + " & b8=0 & t3hR",
                     pre + "local v:2 = t3hR; %s = s1; *[x]:2 EAX = v;" % d1)
    # MOVE(I) #xx,D (X0 Y0 X1 Y1): 0010 00 DD iiiiiiii
    for dd, n in enumerate(["X0", "Y0", "X1", "Y1"]):
        root(':move "#<"^f7_0s8,"%s"' % n, "f15_10=8 & f9_8=%d & f7_0s & f7_0s8" % dd,
             "local v:2 = f7_0s; %s = v;" % n)
    # MOVE(C) S,D register: 0010 10 ddddd DDDDD
    root(":move dsR,dlW", "f15_10=0x0a & dsR & dlW", "MVX = zext(dsR); build dlW;")
    # MOVE(C) X:<ea> 0011 1 W DDDDD ...
    MC = "f15_11=7 & "
    for mm, mode in enumerate(["", "+", "-", "+N"]):
        for rr in range(4):
            R = "R%d" % rr
            pat = MC + "b4=0 & f3_2=%d & f1_0=%d" % (mm, rr)
            root(':move "X:"^%s^","^dcW' % mdisp(R, mode), pat + " & b10=1 & dcW",
                 "EAX = %s; %s MVX = zext(*[x]:2 EAX); build dcW;" % (R, upd(R, mode)))
            root(':move dcR^",X:"^%s' % mdisp(R, mode), pat + " & b10=0 & dcR",
                 "EAX = %s; %s local v:2 = dcR; *[x]:2 EAX = v;" % (R, upd(R, mode)))
    for qbit, (d, kind) in enumerate([("(%s+%s)", "idx"), ("-(%s)", "pre")]):
        for rr in range(4):
            R = "R%d" % rr
            N, M = "N%d" % rr, "M%d" % rr
            dsp = '"%s"' % (d % (R, N) if kind == "idx" else d % R)
            if kind == "idx":
                ea = "aguAdd(%s, %s, 0:1, %s, EAX);" % (R, N, M)
            else:
                ea = "aguAdd(%s, 0xffff:2, 1:1, %s, %s); EAX = %s;" % (R, M, R, R)
            pat = MC + "b4=1 & b3=%d & b2=0 & f1_0=%d" % (qbit, rr)
            root(':move "X:"^%s^","^dcW' % dsp, pat + " & b10=1 & dcW", ea + " MVX = zext(*[x]:2 EAX); build dcW;")
            root(':move dcR^",X:"^%s' % dsp, pat + " & b10=0 & dcR", ea + " local v:2 = dcR; *[x]:2 EAX = v;")
    for z, acc in ((1, "A1"), (0, "B1")):
        pat = MC + "b4=1 & b3=%d & f2_1=3" % z
        root(':move "X:(%s),"^dcW' % acc, pat + " & b10=1 & dcW", "EAX = %s; MVX = zext(*[x]:2 EAX); build dcW;" % acc)
        root(':move dcR^",X:(%s)"' % acc, pat + " & b10=0 & dcR", "EAX = %s; local v:2 = dcR; *[x]:2 EAX = v;" % acc)
    root(':move "X:>"^e16^","^dcW', MC + "b4=1 & b3=0 & f2_1=2 & b10=1 & dcW; e16",
         "EAX = e16; MVX = zext(*[x]:2 EAX); build dcW;")
    root(':move dcR^",X:>"^e16', MC + "b4=1 & b3=0 & f2_1=2 & b10=0 & dcR; e16",
         "local v:2 = dcR; *[x]:2 e16:2 = v;")
    root(':move "#>"^e16^","^dcW', MC + "b4=1 & b3=1 & f2_1=2 & b10=1 & dcW; e16",
         "MVX = e16; build dcW;")
    # MOVE(C) X:(R2+xx) and MOVE(M) P:(R2+xx) (second word)
    root(':move "X:(R2"^r2d^"),"^dc2W', "f15_8=5 & f7_0s & r2d; g15_11=7 & c10=1 & c4=0 & dc2W",
         "local d:2 = f7_0s; EAX = R2 + d; MVX = zext(*[x]:2 EAX); build dc2W;")
    root(':move dc2R^",X:(R2"^r2d^")"', "f15_8=5 & f7_0s & r2d; g15_11=7 & c10=0 & c4=0 & dc2R",
         "local d:2 = f7_0s; EAX = R2 + d; local v:2 = dc2R; *[x]:2 EAX = v;")
    root(':move "P:(R2"^r2d^"),"^mmh2W', "f15_8=5 & f7_0s & r2d; g15_9=1 & c8=1 & c5=0 & mmh2W",
         "local d:2 = f7_0s; EAX = R2 + d; MVX = zext(*[p]:2 EAX); build mmh2W;")
    root(':move mmh2R^",P:(R2"^r2d^")"', "f15_8=5 & f7_0s & r2d; g15_9=1 & c8=0 & c5=0 & mmh2R",
         "local d:2 = f7_0s; EAX = R2 + d; local v:2 = mmh2R; *[p]:2 EAX = v;")
    # MOVE(M) P:<ea> <-> register: 0000 001W RR0MMHHH; P:<ea> <-> X:<ea>: 0000 001W RR11mmRR
    for mm, mode in enumerate(["", "+", "-", "+N"]):
        for rr in range(4):
            R = "R%d" % rr
            pat = "f15_9=1 & f7_6=%d & b5=0 & f4_3=%d" % (rr, mm)
            root(':move "P:"^%s^","^mmhW' % mdisp(R, mode), pat + " & b8=1 & mmhW",
                 "EAX = %s; %s MVX = zext(*[p]:2 EAX); build mmhW;" % (R, upd(R, mode)))
            root(':move mmhR^",P:"^%s' % mdisp(R, mode), pat + " & b8=0 & mmhR",
                 "EAX = %s; %s local v:2 = mmhR; *[p]:2 EAX = v;" % (R, upd(R, mode)))
    for mm in range(4):
        ms = "+N" if mm & 2 else "+"
        md = "+N" if mm & 1 else "+"
        for rs in range(4):
            for rd_ in range(4):
                S, Dd = "R%d" % rs, "R%d" % rd_
                pat = "f15_9=1 & f7_6=%d & f5_4=3 & f3_2=%d & f1_0=%d" % (rs, mm, rd_)
                code_w = ("EAX = %s; EAY = %s; %s %s" % (S, Dd, upd(S, ms), upd(Dd, md)))
                root(':move "P:"^%s^",X:"^%s' % (mdisp(S, ms), mdisp(Dd, md)), pat + " & b8=0",
                     code_w + " local v:2 = *[p]:2 EAX; *[x]:2 EAY = v;")
                root(':move "X:"^%s^",P:"^%s' % (mdisp(S, ms), mdisp(Dd, md)), pat + " & b8=1",
                     code_w + " local v:2 = *[x]:2 EAX; *[p]:2 EAY = v;")
    # MOVE(S) X:<aa> and MOVE(P) X:<pp>: 0001 100W HH b5 aaaaa
    root(':moves "X:<"^f4_0^","^shW', "f15_9=0x0c & b8=1 & b5=0 & f4_0 & shW",
         "EAX = f4_0; MVX = zext(*[x]:2 EAX); build shW;")
    root(':moves shR^",X:<"^f4_0', "f15_9=0x0c & b8=0 & b5=0 & f4_0 & shR",
         "local v:2 = shR; *[x]:2 f4_0:2 = v;")
    root(':movep "X:<<"^pp5^","^shW', "f15_9=0x0c & b8=1 & b5=1 & pp5 & shW",
         "EAX = pp5; MVX = zext(*[x]:2 EAX); build shW;")
    root(':movep shR^",X:<<"^pp5', "f15_9=0x0c & b8=0 & b5=1 & pp5 & shR",
         "local v:2 = shR; local a:2 = pp5; *[x]:2 a = v;")
    # MOVE(P) X:<ea> <-> X:<pp>: 0000 110W RR m ppppp
    for m, mode in ((0, "+"), (1, "+N")):
        for rr in range(4):
            R = "R%d" % rr
            pat = "f15_9=6 & f7_6=%d & b5=%d & pp5" % (rr, m)
            root(':movep "X:"^%s^",X:<<"^pp5' % mdisp(R, mode), pat + " & b8=1",
                 "EAX = %s; %s local v:2 = *[x]:2 EAX; local a:2 = pp5; *[x]:2 a = v;" % (R, upd(R, mode)))
            root(':movep "X:<<"^pp5^",X:"^%s' % mdisp(R, mode), pat + " & b8=0",
                 "EAX = %s; %s local a:2 = pp5; local v:2 = *[x]:2 a; *[x]:2 EAX = v;" % (R, upd(R, mode)))
    # ANDI / ORI: 0001 1 EE o iiiiiiii (EE: 01 MR, 10 OMR, 11 CCR)
    for o, (nm, sym) in enumerate((("andi", "&"), ("ori", "|"))):
        for ee, reg in ((1, "MR"), (2, "OMR"), (3, "CCR")):
            if reg == "MR":
                code = "MR = MR %s f7_0:1;" % sym
            elif reg == "CCR":
                code = "local c:1; getCCR(c); c = c %s f7_0:1; setCCR(c);" % sym
            else:
                code = "OMR = OMR %s zext(f7_0:1);" % sym
            root(':%s "#"^f7_0,"%s"' % (nm, reg), "f15_11=3 & f10_9=%d & b8=%d & f7_0" % (ee, o), code)
    # bit-field operations: 0001 0100 <form> + BBB opcode iiiiiiii
    BF = {0x12: ("bfchg", "chg"), 0x04: ("bfclr", "clr"), 0x18: ("bfset", "set"),
          0x10: ("bftsth", "tsth"), 0x00: ("bftstl", "tstl")}
    for opc, (nm, kind) in BF.items():
        modify = kind in ("chg", "clr", "set")
        b7 = 1 if modify else 0
        if kind == "chg":
            op = "C = (v & mk) == mk; v = v ^ mk;"
        elif kind == "set":
            op = "C = (v & mk) == mk; v = v | mk;"
        elif kind == "clr":
            op = "C = (v & mk) == 0; v = v & ~mk;"
        elif kind == "tsth":
            op = "C = (v & mk) == mk;"
        else:
            op = "C = (v & mk) == 0;"
        wb = " w = v;" if modify else ""
        second = "g12_8=%d & bfmask" % opc
        root(':%s "#"^bfmask,"X:<"^f4_0' % nm, "f15_8=0x14 & b7=%d & b6=1 & b5=0 & f4_0; %s" % (b7, second),
             "local mk:2 = bfmask; local a:2 = f4_0; local v:2 = *[x]:2 a; %s *[x]:2 a = v;" % op if modify else
             "local mk:2 = bfmask; local a:2 = f4_0; local v:2 = *[x]:2 a; %s" % op)
        root(':%s "#"^bfmask,"X:<<"^pp5' % nm, "f15_8=0x14 & b7=%d & b6=1 & b5=1 & pp5; %s" % (b7, second),
             "local mk:2 = bfmask; local a:2 = pp5; local v:2 = *[x]:2 a; %s *[x]:2 a = v;" % op if modify else
             "local mk:2 = bfmask; local a:2 = pp5; local v:2 = *[x]:2 a; %s" % op)
        root(':%s "#"^bfmask,"X:("^f1_0r^")"' % nm, "f15_8=0x14 & b7=%d & f6_5=1 & f1_0r; %s" % (b7, second),
             "local mk:2 = bfmask; local a:2 = f1_0r; local v:2 = *[x]:2 a; %s *[x]:2 a = v;" % op if modify else
             "local mk:2 = bfmask; local a:2 = f1_0r; local v:2 = *[x]:2 a; %s" % op)
        if modify:
            root(':%s "#"^bfmask,dlR' % nm, "f15_8=0x14 & b7=1 & f6_5=0 & dlR & dlW; %s" % second,
                 "local mk:2 = bfmask; local v:2 = dlR; %s MVX = zext(v); build dlW;" % op)
        else:
            root(':%s "#"^bfmask,dlR' % nm, "f15_8=0x14 & b7=0 & f6_5=0 & dlR; %s" % second,
                 "local mk:2 = bfmask; local v:2 = dlR; %s" % op)

    # helper operand subtables
    emit('f1_0r: "R0" is f1_0=0 { export R0; }')
    emit('f1_0r: "R1" is f1_0=1 { export R1; }')
    emit('f1_0r: "R2" is f1_0=2 { export R2; }')
    emit('f1_0r: "R3" is f1_0=3 { export R3; }')
    for nm, fl in (("f7_6r", "f7_6"), ("f5_4r", "f5_4"), ("f9_8r", "f9_8")):
        for i in range(4):
            emit('%s: "R%d" is %s=%d { export R%d; }' % (nm, i, fl, i, i))
    for i in range(4):
        emit('f7_6n: "N%d" is f7_6=%d { export N%d; }' % (i, i, i))
        emit('f7_6m: "M%d" is f7_6=%d { export M%d; }' % (i, i, i))
    emit("pp5: tgt is f4_0 [ tgt = 0xffe0 + f4_0; ] { export *[const]:2 tgt; }")
    emit("jabs: e16 is e16 { export *[p]:2 e16; }")
    emit("jrel: tgt is es16 [ tgt = (inst_start + 2 + es16) & 0xffff; ] { export *[p]:2 tgt; }")
    emit("j8: f7_0 is f7_0 { export *[p]:2 f7_0; }")
    emit("j8r: tgt is f7_0s8 [ tgt = (inst_start + 1 + f7_0s8) & 0xffff; ] { export *[p]:2 tgt; }")
    emit("j6r: tgt is f5_0s [ tgt = (inst_start + 1 + f5_0s) & 0xffff; ] { export *[p]:2 tgt; }")
    emit("dolast: tgt is es16 [ tgt = (inst_start + 2 + es16) & 0xffff; ] { export *[p]:2 tgt; }")
    emit("laAt: tgt is es16 [ tgt = (inst_start + 1 + es16) & 0xffff; ] { export *[p]:2 tgt; }")
    emit("laPrev: tgt is es16 [ tgt = (inst_start + es16) & 0xffff; ] { export *[p]:2 tgt; }")
    emit("bfmask: tgt is g15_13=4 & g7_0 [ tgt = g7_0 << 8; ] { export *[const]:2 tgt; }")
    emit("bfmask: tgt is g15_13=2 & g7_0 [ tgt = g7_0 << 4; ] { export *[const]:2 tgt; }")
    emit("bfmask: tgt is g15_13=1 & g7_0 [ tgt = g7_0 + 0; ] { export *[const]:2 tgt; }")
    emit()

    # tail
    emit("skip1: tgt is epsilon [ tgt = inst_start + 2; ] { export *[p]:2 tgt; }")
    emit("tail: is lend=0 { }")
    emit("lstartAddr: lstart is lstart { export *[p]:2 lstart; }")
    loop = (" local here:2 = inst_next >> 1; if (here != laddr + 1) goto <done>;"
            " if ((MR & 0x80) == 0) goto <done>;"
            " if ((MR & 0x40) != 0) goto lstartAddr;"
            " LC = LC - 1; if (LC == 0) goto <exit>; goto lstartAddr;"
            " <exit> local e:4 = *[ss]:4 SP; SP = SP - 1; local sr:2 = e:2; setSR(sr);"
            " e = *[ss]:4 SP; SP = SP - 1; LA = e(2); LC = e:2;"
            " <done> ")
    emit("tail: is lend=1 & laddr & lstartAddr {%s}" % loop)
    emit()

    # parallel roots
    for cls, clsbits in (("x", "b15=1"), ("f1", "f15_12=5"), ("r", "f15_12=4"), ("u", "f15_11=6")):
        emit(":^aluMn aluOp pmR_%s is tail & %s & aluMn & aluOp & pmR_%s & pmW_%s "
             "{ build pmR_%s; build aluOp; build pmW_%s; build tail; }" % (cls, clsbits, cls, cls, cls, cls))
        emit(":move pmR_%s is tail & %s & b7=0 & f6_4=1 & f2_0=1 & aFn & pmR_%s & pmW_%s "
             "{ build pmR_%s; build pmW_%s; build tail; }" % (cls, clsbits, cls, cls, cls, cls))
    # X:(R2+xx) parallel move: 0000 0101 xxxxxxxx / ---- HHH W ALU. The second-word forms of
    # MOVE(C) (0011 1...0...) and MOVE(M) (0000 001. ..0.....) take precedence.
    R2EXCL = ["g15_12!=0 & g15_12!=3", "g15_12=3 & c11=0", "g15_12=3 & c11=1 & c4=1",
              "g15_12=0 & g11_9!=1", "g15_12=0 & g11_9=1 & c5=1"]
    for ex in R2EXCL:
        for W in (0, 1):
            if W:
                d = '"X:(R2"^r2d^"),"^g2hD'
                rcode = "local d:2 = f7_0s; EAX = R2 + d; MVX = zext(*[x]:2 EAX);"
                wcode = "build g2hW;"
                ops = "g2hD & g2hW"
            else:
                d = 'g2hR^",X:(R2"^r2d^")"'
                rcode = "local d:2 = f7_0s; EAX = R2 + d; MVX = zext(g2hR);"
                wcode = "*[x]:2 EAX = MVX:2;"
                ops = "g2hR"
            emit(":^aluMn2 aluOp2 %s is tail & f15_8=5 & f7_0s & r2d; %s & c8=%d & %s & aluMn2 & aluOp2 "
                 "{ %s build aluOp2; %s build tail; }" % (d, ex, W, ops, rcode, wcode))
            if "c5=1" in ex:
                continue
            emit(":move %s is tail & f15_8=5 & f7_0s & r2d; %s & c8=%d & %s & c7=0 & g6_4=1 & g2_0=1 "
                 "{ %s %s build tail; }" % (d, ex, W, ops, rcode, wcode))
    emit(":^daMn daOp dmR is tail & f15_13=3 & daMn & daOp & dmR & dmW { build dmR; build daOp; build dmW; build tail; }")
    emit(':move dmR is tail & f15_13=3 & b7=0 & b4=1 & f2_0=7 & dmR & dmW { build dmR; build dmW; build tail; }')
    for d, pat, code, tl in ROOTS:
        head, act = (pat.split("[", 1) + [""])[:2]
        act = ("[" + act) if act else ""
        if tl:
            emit("%s is tail & %s %s { %s build tail; }" % (d, head, act, code))
        else:
            emit("%s is %s %s { %s }" % (d, head, act, code))


def main():
    build()
    text = "\n".join(out)
    # token definitions for every field the tables use
    ff = sorted(set(re.findall(r"\bf(\d+)_(\d+)\b", text)), key=lambda x: (-int(x[0]), -int(x[1])))
    gg = sorted(set(re.findall(r"\bg(\d+)_(\d+)\b", text)), key=lambda x: (-int(x[0]), -int(x[1])))
    head = ["# generated by tools/gen_dsp56156.py; do not edit", "",
            "define token ins(16)", "\tw16=(0,15)"]
    head += ["\tb%d=(%d,%d)" % (i, i, i) for i in range(16)]
    head += ["\tf%s_%s=(%s,%s)" % (h, l, l, h) for h, l in ff]
    head += ["\tf7_0s8=(0,7) signed", "\tf5_0s=(0,5) signed",
             "\taF=(3,3) aFn=(3,3) aFn1=(3,3) aJ=(0,1) aXY=(0,0) aQ1=(0,2) aQ2=(0,2)",
             "\tdF=(3,3) dFn=(3,3)",
             "\teF=(3,3) eFn=(3,3) eFn2=(3,3) eXY=(0,0) eJ=(0,1) eQ1=(0,2) eQ2=(0,2)", ";", "",
             "define token w2(16)", "\te16=(0,15)", "\tes16=(0,15) signed"]
    head += ["\tc%d=(%d,%d)" % (i, i, i) for i in range(16)]
    head += ["\tg%s_%s=(%s,%s)" % (h, l, l, h) for h, l in gg if (h, l) != ("7", "0")]
    head += ["\tg7_0=(0,7)",
             "\tcF=(3,3) cFn=(3,3) cJ=(0,1) cXY=(0,0) cQ1=(0,2) cQ2=(0,2)", ";", "",
             "attach variables [ aF dF eF cF ] [ A B ];",
             "attach variables [ aFn dFn eFn eFn2 cFn ] [ B A ];",
             "attach variables [ aFn1 ] [ B1 A1 ];",
             "attach variables [ aJ eJ cJ ] [ X0 Y0 X1 Y1 ];",
             "attach variables [ aXY eXY cXY ] [ X Y ];",
             "attach variables [ aQ1 eQ1 cQ1 ] [ X0 X1 A1 B1 Y0 Y1 Y0 Y1 ];",
             "attach variables [ aQ2 eQ2 cQ2 ] [ X0 X0 Y0 X0 X0 X0 X1 X1 ];", ""]
    text = text.replace("# generated by tools/gen_dsp56156.py; do not edit\n", "", 1)
    sys.stdout.write("\n".join(head) + "\n" + text + "\n")


if __name__ == "__main__":
    main()
