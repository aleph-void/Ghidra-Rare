"""Minimal ADSP-218x instruction encoder for the tests, from the User's Manual Appendix A.
Every helper returns one 24-bit word.  Register and code tables follow Appendix A."""

DREG = "AX0 AX1 MX0 MX1 AY0 AY1 MY0 MY1 SI SE AR MR0 MR1 MR2 SR0 SR1".split()
REGS = [DREG,
        "I0 I1 I2 I3 M0 M1 M2 M3 L0 L1 L2 L3 - - PMOVLAY DMOVLAY".split(),
        "I4 I5 I6 I7 M4 M5 M6 M7 L4 L5 L6 L7 - - - -".split(),
        "ASTAT MSTAT SSTAT IMASK ICNTL CNTR SB PX RX0 TX0 RX1 TX1 IFC OWRCNTR - TOPPCSTACK".split()]
COND = {c: i for i, c in enumerate(
    "EQ NE GT LE LT GE AV NOTAV AC NOTAC NEG POS MV NOTMV NOTCE ALWAYS".split())}
TERM = {c: i for i, c in enumerate(
    "NE EQ LE GT GE LT NOTAV AV NOTAC AC POS NEG NOTMV MV CE FOREVER".split())}
XA = "AX0 AX1 AR MR0 MR1 MR2 SR0 SR1".split()
XM = "MX0 MX1 AR MR0 MR1 MR2 SR0 SR1".split()
XS = "SI - AR MR0 MR1 MR2 SR0 SR1".split()
YA = "AY0 AY1 AF 0".split()
YM = "MY0 MY1 MF 0".split()
# AMF codes
ALU = {"Y": 0x10, "Y+1": 0x11, "X+Y+C": 0x12, "X+Y": 0x13, "NOTY": 0x14, "-Y": 0x15,
       "X-Y+C-1": 0x16, "X-Y": 0x17, "Y-1": 0x18, "Y-X": 0x19, "Y-X+C-1": 0x1a, "NOTX": 0x1b,
       "AND": 0x1c, "OR": 0x1d, "XOR": 0x1e, "ABS": 0x1f}
MAC = {"RND": 1, "MR+RND": 2, "MR-RND": 3, "SS": 4, "SU": 5, "US": 6, "UU": 7,
       "MR+SS": 8, "MR+SU": 9, "MR+US": 10, "MR+UU": 11, "MR-SS": 12, "MR-SU": 13,
       "MR-US": 14, "MR-UU": 15}
SF = {"LSHIFT HI": 0, "LSHIFT HI OR": 1, "LSHIFT LO": 2, "LSHIFT LO OR": 3,
      "ASHIFT HI": 4, "ASHIFT HI OR": 5, "ASHIFT LO": 6, "ASHIFT LO OR": 7,
      "NORM HI": 8, "NORM HI OR": 9, "NORM LO": 10, "NORM LO OR": 11,
      "EXP HI": 12, "EXP HIX": 13, "EXP LO": 14, "EXPADJ": 15}


def reg(name):
    for g, names in enumerate(REGS):
        if name in names:
            return g, names.index(name)
    raise KeyError(name)


def d(name):
    return DREG.index(name)


def alu(op, x="AX0", y="AY0"):
    """(amf, yop, xop) for an ALU operation"""
    return ALU[op], YA.index(y), XA.index(x)


def mac(op, x="MX0", y="MY0"):
    return MAC[op], YM.index(y), XM.index(x)


def const_fields(k):
    """(yy, cc, bo) for a type 9 constant (Appendix A table)"""
    for bit in range(16):
        if k == 1 << bit:
            return bit >> 2, bit & 3, 1
        if k == (~(1 << bit)) & 0xffff:
            return bit >> 2, bit & 3, 3
    raise ValueError(hex(k))


# --- instruction types ---
def t1(comp, dd, pd, dmi, dmm, pmi, pmm):
    amf, y, x = comp if comp else (0, 0, 0)
    return (3 << 22) | (["AY0", "AY1", "MY0", "MY1"].index(pd) << 20) | \
        (["AX0", "AX1", "MX0", "MX1"].index(dd) << 18) | (amf << 13) | (y << 11) | (x << 8) | \
        ((pmi - 4) << 6) | ((pmm - 4) << 4) | (dmi << 2) | dmm


def t2(i, m, data):
    g = i >> 2
    return (5 << 21) | (g << 20) | ((data & 0xffff) << 4) | ((i & 3) << 2) | (m & 3)


def t3(name, addr, write=False):
    g, r = reg(name)
    return (4 << 21) | (int(write) << 20) | (g << 18) | (addr << 4) | r


def t4(comp, z, dreg, i, m, write=False):
    amf, y, x = comp if comp else (0, 0, 0)
    return (3 << 21) | ((i >> 2) << 20) | (int(write) << 19) | (z << 18) | (amf << 13) | \
        (y << 11) | (x << 8) | (d(dreg) << 4) | ((i & 3) << 2) | (m & 3)


def t5(comp, z, dreg, i, m, write=False):
    amf, y, x = comp if comp else (0, 0, 0)
    return (5 << 20) | (int(write) << 19) | (z << 18) | (amf << 13) | (y << 11) | (x << 8) | \
        (d(dreg) << 4) | ((i & 3) << 2) | (m & 3)


def t6(dreg, data):
    return (4 << 20) | ((data & 0xffff) << 4) | d(dreg)


def t7(name, data):
    g, r = reg(name)
    return (3 << 20) | (g << 18) | ((data & 0x3fff) << 4) | r


def t8(comp, z, dst, src):
    amf, y, x = comp if comp else (0, 0, 0)
    return (5 << 19) | (z << 18) | (amf << 13) | (y << 11) | (x << 8) | (d(dst) << 4) | d(src)


def t9(comp, z=0, cond="ALWAYS", const=None, square=False):
    amf, y, x = comp
    b74 = 0
    if const is not None:
        y, cc, bo = const_fields(const)
        b74 = (cc << 2) | bo
    if square:
        b74, y = 1, 0
    return (4 << 19) | (z << 18) | (amf << 13) | (y << 11) | (x << 8) | (b74 << 4) | COND[cond]


def t10(addr, cond="ALWAYS", call=False):
    return (3 << 19) | (int(call) << 18) | (addr << 4) | COND[cond]


def t11(addr, term):
    return (5 << 18) | (addr << 4) | TERM[term]


def t12(sf, x, dreg, i, m, write=False):
    return (9 << 17) | ((i >> 2) << 16) | (int(write) << 15) | (SF[sf] << 11) | \
        (XS.index(x) << 8) | (d(dreg) << 4) | ((i & 3) << 2) | (m & 3)


def t14(sf, x, dst, src):
    return (0x20 << 15) | (SF[sf] << 11) | (XS.index(x) << 8) | (d(dst) << 4) | d(src)


def t15(sf, x, exp):
    return (0x1e << 15) | (SF[sf] << 11) | (XS.index(x) << 8) | (exp & 0xff)


def t16(sf, x, cond="ALWAYS"):
    return (0x1c << 15) | (SF[sf] << 11) | (XS.index(x) << 8) | COND[cond]


def t17(dst, src):
    gd, rd = reg(dst)
    gs, rs = reg(src)
    return (0x0d << 16) | (gd << 10) | (gs << 8) | (rd << 4) | rs


def t18(**modes):
    """modes: name=True (ENA) / False (DIS); names TI MM AS OL BR SR GM"""
    pos = {"TI": 14, "MM": 12, "AS": 10, "OL": 8, "BR": 6, "SR": 4, "GM": 2}
    w = 0x0c << 16
    for k, v in modes.items():
        w |= (3 if v else 2) << pos[k]
    return w


def t19(i, cond="ALWAYS", call=False):
    return (0x0b << 16) | ((i - 4) << 6) | (int(call) << 4) | COND[cond]


def t20(rti=False, cond="ALWAYS"):
    return (0x0a << 16) | (int(rti) << 4) | COND[cond]


def t21(i, m):
    return (0x09 << 16) | ((i >> 2) << 4) | ((i & 3) << 2) | (m & 3)


def t23(x):
    return 0x071000 | (XA.index(x) << 8)


def t24(y, x):
    return 0x060000 | (YA.index(y) << 11) | (XA.index(x) << 8)


SATMR = 0x050000


def t26(pp=0, lp=0, cp=0, spp=0):
    return 0x040000 | (pp << 4) | (lp << 3) | (cp << 2) | spp


ENA_INTS, DIS_INTS = 0x040060, 0x040020


def t27(addr, flag_in=True, call=False):
    return 0x030000 | ((addr & 0xfff) << 4) | ((addr >> 12) << 2) | (int(flag_in) << 1) | int(call)


def t28(cond="ALWAYS", fo=0, fl0=0, fl1=0, fl2=0):
    """flag codes: 1 toggle, 2 reset, 3 set"""
    return 0x020000 | (fl2 << 10) | (fl1 << 8) | (fl0 << 6) | (fo << 4) | COND[cond]


def t29(dreg, addr, write=False):
    return 0x010000 | (int(write) << 15) | (addr << 4) | d(dreg)


NOP = 0
IDLE = 0x028000
