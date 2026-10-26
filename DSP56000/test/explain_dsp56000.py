"""Explanations for DSP56000 decode differences vs MAME unidasm -arch dsp56000 (used by
compare.py). Written from the DSP56000 Family Manual (A.10 encoding summary and the
per-instruction Opcode sections), independently of tools/gen_dsp56000.py:

- valid(word, ext) decides from the manual's encoding tables whether a word is a defined
  instruction. A record where Ghidra rejects a word that MAME decodes is explained only if the
  manual leaves the word undefined (reserved bits set, reserved register or mode codes);
  Ghidra accepting a word the manual leaves undefined is never explained.
- differences between two decodes are explained only by MAME bugs confirmed against the
  manual and the asl assembler (see README): each rule rewrites MAME's text into what MAME
  would print without the bug, and the record is explained if the result equals Ghidra's.
"""
import re

# ------------------------------------------------------------------ manual encoding tables
R5_OK = set(range(4, 32))                       # Table A-20: 00xxx reserved
R6_OK = set(range(4, 0x28)) | set(range(0x39, 0x40))   # Table A-21
RC5_OK = set(range(0, 8)) | set(range(0x19, 0x20))     # MOVEC: 00nnn Mn, 11001..11111
EA_REG = {0, 1, 2, 3, 4, 5, 7}                  # Table A-26 MMM (110 = abs/imm)


def ea_ok(f, allow_abs=True, allow_imm=False):
    mmm, rrr = f >> 3, f & 7
    if mmm in EA_REG:
        return True
    if mmm == 6 and rrr == 0:
        return allow_abs
    if mmm == 6 and rrr == 4:
        return allow_imm
    return False


def alu_ok(a):
    """data ALU opcode byte (A.10.4, Table A-29)"""
    if a & 0x80:
        return True                              # multiply: every QQQ d kkk is defined
    jjj, d, kkk = (a >> 4) & 7, (a >> 3) & 1, a & 7
    if jjj == 0:
        if kkk == 0:
            return d == 0                        # MOVE (00h); 08h reserved
        return kkk != 4
    if jjj == 1:
        return kkk != 5
    return True                                  # 010/011 (both k1 halves) and 1xx


def pmove_ok(w):
    """bits 23..8 as a parallel move (A.10.2); False if not a parallel-move class."""
    hb = w >> 16
    m = (w >> 8) & 0xffff
    W = (w >> 15) & 1
    ea6 = (w >> 8) & 0x3f
    if w & 0x800000:                             # X:Y
        return True
    if (w >> 22) == 1:                           # X:, Y:, L:
        d5 = ((w >> 17) & 0x18) | ((w >> 16) & 7)
        if (w >> 20) & 0xf == 4 and not (w >> 18) & 1:
            pass                                 # L: (LLL all defined)
        elif d5 not in R5_OK:
            return False
        if (w >> 14) & 1:
            if (w >> 20) & 0xf == 4 and not (w >> 18) & 1:
                return ea_ok(ea6, True, False)
            return ea_ok(ea6, True, bool(W) and not (w >> 19) & 1)
        return True
    if (w >> 21) == 1:                           # I, R, U, NOP
        if m == 0x2000:
            return True                          # no move
        if hb == 0x20 and (w >> 13) & 7 == 2:
            return True                          # U
        if hb & 0xfc == 0x20:                    # R
            s5, d5 = (w >> 13) & 0x1f, (w >> 8) & 0x1f
            return s5 in R5_OK and d5 in R5_OK
        return True                              # I: ddddd >= 00100
    if (w >> 20) == 1:                           # class I X:R / R:Y
        return ea_ok(ea6, True, bool(W))
    if (w >> 17) == 4 and not (w >> 14) & 1:     # class II
        return ea_ok(ea6, True, False)
    return False


CC_ANY = range(16)


def nonpar_ok(w, ext):
    hb, m, lo = w >> 16, (w >> 8) & 0xff, w & 0xff
    b = lambda i: (w >> i) & 1
    if hb == 0:
        if w in (0x000000, 0x000004, 0x000005, 0x000006, 0x00000c, 0x000084, 0x000086,
                 0x000087, 0x00008c, 0x000200):
            return True
        if w & 0xfffffe in (0x000008, 0x00000a):         # INC/DEC (DSP56002)
            return True
        if w & 0xfffff0 == 0x000300:                     # DEBUGcc
            return True
        if lo & 0xfc in (0xb8, 0xf8) and lo & 3 != 3:    # ANDI/ORI
            return True
        return False
    if hb == 0x01:
        if m == 0x80 and lo & 0xc7 == 0x40:              # DIV
            return True
        if m & 0xf8 == 0xd8 and lo & 0xf7 == 0x15:       # NORM
            return True
        if m & 0xe0 == 0 and lo & 0xc0 == 0xc0:          # MPY/MAC #n (DSP56002)
            return True
        return False
    if hb == 0x02:                                       # Tcc S1,D1
        return m & 0x0f == 0 and lo & 0x87 == 0 and ((lo >> 4) & 7) in (0, 4, 5, 6, 7)
    if hb == 0x03:                                       # Tcc S1,D1 S2,D2
        return m & 0x08 == 0 and lo & 0x80 == 0 and ((lo >> 4) & 7) in (0, 4, 5, 6, 7)
    if hb == 0x04:
        if m & 0xe0 == 0x40 and lo & 0xf0 == 0x10:       # LUA
            return True
        if m & 0x40 and lo & 0xe0 == 0xa0:               # MOVEC S1,D2 / S2,D1
            return (m & 0x3f) in R6_OK and (lo & 0x1f) in RC5_OK
        return False
    if hb == 0x05:                                       # MOVEC ea/aa/#xx
        if lo & 0xe0 == 0xa0:
            return (lo & 0x1f) in RC5_OK                 # #xx
        if lo & 0xa0 != 0x20 or (lo & 0x1f) not in RC5_OK:
            return False
        if m & 0x40:
            return ea_ok(m & 0x3f, True, bool(m & 0x80) and not lo & 0x40)
        return True
    if hb == 0x06:                                       # DO / REP
        if lo & 0xf0 in (0x80, 0xa0):
            return True                                  # #xxx
        if m & 0xc0 == 0xc0:
            return lo in (0x00, 0x20) and (m & 0x3f) in R6_OK
        if m & 0x80 == 0 and lo & 0xbf in (0x00, 0x20):
            return ea_ok(m & 0x3f, False, False) if m & 0x40 else True
        return False
    if hb == 0x07:                                       # MOVEM
        if m & 0x40:
            return lo & 0xc0 == 0x80 and (lo & 0x3f) in R6_OK and ea_ok(m & 0x3f, True, False)
        return lo & 0xc0 == 0 and (lo & 0x3f) in R6_OK
    if hb in (0x08, 0x09):                               # MOVEP (bit 14 = 1)
        if not m & 0x40:
            return False                                 # class II handled as a move
        if lo & 0x80:
            return ea_ok(m & 0x3f, True, bool(m & 0x80) and not lo & 0x40)
        if lo & 0xc0 == 0x40:
            return ea_ok(m & 0x3f, True, False)
        return (m & 0x3f) in R6_OK
    if hb in (0x0a, 0x0b):                               # bit ops, bit jumps, Jcc/JMP/JSR ea
        mode = m >> 6
        if mode == 3 and lo & 0x80:                      # JMP/JSR/Jcc/JScc ea
            return (lo == 0x80 or lo & 0xf0 == 0xa0) and ea_ok(m & 0x3f, True, False)
        if lo & 0x1f >= 24:
            return False                                 # bit number 11bbb reserved
        if mode == 3:                                    # register bit ops / jumps
            if (m & 0x3f) not in R6_OK:
                return False
            return lo & 0xc0 in (0x00, 0x40)
        if lo & 0x80:                                    # JCLR..JSSET memory
            return ea_ok(m & 0x3f, False, False) if mode == 1 else True
        return ea_ok(m & 0x3f, True, False) if mode == 1 else True
    if hb in (0x0c, 0x0d):                               # JMP/JSR xxx
        return m & 0xf0 == 0
    if hb in (0x0e, 0x0f):                               # Jcc/JScc xxx
        return True
    return False


def valid(w, ext=0):
    hb = w >> 16
    if hb >= 0x10 or (hb in (0x08, 0x09) and not (w >> 14) & 1):
        return pmove_ok(w) and alu_ok(w & 0xff)
    return nonpar_ok(w, ext)


# ------------------------------------------------------------------ MAME bugs
ACC_SRC = ("tfr", "addr", "cmp", "subr", "cmpm", "add", "addl", "sub", "subl")


def mame_fix(t, w):
    """MAME text normalizations that are not bugs: DO prints LA (the last loop word), the
    module prints the assembler's expr = LA + 1."""
    m = re.match(r"^do (.*),(\d+)$", t)
    if m:
        return "do %s,%d" % (m.group(1), (int(m.group(2)) + 1) & 0xffff)
    return t


XYMODE = ["(r%d)", "(r%d)+n%d", "(r%d)-", "(r%d)+"]


def xy_y_manual(w):
    mm = (w >> 20) & 3
    rr = (w >> 13) & 3
    bank = (w >> 10) & 1
    r = (0 if bank else 4) + rr
    return XYMODE[mm].replace("%d", str(r))


def xy_y_mame(w):
    MM = (w >> 11) & 3
    r = ((w >> 8) & 7) ^ 4
    return XYMODE[MM].replace("%d", str(r))


def fixes(w, nm):
    """yield (reason, MAME text with that bug corrected) candidates"""
    out = []
    t = nm
    # 1. accumulator source omitted in the two-operand ALU forms with S = the other accumulator
    a = w & 0xff
    if w >= 0x100000 or (w >> 17) == 4:
        if not a & 0x80 and (a >> 4) & 7 in (0, 1) and a & 7 in (1, 2, 5, 6, 7, 0, 4) and a != 0:
            mn = t.split(" ")[0]
            if mn in ACC_SRC:
                d = "b" if a & 8 else "a"
                s = "a" if a & 8 else "b"
                t2 = re.sub(r"^%s %s\b" % (mn, d), "%s %s,%s" % (mn, s, d), t)
                if t2 != t:
                    t = t2
                    out.append("MAME omits the accumulator source of %s" % mn.upper())
    # 2. XY moves: MAME takes the Y address mode and register from the X fields
    if w & 0x800000:
        ym, yg = xy_y_mame(w), xy_y_manual(w)
        if ym != yg and ("y:" + ym) in t:
            t = t.replace("y:" + ym, "y:" + yg)
            out.append("MAME XY move: Y mode/register taken from the X fields (MM, RRR)")
    return t, out


TCC_S = {0: None, 4: "x0", 5: "y0", 6: "x1", 7: "y1"}


def tcc_manual(w):
    """Tcc S1,D1 from the manual's JJJD table"""
    j, d = (w >> 4) & 7, (w >> 3) & 1
    dst = "b" if d else "a"
    src = TCC_S.get(j, "?")
    if src is None:
        src = "a" if d else "b"
    return "%s,%s" % (src, dst)


def explain(w, nm, ng, mi, gi, mn, gn, ext=None):
    hb = w >> 16
    # Tcc: MAME's S1,D1 register table does not follow the manual (asl agrees with the manual)
    if hb in (2, 3) and valid(w) and not gi:
        m = re.match(r"^(t[a-z][a-z]) ([a-z0-9]+,[a-z0-9]+)( .*)?$", ng)
        if m and m.group(2) == tcc_manual(w):
            rest = (m.group(3) or "").strip()
            mm = re.match(r"^(t[a-z][a-z]) (\S+)( (r\d,r\d))?$", nm)
            if mm and mm.group(1) == m.group(1) and (mm.group(4) or "") == rest:
                return "MAME Tcc: S1,D1 register table differs from the manual"
    # DEBUG / DEBUGcc (DSP56002): MAME decodes 0000xx words ignoring bits 15..8
    if hb == 0 and not gi and (w == 0x000200 or w & 0xfffff0 == 0x000300):
        return "DSP56002 instruction (INC/DEC/DEBUG/DEBUGcc/MPY-MAC #n) MAME lacks"

    if gi and not mi:
        if not valid(w):
            return "MAME decodes an encoding the manual leaves undefined"
        return None
    if mi and not gi:
        hb = w >> 16
        if w in (0x000200,) or w & 0xfffffe in (0x000008, 0x00000a) or w & 0xfffff0 == 0x000300 \
                or (hb == 0x01 and (w >> 13) & 7 == 0 and w & 0xc0 == 0xc0):
            return "DSP56002 instruction (INC/DEC/DEBUG/DEBUGcc/MPY-MAC #n) MAME lacks"
        return None
    t, reasons = fixes(w, nm)
    # MOVEC #xxxx,D1 (long immediate): MAME prints the low 16 bits of the extension word
    if w >> 16 == 0x05 and w & 0xff00 == 0xf400 and ext is not None and mn == gn == 2:
        cand = t.replace("#%d," % (ext & 0xffff), "#%d," % ext, 1)
        if cand == ng:
            return "MAME prints the MOVEC long immediate as 16 bits (formatting)"
    # absolute address (MMMRRR = 110000) in MOVEP P:, bit operations, REP/DO and class I/II
    # moves: MAME prints >$0 and does not consume the extension word
    if mn == 1 and gn == 2 and ext is not None:
        a16 = ext & 0xffff
        cand = t.replace(":0 ", ":%d " % a16).replace(":0,", ":%d," % a16)
        if cand.endswith(":0"):
            cand = cand[:-2] + ":%d" % a16
        if cand == ng:
            return " + ".join(reasons + ["MAME ignores the absolute-address extension word"])
    # MOVEP X/Y:ea and register forms: MAME takes the peripheral address from the ea/register
    # field (bits 13..8) instead of bits 5..0 (asl and the manual agree on bits 5..0)
    if hb in (8, 9) and (w >> 14) & 1 and (w >> 6) & 3 != 1:
        sp = "y" if w & 0x10000 else "x"
        wrong = "%s:%d" % (sp, 0xffc0 + ((w >> 8) & 0x3f))
        right = "%s:%d" % (sp, 0xffc0 + (w & 0x3f))
        cand = t.replace(wrong, right)
        if mn == 1 and gn == 2 and ext is not None:
            cand = cand.replace(":0 ", ":%d " % (ext & 0xffff)).replace(":0,", ":%d," % (ext & 0xffff))
        if cand == ng and (mn == gn or gn == 2):
            return "MAME MOVEP: peripheral address taken from bits 13..8"
    # MOVEP P:ea <-> pp: MAME prints y:<<$ffc0 for the peripheral (space bit 16, pp bits 5..0)
    if hb in (8, 9) and (w >> 6) & 3 == 1 and (w >> 14) & 1:
        pp = "%s:%d" % ("y" if w & 0x10000 else "x", 0xffc0 + (w & 0x3f))
        cand = t.replace("y:%d" % (0xffc0 + ((w >> 8) & 0x3f)), pp)
        if cand == ng and mn == gn:
            return "MAME MOVEP P:ea: peripheral space and address not taken from bits 16 and 5..0"
    if t == ng and mn == gn:
        return " + ".join(reasons) if reasons else None
    return None
