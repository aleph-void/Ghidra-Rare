#!/usr/bin/env python3
"""Generate data/languages/adsp218x_gen.sinc: the repetitive SLEIGH tables of the ADSP-218x module.

Everything here follows the ADSP-2100 Family User's Manual, 3rd edition (1995), Appendix A
(instruction coding) and Chapter 15 (instruction set reference):

  aluop / aluk     ALU function codes (AMF 10000-11111), register and constant Y operands
  macop / macsq    MAC function codes (AMF 00001-01111), xop * yop and xop * xop
  shop / shimm     shifter function codes (SF), register and immediate shift codes
  regR* / regW*    the register selection table (RGP, REG) at the three places it is encoded

Usage: tools/gen_adsp218x.py > data/languages/adsp218x_gen.sinc
"""

out = []
emit = out.append

# --------------------------------------------------------------------------------------------
# ALU.  Operands: X = xa (AX0 AX1 AR MR0 MR1 MR2 SR0 SR1), Y = ya (AY0 AY1 AF; code 3 = 0) or
# the type 9 constant (aluk).  Each constructor computes the result r, sets ASTAT and exports r;
# the destination (AR/AF/none) is written by the caller.
# --------------------------------------------------------------------------------------------

# (amf, display with X/Y placeholders, semantics with x/y, kind)
#   kind "add": r = a + b + c with full flags; args (a, b, c)
#   kind "add2": r = a + b; kind "sub": r = a - b (carry = no borrow); same flags, written with
#   carry/scarry/sborrow so the decompiler recovers comparisons
#   kind "log": logical, AV/AC cleared
#   kind "abs", "pass"
ALU = [
    (0x10, "PASS Y", ("pass", "$y")),
    (0x11, "Y + 1", ("add2", "$y", "1:2")),
    (0x12, "X + Y + C", ("add", "$x", "$y", "AC")),
    (0x13, "X + Y", ("add2", "$x", "$y")),
    (0x14, "NOT Y", ("log", "~$y")),
    (0x15, "-Y", ("sub", "0:2", "$y")),
    (0x16, "X - Y + C - 1", ("add", "$x", "~$y", "AC")),
    (0x17, "X - Y", ("sub", "$x", "$y")),
    (0x18, "Y - 1", ("sub", "$y", "1:2")),
    (0x19, "Y - X", ("sub", "$y", "$x")),
    (0x1a, "Y - X + C - 1", ("add", "$y", "~$x", "AC")),
    (0x1b, "NOT X", ("log", "~$x")),
    (0x1c, "X AND Y", ("log", "$x & $y")),
    (0x1d, "X OR Y", ("log", "$x | $y")),
    (0x1e, "X XOR Y", ("log", "$x ^ $y")),
    (0x1f, "ABS X", ("abs",)),
]

# Display of the Y = 0 (yop = 11) special cases, as the manual names them where it does
ALU_Y0 = {
    0x10: "PASS 0",
    0x11: "PASS 1",
    0x12: "X + C",
    0x13: "PASS X",
    0x14: "NOT 0",
    0x15: "-0",
    0x16: "X + C - 1",
    0x17: "X - 0",
    0x18: "PASS -1",
    0x19: "-X",
    0x1a: "-X + C - 1",
    0x1c: "X AND 0",
    0x1d: "X OR 0",
    0x1e: "X XOR 0",
}

# ALU codes that take a constant in type 9 (manual: ADD, SUBTRACT X-Y, SUBTRACT Y-X,
# AND/OR/XOR, PASS constant through Y, Y + 1 and Y - 1)
ALU_K = [0x10, 0x11, 0x12, 0x13, 0x16, 0x17, 0x18, 0x19, 0x1a, 0x1c, 0x1d, 0x1e]


def alu_sem(sem, x, y):
    kind = sem[0]
    sub = lambda s: s.replace("$x", x).replace("$y", y)
    if kind == "pass":
        return f"local r:2 = {y}; alulog(r);"
    if kind == "log":
        return f"local r:2 = {sub(sem[1])}; alulog(r);"
    if kind == "abs":
        return f"local r:2 = 0; aluabs({x}, r);"
    if kind == "add2":
        a, b = (sub(s) for s in sem[1:])
        return f"local r:2 = 0; aluadd2({a}, {b}, r);"
    if kind == "sub":
        a, b = (sub(s) for s in sem[1:])
        return f"local r:2 = 0; alusub({a}, {b}, r);"
    a, b, c = (sub(s) for s in sem[1:])
    return f"local r:2 = 0; aluadd({a}, {b}, {c}, r);"


def disp(fmt, X, Y):
    # tokenise the display: X and Y become operands, the rest literal strings
    parts = []
    for tok in fmt.split(" "):
        if tok == "X":
            parts.append(X)
        elif tok == "Y":
            parts.append(Y)
        elif tok == "-X":
            parts.append('"-"' + X)
        elif tok == "-Y":
            parts.append('"-"' + Y)
        else:
            parts.append(f'"{tok}"')
    return " ".join(parts)


emit("# ---- ALU: aluop (register or zero Y operand) ----")
for amf, fmt, sem in ALU:
    uses_y = "Y" in fmt
    uses_x = "X" in fmt
    # register Y
    cons = [f"amf={amf}"]
    if uses_y:
        d = disp(fmt, "xa" if uses_x else "", "ya")
        c = " & ".join(cons + (["xa"] if uses_x else []) + ["ya"])
        emit(f"aluop: {d} is {c} {{ {alu_sem(sem, 'xa', 'ya')} export r; }}")
        f0 = ALU_Y0[amf]
        d = disp(f0, "xa", "")
        c = " & ".join(cons + (["xa"] if "X" in f0 else []) + ["yop=3"])
        emit(f"aluop: {d} is {c} {{ {alu_sem(sem, 'xa', '0:2')} export r; }}")
    else:
        d = disp(fmt, "xa", "")
        c = " & ".join(cons + ["xa"])
        emit(f"aluop: {d} is {c} {{ {alu_sem(sem, 'xa', '0:2')} export r; }}")

emit("")
emit("# ---- ALU with a type 9 constant (kval, see aluk_v in adsp218x.slaspec) ----")
for amf, fmt, sem in ALU:
    if amf not in ALU_K:
        continue
    if amf == 0x11:      # PASS constant via Y + 1: shown as the value passed
        emit(f"aluk: \"PASS\" kp1 is amf={amf} & kval & kp1 {{ local r:2 = 0; aluadd2(kval, 1:2, r); export r; }}")
        continue
    if amf == 0x18:      # PASS constant via Y - 1
        emit(f"aluk: \"PASS\" km1 is amf={amf} & kval & km1 {{ local r:2 = 0; alusub(kval, 1:2, r); export r; }}")
        continue
    uses_x = "X" in fmt
    d = disp(fmt, "xa", "kval")
    c = " & ".join([f"amf={amf}", "kval"] + (["xa"] if uses_x else []))
    emit(f"aluk: {d} is {c} {{ {alu_sem(sem, 'xa', 'kval')} export r; }}")

# --------------------------------------------------------------------------------------------
# MAC.  X = xm (MX0 MX1 AR MR0 MR1 MR2 SR0 SR1), Y = ym (MY0 MY1 MF; code 3 = 0).  Result: the
# 40-bit value sign-extended to 8 bytes, MV set; the caller writes MR (40 bits) or MF (31-16).
# --------------------------------------------------------------------------------------------
# amf: (accumulate op, format)
MAC = {
    0x01: ("", "RND"), 0x02: ("MR +", "RND"), 0x03: ("MR -", "RND"),
    0x04: ("", "SS"), 0x05: ("", "SU"), 0x06: ("", "US"), 0x07: ("", "UU"),
    0x08: ("MR +", "SS"), 0x09: ("MR +", "SU"), 0x0a: ("MR +", "US"), 0x0b: ("MR +", "UU"),
    0x0c: ("MR -", "SS"), 0x0d: ("MR -", "SU"), 0x0e: ("MR -", "US"), 0x0f: ("MR -", "UU"),
}


def mac_sem(acc, fmt, x, y):
    xs = fmt in ("SS", "SU", "RND")
    ys = fmt in ("SS", "US", "RND")
    xe = f"sext({x})" if xs else f"zext({x})"
    ye = f"sext({y})" if ys else f"zext({y})"
    s = [f"local p:8 = {xe} * {ye};", "p = p << zext(M_MODE == 0);"]
    if acc == "MR +":
        s.append("local r:8 = sext(MR) + p;")
    elif acc == "MR -":
        s.append("local r:8 = sext(MR) - p;")
    else:
        s.append("local r:8 = p;")
    if fmt == "RND":
        s.append("macrnd(r);")
    s.append("macfin(r);")
    return " ".join(s)


emit("")
emit("# ---- MAC: macop (register or zero Y operand) and macsq (xop * xop, type 9) ----")
for amf, (acc, fmt) in sorted(MAC.items()):
    pre = (f'"{acc.split()[0]}" "{acc.split()[1]}" ' if acc else "")
    emit(f"macop: {pre}xm \"*\" ym \"({fmt})\" is amf={amf} & xm & ym {{ {mac_sem(acc, fmt, 'xm', 'ym')} export r; }}")
    if amf == 0x04:
        emit(f"macop: \"0\" is amf={amf} & yop=3 {{ local r:8 = 0; macfin(r); export r; }}")
    elif amf == 0x08:
        emit(f"macop: \"MR\" is amf={amf} & yop=3 {{ local r:8 = sext(MR); macfin(r); export r; }}")
    elif amf == 0x02:
        emit(f"macop: \"MR\" \"(RND)\" is amf={amf} & yop=3 {{ local r:8 = sext(MR); macrnd(r); macfin(r); export r; }}")
    else:
        emit(f"macop: {pre}xm \"*\" \"0\" \"({fmt})\" is amf={amf} & xm & yop=3 {{ {mac_sem(acc, fmt, 'xm', '0:2')} export r; }}")
for amf, (acc, fmt) in sorted(MAC.items()):
    if fmt not in ("SS", "UU", "RND"):
        continue
    pre = (f'"{acc.split()[0]}" "{acc.split()[1]}" ' if acc else "")
    emit(f"macsq: {pre}xm \"*\" xm2 \"({fmt})\" is amf={amf} & xm & xm2 {{ {mac_sem(acc, fmt, 'xm', 'xm')} export r; }}")

# --------------------------------------------------------------------------------------------
# Shifter.  X = xs (SI, -, AR, MR0, MR1, MR2, SR0, SR1).  Complete operations with destination.
# --------------------------------------------------------------------------------------------
emit("")
emit("# ---- Shifter: shop (SE-controlled, all SF codes) and shimm (immediate shift code) ----")
SF = {
    0: ("LSHIFT", "HI", False), 1: ("LSHIFT", "HI", True), 2: ("LSHIFT", "LO", False), 3: ("LSHIFT", "LO", True),
    4: ("ASHIFT", "HI", False), 5: ("ASHIFT", "HI", True), 6: ("ASHIFT", "LO", False), 7: ("ASHIFT", "LO", True),
    8: ("NORM", "HI", False), 9: ("NORM", "HI", True), 10: ("NORM", "LO", False), 11: ("NORM", "LO", True),
}


def shift_sem(op, ref, orr, code):
    # v: the 16-bit input extended to 8 bytes with the extension bit X; s: the shift distance
    # relative to bit 0 of SR (HI reference adds 16)
    if op == "ASHIFT":
        v = "sext(xs)"
    elif op == "LSHIFT":
        v = "zext(xs)"
    elif ref == "HI":      # NORM (HI): the extension bit is AC (only seen when SE > 0, HIX case)
        v = "zext(xs) | (zext(AC != 0) * 0xffffffffffff0000)"
    else:
        v = "zext(xs)"
    s = [f"local v:8 = {v};", f"local c:8 = {code};"]
    if ref == "HI":
        s.append("c = c + 16;")
    s.append("local o:8 = (v << c) * zext(c s>= 0) + (v s>> (0 - c)) * zext(c s< 0);")
    if orr:
        s.append("SR = SR | o:4;")
    else:
        s.append("SR = o:4;")
    return " ".join(s)


for sf, (op, ref, orr) in SF.items():
    pre = '"SR" "=" "SR" "OR" ' if orr else '"SR" "=" '
    code = "-sext(SE)" if op == "NORM" else "sext(SE)"
    emit(f"shop: {pre}\"{op}\" xs \"({ref})\" is sf={sf} & xs {{ {shift_sem(op, ref, orr, code)} }}")
    if sf < 8:
        emit(f"shimm: {pre}\"{op}\" xs \"BY\" exp8 \"({ref})\" is sf={sf} & xs & exp8 {{ {shift_sem(op, ref, orr, 'sext(exp8:1)')} }}")
emit('shop: "SE" "=" "EXP" xs "(HI)" is sf=12 & xs { expdet(xs); SS = xs s< 0; SE = sext(EXPV:1); }')
emit('shop: "SE" "=" "EXP" xs "(HIX)" is sf=13 & xs { expdet(xs); SS = (xs s< 0) ^ AV; '
     'SE = sext(EXPV:1) * zext(AV == 0) + zext(AV != 0); }')
emit('shop: "SE" "=" "EXP" xs "(LO)" is sf=14 & xs { local k:2 = lzcount(xs ^ (zext(SS) * 0xffff)); '
     'local lo:2 = -15 - k; SE = SE * zext(SE != 0xfff1) + lo * zext(SE == 0xfff1); }')
emit('shop: "SB" "=" "EXPADJ" xs is sf=15 & xs { expdet(xs); SB = SB * zext(EXPV s<= SB) + EXPV * zext(EXPV s> SB); }')

# --------------------------------------------------------------------------------------------
# Register selection table (Appendix A, REG / RGP) at three positions:
#   3: rgp (19-18), reg (3-0)     types 3 and 7
#   d: drgp (11-10), dreg (7-4)   type 17 destination
#   s: srgp (9-8), sreg (3-0)     type 17 source
# Reads export the value as the DMD bus sees it; writes export the target and a matching
# fixup table (regF*) completes register-specific side effects after the write.
# --------------------------------------------------------------------------------------------
DREGS = "AX0 AX1 MX0 MX1 AY0 AY1 MY0 MY1 SI SE AR MR0 MR1 MR2 SR0 SR1".split()
G1 = "I0 I1 I2 I3 M0 M1 M2 M3 L0 L1 L2 L3".split() + [None, None, "PMOVLAY", "DMOVLAY"]
G2 = "I4 I5 I6 I7 M4 M5 M6 M7 L4 L5 L6 L7".split() + [None, None, None, None]
G3 = ["ASTAT", "MSTAT", "SSTAT", "IMASK", "ICNTL", "CNTR", "SB", "PX", "RX0", "TX0", "RX1", "TX1",
      "IFC", "OWRCNTR", None, None]
GROUPS = [DREGS, G1, G2, G3]
READONLY = {"SSTAT"}
WRITEONLY = {"IFC", "OWRCNTR"}


def fixup(name):
    """p-code applied after <name> has been written with a 16-bit value"""
    if name in ("MR1",):
        return "MR2 = MR1 s>> 15;"
    if name in ("MR2", "SE"):
        return f"{name} = sext({name}:1);"
    if name[0] in "IL" and name[1:].isdigit():
        return f"{name} = {name} & 0x3fff;"
    if name[0] == "M" and name[1:].isdigit():
        return f"{name} = ({name} << 2) s>> 2;"
    return {
        "ASTAT": "setastat(ASTAT);",
        "MSTAT": "setmstat(MSTAT);",
        "IMASK": "IMASK = IMASK & 0x3ff;",
        "ICNTL": "ICNTL = ICNTL & 0x1f;",
        "CNTR": "cntpush(CNTR); CNTR = CNTRW & 0x3fff;",
        "SB": "SB = (SB << 11) s>> 11;",
        "PX": "PX = PX & 0xff;",
        "OWRCNTR": "CNTR = OWRCNTR & 0x3fff;",
        "IFC": "ifc(IFC);",
    }.get(name, "")


def read_sem(name):
    if name == "ASTAT":
        return "local v:2 = 0; getastatm(v); export v;"
    if name == "MSTAT":
        return "local v:2 = 0; getmstatm(v); export v;"
    if name == "SSTAT":
        return "local v:2 = 0; getsstatm(v); export v;"
    return f"export {name};"


def write_target(name):
    return {"CNTR": "CNTRW"}.get(name, name)


POS = {"3": ("rgp", "reg"), "d": ("drgp", "dregf"), "s": ("srgp", "sregf")}
for tag, (gf, rf) in POS.items():
    emit("")
    emit(f"# ---- register selection table at position {tag} ----")
    for g, names in enumerate(GROUPS):
        for r, name in enumerate(names):
            if name is None:
                continue
            if tag in "3s" and name not in WRITEONLY:
                emit(f'regR{tag}: "{name}" is {gf}={g} & {rf}={r} {{ {read_sem(name)} }}')
            if tag in "3d" and name not in READONLY:
                emit(f'regW{tag}: "{name}" is {gf}={g} & {rf}={r} {{ export {write_target(name)}; }}')
                emit(f'regF{tag}: is {gf}={g} & {rf}={r} {{ {fixup(name)} }}')

# data register write fixups (DREG fields at bits 7-4 and 3-0, and type 1 destinations)
for tag, f in (("4", "dreg4"), ("0", "dreg0")):
    emit("")
    for r, name in enumerate(DREGS):
        emit(f"dfix{tag}: is {f}={r} {{ {fixup(name)} }}")


# --------------------------------------------------------------------------------------------
# Indirect addressing DM(I,M) / PM(I,M) with post-modify through the modulus logic; DAG1
# addresses pass through the bit-reverse logic.
#   DMg20: types 2 and 4 (G bit 20)   DMg16: type 12 (G bit 16)   DMt1: type 1 (DAG1)
#   PMd:   types 5 and 13 (DAG2)      PMt1: type 1 (DAG2)         MODg4: type 21
# --------------------------------------------------------------------------------------------
def dag(name, gfield, ifield, mfield, space, dags, display=True):
    emit("")
    for g in dags:
        for i in range(4):
            for m in range(4):
                I, M, L = f"I{4*g+i}", f"M{4*g+m}", f"L{4*g+i}"
                cons = ([f"{gfield}={g}"] if gfield else []) + [f"{ifield}={i}", f"{mfield}={m}"]
                br = "bitrev(a); " if g == 0 else ""
                if space is None:
                    emit(f'{name}: "({I},{M})" is {" & ".join(cons)} {{ dagmod({I}, {M}, {L}); }}')
                else:
                    sz = 2 if space == "dm" else 3
                    emit(f'{name}: "{space.upper()}({I},{M})" is {" & ".join(cons)} '
                         f'{{ local a:2 = {I}; {br}dagmod({I}, {M}, {L}); export *[{space}]:{sz} a; }}')

dag("DMg20", "g20", "i32", "m10", "dm", (0, 1))
dag("DMg16", "g16", "i32", "m10", "dm", (0, 1))
dag("DMt1", None, "dmi", "dmm", "dm", (0,))
dag("PMd", None, "i32", "m10", "pm", (1,))
dag("PMt1", None, "pmi", "pmm", "pm", (1,))
dag("MODg4", "g4", "i32", "m10", None, (0, 1))

print("# Generated by tools/gen_adsp218x.py from the ADSP-2100 Family User's Manual tables. Do not edit.")
print("\n".join(out))
