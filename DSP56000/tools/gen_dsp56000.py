#!/usr/bin/env python3
"""Generate data/languages/dsp56000_gen.sinc: the DSP56000/56001/56002 instruction tables.

    python3 tools/gen_dsp56000.py > data/languages/dsp56000_gen.sinc

Encodings follow the Motorola DSP56000 Family Manual (DSP56KFAMUM/AD): the parallel-move
encodings and the data ALU opcode table (A.10.2, A.10.4, Tables A-27..A-31) and the
non-parallel instruction formats (A.10.3 and the per-instruction Opcode sections).

Every instruction word is decoded by one root constructor. Instructions with a parallel move
evaluate in three phases: pmR (move sources and effective addresses, before the ALU
operation), the data ALU operation, then pmW (move destinations), so a move reads the old
value of a register the ALU operation writes (manual 6.x / A.6). Every root constructor ends
with 'tail', which adds the REP repeat and the DO loop-end p-code selected by the
disassembly context (see the slaspec).
"""
import sys

out = []


def emit(s=""):
    out.append(s)


# ------------------------------------------------------------------ register encodings
R5 = {4: "X0", 5: "X1", 6: "Y0", 7: "Y1",
      8: "A0", 9: "B0", 10: "A2", 11: "B2", 12: "A1", 13: "B1", 14: "A", 15: "B"}
for i in range(8):
    R5[16 + i] = "R%d" % i
    R5[24 + i] = "N%d" % i
R6 = dict(R5)
for i in range(8):
    R6[32 + i] = "M%d" % i
for g, n in enumerate(["SR", "OMR", "SP", "SSH", "SSL", "LA", "LC"], 1):
    R6[56 + g] = n
# MOVEC control-register field (5 bits): 00fff = Mn, 11ggg = program controller registers
RC5 = {i: "M%d" % i for i in range(8)}
for g, n in enumerate(["SR", "OMR", "SP", "SSH", "SSL", "LA", "LC"], 1):
    RC5[24 + g] = n

def disp(n):
    """display text for a register: quoted, since the register is not a pattern operand"""
    return '"%s"' % n


def rd(n, t):
    """p-code reading register n onto a 24-bit bus into local t (declared by the caller)."""
    if n in ("X0", "X1", "Y0", "Y1", "A0", "A1", "B0", "B1", "OMR"):
        return "%s = %s;" % (t, n)
    if n in ("A2", "B2"):
        return "%s = sext(%s);" % (t, n)
    if n in ("A", "B"):
        return "busAcc(%s, %s);" % (n, t)
    if n == "SR":
        return "local srv:2; getSR(srv); %s = zext(srv);" % t
    if n == "SSH":
        return "local sse:4 = *[ss]:4 SP; local ssh:2 = sse(2); %s = zext(ssh); SP = SP - 1;" % t
    if n == "SSL":
        return "local sse:4 = *[ss]:4 SP; %s = zext(sse:2);" % t
    return "%s = zext(%s);" % (t, n)          # R, N, M, SP, LA, LC


def wr(n, v):
    """p-code writing the 24-bit bus value held in the low bits of v (MVX or MVY) to n."""
    if n in ("X0", "X1", "Y0", "Y1", "A0", "A1", "B0", "B1", "OMR"):
        return "%s = %s:3;" % (n, v)
    if n in ("A2", "B2"):
        return "%s = %s:1;" % (n, v)
    if n in ("A", "B"):
        return "local wv:3 = %s:3; accWrite24(%s, wv);" % (v, n)
    if n == "SR":
        return "local wv:2 = %s:2; setSR(wv);" % v
    if n == "SP":
        return "SP = %s:1 & 0x3f;" % v
    if n == "SSH":
        return ("SP = SP + 1; local sse:4 = *[ss]:4 SP; "
                "*[ss]:4 SP = (sse & 0xffff) | (zext(%s:2) << 16);" % v)
    if n == "SSL":
        return ("local sse:4 = *[ss]:4 SP; "
                "*[ss]:4 SP = (sse & 0xffff0000) | zext(%s:2);" % v)
    return "%s = %s:2;" % (n, v)              # R, N, M, LA, LC


def regtables(name, table, cons):
    """Emit <name>R (read: exports a 24-bit local), <name>W (write MVX), <name>V (write MVY)
    for a register field. cons(code) gives the pattern constraint for an encoding."""
    for code, n in sorted(table.items()):
        emit('%sR: %s is %s { local t:3 = 0; %s export t; }' % (name, disp(n), cons(code), rd(n, "t")))
    for code, n in sorted(table.items()):
        emit('%sW: %s is %s { %s }' % (name, disp(n), cons(code), wr(n, "MVX")))
    for code, n in sorted(table.items()):
        emit('%sD: %s is %s { }' % (name, disp(n), cons(code)))
    emit()


# ------------------------------------------------------------------ effective addresses
EA_MODES = [  # MMM, display, p-code (r = Rn, n = Nn, m = Mn, T = target EA temp)
    (0, '"("^%(r)s^")-"^%(n)s', "T = %(r)s; local o:2 = -%(n)s; aguAdd(%(r)s, o, 1:1, %(m)s, %(r)s);"),
    (1, '"("^%(r)s^")+"^%(n)s', "T = %(r)s; aguAdd(%(r)s, %(n)s, 0:1, %(m)s, %(r)s);"),
    (2, '"("^%(r)s^")-"', "T = %(r)s; local o:2 = 0xffff; aguAdd(%(r)s, o, 1:1, %(m)s, %(r)s);"),
    (3, '"("^%(r)s^")+"', "T = %(r)s; local o:2 = 1; aguAdd(%(r)s, o, 0:1, %(m)s, %(r)s);"),
    (4, '"("^%(r)s^")"', "T = %(r)s;"),
    (5, '"("^%(r)s^"+"^%(n)s^")"', "aguAdd(%(r)s, %(n)s, 0:1, %(m)s, T);"),
    (7, '"-("^%(r)s^")"', "local o:2 = 0xffff; aguAdd(%(r)s, o, 1:1, %(m)s, %(r)s); T = %(r)s;"),
]


def ea_tables():
    # 6-bit MMMRRR effective address in bits 13..8, register forms only (eaRegX / eaRegY);
    # absolute (110000) and immediate (110100) forms are separate.
    for T in ("EAX", "EAY"):
        nm = "eaReg" + T[-1]
        for mmm, d, p in EA_MODES:
            env = {"r": "rn8", "n": "nn8", "m": "mn8"}
            emit('%s: %s is f13_11=%d & rn8 & nn8 & mn8 { %s }'
                 % (nm, d % env, mmm, (p % env).replace("T", T)))
        emit()
    # XY moves: X uses MM (12,11) and R0-R7 (10..8); Y uses mm (21,20), rr (14,13) in the
    # opposite bank
    XY = [(0, '"("^%(r)s^")"', "T = %(r)s;"),
          (1, '"("^%(r)s^")+"^%(n)s', "T = %(r)s; aguAdd(%(r)s, %(n)s, 0:1, %(m)s, %(r)s);"),
          (2, '"("^%(r)s^")-"', "T = %(r)s; local o:2 = 0xffff; aguAdd(%(r)s, o, 1:1, %(m)s, %(r)s);"),
          (3, '"("^%(r)s^")+"', "T = %(r)s; local o:2 = 1; aguAdd(%(r)s, o, 0:1, %(m)s, %(r)s);")]
    for mm, d, p in XY:
        env = {"r": "rn8", "n": "nn8", "m": "mn8"}
        emit('xyX: "x:"^%s is f12_11=%d & rn8 & nn8 & mn8 { %s }' % (d % env, mm, (p % env).replace("T", "EAX")))
    for bank in (0, 1):
        for rr in range(4):
            reg = (4 if bank == 0 else 0) + rr
            env = {"r": "R%d" % reg, "n": "N%d" % reg, "m": "M%d" % reg}
            denv = {k: '"%s"' % v for k, v in env.items()}
            for mm, d, p in XY:
                emit('xyY: "y:"^%s is b10=%d & f14_13=%d & f21_20=%d { %s }'
                     % (d % denv, bank, rr, mm, (p % env).replace("T", "EAY")))
    emit()


# ------------------------------------------------------------------ data ALU (parallel)
ALU = []  # (constraint, mnemonic, operand display, p-code)


def alu(cons, mn, ops, code):
    ALU.append((cons, mn, ops, code))


S56_ACC = "local s:7 = aDn;"
S56_XY = "local s:7 = sext(aJxy);"
S56_24 = "local s:7 = sext(aJ24) << 24;"


def arith_ops():
    # JJJ = 000 / 001: source is the other accumulator
    J0 = "b7=0 & f6_4=0 & f2_0=%d"
    J1 = "b7=0 & f6_4=1 & f2_0=%d"
    alu(J0 % 1, "tfr", "aDn,aD", "aD = aDn;")
    alu(J0 % 2, "addr", "aDn,aD", S56_ACC + " local t:7 = aD s>> 1; local r:7; addFlags(t, s, 0:1, r); ccEUNZ(r); aD = r;")
    alu(J0 % 3, "tst", "aD", "ccEUNZ(aD); V = 0;")
    alu(J0 % 5, "cmp", "aDn,aD", S56_ACC + " local r:7; subFlags(aD, s, 0:1, r); ccEUNZ(r);")
    alu(J0 % 6, "subr", "aDn,aD", S56_ACC + " local t:7 = aD s>> 1; local r:7; subFlags(t, s, 0:1, r); ccEUNZ(r); aD = r;")
    alu(J0 % 7, "cmpm", "aDn,aD", S56_ACC + " local da:7; abs56(aD, da); local sa:7; abs56(s, sa); local r:7; subFlags(da, sa, 0:1, r); ccEUNZ(r);")
    alu(J1 % 0, "add", "aDn,aD", S56_ACC + " local r:7; addFlags(aD, s, 0:1, r); ccEUNZ(r); aD = r;")
    alu(J1 % 1, "rnd", "aD", "local r:7; roundAcc(aD, r); V = !(aD s< 0) && (r s< 0); L = L || V; ccEUNZ(r); aD = r;")
    alu(J1 % 2, "addl", "aDn,aD", S56_ACC + " local t:7 = aD << 1; local v1:1 = (aD s< 0) != (t s< 0); local r:7; addFlags(t, s, 0:1, r); V = V || v1; L = L || V; ccEUNZ(r); aD = r;")
    alu(J1 % 3, "clr", "aD", "aD = 0; E = 0; U = 1; N = 0; Z = 1; V = 0;")
    alu(J1 % 4, "sub", "aDn,aD", S56_ACC + " local r:7; subFlags(aD, s, 0:1, r); ccEUNZ(r); aD = r;")
    alu(J1 % 6, "subl", "aDn,aD", S56_ACC + " local t:7 = aD << 1; local v1:1 = (aD s< 0) != (t s< 0); local r:7; subFlags(t, s, 0:1, r); V = V || v1; L = L || V; ccEUNZ(r); aD = r;")
    alu(J1 % 7, "not", "aD", "local m:3 = aD(3); m = ~m; setMid(aD, m); ccLogic(m);")
    # JJJ = 010 / 011 with k1 = 1: shifts, ABS, NEG on D
    J2 = "b7=0 & f6_4=2 & f2_0=%d"
    J3 = "b7=0 & f6_4=3 & f2_0=%d"
    alu(J2 % 2, "asr", "aD", "C = (aD & 1) != 0; local r:7 = aD s>> 1; V = 0; ccEUNZ(r); aD = r;")
    alu(J2 % 3, "lsr", "aD", "local m:3 = aD(3); C = (m & 1) != 0; m = m >> 1; setMid(aD, m); ccLogic(m);")
    alu(J2 % 6, "abs", "aD", "local r:7; abs56(aD, r); V = r s< 0; L = L || V; ccEUNZ(r); aD = r;")
    alu(J2 % 7, "ror", "aD", "local m:3 = aD(3); local c0:1 = (m & 1) != 0; m = (m >> 1) | (zext(C) << 23); C = c0; setMid(aD, m); ccLogic(m);")
    alu(J3 % 2, "asl", "aD", "local r:7 = aD << 1; C = aD s< 0; V = (aD s< 0) != (r s< 0); L = L || V; ccEUNZ(r); aD = r;")
    alu(J3 % 3, "lsl", "aD", "local m:3 = aD(3); C = (m & 0x800000) != 0; m = m << 1; setMid(aD, m); ccLogic(m);")
    alu(J3 % 6, "neg", "aD", "local z:7 = 0; local r:7 = z - aD; V = sborrow(z, aD); L = L || V; ccEUNZ(r); aD = r;")
    alu(J3 % 7, "rol", "aD", "local m:3 = aD(3); local c0:1 = (m & 0x800000) != 0; m = (m << 1) | zext(C); C = c0; setMid(aD, m); ccLogic(m);")
    # JJJ = 01x with k1 = 0: X or Y (48-bit) source
    JXY = "b7=0 & f6_5=1 & f2_0=%d"
    alu(JXY % 0, "add", "aJxy,aD", S56_XY + " local r:7; addFlags(aD, s, 0:1, r); ccEUNZ(r); aD = r;")
    alu(JXY % 1, "adc", "aJxy,aD", S56_XY + " local r:7; addFlags(aD, s, C, r); ccEUNZ(r); aD = r;")
    alu(JXY % 4, "sub", "aJxy,aD", S56_XY + " local r:7; subFlags(aD, s, 0:1, r); ccEUNZ(r); aD = r;")
    alu(JXY % 5, "sbc", "aJxy,aD", S56_XY + " local r:7; subFlags(aD, s, C, r); ccEUNZ(r); aD = r;")
    # JJJ = 1xx: X0, Y0, X1, Y1 source
    J4 = "b7=0 & b6=1 & f2_0=%d"
    alu(J4 % 0, "add", "aJ24,aD", S56_24 + " local r:7; addFlags(aD, s, 0:1, r); ccEUNZ(r); aD = r;")
    alu(J4 % 1, "tfr", "aJ24,aD", S56_24 + " aD = s;")
    alu(J4 % 2, "or", "aJ24,aD", "local m:3 = aD(3) | aJ24; setMid(aD, m); ccLogic(m);")
    alu(J4 % 3, "eor", "aJ24,aD", "local m:3 = aD(3) ^ aJ24; setMid(aD, m); ccLogic(m);")
    alu(J4 % 4, "sub", "aJ24,aD", S56_24 + " local r:7; subFlags(aD, s, 0:1, r); ccEUNZ(r); aD = r;")
    alu(J4 % 5, "cmp", "aJ24,aD", S56_24 + " local r:7; subFlags(aD, s, 0:1, r); ccEUNZ(r);")
    alu(J4 % 6, "and", "aJ24,aD", "local m:3 = aD(3) & aJ24; setMid(aD, m); ccLogic(m);")
    alu(J4 % 7, "cmpm", "aJ24,aD", S56_24 + " local da:7; abs56(aD, da); local sa:7; abs56(s, sa); local r:7; subFlags(da, sa, 0:1, r); ccEUNZ(r);")
    # multiply: 1QQQ dkkk (k2 = negate, k1 = accumulate, k0 = round)
    for k1 in (0, 1):
        for k0 in (0, 1):
            mn = ["mpy", "mpyr", "mac", "macr"][k1 * 2 + k0]
            code = "local prd:7; fmul(aQ1, aQ2, prd); local sg:7 = b2; prd = prd - ((prd << 1) * sg);"
            if k1:
                code += " local r:7; local cs:1 = C; addFlags(aD, prd, 0:1, r); C = cs;"
            else:
                code += " local r:7 = prd; V = 0;"
            if k0:
                code += (" local q:7; roundAcc(r, q); V = V || (!(r s< 0) && (q s< 0)); L = L || V;"
                         " r = q;")
            code += " ccEUNZ(r); aD = r;"
            alu("b7=1 & b1=%d & b0=%d" % (k1, k0), mn, "msign^aQ1^\",\"^aQ2^\",\"^aD", code)


def alu_tables():
    arith_ops()
    emit('msign: "-" is b2=1 { }')
    emit('msign: "" is b2=0 { }')
    emit()
    for cons, mn, ops, code in ALU:
        emit('aluMn: "%s" is %s { }' % (mn, cons))
    emit()
    for cons, mn, ops, code in ALU:
        emit('aluOp: %s is %s & aDn & aD & aJ24 & aJxy & aQ1 & aQ2 & msign & b2 { %s }'
             % (ops, cons, code))
    emit()


# ------------------------------------------------------------------ parallel moves
def mem(space, T):
    return "*[%s]:4 %s" % (space, T)


def pm_tables():
    # register tables in the positions the move formats use
    def r5split(code):
        return "f21_20=%d & f18_16=%d" % (code >> 3, code & 7)
    regtables("mr", R5, r5split)                                # X:/Y: moves
    regtables("ir", R5, lambda c: "f20_16=%d" % c)                # immediate short dest
    regtables("rs", R5, lambda c: "f17_13=%d" % c)                # R move source
    regtables("rd", R5, lambda c: "f12_8=%d" % c)                 # R move destination
    # immediate short: left-justified into X0..Y1, A, B; right-justified into A0..B2, Rn, Nn
    for code, n in sorted(R5.items()):
        if n in ("X0", "X1", "Y0", "Y1", "A", "B"):
            v = "zext(imm8:1) << 16"
        else:
            v = "zext(imm8:1)"
        emit('immS: "#<"^imm8 is f20_16=%d & imm8 { MVX = %s; }' % (code, v))
    emit()

    # --- read phase (displayed) / write phase
    P = []   # (pattern, display, read code, write code)

    def pm(pat, d, r, w):
        P.append((pat, d, r, w))

    # no move / address register update
    pm("hb=0x20 & f15_8=0", '""', "", "")
    for mm, d in enumerate(['"("^rn8^")-"^nn8', '"("^rn8^")+"^nn8', '"("^rn8^")-"', '"("^rn8^")+"']):
        code = ["local o:2 = -nn8; aguAdd(rn8, o, 1:1, mn8, rn8);",
                "aguAdd(rn8, nn8, 0:1, mn8, rn8);",
                "local o:2 = 0xffff; aguAdd(rn8, o, 1:1, mn8, rn8);",
                "local o:2 = 1; aguAdd(rn8, o, 0:1, mn8, rn8);"][mm]
        pm("hb=0x20 & f15_13=2 & f12_11=%d & rn8 & nn8 & mn8" % mm, d, code, "")
    # register to register
    pm("f23_18=8 & rsR & rdW", 'rsR^","^rdW', "MVX = zext(rsR);", "build rdW;")
    # immediate short
    pm("f23_21=1 & immS & irW", 'immS^","^irW', "build immS;", "build irW;")
    # X: and Y: memory moves (W = 1: memory -> register)
    for sp, sb in (("x", 0), ("y", 1)):
        base = "f23_22=1 & b19=%d" % sb
        # effective address
        pm(base + " & b15=1 & b14=1 & eaRegX & mrW", '"%s:"^eaRegX^","^mrW' % sp,
           "build eaRegX; local mx:4 = %s; MVX = mx:3;" % mem(sp, "EAX"), "build mrW;")
        pm(base + " & b15=0 & b14=1 & eaRegX & mrR", 'mrR^",%s:"^eaRegX' % sp,
           "build eaRegX; MVX = zext(mrR);", "%s = zext(MVX);" % mem(sp, "EAX"))
        # absolute address (extension word)
        pm(base + " & b15=1 & b14=1 & f13_8=0x30 & mrW; e16", '"%s:>"^e16^","^mrW' % sp,
           "EAX = e16; local mx:4 = %s; MVX = mx:3;" % mem(sp, "EAX"), "build mrW;")
        pm(base + " & b15=0 & b14=1 & f13_8=0x30 & mrR; e16", 'mrR^",%s:>"^e16' % sp,
           "EAX = e16; MVX = zext(mrR);", "%s = zext(MVX);" % mem(sp, "EAX"))
        # immediate (extension word), read only
        if sb == 0:
            pm(base + " & b15=1 & b14=1 & f13_8=0x34 & mrW; e24", '"#"^e24^","^mrW',
               "MVX = e24;", "build mrW;")
        # absolute short
        pm(base + " & b15=1 & b14=0 & f13_8 & mrW", '"%s:<"^f13_8^","^mrW' % sp,
           "EAX = f13_8; local mx:4 = %s; MVX = mx:3;" % mem(sp, "EAX"), "build mrW;")
        pm(base + " & b15=0 & b14=0 & f13_8 & mrR", 'mrR^",%s:<"^f13_8' % sp,
           "EAX = f13_8; MVX = zext(mrR);", "%s = zext(MVX);" % mem(sp, "EAX"))
    # L: long memory moves; LLL = A10 B10 X Y A B AB BA
    LREAD = {0: "MVX = zext(A1); MVY = zext(A0);", 1: "MVX = zext(B1); MVY = zext(B0);",
             2: "MVX = zext(X1); MVY = zext(X0);", 3: "MVX = zext(Y1); MVY = zext(Y0);",
             4: "local l:6; busAcc48(A, l); local lh:3 = l(3); MVX = zext(lh); MVY = zext(l:3);",
             5: "local l:6; busAcc48(B, l); local lh:3 = l(3); MVX = zext(lh); MVY = zext(l:3);",
             6: "local h:3; busAcc(A, h); local g:3; busAcc(B, g); MVX = zext(h); MVY = zext(g);",
             7: "local h:3; busAcc(B, h); local g:3; busAcc(A, g); MVX = zext(h); MVY = zext(g);"}
    LWRITE = {0: "A1 = MVX:3; A0 = MVY:3;", 1: "B1 = MVX:3; B0 = MVY:3;",
              2: "X1 = MVX:3; X0 = MVY:3;", 3: "Y1 = MVX:3; Y0 = MVY:3;",
              4: "local l:6 = (zext(MVX:3) << 24) | zext(MVY:3); A = sext(l);",
              5: "local l:6 = (zext(MVX:3) << 24) | zext(MVY:3); B = sext(l);",
              6: "local h:3 = MVX:3; accWrite24(A, h); local g:3 = MVY:3; accWrite24(B, g);",
              7: "local h:3 = MVX:3; accWrite24(B, h); local g:3 = MVY:3; accWrite24(A, g);"}
    LNAME = ['"A10"', '"B10"', '"X"', '"Y"', '"A"', '"B"', '"AB"', '"BA"']
    for lll in range(8):
        pat = "f23_20=4 & b18=0 & b19=%d & f17_16=%d" % (lll >> 2, lll & 3)
        n = LNAME[lll]
        memr = "local mx:4 = *[x]:4 EAX; MVX = mx:3; local my:4 = *[y]:4 EAX; MVY = my:3;"
        memw = "*[x]:4 EAX = zext(MVX); *[y]:4 EAX = zext(MVY);"
        pm(pat + " & b15=1 & b14=1 & eaRegX", '"l:"^eaRegX^","^%s' % n,
           "build eaRegX; " + memr, LWRITE[lll])
        pm(pat + " & b15=0 & b14=1 & eaRegX", '%s^",l:"^eaRegX' % n,
           "build eaRegX; " + LREAD[lll], memw)
        pm(pat + " & b15=1 & b14=1 & f13_8=0x30; e16", '"l:>"^e16^","^%s' % n,
           "EAX = e16; " + memr, LWRITE[lll])
        pm(pat + " & b15=0 & b14=1 & f13_8=0x30; e16", '%s^",l:>"^e16' % n,
           "EAX = e16; " + LREAD[lll], memw)
        pm(pat + " & b15=1 & b14=0 & f13_8", '"l:<"^f13_8^","^%s' % n,
           "EAX = f13_8; " + memr, LWRITE[lll])
        pm(pat + " & b15=0 & b14=0 & f13_8", '%s^",l:<"^f13_8' % n,
           "EAX = f13_8; " + LREAD[lll], memw)
    # X:R class I: X:ea <-> X0/X1/A/B, and S2 (A/B) -> D2 (Y0/Y1)
    xrc = "local s2:3; busAcc(c1d, s2); MVY = zext(s2);"
    xrw = "c1f = MVY:3;"
    for (tail, eadisp, eacode) in (("eaRegX", "eaRegX", "build eaRegX;"),
                                   ("f13_8=0x30; e16", '">"^e16', "EAX = e16;")):
        pm("f23_20=1 & b14=0 & b15=1 & c1ffW & c1d & c1f & " + tail,
           '"x:"^%s^","^c1ffW^" "^c1d^","^c1f' % eadisp,
           eacode + " local mx:4 = *[x]:4 EAX; MVX = mx:3; " + xrc, "build c1ffW; " + xrw)
        pm("f23_20=1 & b14=0 & b15=0 & c1ffR & c1d & c1f & " + tail,
           'c1ffR^",x:"^%s^" "^c1d^","^c1f' % eadisp,
           eacode + " MVX = zext(c1ffR); " + xrc, "*[x]:4 EAX = zext(MVX); " + xrw)
    pm("f23_20=1 & b14=0 & b15=1 & c1ffW & c1d & c1f & f13_8=0x34; e24",
       '"#"^e24^","^c1ffW^" "^c1d^","^c1f', "MVX = e24; " + xrc, "build c1ffW; " + xrw)
    # R:Y class I: S1 (A/B) -> D1 (X0/X1), and Y:ea <-> Y0/Y1/A/B
    ryc = "local s1:3; busAcc(c1yd, s1); MVX = zext(s1);"
    ryw = "c1ye = MVX:3;"
    for (tail, eadisp, eacode) in (("eaRegX", "eaRegX", "build eaRegX;"),
                                   ("f13_8=0x30; e16", '">"^e16', "EAX = e16;")):
        pm("f23_20=1 & b14=1 & b15=1 & c1yffW & c1yd & c1ye & " + tail,
           'c1yd^","^c1ye^" y:"^%s^","^c1yffW' % eadisp,
           eacode + " local my:4 = *[y]:4 EAX; MVY = my:3; " + ryc, "build c1yffW; " + ryw)
        pm("f23_20=1 & b14=1 & b15=0 & c1yffR & c1yd & c1ye & " + tail,
           'c1yd^","^c1ye^" "^c1yffR^",y:"^%s' % eadisp,
           eacode + " MVY = zext(c1yffR); " + ryc, "*[y]:4 EAX = zext(MVY); " + ryw)
    pm("f23_20=1 & b14=1 & b15=1 & c1yffW & c1yd & c1ye & f13_8=0x34; e24",
       'c1yd^","^c1ye^" #"^e24^","^c1yffW', "MVY = e24; " + ryc, "build c1yffW; " + ryw)
    # class II: A -> X:ea, X0 -> A  /  Y0 -> A, A -> Y:ea
    for (tail, eadisp, eacode) in (("eaRegX", "eaRegX", "build eaRegX;"),
                                   ("f13_8=0x30; e16", '">"^e16', "EAX = e16;")):
        pm("f23_17=4 & b15=0 & b14=0 & c2d & c2e & " + tail,
           'c2d^",x:"^%s^" X0,"^c2e' % eadisp,
           eacode + " local s:3; busAcc(c2d, s); MVX = zext(s); MVY = zext(X0);",
           "*[x]:4 EAX = zext(MVX); local v:3 = MVY; accWrite24(c2d, v);")
        pm("f23_17=4 & b15=1 & b14=0 & c2d & c2e & " + tail,
           '"Y0,"^c2d^" "^c2e^",y:"^%s' % eadisp,
           eacode + " local s:3; busAcc(c2d, s); MVX = zext(s); MVY = zext(Y0);",
           "*[y]:4 EAX = zext(MVX); local v:3 = MVY; accWrite24(c2d, v);")
    # XY moves: W (bit 15) for X, w (bit 22) for Y
    for W in (0, 1):
        for w in (0, 1):
            dx = 'xyX^","^xyeeW' if W else 'xyeeR^","^xyX'
            dy = 'xyY^","^xyffW' if w else 'xyffR^","^xyY'
            rx = "build xyX; " + ("local mx:4 = *[x]:4 EAX; MVX = mx:3;" if W else "MVX = zext(xyeeR);")
            ry = "build xyY; " + ("local my:4 = *[y]:4 EAY; MVY = my:3;" if w else "MVY = zext(xyffR);")
            wx = "build xyeeW;" if W else "*[x]:4 EAX = zext(MVX);"
            wy = "build xyffW;" if w else "*[y]:4 EAY = zext(MVY);"
            pm("b23=1 & b15=%d & b22=%d & xyX & xyY & %s & %s"
               % (W, w, "xyeeW" if W else "xyeeR", "xyffW" if w else "xyffR"),
               dx + '^" "^' + dy, rx + " " + ry, wx + " " + wy)

    # small register tables for the class I / XY fields
    for nm, field, regs in (("xyee", "f19_18", ["X0", "X1", "A", "B"]),
                            ("c1ff", "f19_18", ["X0", "X1", "A", "B"]),
                            ("xyff", "f17_16", ["Y0", "Y1", "A", "B"]),
                            ("c1yff", "f17_16", ["Y0", "Y1", "A", "B"])):
        for i, n in enumerate(regs):
            emit('%sR: %s is %s=%d { local t:3 = 0; %s export t; }' % (nm, disp(n), field, i, rd(n, "t")))
        src = "MVY" if nm in ("xyff", "c1yff") else "MVX"
        for i, n in enumerate(regs):
            emit('%sW: %s is %s=%d { %s }' % (nm, disp(n), field, i, wr(n, src)))
        for i, n in enumerate(regs):
            emit('%sD: %s is %s=%d { }' % (nm, disp(n), field, i))
    emit()
    # the read phase displays destination registers through the display-only tables (the
    # write tables would be built, i.e. written, in the read phase)
    import re as _re
    def todisp(t):
        return _re.sub(r"\b(mr|ir|rs|rd|xyee|xyff|c1ff|c1yff)W\b", r"\1D", t)
    for pat, d, r, w in P:
        emit("pmR: %s is %s { %s }" % (todisp(d), todisp(pat), r))
    emit()
    # the write phase decodes the same bits, but must not contain the read-phase operand
    # subtables (SLEIGH builds every operand that is not built explicitly, which would repeat
    # their address updates and register reads); the extension word belongs to pmR
    SIDE = {"eaRegX", "xyX", "xyY", "immS", "mrR", "rsR", "xyeeR", "xyffR", "c1ffR", "c1yffR"}
    for pat, d, r, w in P:
        wpat = pat.split(";")[0]
        wpat = " & ".join(x.strip() for x in wpat.split("&") if x.strip() not in SIDE)
        emit("pmW: is %s { %s }" % (wpat, w))
    emit()


# ------------------------------------------------------------------ non-parallel
CC = ["cc", "ge", "ne", "pl", "nn", "ec", "lc", "gt", "cs", "lt", "eq", "mi", "nr", "es", "ls", "le"]
CCX = ["!C", "!(N ^^ V)", "!Z", "!N", "!(Z || (!U && !E))", "!E", "!L", "!(Z || (N ^^ V))",
       "C", "N ^^ V", "Z", "N", "Z || (!U && !E)", "E", "L", "Z || (N ^^ V)"]


def cond_tables():
    for fld, nm in (("f15_12", "cc12"), ("f3_0", "cc0")):
        for i, c in enumerate(CC):
            emit('%s: "%s" is %s=%d { local t:1 = %s; export t; }' % (nm, c, fld, i, CCX[i]))
    emit()


ROOTS = []


def root(disp, pat, code, flow_tail=True):
    ROOTS.append((disp, pat, code))


def nonparallel():
    # 6-bit register field at 13..8 (MOVEC/MOVEP/DO/REP/bit ops) and at 5..0 (MOVEM)
    regtables("g6", R6, lambda c: "f13_8=%d" % c)
    regtables("m6", R6, lambda c: "f5_0=%d" % c)
    regtables("c5", RC5, lambda c: "f4_0=%d" % c)
    # 6-bit memory operand at 13..8 with space bit s at bit 6 (X/Y), used by MOVEC/DO/REP/bits
    for sp, sb in (("x", 0), ("y", 1)):
        emit('memS6: "%s:"^eaRegX is b6=%d & b14=1 & eaRegX { build eaRegX; export *[%s]:4 EAX; }' % (sp, sb, sp))
        emit('memS6: "%s:>"^e16 is b6=%d & b14=1 & f13_8=0x30; e16 { export *[%s]:4 e16; }' % (sp, sb, sp))
        emit('memS6: "%s:<"^f13_8 is b6=%d & b14=0 & f13_8 { export *[%s]:4 f13_8; }' % (sp, sb, sp))
    emit()
    # same with immediate allowed (read contexts: MOVEC source, DO/REP count)
    # absolute-only P memory for MOVEM
    emit('pmem: "p:"^eaRegX is b14=1 & eaRegX { build eaRegX; export *[p]:4 EAX; }')
    emit('pmem: "p:>"^e16 is b14=1 & f13_8=0x30; e16 { export *[p]:4 e16; }')
    emit('pmem: "p:<"^f13_8 is b14=0 & f13_8 { export *[p]:4 f13_8; }')
    emit()
    # I/O short address (FFC0h + pp) in X or Y space selected by bit 16, at bits 5..0
    for sp, sb in (("x", 0), ("y", 1)):
        emit('ppS16: "%s:<<"^tgt is b16=%d & f5_0 [ tgt = 0xffc0 + f5_0; ] { export *[%s]:4 tgt; }' % (sp, sb, sp))
        emit('ppS6: "%s:<<"^tgt is b6=%d & f13_8 [ tgt = 0xffc0 + f13_8; ] { export *[%s]:4 tgt; }' % (sp, sb, sp))
    emit()
    emit('jabs: e16 is e16 { export *[p]:4 e16; }')
    emit('jeaR: eaRegX is eaRegX { build eaRegX; local a:2 = EAX; export a; }')
    emit('jeaA: e16 is f13_8=0x30; e16 { export *[p]:4 e16; }')
    # memory operand of the bit-test jumps: register modes and absolute short only (the
    # jump address takes the extension word)
    for sp, sb in (("x", 0), ("y", 1)):
        emit('memJ: "%s:"^eaRegX is b6=%d & b14=1 & eaRegX { build eaRegX; export *[%s]:4 EAX; }' % (sp, sb, sp))
        emit('memJ: "%s:<"^f13_8 is b6=%d & b14=0 & f13_8 { export *[%s]:4 f13_8; }' % (sp, sb, sp))
    emit('laAt: e16 is e16 { export *[p]:4 e16; }')
    emit('laPrev: tgt is e16 [ tgt = e16 - 1; ] { export *[p]:4 tgt; }')
    emit('j12: f11_0 is f11_0 { export *[p]:4 f11_0; }')
    emit('dolast: tgt is e16 [ tgt = e16 + 1; ] { export *[p]:4 tgt; }')
    emit()

    # --- zero-operand and simple
    root(":nop", "w24=0", "")
    root(":rti", "w24=0x000004", "local e:4 = *[ss]:4 SP; SP = SP - 1; local sr:2 = e:2; setSR(sr); local pc:2 = e(2); return [pc];")
    root(":illegal", "w24=0x000005", "illegal();")
    root(":swi", "w24=0x000006", "softwareInterrupt();")
    root(":rts", "w24=0x00000c", "local e:4 = *[ss]:4 SP; SP = SP - 1; local pc:2 = e(2); return [pc];")
    root(":reset", "w24=0x000084", "resetPeripherals();")
    root(":wait", "w24=0x000086", "waitForInterrupt();")
    root(":stop", "w24=0x000087", "stopProcessing();")
    root(":enddo", "w24=0x00008c",
         "local e:4 = *[ss]:4 SP; SP = SP - 1; local sr:2 = e:2; MR = (MR & 0x7f) | (sr(1) & 0x80); "
         "e = *[ss]:4 SP; SP = SP - 1; LA = e(2); LC = e:2;")
    # DSP56002: INC, DEC, DEBUG, DEBUGcc
    root(":inc d0", "f23_4=0 & f3_1=4 & d0",
         "local one:7 = 1; local r:7; addFlags(d0, one, 0:1, r); ccEUNZ(r); d0 = r;")
    root(":dec d0", "f23_4=0 & f3_1=5 & d0",
         "local one:7 = 1; local r:7; subFlags(d0, one, 0:1, r); ccEUNZ(r); d0 = r;")
    root(":debug", "w24=0x000200", "debugMode();")
    root(":debug^cc0", "f23_4=0x00030 & cc0", "if (!cc0) goto inst_next; debugMode();")
    # ANDI / ORI to MR, CCR, OMR
    for op, nm, sym in ((0x2e, "andi", "&"), (0x3e, "ori", "|")):
        for ee, reg in enumerate(["mr", "ccr", "omr"]):
            if reg == "mr":
                code = "MR = MR %s imm8:1;" % sym
            elif reg == "ccr":
                code = "local c:1; getCCR(c); c = c %s imm8:1; setCCR(c);" % sym
            else:
                code = "OMR = OMR %s zext(imm8:1);" % sym
            root(':%s "#"^imm8,"%s"' % (nm, reg), "hb=0 & f7_2=%d & f1_0=%d & imm8" % (op, ee), code)
    # DIV
    root(":div divJ,dD", "hb=0x01 & f15_8=0x80 & f7_6=1 & divJ & dD & f2_0=0",
         "local sx:1 = (dD s< 0) != (divJ s< 0); local t:7 = (dD << 1) | zext(C); "
         "local hi:4 = t(3); local s:4 = sext(divJ); "
         "local r:4 = hi + s * zext(sx) - s * zext(!sx); "
         "local res:7 = (zext(r) << 24) | (t & 0xffffff); "
         "V = (dD s< 0) != ((dD << 1) s< 0); L = L || V; C = !(res s< 0); dD = res;")
    # NORM Rn,D
    root(":norm rn8,dD", "hb=0x01 & f15_11=0x1b & rn8 & f7_4=1 & dD & f2_0=5",
         "local adj:1; scaleAdj(adj); ccEUNZ(dD); "
         "local up:1 = !E && U && !Z; local dn:1 = E; "
         "local r:7 = (dD << 1) * zext(up) + (dD s>> 1) * zext(dn) + dD * zext(!up && !dn); "
         "local rv1:1 = (dD s< 0) != (r s< 0); "
         "rn8 = rn8 - zext(up) + zext(dn); V = rv1; L = L || V; ccEUNZ(r); dD = r;")
    # MPY/MPYR/MAC/MACR (+-)S,#n,D  (DSP56002)
    for op, mn in ((0, "mpy"), (1, "mpyr"), (2, "mac"), (3, "macr")):
        code = "local prd:7 = sext(macQ); prd = (prd << 24) s>> nsh; local sg:7 = b2; prd = prd - ((prd << 1) * sg);"
        if op & 2:
            code += " local r:7; local cs:1 = C; addFlags(dD, prd, 0:1, r); C = cs;"
        else:
            code += " local r:7 = prd; V = 0;"
        if op & 1:
            code += " local q:7; roundAcc(r, q); V = V || (!(r s< 0) && (q s< 0)); L = L || V; r = q;"
        code += " ccEUNZ(r); dD = r;"
        root(':%s msign^macQ,"#"^nsh,dD' % mn,
             "hb=0x01 & f15_13=0 & nsh & f7_6=3 & macQ & dD & msign & b2 & f1_0=%d" % op, code)
    # Tcc
    tsrc = {0: None, 4: "X0", 5: "Y0", 6: "X1", 7: "Y1"}
    for j, s in tsrc.items():
        for d in (0, 1):
            dst = ["A", "B"][d]
            src = ["B", "A"][d] if s is None else s
            val = src if s is None else "(sext(%s) << 24)" % s
            root(':t^cc12 "%s,%s"' % (src, dst), "hb=0x02 & cc12 & f11_8=0 & b7=0 & f6_4=%d & b3=%d & f2_0=0" % (j, d),
                 "if (!cc12) goto inst_next; %s = %s;" % (dst, val))
            root(':t^cc12 "%s,%s" rn8,rn0' % (src, dst),
                 "hb=0x03 & cc12 & b11=0 & rn8 & b7=0 & f6_4=%d & b3=%d & rn0" % (j, d),
                 "if (!cc12) goto inst_next; local rs:2 = rn8; %s = %s; rn0 = rs;" % (dst, val))
    # LUA ea,D (U-type modes)
    for mm, d in enumerate(['"("^rn8^")-"^nn8', '"("^rn8^")+"^nn8', '"("^rn8^")-"', '"("^rn8^")+"']):
        code = ["local o:2 = -nn8; aguAdd(rn8, o, 1:1, mn8, r);",
                "aguAdd(rn8, nn8, 0:1, mn8, r);",
                "local o:2 = 0xffff; aguAdd(rn8, o, 1:1, mn8, r);",
                "local o:2 = 1; aguAdd(rn8, o, 0:1, mn8, r);"][mm]
        for dn in range(16):
            dr = ("R%d" % dn) if dn < 8 else ("N%d" % (dn - 8))
            root(':lua %s,"%s"' % (d, dr),
                 "hb=0x04 & f15_13=2 & f12_11=%d & rn8 & nn8 & mn8 & f7_4=1 & f3_0=%d" % (mm, dn),
                 "local r:2; %s %s = r;" % (code, dr))
    # MOVEC
    root(":movec g6R,c5W", "hb=0x04 & b15=1 & b14=1 & g6R & f7_5=5 & c5W", "MVX = zext(g6R); build c5W;")
    root(":movec c5R,g6W", "hb=0x04 & b15=0 & b14=1 & g6W & f7_5=5 & c5R", "MVX = zext(c5R); build g6W;")
    root(':movec memS6,c5W', "hb=0x05 & b15=1 & b7=0 & b5=1 & memS6 & c5W", "local mv:4 = memS6; MVX = mv:3; build c5W;")
    root(':movec "#"^e24,c5W', "hb=0x05 & b15=1 & f13_8=0x34 & b14=1 & b7=0 & b6=0 & b5=1 & c5W; e24",
         "MVX = e24; build c5W;")
    root(':movec c5R,memS6', "hb=0x05 & b15=0 & b7=0 & b5=1 & memS6 & c5R", "memS6 = zext(c5R);")
    root(':movec "#<"^imm8,c5W', "hb=0x05 & imm8 & f7_5=5 & c5W", "MVX = zext(imm8:1); build c5W;")
    # MOVEM
    root(":movem pmem,m6W", "hb=0x07 & b15=1 & f7_6=2 & b14=1 & pmem & m6W", "local mv:4 = pmem; MVX = mv:3; build m6W;")
    root(":movem m6R,pmem", "hb=0x07 & b15=0 & f7_6=2 & b14=1 & pmem & m6R", "pmem = zext(m6R);")
    root(":movem pmem,m6W", "hb=0x07 & b15=1 & f7_6=0 & b14=0 & pmem & m6W", "local mv:4 = pmem; MVX = mv:3; build m6W;")
    root(":movem m6R,pmem", "hb=0x07 & b15=0 & f7_6=0 & b14=0 & pmem & m6R", "pmem = zext(m6R);")
    # MOVEP: X/Y:ea <-> pp, P:ea <-> pp, register <-> pp; W = 1 writes the peripheral
    root(":movep memS6,ppS16", "f23_17=4 & b15=1 & b14=1 & b7=1 & memS6 & ppS16", "ppS16 = memS6;")
    root(":movep ppS16,memS6", "f23_17=4 & b15=0 & b14=1 & b7=1 & memS6 & ppS16", "memS6 = ppS16;")
    root(':movep "#"^e24,ppS16', "f23_17=4 & b15=1 & b14=1 & b7=1 & b6=0 & f13_8=0x34 & ppS16; e24", "ppS16 = zext(e24:3);")
    root(":movep pmem,ppS16", "f23_17=4 & b15=1 & b14=1 & f7_6=1 & pmem & ppS16", "ppS16 = pmem;")
    root(":movep ppS16,pmem", "f23_17=4 & b15=0 & b14=1 & f7_6=1 & pmem & ppS16", "pmem = ppS16;")
    root(":movep g6R,ppS16", "f23_17=4 & b15=1 & b14=1 & f7_6=0 & g6R & ppS16", "ppS16 = zext(g6R);")
    root(":movep ppS16,g6W", "f23_17=4 & b15=0 & b14=1 & f7_6=0 & g6W & ppS16", "local mv:4 = ppS16; MVX = mv:3; build g6W;")
    # REP / DO
    # REP: the repeated instruction is executed through delayslot(1), in a loop, so the same
    # instruction reached by a jump (not through REP) runs once (no disassembly context)
    REPL = "LCSV = LC; LC = %s; <rep_top> delayslot(1); LC = LC - 1; if (LC != 0) goto <rep_top>; LC = LCSV;"
    root(':rep "#"^cnt', "hb=0x06 & imm8 & f7_4=0xa & f3_0 [ cnt = (f3_0 << 8) | imm8; ]",
         REPL % "cnt")
    root(":rep g6R", "hb=0x06 & f15_14=3 & g6R & f7_0=0x20",
         "local n:3 = g6R; " + REPL % "n:2")
    root(":rep memJ", "hb=0x06 & b15=0 & memJ & b7=0 & f5_0=0x20",
         "local mv:4 = memJ; " + REPL % "mv:2")
    ctx = "lend = 1; laddr = e16; lstart = inst_start + 2; globalset(laAt, lend); globalset(laAt, laddr); globalset(laAt, lstart); globalset(laPrev, lend); globalset(laPrev, laddr); globalset(laPrev, lstart);"
    dosem = ("local srv:2; getSR(srv); local nx:2 = inst_next / 4; sspush(LA, LC); sspush(nx, srv); "
             "LA = e16; LC = %s; MR = MR | 0x80;")
    root(':do "#"^cnt,dolast', "hb=0x06 & imm8 & f7_4=8 & f3_0; dolast & laAt & laPrev & e16 [ cnt = (f3_0 << 8) | imm8; " + ctx + " ]",
         dosem % "cnt")
    root(":do g6R,dolast", "hb=0x06 & f15_14=3 & g6R & f7_0=0; dolast & laAt & laPrev & e16 [ " + ctx + " ]",
         dosem % "g6R:2")
    root(":do memJ,dolast", "hb=0x06 & b15=0 & memJ & b7=0 & f5_0=0; dolast & laAt & laPrev & e16 [ " + ctx + " ]",
         "local mv:4 = memJ; local v:3 = mv:3; " + dosem % "v:2")
    # bit operations: 0000 101X, bits 15..14 = 00 aa, 01 ea, 10 pp, 11 register
    BOPS = {(0, 0): ("bclr", "&~"), (0, 1): ("bset", "|"), (1, 0): ("bchg", "^"), (1, 1): ("btst", None)}
    JOPS = {(0, 0): ("jclr", 0, 0), (0, 1): ("jset", 1, 0), (1, 0): ("jsclr", 0, 1), (1, 1): ("jsset", 1, 1)}
    for (x, b5), (nm, op) in BOPS.items():
        if op is None:
            mem_code = "local mv:4 = %s; local v:3 = mv:3; C = ((v >> bnum) & 1) != 0;"
        elif op == "&~":
            mem_code = "local mv:4 = %s; local v:3 = mv:3; C = ((v >> bnum) & 1) != 0; %s = zext(v & ~(1 << bnum));"
        else:
            mem_code = "local mv:4 = %s; local v:3 = mv:3; C = ((v >> bnum) & 1) != 0; %s = zext(v " + op + " (1 << bnum));"
        def mc(opnd):
            return mem_code.replace("%s", opnd)
        root(':%s "#"^bnum,memS6' % nm, "f23_17=5 & b16=%d & b15=0 & memS6 & b7=0 & b5=%d & bnumc<24 & bnum" % (x, b5), mc("memS6"))
        root(':%s "#"^bnum,ppS6' % nm, "f23_17=5 & b16=%d & f15_14=2 & ppS6 & b7=0 & b5=%d & bnumc<24 & bnum" % (x, b5), mc("ppS6"))
        if op is None:
            rc = "MVX = zext(g6R); local v:3 = MVX:3; C = ((v >> bnum) & 1) != 0;"
            root(':%s "#"^bnum,g6R' % nm, "f23_17=5 & b16=%d & f15_14=3 & g6R & f7_6=1 & b5=%d & bnumc<24 & bnum" % (x, b5), rc)
        else:
            expr = {"&~": "v & ~(1 << bnum)", "|": "v | (1 << bnum)", "^": "v ^ (1 << bnum)"}[op]
            rc = "local v:3 = g6R; C = ((v >> bnum) & 1) != 0; MVX = zext(%s); build g6W;" % expr
            root(':%s "#"^bnum,g6R' % nm, "f23_17=5 & b16=%d & f15_14=3 & g6R & g6W & f7_6=1 & b5=%d & bnumc<24 & bnum" % (x, b5), rc)
    for (x, b5), (nm, want, sub) in JOPS.items():
        if sub:
            act = "local srv:2; getSR(srv); local nx:2 = inst_next / 4; sspush(nx, srv); call jabs;"
        else:
            act = "goto jabs;"
        test = "C = ((v >> bnum) & 1) != 0; if (C != %d) goto inst_next; %s" % (want, act)
        root(':%s "#"^bnum,memJ,jabs' % nm, "f23_17=5 & b16=%d & b15=0 & memJ & b7=1 & b5=%d & bnumc<24 & bnum; jabs" % (x, b5),
             "local mv:4 = memJ; local v:3 = mv:3; " + test)
        root(':%s "#"^bnum,ppS6,jabs' % nm, "f23_17=5 & b16=%d & f15_14=2 & ppS6 & b7=1 & b5=%d & bnumc<24 & bnum; jabs" % (x, b5),
             "local mv:4 = ppS6; local v:3 = mv:3; " + test)
        root(':%s "#"^bnum,g6R,jabs' % nm, "f23_17=5 & b16=%d & f15_14=3 & g6R & f7_6=0 & b5=%d & bnumc<24 & bnum; jabs" % (x, b5),
             "local v:3 = g6R; " + test)
    # jumps
    JSUB = "local srv:2; getSR(srv); local nx:2 = inst_next / 4; sspush(nx, srv); "
    root(":jmp jeaR", "hb=0x0a & f15_14=3 & jeaR & f7_0=0x80", "goto [jeaR];")
    root(":jmp jeaA", "hb=0x0a & f15_14=3 & f7_0=0x80 & jeaA", "goto jeaA;")
    root(":jsr jeaR", "hb=0x0b & f15_14=3 & jeaR & f7_0=0x80", JSUB + "call [jeaR];")
    root(":jsr jeaA", "hb=0x0b & f15_14=3 & f7_0=0x80 & jeaA", JSUB + "call jeaA;")
    root(":j^cc0 jeaR", "hb=0x0a & f15_14=3 & jeaR & f7_4=0xa & cc0", "if (!cc0) goto inst_next; goto [jeaR];")
    root(":j^cc0 jeaA", "hb=0x0a & f15_14=3 & f7_4=0xa & cc0 & jeaA", "if (cc0) goto jeaA;")
    root(":js^cc0 jeaR", "hb=0x0b & f15_14=3 & jeaR & f7_4=0xa & cc0",
         "if (!cc0) goto inst_next; " + JSUB + "call [jeaR];")
    root(":js^cc0 jeaA", "hb=0x0b & f15_14=3 & f7_4=0xa & cc0 & jeaA",
         "if (!cc0) goto inst_next; " + JSUB + "call jeaA;")
    root(":jmp j12", "hb=0x0c & f15_12=0 & j12", "goto j12;")
    root(":jsr j12", "hb=0x0d & f15_12=0 & j12",
         "local srv:2; getSR(srv); local nx:2 = inst_next / 4; sspush(nx, srv); call j12;")
    root(":j^cc12 j12", "hb=0x0e & cc12 & j12", "if (cc12) goto j12;")
    root(":js^cc12 j12", "hb=0x0f & cc12 & j12",
         "if (!cc12) goto inst_next; local srv:2; getSR(srv); local nx:2 = inst_next / 4; sspush(nx, srv); call j12;")


def tail_table():
    emit("# DO loop-end p-code appended to every instruction")
    emit("tail: is lend=0 { }")
    emit("lstartAddr: lstart is lstart { export *[p]:4 lstart; }")
    emit("tail: is lend=1 & laddr & lstartAddr {"
         " local here:2 = inst_next / 4; if (here != laddr + 1) goto <done>;"
         " if ((MR & 0x80) == 0) goto <done>;"
         " LC = LC - 1; if (LC == 0) goto <exit>; goto lstartAddr;"
         " <exit> local e:4 = *[ss]:4 SP; SP = SP - 1; local sr:2 = e:2; setSR(sr);"
         " e = *[ss]:4 SP; SP = SP - 1; LA = e(2); LC = e:2;"
         " <done> }")
    emit()


def main():
    emit("# generated by tools/gen_dsp56000.py; do not edit")
    emit()
    emit("macro abs56(v, out) { local m:7 = zext(v s< 0); out = (v ^ (-m)) + m; }")
    emit("macro setMid(acc, m) { acc = (acc & ~(0xffffff:7 << 24)) | (zext(m) << 24); }")
    emit()
    ea_tables()
    alu_tables()
    pm_tables()
    cond_tables()
    nonparallel()
    tail_table()
    
    emit()
    # parallel instruction roots
    # one root per parallel-move class, so the class bits are explicit in the root pattern
    # (SLEIGH picks a root by its own constraints before resolving operand subtables)
    for cls in ("b23=1", "f23_22=1", "f23_21=1", "f23_20=1", "f23_17=4 & b14=0"):
        emit(":^aluMn aluOp pmR is (tail & %s & aluMn & aluOp & pmW) ... & pmR { build pmR; build aluOp; build pmW; build tail; }" % cls)
        emit(":move pmR is (tail & %s & f7_0=0 & pmW) ... & pmR { build pmR; build pmW; build tail; }" % cls)
    emit()
    VAR = ("pmR", "memS6", "pmem", "jeaA")
    for d, pat, code in ROOTS:
        notail = d.startswith(":rep") or d.startswith(":do ")
        head, act = (pat.split("[", 1) + [""])[:2]
        if notail:
            parts = [x.strip() for x in head.split("&")]
            if ";" not in head and any(x in VAR for x in parts):
                var = [x for x in parts if x in VAR]
                rest = [x for x in parts if x not in VAR]
                head = "(%s) ... & %s " % (" & ".join(rest), " & ".join(var))
            emit("%s is %s %s { %s }" % (d, head, ("[" + act) if act else "", code))
            continue
        if ";" not in head:
            parts = [x.strip() for x in head.split("&")]
            var = [x for x in parts if x in VAR]
            if var:
                rest = [x for x in parts if x not in VAR]
                head = "(tail & %s) ... & %s " % (" & ".join(rest), " & ".join(var))
                pat = head + ("[" + act if act else "")
                emit("%s is %s { %s build tail; }" % (d, pat, code))
                continue
        pat = pat.replace("XCTX", "")
        # disassembly actions in brackets stay at the end of the pattern
        if "[" in pat:
            p, act = pat.split("[", 1)
            act = "[" + act
            ctx = ""
            if "dolast &" in p:
                act = act.rstrip()
            emit("%s is tail & %s %s { %s build tail; }" % (d, p, act, code))
        else:
            emit("%s is tail & %s { %s build tail; }" % (d, pat, code))
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
