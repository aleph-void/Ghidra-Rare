#!/usr/bin/env python3
# Generates data/languages/rl78.sinc, the RL78 instruction set, for rl78.slaspec (RL78-S3 core,
# with the multiply/divide/MAC instructions) and rl78_s2.slaspec (RL78-S1/S2 cores, without them).
#
#   python3 tools/gen_rl78.py            (from the module directory)
#
# Encodings follow the RL78 Family User's Manual: Software (R01US0015, "5.6 Instruction codes")
# and were checked opcode by opcode against GNU objdump (see test/). Output is deterministic.
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "languages", "rl78.sinc")

L = []


def emit(s=""):
    L.append(s)


R8 = ["X", "A", "C", "B", "E", "D", "L", "H"]
RP = ["AX", "BC", "DE", "HL"]


def breg(bank, name):
    return name if bank == 0 else "RB%d_%s" % (bank, name)


# ---------------------------------------------------------------------------------------------
# Banked register subtables. The register bank (PSW.RBS) is tracked in the "bank" context field,
# which SEL RBn sets for the following code with globalset().
# ---------------------------------------------------------------------------------------------
emit("# ---- banked registers ----")
for i, n in enumerate(R8):
    for b in range(4):
        emit('r%s: "%s" is bank=%d { export %s; }' % (n, n, b, breg(b, n)))
for i, n in enumerate(RP):
    for b in range(4):
        emit('r%s: "%s" is bank=%d { export %s; }' % (n, n, b, breg(b, n)))
for n in ["BCAX", "HLDE"]:
    for b in range(4):
        emit('r%s: "%s" is bank=%d { export %s; }' % (n, n, b, breg(b, n)))
# 8-bit register in bits 0-2 of the opcode byte
for i, n in enumerate(R8):
    emit("r8: r%s is r3=%d & r%s { export r%s; }" % (n, i, n, n))
# register pair in bits 1-2
for i, n in enumerate(RP):
    emit("rp12: r%s is frp12=%d & r%s { export r%s; }" % (n, i, n, n))
# register pair in bits 4-5
for i, n in enumerate(RP):
    emit("rp45: r%s is frp45=%d & r%s { export r%s; }" % (n, i, n, n))
# X, A, C, B in bits 0-1
for i, n in enumerate(["X", "A", "C", "B"]):
    emit("rg01: r%s is frg01=%d & r%s { export r%s; }" % (n, i, n, n))
emit()

# ---------------------------------------------------------------------------------------------
# Memory operands. Each exists for byte (1) and word (2) access. Without the ES: prefix, data
# addresses are in the near area F0000-FFFFF; with it the upper four bits come from ES.
# ---------------------------------------------------------------------------------------------
emit("# ---- memory operands ----")
for s in (1, 2):
    # !addr16
    emit('abs%d: "!"^a is esp=0 & imm16 [ a = 0xF0000 | imm16; ] { export *[ram]:%d a; }' % (s, s))
    emit('abs%d: "ES:!"^imm16 is esp=1 & imm16 { local a:3 = (zext(ES & 0xF) << 16) | imm16; export *[ram]:%d a; }' % (s, s))
    # saddr: FFE20-FFF1F, encoded as the low byte of the address
    emit("saddr%d: a is s_hi3=0 & imm8 [ a = 0xFFF00 + imm8; ] { export *[ram]:%d a; }" % (s, s))
    emit("saddr%d: a is imm8 [ a = 0xFFE00 + imm8; ] { export *[ram]:%d a; }" % (s, s))
    # [DE], [HL]
    for r in ("DE", "HL"):
        emit('ind%s%d: "["^r%s^"]" is esp=0 & r%s { local a:3 = segment(NEARSEG, r%s); export *[ram]:%d a; }' % (r, s, r, r, r, s))
        emit('ind%s%d: "ES:["^r%s^"]" is esp=1 & r%s { local b:1 = ES & 0xF; local a:3 = segment(b, r%s); export *[ram]:%d a; }' % (r, s, r, r, r, s))
        # [DE+byte], [HL+byte]
        emit('dsp%s%d: "["^r%s^"+"^imm8^"]" is esp=0 & r%s; imm8 { local a:3 = segment(NEARSEG, r%s + imm8); export *[ram]:%d a; }' % (r, s, r, r, r, s))
        emit('dsp%s%d: "ES:["^r%s^"+"^imm8^"]" is esp=1 & r%s; imm8 { local b:1 = ES & 0xF; local a:3 = segment(b, r%s + imm8); export *[ram]:%d a; }' % (r, s, r, r, r, s))
    # [SP+byte] (ES ignored)
    emit('dspSP%d: "[SP+"^imm8^"]" is imm8 { local a:3 = segment(NEARSEG, SP + imm8); export *[ram]:%d a; }' % (s, s))
    # [HL+B], [HL+C]
    for r in ("B", "C"):
        emit('idx%s%d: "[HL+"^r%s^"]" is esp=0 & rHL & r%s { local a:3 = segment(NEARSEG, rHL + zext(r%s)); export *[ram]:%d a; }' % (r, s, r, r, r, s))
        emit('idx%s%d: "ES:[HL+"^r%s^"]" is esp=1 & rHL & r%s { local b:1 = ES & 0xF; local a:3 = segment(b, rHL + zext(r%s)); export *[ram]:%d a; }' % (r, s, r, r, r, s))
    # word[B], word[C], word[BC]
    for r in ("B", "C", "BC"):
        ext = "zext(r%s)" % r if r != "BC" else "rBC"
        emit('wd%s%d: imm16^"["^r%s^"]" is esp=0 & r%s & imm16 { local w:2 = imm16; local a:3 = segment(NEARSEG, w + %s); export *[ram]:%d a; }' % (r, s, r, r, ext, s))
        emit('wd%s%d: "ES:"^imm16^"["^r%s^"]" is esp=1 & r%s & imm16 { local w:2 = imm16; local b:1 = ES & 0xF; local a:3 = segment(b, w + %s); export *[ram]:%d a; }' % (r, s, r, r, ext, s))
emit()
# sfr: FFF00-FFFFF. The CPU registers at FFFF8-FFFFF are named as objdump and the manual do.
emit("# ---- sfr operands ----")
for v, n in [(0xF8, "SPL"), (0xF9, "SPH"), (0xFA, "PSW"), (0xFC, "CS"), (0xFD, "ES"), (0xFE, "PMC"), (0xFF, "MEM")]:
    emit('sfr1: "%s" is imm8=0x%X { export %s; }' % (n, v, n))
emit("sfr1: a is imm8 [ a = 0xFFF00 + imm8; ] { export *[ram]:1 a; }")
emit('sfr2: "SP" is imm8=0xF8 { export SP; }')
emit("sfr2: a is imm8 [ a = 0xFFF00 + imm8; ] { export *[ram]:2 a; }")
# movw rp, !addr16 prints !FFF8 as SP (the manual's MOVW rp, SP)
emit('absSP2: "SP" is esp=0 & imm16=0xFFF8 { export SP; }')
emit("absSP2: abs2 is abs2 { export abs2; }")
emit()

# ---------------------------------------------------------------------------------------------
# Branch targets
# ---------------------------------------------------------------------------------------------
emit("# ---- branch targets ----")
emit('rel8: "$"^t is simm8 [ t = (inst_next + simm8) & 0xFFFFF; ] { export *[ram]:1 t; }')
emit('rel16: "$!"^t is simm16 [ t = (inst_next + simm16) & 0xFFFFF; ] { export *[ram]:1 t; }')
emit('jabs16: "!"^imm16 is imm16 { export *[ram]:1 imm16; }')
emit('jabs20: "!!"^imm20 is imm20 { export *[ram]:1 imm20; }')
emit()


def C(text, pattern, body):
    """Emit one instruction constructor. Every real instruction requires phase=1 (see the
    prefix/skip wrappers in rl78.slaspec)."""
    text = re.sub(r'(?<!["\w])(SP|ES|CY|PSW)(?!["\w])', r'"\1"', text)
    emit(":%s is phase=1 & %s {%s}" % (text, pattern, (" " + body + " ") if body else ""))


# ---------------------------------------------------------------------------------------------
# 8-bit arithmetic and logic
# ---------------------------------------------------------------------------------------------
emit("# ---- 8-bit ALU ----")
ALU = [  # name, first-map row, 61-map row for [HL+B]/[HL+C], macro
    ("add", 0x00, 0x80, "add8"), ("addc", 0x10, 0x90, "addc8"), ("sub", 0x20, 0xA0, "sub8"),
    ("subc", 0x30, 0xB0, "subc8"), ("cmp", 0x40, 0xC0, "cmp8"), ("and", 0x50, 0xD0, "and8"),
    ("or", 0x60, 0xE0, "or8"), ("xor", 0x70, 0xF0, "xor8")]
for name, row, hrow, m in ALU:
    C("%s saddr1, #imm8" % name, "op=0x%02X; saddr1; imm8" % (row | 0xA), "%s(saddr1, imm8:1);" % m)
    C("%s rA, saddr1" % name, "op=0x%02X & rA; saddr1" % (row | 0xB), "%s(rA, saddr1);" % m)
    C("%s rA, #imm8" % name, "op=0x%02X & rA; imm8" % (row | 0xC), "%s(rA, imm8:1);" % m)
    C("%s rA, indHL1" % name, "op=0x%02X & rA & indHL1" % (row | 0xD), "%s(rA, indHL1);" % m)
    C("%s rA, dspHL1" % name, "op=0x%02X & rA; dspHL1" % (row | 0xE), "%s(rA, dspHL1);" % m)
    C("%s rA, abs1" % name, "op=0x%02X & rA; abs1" % (row | 0xF), "%s(rA, abs1);" % m)
    # 61 map: <op> r, A (reg in 0-7) and <op> A, r (r != A)
    C("%s r8, rA" % name, "op=0x61; op_hi=%d & b3=0 & r8 & rA" % (row >> 4), "%s(r8, rA);" % m)
    C("%s rA, r8" % name, "op=0x61; op_hi=%d & b3=1 & r3!=1 & r8 & rA" % (row >> 4), "%s(rA, r8);" % m)
    C("%s rA, idxB1" % name, "op=0x61; op=0x%02X & rA & idxB1" % hrow, "%s(rA, idxB1);" % m)
    C("%s rA, idxC1" % name, "op=0x61; op=0x%02X & rA & idxC1" % (hrow | 2), "%s(rA, idxC1);" % m)
C("cmp abs1, #imm8", "op=0x40; abs1; imm8", "cmp8(abs1, imm8:1);")
emit()

# ---------------------------------------------------------------------------------------------
# 16-bit arithmetic
# ---------------------------------------------------------------------------------------------
emit("# ---- 16-bit ALU ----")
for name, row, m in [("addw", 0x00, "add16"), ("subw", 0x20, "sub16"), ("cmpw", 0x40, "cmp16")]:
    C("%s rAX, abs2" % name, "op=0x%02X & rAX; abs2" % (row | 2), "%s(rAX, abs2);" % m)
    C("%s rAX, #imm16" % name, "op=0x%02X & rAX; imm16" % (row | 4), "%s(rAX, imm16:2);" % m)
    C("%s rAX, saddr2" % name, "op=0x%02X & rAX; saddr2" % (row | 6), "%s(rAX, saddr2);" % m)
    C("%s rAX, rp12" % name, "op_hi=%d & b3=0 & b0=1 & rAX & rp12%s" % (row >> 4, " & frp12!=0" if name != "addw" and name != "subw" else ""), "%s(rAX, rp12);" % m)
    C("%s rAX, dspHL2" % name, "op=0x61; op=0x%02X & rAX; dspHL2" % (row | 9), "%s(rAX, dspHL2);" % m)
C("addw SP, #imm8", "op=0x10; imm8", "SP = SP + imm8;")
C("subw SP, #imm8", "op=0x20; imm8", "SP = SP - imm8;")
emit()

# ---------------------------------------------------------------------------------------------
# increment / decrement
# ---------------------------------------------------------------------------------------------
emit("# ---- inc/dec ----")
for name, row, w, m in [("inc", 0x80, 0xA0, "inc8"), ("dec", 0x90, 0xB0, "dec8")]:
    C("%s r8" % name, "op_hi=%d & b3=0 & r8" % (row >> 4), "%s(r8);" % m)
    C("%s abs1" % name, "op=0x%02X; abs1" % w, "%s(abs1);" % m)
    C("%s saddr1" % name, "op=0x%02X; saddr1" % (w | 4), "%s(saddr1);" % m)
    C("%s dspHL1" % name, "op=0x61; op=0x%02X; dspHL1" % (0x59 if name == "inc" else 0x69), "%s(dspHL1);" % m)
for name, w, d in [("incw", 0xA0, "+"), ("decw", 0xB0, "-")]:
    C("%s rp12" % name, "op_hi=%d & b3=0 & b0=1 & rp12" % (w >> 4), "rp12 = rp12 %s 1;" % d)
    C("%s abs2" % name, "op=0x%02X; abs2" % (w | 2), "abs2 = abs2 %s 1;" % d)
    C("%s saddr2" % name, "op=0x%02X; saddr2" % (w | 6), "saddr2 = saddr2 %s 1;" % d)
    C("%s dspHL2" % name, "op=0x61; op=0x%02X; dspHL2" % (0x79 if name == "incw" else 0x89), "dspHL2 = dspHL2 %s 1;" % d)
emit()

# ---------------------------------------------------------------------------------------------
# 8-bit transfer
# ---------------------------------------------------------------------------------------------
emit("# ---- mov ----")
C("mov r8, #imm8", "op_hi=5 & b3=0 & r8; imm8", "r8 = imm8;")
C("mov rA, r8", "op_hi=6 & b3=0 & r3!=1 & r8 & rA", "rA = r8;")
C("mov r8, rA", "op_hi=7 & b3=0 & r3!=1 & r8 & rA", "r8 = rA;")
C("mov saddr1, #imm8", "op=0xCD; saddr1; imm8", "saddr1 = imm8;")
C("mov sfr1, #imm8", "op=0xCE; sfr1; imm8", "sfr1 = imm8;")
C("mov abs1, #imm8", "op=0xCF; abs1; imm8", "abs1 = imm8;")
C("mov rA, saddr1", "op=0x8D & rA; saddr1", "rA = saddr1;")
C("mov saddr1, rA", "op=0x9D & rA; saddr1", "saddr1 = rA;")
C("mov rA, sfr1", "op=0x8E & rA; sfr1", "rA = sfr1;")
C("mov sfr1, rA", "op=0x9E & rA; sfr1", "sfr1 = rA;")
C("mov rA, abs1", "op=0x8F & rA; abs1", "rA = abs1;")
C("mov abs1, rA", "op=0x9F & rA; abs1", "abs1 = rA;")
C("mov ES, #imm8", "op=0x41; imm8", "ES = imm8;")
C("mov ES, saddr1", "op=0x61; op=0xB8; saddr1", "ES = saddr1;")
for r, ld, st in [("DE", 0x89, 0x99), ("HL", 0x8B, 0x9B)]:
    C("mov rA, ind%s1" % r, "op=0x%02X & rA & ind%s1" % (ld, r), "rA = ind%s1;" % r)
    C("mov ind%s1, rA" % r, "op=0x%02X & rA & ind%s1" % (st, r), "ind%s1 = rA;" % r)
for r, ld, st, imm in [("DE", 0x8A, 0x9A, 0xCA), ("HL", 0x8C, 0x9C, 0xCC), ("SP", 0x88, 0x98, 0xC8)]:
    C("mov rA, dsp%s1" % r, "op=0x%02X & rA; dsp%s1" % (ld, r), "rA = dsp%s1;" % r)
    C("mov dsp%s1, rA" % r, "op=0x%02X & rA; dsp%s1" % (st, r), "dsp%s1 = rA;" % r)
    C("mov dsp%s1, #imm8" % r, "op=0x%02X; dsp%s1; imm8" % (imm, r), "dsp%s1 = imm8;" % r)
for r, ld, st in [("B", 0xC9, 0xD9), ("C", 0xE9, 0xF9)]:
    C("mov rA, idx%s1" % r, "op=0x61; op=0x%02X & rA & idx%s1" % (ld, r), "rA = idx%s1;" % r)
    C("mov idx%s1, rA" % r, "op=0x61; op=0x%02X & rA & idx%s1" % (st, r), "idx%s1 = rA;" % r)
for r, ld, st, imm in [("B", 0x09, 0x18, 0x19), ("C", 0x29, 0x28, 0x38), ("BC", 0x49, 0x48, 0x39)]:
    C("mov rA, wd%s1" % r, "op=0x%02X & rA; wd%s1" % (ld, r), "rA = wd%s1;" % r)
    C("mov wd%s1, rA" % r, "op=0x%02X & rA; wd%s1" % (st, r), "wd%s1 = rA;" % r)
    C("mov wd%s1, #imm8" % r, "op=0x%02X; wd%s1; imm8" % (imm, r), "wd%s1 = imm8;" % r)
for r, sa, ab in [("X", 0xD8, 0xD9), ("B", 0xE8, 0xE9), ("C", 0xF8, 0xF9)]:
    C("mov r%s, saddr1" % r, "op=0x%02X & r%s; saddr1" % (sa, r), "r%s = saddr1;" % r)
    C("mov r%s, abs1" % r, "op=0x%02X & r%s; abs1" % (ab, r), "r%s = abs1;" % r)
emit()

# xch
emit("# ---- xch ----")
C("xch rA, rX", "op=0x08 & rA & rX", "local t:1 = rA; rA = rX; rX = t;")
C("xch rA, r8", "op=0x61; op_hi=8 & b3=1 & r3!=1 & r8 & rA", "local t:1 = rA; rA = r8; r8 = t;")
for opr, code in [("saddr1", 0xA8), ("idxC1", 0xA9), ("abs1", 0xAA), ("sfr1", 0xAB), ("indHL1", 0xAC),
                  ("dspHL1", 0xAD), ("indDE1", 0xAE), ("dspDE1", 0xAF), ("idxB1", 0xB9)]:
    sep = "; " if opr in ("saddr1", "abs1", "sfr1", "dspHL1", "dspDE1") else " & "
    C("xch rA, %s" % opr, "op=0x61; op=0x%02X & rA%s%s" % (code, sep, opr), "local t:1 = rA; rA = %s; %s = t;" % (opr, opr))
emit()

# oneb / clrb / cmp0
emit("# ---- oneb/clrb/cmp0/onew/clrw ----")
for name, row, body in [("oneb", 0xE0, "%s = 1;"), ("clrb", 0xF0, "%s = 0;"), ("cmp0", 0xD0, "cmp0(%s);")]:
    C("%s rg01" % name, "op_hi=%d & op_lo<4 & rg01" % (row >> 4), body % "rg01")
    C("%s saddr1" % name, "op=0x%02X; saddr1" % (row | 4), body % "saddr1")
    C("%s abs1" % name, "op=0x%02X; abs1" % (row | 5), body % "abs1")
C("onew rAX", "op=0xE6 & rAX", "rAX = 1;")
C("onew rBC", "op=0xE7 & rBC", "rBC = 1;")
C("clrw rAX", "op=0xF6 & rAX", "rAX = 0;")
C("clrw rBC", "op=0xF7 & rBC", "rBC = 0;")
emit()

# movs / cmps
C("movs dspHL1, rX", "op=0x61; op=0xCE & rX & rA; dspHL1", "dspHL1 = rX; Z = (rX == 0); CY = (rA == 0) || (rX == 0);")
C("cmps rX, dspHL1", "op=0x61; op=0xDE & rX & rA; dspHL1",
  "local m:1 = dspHL1; AC = (rX & 0xF) < (m & 0xF); Z = (rX == m); CY = (rX != m) || (rA == 0) || (rX == 0);")
emit()

# ---------------------------------------------------------------------------------------------
# 16-bit transfer
# ---------------------------------------------------------------------------------------------
emit("# ---- movw ----")
C("movw rp12, #imm16", "op_hi=3 & b3=0 & b0=0 & rp12; imm16", "rp12 = imm16;")
C("movw rAX, rp12", "op_hi=1 & b3=0 & b0=1 & frp12!=0 & rp12 & rAX", "rAX = rp12;")
C("movw rp12, rAX", "op_hi=1 & b3=0 & b0=0 & frp12!=0 & rp12 & rAX", "rp12 = rAX;")
C("movw saddr2, #imm16", "op=0xC9; saddr2; imm16", "saddr2 = imm16;")
C("movw sfr2, #imm16", "op=0xCB; sfr2; imm16", "sfr2 = imm16;")
C("movw rAX, saddr2", "op=0xAD & rAX; saddr2", "rAX = saddr2;")
C("movw saddr2, rAX", "op=0xBD & rAX; saddr2", "saddr2 = rAX;")
C("movw rAX, sfr2", "op=0xAE & rAX; sfr2", "rAX = sfr2;")
C("movw sfr2, rAX", "op=0xBE & rAX; sfr2", "sfr2 = rAX;")
C("movw rAX, abs2", "op=0xAF & rAX; abs2", "rAX = abs2;")
C("movw abs2, rAX", "op=0xBF & rAX; abs2", "abs2 = rAX;")
for r, ld, st in [("DE", 0xA9, 0xB9), ("HL", 0xAB, 0xBB)]:
    C("movw rAX, ind%s2" % r, "op=0x%02X & rAX & ind%s2" % (ld, r), "rAX = ind%s2;" % r)
    C("movw ind%s2, rAX" % r, "op=0x%02X & rAX & ind%s2" % (st, r), "ind%s2 = rAX;" % r)
for r, ld, st in [("DE", 0xAA, 0xBA), ("HL", 0xAC, 0xBC), ("SP", 0xA8, 0xB8)]:
    C("movw rAX, dsp%s2" % r, "op=0x%02X & rAX; dsp%s2" % (ld, r), "rAX = dsp%s2;" % r)
    C("movw dsp%s2, rAX" % r, "op=0x%02X & rAX; dsp%s2" % (st, r), "dsp%s2 = rAX;" % r)
for r, ld, st in [("B", 0x59, 0x58), ("C", 0x69, 0x68), ("BC", 0x79, 0x78)]:
    C("movw rAX, wd%s2" % r, "op=0x%02X & rAX; wd%s2" % (ld, r), "rAX = wd%s2;" % r)
    C("movw wd%s2, rAX" % r, "op=0x%02X & rAX; wd%s2" % (st, r), "wd%s2 = rAX;" % r)
C("movw rp45, saddr2", "op_lo=0xA & op_hi>=0xD & rp45; saddr2", "rp45 = saddr2;")
C("movw rp45, absSP2", "op_lo=0xB & op_hi>=0xD & rp45; absSP2", "rp45 = absSP2;")
C("xchw rAX, rp12", "op_hi=3 & b3=0 & b0=1 & frp12!=0 & rp12 & rAX", "local t:2 = rAX; rAX = rp12; rp12 = t;")
emit()

# ---------------------------------------------------------------------------------------------
# shifts and rotates
# ---------------------------------------------------------------------------------------------
emit("# ---- shifts/rotates ----")
for r, lo in [("C", 7), ("B", 8), ("A", 9)]:
    C("shl r%s, cnt" % r, "op=0x31; op_lo=%d & b7=0 & cnt & r%s" % (lo, r), "shl8(r%s, cnt:1);" % r)
C("shr rA, cnt", "op=0x31; op_lo=0xA & b7=0 & cnt & rA", "shr8(rA, cnt:1);")
C("sar rA, cnt", "op=0x31; op_lo=0xB & b7=0 & cnt & rA", "sar8(rA, cnt:1);")
C("shlw rBC, wcnt", "op=0x31; op_lo=0xC & wcnt & rBC", "shl16(rBC, wcnt:2);")
C("shlw rAX, wcnt", "op=0x31; op_lo=0xD & wcnt & rAX", "shl16(rAX, wcnt:2);")
C("shrw rAX, wcnt", "op=0x31; op_lo=0xE & wcnt & rAX", "shr16(rAX, wcnt:2);")
C("sarw rAX, wcnt", "op=0x31; op_lo=0xF & wcnt & rAX", "sar16(rAX, wcnt:2);")
C("ror rA, 1", "op=0x61; op=0xDB & rA", "CY = rA & 1; rA = (rA >> 1) | (rA << 7);")
C("rol rA, 1", "op=0x61; op=0xEB & rA", "CY = rA >> 7; rA = (rA << 1) | (rA >> 7);")
C("rorc rA, 1", "op=0x61; op=0xFB & rA", "local c:1 = CY; CY = rA & 1; rA = (rA >> 1) | (c << 7);")
C("rolc rA, 1", "op=0x61; op=0xDC & rA", "local c:1 = CY; CY = rA >> 7; rA = (rA << 1) | c;")
C("rolwc rAX, 1", "op=0x61; op=0xEE & rAX", "local c:2 = zext(CY); CY = rAX[15,1]; rAX = (rAX << 1) | c;")
C("rolwc rBC, 1", "op=0x61; op=0xFE & rBC", "local c:2 = zext(CY); CY = rBC[15,1]; rBC = (rBC << 1) | c;")
emit()

# ---------------------------------------------------------------------------------------------
# bit manipulation
# ---------------------------------------------------------------------------------------------
emit("# ---- bit manipulation ----")
BITOPS = [  # low nibble (0bit / 1bit forms), mnemonic, body (m = memory/register byte)
    (1, "mov1", "dst"), (2, "set1", None), (3, "clr1", None), (4, "mov1", "src"),
    (5, "and1", "and"), (6, "or1", "or"), (7, "xor1", "xor")]


def bitop(mn, kind, opnd, bit):
    if mn == "set1":
        return ("set1 %s^\".\"^%s" % (opnd, bit), "%s = %s | (1 << %s);" % (opnd, opnd, bit))
    if mn == "clr1":
        return ("clr1 %s^\".\"^%s" % (opnd, bit), "%s = %s & ~(1 << %s);" % (opnd, opnd, bit))
    if kind == "dst":
        return ("mov1 %s^\".\"^%s, CY" % (opnd, bit), "%s = (%s & ~(1 << %s)) | (CY << %s);" % (opnd, opnd, bit, bit))
    get = "((%s >> %s) & 1)" % (opnd, bit)
    if kind == "src":
        return ("mov1 CY, %s^\".\"^%s" % (opnd, bit), "CY = %s;" % get)
    o = {"and": "&", "or": "|", "xor": "^"}[kind]
    return ("%s CY, %s^\".\"^%s" % (mn, opnd, bit), "CY = CY %s %s;" % (o, get))


for lo, mn, kind in BITOPS:
    # saddr (0bit, lo), sfr (0bit, lo+8), [HL] (1bit, lo), A (1bit, lo+8)
    for opnd, b7, lo2, sep in [("saddr1", 0, lo, "; "), ("sfr1", 0, lo | 8, "; "), ("indHL1", 1, lo, " & "), ("rA", 1, lo | 8, " & ")]:
        text, body = bitop(mn, kind, opnd, "bitn")
        C(text, "op=0x71; b7=%d & op_lo=%d & bitn%s%s" % (b7, lo2, sep, opnd), body)
C('set1 abs1^"."^bitn', "op=0x71; b7=0 & op_lo=0 & bitn; abs1", "abs1 = abs1 | (1 << bitn);")
C('clr1 abs1^"."^bitn', "op=0x71; b7=0 & op_lo=8 & bitn; abs1", "abs1 = abs1 & ~(1 << bitn);")
C("ei", "op=0x71; op=0x7A; op=0xFA", "IE = 1;")
C("di", "op=0x71; op=0x7B; op=0xFA", "IE = 0;")
C("set1 CY", "op=0x71; op=0x80", "CY = 1;")
C("clr1 CY", "op=0x71; op=0x88", "CY = 0;")
C("not1 CY", "op=0x71; op=0xC0", "CY = CY ^ 1;")
emit()

# ---------------------------------------------------------------------------------------------
# branches, calls, returns
# ---------------------------------------------------------------------------------------------
emit("# ---- flow ----")
C("br jabs20", "op=0xEC; jabs20", "goto jabs20;")
C("br jabs16", "op=0xED; jabs16", "goto jabs16;")
C("br rel16", "op=0xEE; rel16", "goto rel16;")
C("br rel8", "op=0xEF; rel8", "goto rel8;")
C("br rAX", "op=0x61; op=0xCB & rAX", "local t:3 = (zext(CS & 0xF) << 16) | zext(rAX); goto [t];")
for name, code, cond in [("bc", 0xDC, "CY == 1"), ("bz", 0xDD, "Z == 1"), ("bnc", 0xDE, "CY == 0"), ("bnz", 0xDF, "Z == 0")]:
    C("%s rel8" % name, "op=0x%02X; rel8" % code, "if (%s) goto rel8;" % cond)
C("bh rel8", "op=0x61; op=0xC3; rel8", "if ((Z | CY) == 0) goto rel8;")
C("bnh rel8", "op=0x61; op=0xD3; rel8", "if ((Z | CY) == 1) goto rel8;")
for name, lo, test, clr in [("btclr", 0, "!= 0", True), ("bt", 2, "!= 0", False), ("bf", 4, "== 0", False)]:
    for opnd, b7, lo2, sep in [("saddr1", 0, lo, "; "), ("sfr1", 1, lo, "; "), ("rA", 0, lo + 1, " & "), ("indHL1", 1, lo + 1, " & ")]:
        body = "local m:1 = %s; if (((m >> bitn) & 1) %s) goto <no>; " % (opnd, "== 0" if test == "!= 0" else "!= 0")
        if clr:
            body += "%s = m & ~(1 << bitn); " % opnd
        body += "goto rel8; <no>"
        C('%s %s^"."^bitn, rel8' % (name, opnd), "op=0x31; b7=%d & op_lo=%d & bitn%s%s; rel8" % (b7, lo2, sep, opnd), body)
C("call jabs20", "op=0xFC; jabs20", "pushpc(inst_next); call jabs20;")
C("call jabs16", "op=0xFD; jabs16", "pushpc(inst_next); call jabs16;")
C("call rel16", "op=0xFE; rel16", "pushpc(inst_next); call rel16;")
C("call rp45", "op=0x61; op_lo=0xA & op_hi>=0xC & rp45", "local t:3 = (zext(CS & 0xF) << 16) | zext(rp45); pushpc(inst_next); call [t];")
emit('callt_t: "["^a^"]" is nnn & mm [ a = 0x80 + mm * 16 + nnn * 2; ] { export *[ram]:2 a; }')
C("callt callt_t", "op=0x61; b7=1 & b3=0 & op_lo>=4 & op_lo<8 & callt_t", "local t:3 = zext(callt_t); pushpc(inst_next); call [t];")
# BRK enters the handler at the vector in 0007E and returns with RETB: modelled as a userop
# that returns, so that an erased or not-yet-loaded vector does not become a call target.
C("brk", "op=0x61; op=0xCC", "brk();")
C("brk1", "op=0xFF", "brk1();")
C("ret", "op=0xD7", "local sa:3 = segment(NEARSEG, SP); local t:3 = *[ram]:3 sa; SP = SP + 4; return [t];")
C("reti", "op=0x61; op=0xFC", "local sa:3 = segment(NEARSEG, SP); local t:3 = *[ram]:3 sa; PSW = *[ram]:1 (sa + 3); SP = SP + 4; return [t];")
C("retb", "op=0x61; op=0xEC", "local sa:3 = segment(NEARSEG, SP); local t:3 = *[ram]:3 sa; PSW = *[ram]:1 (sa + 3); SP = SP + 4; return [t];")
emit()

# skips: set a context bit on the next instruction (see the wrappers in rl78.slaspec)
emit("# ---- conditional skips ----")
for name, code, v in [("skc", 0xC8, 1), ("sknc", 0xD8, 2), ("skz", 0xE8, 3), ("sknz", 0xF8, 4), ("skh", 0xE3, 5), ("sknh", 0xF3, 6)]:
    emit(":%s is phase=1 & op=0x61; op=0x%02X [ skip = %d; globalset(inst_next, skip); ] { }" % (name, code, v))
emit()

# stack
emit("# ---- stack ----")
C("push rp12", "op_hi=0xC & b3=0 & b0=1 & rp12", "SP = SP - 2; local sa:3 = segment(NEARSEG, SP); *[ram]:2 sa = rp12;")
C("pop rp12", "op_hi=0xC & b3=0 & b0=0 & rp12", "local sa:3 = segment(NEARSEG, SP); rp12 = *[ram]:2 sa; SP = SP + 2;")
C("push PSW", "op=0x61; op=0xDD", "SP = SP - 2; local sa:3 = segment(NEARSEG, SP); *[ram]:1 (sa + 1) = PSW; *[ram]:1 sa = 0;")
C("pop PSW", "op=0x61; op=0xCD", "local sa:3 = segment(NEARSEG, SP); PSW = *[ram]:1 (sa + 1); SP = SP + 2;")
emit()

# misc
emit("# ---- misc ----")
C("nop", "op=0x00", "")
C("mulu rX", "op=0xD6 & rX & rA & rAX", "rAX = zext(rA) * zext(rX);")
C("halt", "op=0x61; op=0xED", "halt();")
C("stop", "op=0x61; op=0xFD", "stop();")
for b in range(4):
    emit(":sel \"RB%d\" is phase=1 & op=0x61; op=0x%02X [ bank = %d; globalset(inst_next, bank); ] { RBS0 = %d; RBS1 = %d; }" % (b, 0xCF | (b << 4), b, b & 1, b >> 1))
emit()

# RL78-S3 multiply / divide / multiply-accumulate (CE FB xx, a "mov 0xffffb, #xx" on S1/S2)
emit("@ifdef RL78_S3")
C("mulhu", "op=0xCE; op=0xFB; op=0x01 & rAX & rBC & rBCAX", "rBCAX = zext(rAX) * zext(rBC);")
C("mulh", "op=0xCE; op=0xFB; op=0x02 & rAX & rBC & rBCAX", "rBCAX = sext(rAX) * sext(rBC);")
C("divhu", "op=0xCE; op=0xFB; op=0x03 & rAX & rDE",
  "local n:2 = rAX; local d:2 = rDE; if (d == 0) goto <z>; rAX = n / d; rDE = n % d; goto <e>; <z> rAX = 0xFFFF; rDE = n; <e>")
C("divwu", "op=0xCE; op=0xFB; (op=0x0B | op=0x04) & rBCAX & rHLDE",
  "local n:4 = rBCAX; local d:4 = rHLDE; if (d == 0) goto <z>; rBCAX = n / d; rHLDE = n % d; goto <e>; <z> rBCAX = 0xFFFFFFFF; rHLDE = n; <e>")
C("machu", "op=0xCE; op=0xFB; op=0x05 & rAX & rBC",
  "local o:4 = MACR; MACR = o + zext(rAX) * zext(rBC); CY = MACR < o; AC = 0;")
C("mach", "op=0xCE; op=0xFB; op=0x06 & rAX & rBC",
  "local o:4 = MACR; local p:4 = sext(rAX) * sext(rBC); MACR = o + p; CY = (o ^ MACR) s< 0; AC = MACR s< 0;")
emit("@endif")

with open(OUT, "w") as f:
    f.write("# Generated by tools/gen_rl78.py; do not edit.\n")
    f.write("\n".join(L) + "\n")
print("wrote", OUT, sum(1 for l in L if l.startswith(":")), "constructors")
