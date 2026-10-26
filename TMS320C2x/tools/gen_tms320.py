#!/usr/bin/env python3
"""SLEIGH generator for the TI TMS320C2x (TMS32020/C25/C26) and TMS320C5x (C50/C51/C53) DSPs.

    gen_tms320.py <data/languages dir>

Writes tms320c2x.sinc and tms320c5x.sinc (one per family) and the four .slaspec wrappers
(big- and little-endian word order for each family). Encodings and semantics come from the
TMS320C2x User's Guide (SPRU014C) and the TMS320C5x User's Guide (SPRU056D); MAME unidasm was
used only as a black-box decode reference. The two families share the operand machinery
(direct/indirect addressing, ARP/DP tracking, repeat wrappers) and differ in their opcode tables:
the C5x re-encodes the C2x instruction set, so it is a superset in function, not in encoding.

Context tracking (flowing context registers, settable by the user):
  arp_k/arp_v  current auxiliary register pointer (known flag, value); the root constructor copies
               them to arpkc/arpvc so that an instruction can use the old ARP while setting the next
  dp_k/dp_v    data page pointer (direct addresses become absolute data references when known)
  sxm_k/sxm_v, ovm_k/ovm_v, pm_k/pm_v  sign-extension mode, overflow mode, product shift mode
  ndx, trm     (C5x) PMST.NDX and PMST.TRM; 0 (reset) = C2x-compatible AR0 indexing and TREG copies
Unknown values fall back to run-time p-code on ARP, DP, SXM, OVM and PM.
"""
import os
import re
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "."

# --------------------------------------------------------------------------------------------
# Instruction tables. Pattern letters (16 chars, MSB first):
#   0/1 fixed bit     M  data-memory operand byte (direct dma or indirect {ind} [,ARn])
#   P  page-0 data operand byte (SST: direct form forced to page 0)
#   Q  memory-mapped-register operand byte (C5x LAMM/SAMM/LMMR/SMMR)
#   B  branch AR-modify byte (bits 6-0; bit 7 must be 1 in the pattern)
#   N  NORM indirect byte (bits 6-0 for C5x, bits 6-4 for C2x)
#   s  4-bit shift   x 3-bit shift   r AR number   k immediate   b bit code   p port
#   m  2-bit mode    f 1-bit flag    c condition (C5x TP+ZLVC, 10 bits)   n XC word count
# Second word: "w" = 16-bit immediate / address.
# Each entry: (display, pattern, second word?, semantics, context-action)
# Display placeholders: {M} {s} {x} {r} {k} {b} {p} {m} {f} {c} {w} {lk} {pma} {B} {N} {n}
# --------------------------------------------------------------------------------------------


class Ins:
    def __init__(self, disp, pat, sem, w2=None, ctx="", delay=0):
        self.disp, self.pat, self.sem, self.w2, self.ctx, self.delay = disp, pat.replace(" ", ""), sem, w2, ctx, delay
        assert len(self.pat) == 16, (disp, pat)


# ---- p-code helpers (generated inline: SLEIGH macros cannot hold labels) ----

class Gen:
    def __init__(self):
        self.n = 0

    def u(self):
        self.n += 1
        return self.n


# Mode bits (SXM, OVM, PM) known from the context generate straight-line p-code; constructors are
# emitted once per known value plus once for "unknown", which tests the status register at run
# time. MODE holds the variant being generated; USED records which modes a semantics consults.
MODE = {"sxm": None, "ovm": None, "pm": None, "circ": None}
USED = set()


def sxsel(g, if1, if0):
    """p-code for SXM = 1 / SXM = 0."""
    USED.add("sxm")
    v = MODE["sxm"]
    if v == 1:
        return if1
    if v == 0:
        return if0
    n = g.u()
    return f"if (SXM == 0) goto <sz{n}>;\n{if1}goto <sd{n}>;\n<sz{n}>\n{if0}<sd{n}>\n"


def circ_check(n, nv="nv", old="t"):
    """C5x circular buffers (SPRU056D 5.6): if the AR equals CBERk of an enabled buffer k that
    points at this AR, any modification loads CBSRk instead of the new value."""
    return (f"if (!(((CBCR & 8) != 0) && ((CBCR & 7) == arnum) && ({old} == CBER1))) goto <c2{n}>;\n"
            f"{nv} = CBSR1;\ngoto <cd{n}>;\n<c2{n}>\n"
            f"if (!(((CBCR & 0x80) != 0) && (((CBCR >> 4) & 7) == arnum) && ({old} == CBER2))) goto <cd{n}>;\n"
            f"{nv} = CBSR2;\n<cd{n}>\n")


def ar_add(g, expr):
    """arcur = expr (in terms of the current value 'arcur'), with C5x circular buffers when the
    circ context bit is set."""
    USED.add("circ")
    if MODE["circ"] != 1:
        return f"arcur = {expr};\n"
    n = g.u()
    return f"local _o{n}:2 = arcur;\nlocal _n{n}:2 = {expr};\n" + circ_check(n, f"_n{n}", f"_o{n}") + \
        f"arcur = _n{n};\n"


def ext16(g, dst, src):
    """dst:4 = src:2 extended per SXM."""
    USED.add("sxm")
    v = MODE["sxm"]
    if v == 1:
        return f"local {dst}:4 = sext({src});\n"
    if v == 0:
        return f"local {dst}:4 = zext({src});\n"
    n = g.u()
    return (f"local {dst}:4 = zext({src});\n"
            f"if (SXM == 0) goto <sx{n}>;\n"
            f"{dst} = sext({src});\n"
            f"<sx{n}>\n")


def sat(g, o, a):
    USED.add("ovm")
    v = MODE["ovm"]
    if v == 0:
        return ""
    n = g.u()
    cond = f"{o} == 0" if v == 1 else f"{o} == 0 || OVM == 0"
    return (f"if ({cond}) goto <ns{n}>;\n"
            f"ACC = 0x7fffffff + zext({a} s< 0);\n"
            f"<ns{n}>\n")


def acc_add(g, val, cmode="full", satok=True):
    """ACC += val:4 ; C per cmode (full/set/none); OV latched; OVM saturation."""
    n = g.u()
    a, b, o = f"_a{n}", f"_b{n}", f"_o{n}"
    s = f"local {a}:4 = ACC;\nlocal {b}:4 = {val};\n"
    if cmode == "full":
        s += f"C = carry({a}, {b});\n"
    elif cmode == "set":
        s += f"C = C | carry({a}, {b});\n"
    s += f"local {o}:1 = scarry({a}, {b});\nOV = OV | {o};\nACC = {a} + {b};\n"
    if satok:
        s += sat(g, o, a)
    return s


def acc_sub(g, val, cmode="full", satok=True):
    n = g.u()
    a, b, o = f"_a{n}", f"_b{n}", f"_o{n}"
    s = f"local {a}:4 = ACC;\nlocal {b}:4 = {val};\n"
    if cmode == "full":
        s += f"C = {b} <= {a};\n"
    elif cmode == "reset":
        s += f"C = C & ({b} <= {a});\n"
    s += f"local {o}:1 = sborrow({a}, {b});\nOV = OV | {o};\nACC = {a} - {b};\n"
    if satok:
        s += sat(g, o, a)
    return s


def acc_addc(g, val):
    n = g.u()
    a, b, o, uu, ss = f"_a{n}", f"_b{n}", f"_o{n}", f"_u{n}", f"_s{n}"
    return (f"local {a}:4 = ACC;\nlocal {b}:4 = {val};\n"
            f"local {uu}:8 = zext({a}) + zext({b}) + zext(C);\n"
            f"local {ss}:8 = sext({a}) + sext({b}) + zext(C);\n"
            f"C = ({uu} >> 32) != 0;\nACC = {uu}:4;\n"
            f"local {o}:1 = {ss} != sext(ACC);\nOV = OV | {o};\n" + sat(g, o, a))


def acc_subb(g, val):
    n = g.u()
    a, b, o, uu, ss = f"_a{n}", f"_b{n}", f"_o{n}", f"_u{n}", f"_s{n}"
    return (f"local {a}:4 = ACC;\nlocal {b}:4 = {val};\n"
            f"local {uu}:8 = zext({a}) - zext({b}) - zext(C == 0);\n"
            f"local {ss}:8 = sext({a}) - sext({b}) - zext(C == 0);\n"
            f"C = ({uu} >> 32) == 0;\nACC = {uu}:4;\n"
            f"local {o}:1 = {ss} != sext(ACC);\nOV = OV | {o};\n" + sat(g, o, a))


def pshift(g, dst):
    """dst:4 = PREG through the product shifter (PM)."""
    USED.add("pm")
    v = MODE["pm"]
    if v is not None:
        return f"local {dst}:4 = " + ["PREG", "PREG << 1", "PREG << 4", "PREG s>> 6"][v] + ";\n"
    n = g.u()
    return (f"local {dst}:4 = PREG;\n"
            f"if (PM == 0) goto <ps{n}>;\n{dst} = PREG << 1;\n"
            f"if (PM == 1) goto <ps{n}>;\n{dst} = PREG << 4;\n"
            f"if (PM == 2) goto <ps{n}>;\n{dst} = PREG s>> 6;\n<ps{n}>\n")


def push(fam, v):
    return ("STK7 = STK6; STK6 = STK5; STK5 = STK4; STK4 = STK3; STK3 = STK2; STK2 = STK1; "
            f"STK1 = STK0; STK0 = {v};\n")


POP = ("STK0 = STK1; STK1 = STK2; STK2 = STK3; STK3 = STK4; STK4 = STK5; STK5 = STK6; "
       "STK6 = STK7;\n")


def ctx_set(**kv):
    s = ""
    for k, v in kv.items():
        s += f"{k}={v}; globalset(inst_next, {k}); "
    return s


# ---------------------------------------------------------------- C2x table
def c2x_table():
    g = Gen()
    T = []
    A = T.append

    def mem_op(name, code, op8, kind="M", ctx=""):
        A(Ins(name + " {M}{nx}", op8 + kind * 8, code, ctx=ctx))

    # accumulator memory reference
    A(Ins("ADD {M},{s}{nx}", "0000 ssss MMMMMMMM",
          lambda: ext16(g, "_v", "{M}") + acc_add(g, "_v << {s}")))
    A(Ins("SUB {M},{s}{nx}", "0001 ssss MMMMMMMM",
          lambda: ext16(g, "_v", "{M}") + acc_sub(g, "_v << {s}")))
    A(Ins("LAC {M},{s}{nx}", "0010 ssss MMMMMMMM",
          lambda: ext16(g, "_v", "{M}") + "ACC = _v << {s};\n"))
    A(Ins("LAR {r},{M}{nx}", "0011 0rrr MMMMMMMM", lambda: "{r} = {M};\n"))
    mem_op("MPY", lambda: "PREG = sext(TREG) * sext({M});\n", "00111000")
    mem_op("SQRA", lambda: pshift(g, "_p") + acc_add(g, "_p") +
           "TREG = {M};\nPREG = sext(TREG) * sext(TREG);\n", "00111001")
    mem_op("MPYA", lambda: pshift(g, "_p") + acc_add(g, "_p") +
           "PREG = sext(TREG) * sext({M});\n", "00111010")
    mem_op("MPYS", lambda: pshift(g, "_p") + acc_sub(g, "_p") +
           "PREG = sext(TREG) * sext({M});\n", "00111011")
    mem_op("LT", lambda: "TREG = {M};\n", "00111100")
    mem_op("LTA", lambda: "TREG = {M};\n" + pshift(g, "_p") + acc_add(g, "_p"), "00111101")
    mem_op("LTP", lambda: "TREG = {M};\n" + pshift(g, "_p") + "ACC = _p;\n", "00111110")
    mem_op("LTD", lambda: "local _a:2 = {M};\nlocal _d:2 = *[data]:2 _a;\nTREG = _d;\n"
           "*[data]:2 (_a + 1) = _d;\n" + pshift(g, "_p") + acc_add(g, "_p"), "00111111", kind="A")
    mem_op("ZALH", lambda: "ACC = zext({M}) << 16;\n", "01000000")
    mem_op("ZALS", lambda: "ACC = zext({M});\n", "01000001")
    mem_op("LACT", lambda: ext16(g, "_v", "{M}") + "ACC = _v << (TREG & 0xf);\n", "01000010")
    mem_op("ADDC", lambda: acc_addc(g, "zext({M})"), "01000011")
    mem_op("SUBH", lambda: acc_sub(g, "zext({M}) << 16", "reset"), "01000100")
    mem_op("SUBS", lambda: acc_sub(g, "zext({M})"), "01000101")
    mem_op("SUBT", lambda: ext16(g, "_v", "{M}") + acc_sub(g, "_v << (TREG & 0xf)"), "01000110")
    mem_op("SUBC", lambda: subc(g), "01000111")
    mem_op("ADDH", lambda: acc_add(g, "zext({M}) << 16", "set"), "01001000")
    mem_op("ADDS", lambda: acc_add(g, "zext({M})"), "01001001")
    mem_op("ADDT", lambda: ext16(g, "_v", "{M}") + acc_add(g, "_v << (TREG & 0xf)"), "01001010")
    mem_op("RPT", lambda: "RPTC = {M} & 0xff;\n", "01001011", ctx=ctx_set(rpt=1))
    mem_op("XOR", lambda: "ACCL = ACCL ^ {M};\n", "01001100")
    mem_op("OR", lambda: "ACCL = ACCL | {M};\n", "01001101")
    mem_op("AND", lambda: "ACC = zext(ACCL & {M});\n", "01001110")
    mem_op("SUBB", lambda: acc_subb(g, "zext({M})"), "01001111")
    mem_op("LST", lambda: "local _s:2 = {M};\nARP = _s(1) >> 5;\nOV = _s[12,1];\n"
           "OVM = _s[11,1];\nDP = _s & 0x1ff;\n", "01010000",
           ctx=ctx_set(arp_k=0, dp_k=0, ovm_k=0))
    mem_op("LST1", lambda: "local _s:2 = {M};\nARB = _s(1) >> 5;\nARP = ARB;\n"
           "CNF = _s[12,1];\nTC = _s[11,1];\nSXM = _s[10,1];\n"
           "C = _s[9,1];\nHM = _s[6,1];\nFSM = _s[5,1];\nXF = _s[4,1];\n"
           "FO = _s[3,1];\nTXM = _s[2,1];\nPM = _s:1 & 3;\n", "01010001",
           ctx=ctx_set(arp_k=0, sxm_k=0, pm_k=0))
    mem_op("LDP", lambda: "DP = {M} & 0x1ff;\n", "01010010", ctx=ctx_set(dp_k=0))
    mem_op("LPH", lambda: "PH = {M};\n", "01010011")
    mem_op("PSHD", lambda: push("c2x", "{M}"), "01010100")
    # MAR (0x55): direct form is a NOP; *,ARn alone is LARP
    A(Ins("NOP", "0101 0101 0000 0000", lambda: ""))
    A(Ins("MAR {M}", "0101 0101 0MMMMMMM", lambda: "", ))  # direct, nonzero dma (NOP)
    A(Ins("LARP {lp}", "0101 0101 1000 1ppp", lambda: "ARB = ARP;\nARP = {lp};\n",
          ctx="arp_k=1; arp_v={lp}; globalset(inst_next, arp_k); globalset(inst_next, arp_v);"))
    A(Ins("MAR {M}{nx}", "0101 0101 1MMMMMMM", lambda: "build {M};\n"))
    mem_op("DMOV", lambda: "local _a:2 = {M};\n*[data]:2 (_a + 1) = *[data]:2 _a;\n", "01010110", kind="A")
    mem_op("BITT", lambda: "TC = (({M} >> (15 - (TREG & 0xf))) & 1) != 0;\n", "01010111")
    mem_op("TBLR", lambda: "{M} = *[prog]:2 (ACCL + rpti);\n", "01011000")
    mem_op("TBLW", lambda: "*[prog]:2 (ACCL + rpti) = {M};\n", "01011001")
    mem_op("SQRS", lambda: pshift(g, "_p") + acc_sub(g, "_p") +
           "TREG = {M};\nPREG = sext(TREG) * sext(TREG);\n", "01011010")
    mem_op("LTS", lambda: "TREG = {M};\n" + pshift(g, "_p") + acc_sub(g, "_p"), "01011011")
    A(Ins("MACD {pma},{M}{nx}", "0101 1100 AAAAAAAA",
          lambda: pshift(g, "_p") + acc_add(g, "_p") + "local _a:2 = {M};\nTREG = *[data]:2 _a;\n"
          "PREG = sext(TREG) * sext(*[prog]:2 ({w} + rpti));\n*[data]:2 (_a + 1) = TREG;\n",
          w2="w"))
    A(Ins("MAC {pma},{M}{nx}", "0101 1101 MMMMMMMM",
          lambda: pshift(g, "_p") + acc_add(g, "_p") + "TREG = {M};\n"
          "PREG = sext(TREG) * sext(*[prog]:2 ({w} + rpti));\n", w2="w"))
    A(Ins("BC {pma}{B}", "0101 1110 1BBBBBBB", lambda: "build {B};\nif (C != 0) goto {pma};\n", w2="a"))
    A(Ins("BNC {pma}{B}", "0101 1111 1BBBBBBB", lambda: "build {B};\nif (C == 0) goto {pma};\n", w2="a"))
    A(Ins("SACL {M},{x}{nx}", "0110 0xxx MMMMMMMM", lambda: "local _t:4 = ACC << {x};\n{M} = _t:2;\n"))
    A(Ins("SACH {M},{x}{nx}", "0110 1xxx MMMMMMMM", lambda: "local _t:4 = ACC << {x};\n{M} = _t(2);\n"))
    A(Ins("SAR {r},{M}{nx}", "0111 0rrr MMMMMMMM", lambda: "local _t:2 = {r};\nbuild {M};\n{M} = _t;\n"))
    mem_op("SST", lambda: "{M} = (zext(ARP) << 13) | (zext(OV) << 12) | (zext(OVM) << 11) | 0x400 | "
           "(zext(INTM) << 9) | DP;\n", "01111000", kind="P")
    mem_op("SST1", lambda: "{M} = (zext(ARB) << 13) | (zext(CNF) << 12) | (zext(TC) << 11) | "
           "(zext(SXM) << 10) | (zext(C) << 9) | 0x180 | (zext(HM) << 6) | (zext(FSM) << 5) | "
           "(zext(XF) << 4) | (zext(FO) << 3) | (zext(TXM) << 2) | zext(PM);\n", "01111001", kind="P")
    mem_op("POPD", lambda: "{M} = STK0;\n" + POP, "01111010")
    mem_op("ZALR", lambda: "ACC = (zext({M}) << 16) | 0x8000;\n", "01111011")
    mem_op("SPL", lambda: pshift(g, "_p") + "{M} = _p:2;\n", "01111100")
    mem_op("SPH", lambda: pshift(g, "_p") + "{M} = _p(2);\n", "01111101")
    A(Ins("ADRK {k}", "0111 1110 kkkkkkkk", lambda: "arcur = arcur + {k};\n"))
    A(Ins("SBRK {k}", "0111 1111 kkkkkkkk", lambda: "arcur = arcur - {k};\n"))
    A(Ins("IN {M},{pa}{nx}", "1000 pppp MMMMMMMM", lambda: "{M} = {pa};\n"))
    A(Ins("BIT {M},{b}{nx}", "1001 bbbb MMMMMMMM", lambda: "TC = (({M} >> (15 - {b})) & 1) != 0;\n"))
    A(Ins("MPYK {k13}", "101k kkkk kkkk kkkk", lambda: "PREG = sext(TREG) * {k13};\n"))
    A(Ins("LARK {r},{k}", "1100 0rrr kkkkkkkk", lambda: "{r} = {k};\n"))
    A(Ins("LDPK {k9}", "1100 100k kkkkkkkk", lambda: "DP = {k9};\n",
          ctx="dp_k=1; dp_v={k9}; globalset(inst_next, dp_k); globalset(inst_next, dp_v);"))
    A(Ins("ZAC", "1100 1010 0000 0000", lambda: "ACC = 0;\n"))
    A(Ins("LACK {k}", "1100 1010 kkkkkkkk", lambda: "ACC = {k};\n"))
    A(Ins("RPTK {k}", "1100 1011 kkkkkkkk", lambda: "RPTC = {k};\n", ctx=ctx_set(rpt=1)))
    A(Ins("ADDK {k}", "1100 1100 kkkkkkkk", lambda: acc_add(g, "{k}")))
    A(Ins("SUBK {k}", "1100 1101 kkkkkkkk", lambda: acc_sub(g, "{k}")))
    mem_op("MPYU", lambda: "PREG = zext(TREG) * zext({M});\n", "11001111")
    # CE group
    ce = [
        (0x00, "EINT", "INTM = 0;\n", ""), (0x01, "DINT", "INTM = 1;\n", ""),
        (0x02, "ROVM", "OVM = 0;\n", ctx_set(ovm_k=1, ovm_v=0)),
        (0x03, "SOVM", "OVM = 1;\n", ctx_set(ovm_k=1, ovm_v=1)),
        (0x04, "CNFD", "CNF = 0;\n", ""), (0x05, "CNFP", "CNF = 1;\n", ""),
        (0x06, "RSXM", "SXM = 0;\n", ctx_set(sxm_k=1, sxm_v=0)),
        (0x07, "SSXM", "SXM = 1;\n", ctx_set(sxm_k=1, sxm_v=1)),
        (0x0C, "RXF", "XF = 0;\n", ""), (0x0D, "SXF", "XF = 1;\n", ""),
        (0x14, "PAC", "PS", ""), (0x15, "APAC", "PSA", ""), (0x16, "SPAC", "PSS", ""),
        (0x18, "SFL", "C = ACC[31,1];\nACC = ACC << 1;\n", ""),
        (0x19, "SFR", "SFR", ""),
        (0x1B, "ABS", "ABS", ""),
        (0x1C, "PUSH", push("c2x", "ACCL"), ""),
        (0x1D, "POP", "ACC = zext(STK0);\n" + POP, ""),
        (0x1E, "TRAP", "TRAP", ""),
        (0x1F, "IDLE", "INTM = 0;\nidle();\n", ""),
        (0x20, "RTXM", "TXM = 0;\n", ""), (0x21, "STXM", "TXM = 1;\n", ""),
        (0x23, "NEG", "NEG", ""),
        (0x24, "CALA", "CALA", ""), (0x25, "BACC", "goto [ACCL];\n", ""),
        (0x26, "RET", "RET", ""),
        (0x27, "CMPL", "ACC = ~ACC;\n", ""),
        (0x30, "RC", "C = 0;\n", ""), (0x31, "SC", "C = 1;\n", ""),
        (0x32, "RTC", "TC = 0;\n", ""), (0x33, "STC", "TC = 1;\n", ""),
        (0x34, "ROL", "local _c:1 = C;\nC = ACC[31,1];\nACC = (ACC << 1) | zext(_c);\n", ""),
        (0x35, "ROR", "local _c:1 = C;\nC = ACC[0,1];\nACC = (ACC >> 1) | (zext(_c) << 31);\n", ""),
        (0x36, "RFSM", "FSM = 0;\n", ""), (0x37, "SFSM", "FSM = 1;\n", ""),
        (0x38, "RHM", "HM = 0;\n", ""), (0x39, "SHM", "HM = 1;\n", ""),
    ]
    for lo, name, code, ctx in ce:
        A(Ins(name, "1100 1110" + format(lo, "08b"), (lambda c=code: special(g, c, "c2x")), ctx=ctx))
    A(Ins("SPM {m}", "1100 1110 0000 10mm", lambda: "PM = {m};\n",
          ctx="pm_k=1; pm_v={m}; globalset(inst_next, pm_k); globalset(inst_next, pm_v);"))
    A(Ins("FORT {f}", "1100 1110 0000 111f", lambda: "FO = {f};\n"))
    A(Ins("CONF {m}", "1100 1110 0011 11mm", lambda: "CNF = {m};\n"))
    for cm in range(4):
        A(Ins(f"CMPR {cm}", "1100 1110 0101 00" + format(cm, "02b"), (lambda c=cm: cmpr("AR0", c))))
    A(Ins("NORM {N}", "1100 1110 1NNN 0010", lambda: norm()))
    # long immediates
    A(Ins("LRLK {r},{lk}", "1101 0rrr 0000 0000", lambda: "{r} = {w};\n", w2="w"))
    A(Ins("LALK {lk},{s}", "1101 ssss 0000 0001",
          lambda: ext16(g, "_v", "{w}") + "ACC = _v << {s};\n", w2="w"))
    A(Ins("ADLK {lk},{s}", "1101 ssss 0000 0010",
          lambda: ext16(g, "_v", "{w}") + acc_add(g, "_v << {s}"), w2="w"))
    A(Ins("SBLK {lk},{s}", "1101 ssss 0000 0011",
          lambda: ext16(g, "_v", "{w}") + acc_sub(g, "_v << {s}"), w2="w"))
    A(Ins("ANDK {lk},{s}", "1101 ssss 0000 0100", lambda: "ACC = ACC & (zext({w}) << {s});\n", w2="w"))
    A(Ins("ORK {lk},{s}", "1101 ssss 0000 0101", lambda: "ACC = ACC | (zext({w}) << {s});\n", w2="w"))
    A(Ins("XORK {lk},{s}", "1101 ssss 0000 0110", lambda: "ACC = ACC ^ (zext({w}) << {s});\n", w2="w"))
    A(Ins("OUT {M},{pa}{nx}", "1110 pppp MMMMMMMM", lambda: "{pa} = {M};\n"))
    br = [(0xF0, "BV", "OV != 0", "OV = 0;\n", ""), (0xF1, "BGZ", "ACC s> 0", "", ""),
          (0xF2, "BLEZ", "ACC s<= 0", "", ""), (0xF3, "BLZ", "ACC s< 0", "", ""),
          (0xF4, "BGEZ", "ACC s>= 0", "", ""), (0xF5, "BNZ", "ACC != 0", "", ""),
          (0xF6, "BZ", "ACC == 0", "", ""), (0xF8, "BBZ", "TC == 0", "", ""),
          (0xF9, "BBNZ", "TC != 0", "", ""), (0xFA, "BIOZ", "BIO == 0", "", "")]
    for op, name, cond, taken, _ in br:
        if taken:
            code = (f"build {{B}};\nif (!({cond})) goto <nt>;\n{taken}goto {{pma}};\n<nt>\n")
        else:
            code = f"build {{B}};\nif ({cond}) goto {{pma}};\n"
        A(Ins(name + " {pma}{B}", format(op, "08b") + "1BBBBBBB", (lambda c=code: c), w2="a"))
    # BNV: branch if OV = 0, else clear OV
    A(Ins("BNV {pma}{B}", "1111 0111 1BBBBBBB",
          lambda: "build {B};\nif (OV == 0) goto {pma};\nOV = 0;\n", w2="a"))
    A(Ins("BANZ {pma}{B}", "1111 1011 1BBBBBBB",
          lambda: "local _nz:1 = arcur != 0;\nbuild {B};\nif (_nz) goto {pma};\n", w2="a"))
    A(Ins("BLKP {pma},{M}{nx}", "1111 1100 MMMMMMMM", lambda: "{M} = *[prog]:2 ({w} + rpti);\n", w2="w"))
    A(Ins("BLKD {dlk},{M}{nx}", "1111 1101 MMMMMMMM", lambda: "{M} = *[data]:2 ({w} + rpti);\n", w2="d"))
    A(Ins("CALL {pma}{B}", "1111 1110 1BBBBBBB",
          lambda: "build {B};\n" + push("c2x", "{ret}") + "call {pma};\n", w2="a"))
    A(Ins("B {pma}{B}", "1111 1111 1BBBBBBB", lambda: "build {B};\ngoto {pma};\n", w2="a"))
    return T, g


def subc(g):
    return ("local _a:4 = ACC;\nlocal _b:4 = zext({M}) << 15;\nlocal _r:4 = _a - _b;\n"
            "C = _b <= _a;\nOV = OV | sborrow(_a, _b);\n"
            "if (_r s< 0) goto <neg>;\nACC = (_r << 1) + 1;\ngoto <done>;\n"
            "<neg>\nACC = _a << 1;\n<done>\n")


def cmpr(other, cm):
    op = ["==", "<", ">", "!="][cm]
    return f"TC = arcur {op} {other};\n"


def norm():
    return ("if (ACC == 0) goto <one>;\n"
            "if ((ACC[31,1] ^ ACC[30,1]) != 0) goto <one>;\n"
            "TC = 0;\nACC = ACC << 1;\nbuild {N};\ngoto <done>;\n"
            "<one>\nTC = 1;\n<done>\n")


def special(g, code, fam):
    if code == "PS":
        return pshift(g, "_p") + "ACC = _p;\n"
    if code == "PSA":
        return pshift(g, "_p") + acc_add(g, "_p")
    if code == "PSS":
        return pshift(g, "_p") + acc_sub(g, "_p")
    if code == "SFR":
        return "C = ACC[0,1];\n" + sxsel(g, "ACC = ACC s>> 1;\n", "ACC = ACC >> 1;\n")
    if code == "ABS":
        # |ACC| -> ACC; 8000 0000h overflows (saturates to 7FFF FFFFh with OVM)
        s = ("local _a:4 = ACC;\nlocal _o:1 = _a == 0x80000000;\nOV = OV | _o;\n"
             "if (_a s>= 0) goto <pos>;\nACC = -_a;\n<pos>\n"
             + sat(g, "_o", "0:4"))
        if fam == "c5x":
            s += "C = 0;\n"
        return s
    if code == "NEG":
        return ("local _a:4 = ACC;\nlocal _o:1 = _a == 0x80000000;\nOV = OV | _o;\nACC = -_a;\n"
                "C = ACC == 0;\n" + sat(g, "_o", "0:4"))
    if code == "TRAP":
        return push(fam, "{ret}") + "call {tv};\n"
    if code == "CALA":
        return push(fam, "{ret}") + "call [ACCL];\n"
    if code == "RET":
        return "local _r:2 = STK0;\n" + POP + "return [_r];\n"
    return code


# ---------------------------------------------------------------- C5x table
def c5x_table():
    g = Gen()
    T = []
    A = T.append

    def mem_op(name, code, op8, kind="M", ctx=""):
        A(Ins(name + " {M}{nx}", op8 + kind * 8, code, ctx=ctx))

    def tload(v):
        # TREG0 load; with PMST.TRM = 0 (trm context 0) TREG1 and TREG2 load as well
        return f"TREG0 = {v};\n" + "build trmc;\n"

    A(Ins("LAR {r},{M}{nx}", "0000 0rrr MMMMMMMM", lambda: "{r} = {M};\n"))
    mem_op("LAMM", lambda: "ACC = zext({M});\n", "00001000", kind="Q")
    A(Ins("SMMR {M},{dlki}{nx}", "0000 1001 QQQQQQQQ", lambda: "*[data]:2 ({w} + rpti) = {M};\n", w2="d"))
    mem_op("SUBC", lambda: subc(g), "00001010")
    mem_op("RPT", lambda: "RPTC = {M};\n", "00001011", ctx=ctx_set(rpt=1))
    A(Ins("OUT {M},{pa16}{nx}", "0000 1100 MMMMMMMM", lambda: "*[io]:2 ({w} + rpti) = {M};\n", w2="p"))
    mem_op("LDP", lambda: "DP = {M} & 0x1ff;\n", "00001101", ctx=ctx_set(dp_k=0))
    A(Ins("LST #0,{M}{nx}", "0000 1110 MMMMMMMM",
          lambda: "local _s:2 = {M};\nARB = ARP;\nARP = _s(1) >> 5;\nOV = _s[12,1];\n"
          "OVM = _s[11,1];\nDP = _s & 0x1ff;\n",
          ctx=ctx_set(arp_k=0, dp_k=0, ovm_k=0)))
    A(Ins("LST #1,{M}{nx}", "0000 1111 MMMMMMMM",
          lambda: "local _s:2 = {M};\nARB = _s(1) >> 5;\nARP = ARB;\n"
          "CNF = _s[12,1];\nTC = _s[11,1];\nSXM = _s[10,1];\n"
          "C = _s[9,1];\nHM = _s[6,1];\nXF = _s[4,1];\nPM = _s:1 & 3;\n",
          ctx=ctx_set(arp_k=0, sxm_k=0, pm_k=0)))
    A(Ins("LACC {M},{s}{nx}", "0001 ssss MMMMMMMM", lambda: ext16(g, "_v", "{M}") + "ACC = _v << {s};\n"))
    A(Ins("ADD {M},{s}{nx}", "0010 ssss MMMMMMMM", lambda: ext16(g, "_v", "{M}") + acc_add(g, "_v << {s}")))
    A(Ins("SUB {M},{s}{nx}", "0011 ssss MMMMMMMM", lambda: ext16(g, "_v", "{M}") + acc_sub(g, "_v << {s}")))
    A(Ins("BIT {M},{b}{nx}", "0100 bbbb MMMMMMMM", lambda: "TC = (({M} >> (15 - {b})) & 1) != 0;\n"))
    mem_op("MPYA", lambda: pshift(g, "_p") + acc_add(g, "_p") + "PREG = sext(TREG0) * sext({M});\n", "01010000")
    mem_op("MPYS", lambda: pshift(g, "_p") + acc_sub(g, "_p") + "PREG = sext(TREG0) * sext({M});\n", "01010001")
    mem_op("SQRA", lambda: pshift(g, "_p") + acc_add(g, "_p") + "local _d:2 = {M};\n" + tload("_d") +
           "PREG = sext(_d) * sext(_d);\n", "01010010")
    mem_op("SQRS", lambda: pshift(g, "_p") + acc_sub(g, "_p") + "local _d:2 = {M};\n" + tload("_d") +
           "PREG = sext(_d) * sext(_d);\n", "01010011")
    mem_op("MPY", lambda: "PREG = sext(TREG0) * sext({M});\n", "01010100")
    mem_op("MPYU", lambda: "PREG = zext(TREG0) * zext({M});\n", "01010101")
    mem_op("BLDP", lambda: "*[prog]:2 (BMAR + rpti) = {M};\n", "01010111")
    for op, name, opx in ((0x58, "XPL", "^"), (0x59, "OPL", "|"), (0x5A, "APL", "&")):
        mem_op(name, (lambda o=opx: "local _r:2 = {M} " + o + " DBMR;\n{M} = _r;\nTC = _r == 0;\n"),
               format(op, "08b"))
        A(Ins(name + " {lk},{M}{nx}", format(op + 4, "08b") + "MMMMMMMM",
              (lambda o=opx: "local _r:2 = {M} " + o + " {w};\n{M} = _r;\nTC = _r == 0;\n"), w2="w"))
    mem_op("CPL", lambda: "TC = {M} == DBMR;\n", "01011011")
    A(Ins("CPL {lk},{M}{nx}", "0101 1111 MMMMMMMM", lambda: "TC = {M} == {w};\n", w2="w"))
    mem_op("ADDC", lambda: acc_addc(g, "zext({M})"), "01100000")
    A(Ins("ADD {M},16{nx}", "0110 0001 MMMMMMMM", lambda: acc_add(g, "zext({M}) << 16", "set")))
    mem_op("ADDS", lambda: acc_add(g, "zext({M})"), "01100010")
    mem_op("ADDT", lambda: ext16(g, "_v", "{M}") + acc_add(g, "_v << (TREG1 & 0xf)"), "01100011")
    mem_op("SUBB", lambda: acc_subb(g, "zext({M})"), "01100100")
    A(Ins("SUB {M},16{nx}", "0110 0101 MMMMMMMM", lambda: acc_sub(g, "zext({M}) << 16", "reset")))
    mem_op("SUBS", lambda: acc_sub(g, "zext({M})"), "01100110")
    mem_op("SUBT", lambda: ext16(g, "_v", "{M}") + acc_sub(g, "_v << (TREG1 & 0xf)"), "01100111")
    mem_op("ZALR", lambda: "ACC = (zext({M}) << 16) | 0x8000;\n", "01101000")
    mem_op("LACL", lambda: "ACC = zext({M});\n", "01101001")
    A(Ins("LACC {M},16{nx}", "0110 1010 MMMMMMMM", lambda: "ACC = zext({M}) << 16;\n"))
    mem_op("LACT", lambda: ext16(g, "_v", "{M}") + "ACC = _v << (TREG1 & 0xf);\n", "01101011")
    mem_op("XOR", lambda: "ACCL = ACCL ^ {M};\n", "01101100")
    mem_op("OR", lambda: "ACCL = ACCL | {M};\n", "01101101")
    mem_op("AND", lambda: "ACC = zext(ACCL & {M});\n", "01101110")
    mem_op("BITT", lambda: "TC = (({M} >> (15 - (TREG2 & 0xf))) & 1) != 0;\n", "01101111")
    mem_op("LTA", lambda: "local _d:2 = {M};\n" + tload("_d") + pshift(g, "_p") + acc_add(g, "_p"), "01110000")
    mem_op("LTP", lambda: "local _d:2 = {M};\n" + tload("_d") + pshift(g, "_p") + "ACC = _p;\n", "01110001")
    mem_op("LTD", lambda: "local _a:2 = {M};\nlocal _d:2 = *[data]:2 _a;\n" + tload("_d") +
           "*[data]:2 (_a + 1) = _d;\n" + pshift(g, "_p") + acc_add(g, "_p"), "01110010", kind="A")
    mem_op("LT", lambda: "local _d:2 = {M};\n" + tload("_d"), "01110011")
    mem_op("LTS", lambda: "local _d:2 = {M};\n" + tload("_d") + pshift(g, "_p") + acc_sub(g, "_p"), "01110100")
    mem_op("LPH", lambda: "PH = {M};\n", "01110101")
    mem_op("PSHD", lambda: push("c5x", "{M}"), "01110110")
    mem_op("DMOV", lambda: "local _a:2 = {M};\n*[data]:2 (_a + 1) = *[data]:2 _a;\n", "01110111", kind="A")
    A(Ins("ADRK {k}", "0111 1000 kkkkkkkk", lambda: ar_add(g, "arcur + {k}")))
    A(Ins("B {pma}{B}", "0111 1001 1BBBBBBB", lambda: "build {B};\ngoto {pma};\n", w2="a"))
    A(Ins("CALL {pma}{B}", "0111 1010 1BBBBBBB",
          lambda: "build {B};\n" + push("c5x", "{ret}") + "call {pma};\n", w2="a"))
    A(Ins("BANZ {pma}{B}", "0111 1011 1BBBBBBB",
          lambda: "local _nz:1 = arcur != 0;\nbuild {B};\nif (_nz) goto {pma};\n", w2="a"))
    A(Ins("SBRK {k}", "0111 1100 kkkkkkkk", lambda: ar_add(g, "arcur - {k}")))
    A(Ins("BD {pma}{B}", "0111 1101 1BBBBBBB", lambda: "build {B};\ndelayslot(4);\ngoto {pma};\n",
          w2="a", delay=2))
    A(Ins("CALLD {pma}{B}", "0111 1110 1BBBBBBB",
          lambda: "build {B};\n" + push("c5x", "{retd}") + "delayslot(4);\ncall {pma};\n", w2="a", delay=2))
    A(Ins("BANZD {pma}{B}", "0111 1111 1BBBBBBB",
          lambda: "local _nz:1 = arcur != 0;\nbuild {B};\ndelayslot(4);\nif (_nz) goto {pma};\n",
          w2="a", delay=2))
    A(Ins("SAR {r},{M}{nx}", "1000 0rrr MMMMMMMM", lambda: "local _t:2 = {r};\nbuild {M};\n{M} = _t;\n"))
    mem_op("SAMM", lambda: "{M} = ACCL;\n", "10001000", kind="Q")
    A(Ins("LMMR {M},{dlki}{nx}", "1000 1001 QQQQQQQQ", lambda: "{M} = *[data]:2 ({w} + rpti);\n", w2="d"))
    mem_op("POPD", lambda: "{M} = STK0;\n" + POP, "10001010")
    A(Ins("NOP", "1000 1011 0000 0000", lambda: ""))
    A(Ins("MAR {M}", "1000 1011 0MMMMMMM", lambda: ""))
    A(Ins("MAR {M}{nx}", "1000 1011 1MMMMMMM", lambda: "build {M};\n"))
    mem_op("SPL", lambda: pshift(g, "_p") + "{M} = _p:2;\n", "10001100")
    mem_op("SPH", lambda: pshift(g, "_p") + "{M} = _p(2);\n", "10001101")
    A(Ins("SST #0,{M}{nx}", "1000 1110 PPPPPPPP",
          lambda: "{M} = (zext(ARP) << 13) | (zext(OV) << 12) | (zext(OVM) << 11) | 0x400 | "
          "(zext(INTM) << 9) | DP;\n"))
    A(Ins("SST #1,{M}{nx}", "1000 1111 PPPPPPPP",
          lambda: "{M} = (zext(ARB) << 13) | (zext(CNF) << 12) | (zext(TC) << 11) | "
          "(zext(SXM) << 10) | (zext(C) << 9) | 0x1ac | (zext(HM) << 6) | (zext(XF) << 4) | zext(PM);\n"))
    A(Ins("SACL {M},{x}{nx}", "1001 0xxx MMMMMMMM", lambda: "local _t:4 = ACC << {x};\n{M} = _t:2;\n"))
    A(Ins("SACH {M},{x}{nx}", "1001 1xxx MMMMMMMM", lambda: "local _t:4 = ACC << {x};\n{M} = _t(2);\n"))
    A(Ins("NORM {N}", "1010 0000 1NNNNNNN", lambda: norm()))
    A(Ins("MAC {pma},{M}{nx}", "1010 0010 MMMMMMMM",
          lambda: pshift(g, "_p") + acc_add(g, "_p") + "local _d:2 = {M};\n" + tload("_d") +
          "PREG = sext(_d) * sext(*[prog]:2 ({w} + rpti));\n", w2="w"))
    A(Ins("MACD {pma},{M}{nx}", "1010 0011 AAAAAAAA",
          lambda: pshift(g, "_p") + acc_add(g, "_p") + "local _a:2 = {M};\nlocal _d:2 = *[data]:2 _a;\n" +
          tload("_d") + "PREG = sext(_d) * sext(*[prog]:2 ({w} + rpti));\n*[data]:2 (_a + 1) = _d;\n", w2="w"))
    A(Ins("BLPD BMAR,{M}{nx}", "1010 0100 MMMMMMMM", lambda: "{M} = *[prog]:2 (BMAR + rpti);\n"))
    A(Ins("BLPD {pmai},{M}{nx}", "1010 0101 MMMMMMMM", lambda: "{M} = *[prog]:2 ({w} + rpti);\n", w2="w"))
    mem_op("TBLR", lambda: "{M} = *[prog]:2 (ACCL + rpti);\n", "10100110")
    mem_op("TBLW", lambda: "*[prog]:2 (ACCL + rpti) = {M};\n", "10100111")
    A(Ins("BLDD {dlki},{M}{nx}", "1010 1000 MMMMMMMM", lambda: "{M} = *[data]:2 ({w} + rpti);\n", w2="d"))
    A(Ins("BLDD {M},{dlki}{nx}", "1010 1001 MMMMMMMM", lambda: "*[data]:2 ({w} + rpti) = {M};\n", w2="d"))
    mem_op("MADS", lambda: pshift(g, "_p") + acc_add(g, "_p") + "local _d:2 = {M};\n" + tload("_d") +
           "PREG = sext(_d) * sext(*[prog]:2 (BMAR + rpti));\n", "10101010")
    mem_op("MADD", lambda: pshift(g, "_p") + acc_add(g, "_p") + "local _a:2 = {M};\nlocal _d:2 = *[data]:2 _a;\n" + tload("_d") +
           "PREG = sext(_d) * sext(*[prog]:2 (BMAR + rpti));\n*[data]:2 (_a + 1) = _d;\n", "10101011", kind="A")
    A(Ins("BLDD BMAR,{M}{nx}", "1010 1100 MMMMMMMM", lambda: "{M} = *[data]:2 (BMAR + rpti);\n"))
    A(Ins("BLDD {M},BMAR{nx}", "1010 1101 MMMMMMMM", lambda: "*[data]:2 (BMAR + rpti) = {M};\n"))
    A(Ins("SPLK {lk},{M}{nx}", "1010 1110 MMMMMMMM", lambda: "{M} = {w};\n", w2="w"))
    A(Ins("IN {M},{pa16}{nx}", "1010 1111 MMMMMMMM", lambda: "{M} = *[io]:2 ({w} + rpti);\n", w2="p"))
    A(Ins("LAR {r},#{k}", "1011 0rrr kkkkkkkk", lambda: "{r} = {k};\n"))
    A(Ins("ADD #{k}", "1011 1000 kkkkkkkk", lambda: acc_add(g, "{k}")))
    A(Ins("LACL #{k}", "1011 1001 kkkkkkkk", lambda: "ACC = {k};\n"))
    A(Ins("SUB #{k}", "1011 1010 kkkkkkkk", lambda: acc_sub(g, "{k}")))
    A(Ins("RPT #{k}", "1011 1011 kkkkkkkk", lambda: "RPTC = {k};\n", ctx=ctx_set(rpt=1)))
    A(Ins("LDP #{k9}", "1011 110k kkkkkkkk", lambda: "DP = {k9};\n",
          ctx="dp_k=1; dp_v={k9}; globalset(inst_next, dp_k); globalset(inst_next, dp_v);"))
    be = [
        (0x00, "ABS", "ABS", ""), (0x01, "CMPL", "ACC = ~ACC;\n", ""), (0x02, "NEG", "NEG", ""),
        (0x03, "PAC", "PS", ""), (0x04, "APAC", "PSA", ""), (0x05, "SPAC", "PSS", ""),
        (0x09, "SFL", "C = ACC[31,1];\nACC = ACC << 1;\n", ""), (0x0A, "SFR", "SFR", ""),
        (0x0C, "ROL", "local _c:1 = C;\nC = ACC[31,1];\nACC = (ACC << 1) | zext(_c);\n", ""),
        (0x0D, "ROR", "local _c:1 = C;\nC = ACC[0,1];\nACC = (ACC >> 1) | (zext(_c) << 31);\n", ""),
        (0x10, "ADDB", "ADDB", ""), (0x11, "ADCB", "ADCB", ""),
        (0x12, "ANDB", "ACC = ACC & ACCB;\n", ""), (0x13, "ORB", "ACC = ACC | ACCB;\n", ""),
        (0x14, "ROLB", "local _c:1 = C;\nC = ACC[31,1];\nACC = (ACC << 1) | (ACCB >> 31);\n"
                       "ACCB = (ACCB << 1) | zext(_c);\n", ""),
        (0x15, "RORB", "local _c:1 = C;\nC = ACCB[0,1];\nACCB = (ACCB >> 1) | (ACC << 31);\n"
                       "ACC = (ACC >> 1) | (zext(_c) << 31);\n", ""),
        (0x16, "SFLB", "C = ACC[31,1];\nACC = (ACC << 1) | (ACCB >> 31);\nACCB = ACCB << 1;\n", ""),
        (0x17, "SFRB", "SFRB", ""),
        (0x18, "SBB", "SBB", ""), (0x19, "SBBB", "SBBB", ""),
        (0x1A, "XORB", "ACC = ACC ^ ACCB;\n", ""),
        (0x1B, "CRGT", "if (ACC s< ACCB) goto <lt>;\nACCB = ACC;\nC = 1;\ngoto <done>;\n"
                       "<lt>\nACC = ACCB;\nC = 0;\n<done>\n", ""),
        (0x1C, "CRLT", "if (ACC s>= ACCB) goto <ge>;\nACCB = ACC;\nC = 1;\ngoto <done>;\n"
                       "<ge>\nC = 0;\nif (ACC == ACCB) goto <done>;\nACC = ACCB;\n<done>\n", ""),
        (0x1D, "EXAR", "local _t:4 = ACC;\nACC = ACCB;\nACCB = _t;\n", ""),
        (0x1E, "SACB", "ACCB = ACC;\n", ""), (0x1F, "LACB", "ACC = ACCB;\n", ""),
        (0x20, "BACC", "goto [ACCL];\n", ""),
        (0x22, "IDLE", "idle();\n", ""), (0x23, "IDLE2", "idle2();\n", ""),
        (0x30, "CALA", "CALA", ""), (0x32, "POP", "ACC = zext(STK0);\n" + POP, ""),
        (0x38, "RETI", "RETI", ""), (0x3A, "RETE", "RETE", ""),
        (0x3C, "PUSH", push("c5x", "ACCL"), ""),
        (0x51, "TRAP", "VEC22", ""), (0x52, "NMI", "VEC24", ""),
        (0x58, "ZPR", "PREG = 0;\n", ""), (0x59, "ZAP", "ACC = 0;\nPREG = 0;\n", ""),
        (0x5A, "SATH", "SATH", ""), (0x5B, "SATL", "SATL", ""),
    ]
    for lo, name, code, ctx in be:
        A(Ins(name, "1011 1110" + format(lo, "08b"), (lambda c=code: special5(g, c)), ctx=ctx))
    # Emulation/debug instructions that SPRU056D does not list; mnemonics and encodings as TI's
    # assembler accepts them, recorded by c5xtools' conformance corpus. Semantics undocumented.
    for lo, name in ((0x31, "TRAPD"), (0x90, "ESTOP"), (0x91, "ESTPD"), (0x92, "EMRET"), (0x93, "ETRAP"),
                     (0xB0, "EMPSD"), (0xB1, "EHWBS"), (0xB3, "EHWBT")):
        A(Ins(name, "1011 1110" + format(lo, "08b"), (lambda nm=name: f"emulation_{nm.lower()}();\n")))
    A(Ins("BACCD", "1011 1110 0010 0001", lambda: "local _t:2 = ACCL;\ndelayslot(4);\ngoto [_t];\n", delay=2))
    A(Ins("CALAD", "1011 1110 0011 1101",
          lambda: "local _t:2 = ACCL;\n" + push("c5x", "{retd}") + "delayslot(4);\ncall [_t];\n", delay=2))
    bits = [("INTM", ""), ("OVM", "ovm"), ("CNF", ""), ("SXM", "sxm"), ("HM", ""), ("TC", ""),
            ("XF", ""), ("C", "")]
    for i, (bit, ck) in enumerate(bits):
        for v, name in ((0, "CLRC"), (1, "SETC")):
            ctx = ctx_set(**{ck + "_k": 1, ck + "_v": v}) if ck else ""
            A(Ins(f"{name} {bit}", "1011 1110 0100" + format(2 * i + v, "04b"),
                  (lambda b=bit, vv=v: f"{b} = {vv};\n"), ctx=ctx))
    A(Ins("INTR {k5}", "1011 1110 011k kkkk", lambda: "local _v:2 = (PMST & 0xf800) | ({k5} * 2);\n" +
          push("c5x", "{ret}") + "INTM = 1;\ncall [_v];\n"))
    A(Ins("MPY {lk}", "1011 1110 1000 0000", lambda: "PREG = sext(TREG0) * sext({w});\n", w2="w"))
    A(Ins("AND {lk},16", "1011 1110 1000 0001", lambda: "ACC = ACC & (zext({w}) << 16);\n", w2="w"))
    A(Ins("OR {lk},16", "1011 1110 1000 0010", lambda: "ACC = ACC | (zext({w}) << 16);\n", w2="w"))
    A(Ins("XOR {lk},16", "1011 1110 1000 0011", lambda: "ACC = ACC ^ (zext({w}) << 16);\n", w2="w"))
    A(Ins("RPT {lk}", "1011 1110 1100 0100", lambda: "RPTC = {w};\n", w2="w", ctx=ctx_set(rpt=1)))
    A(Ins("RPTZ {lk}", "1011 1110 1100 0101", lambda: "ACC = 0;\nPREG = 0;\nRPTC = {w};\n", w2="w",
          ctx=ctx_set(rpt=1)))
    A(Ins("RPTB {pma}", "1011 1110 1100 0110",
          lambda: "PMST = PMST | 1;\nPASR = {ret};\nPAER = {w};\n", w2="b",
          ctx="rbe1=1; rbe2=1; rbs=inst_start+2; globalset({pma}, rbe1); globalset({pma}, rbs); "
              "globalset({pm1}, rbe2); globalset({pm1}, rbs);"))
    A(Ins("SPM {m}", "1011 1111 0000 00mm", lambda: "PM = {m};\n",
          ctx="pm_k=1; pm_v={m}; globalset(inst_next, pm_k); globalset(inst_next, pm_v);"))
    A(Ins("LAR {r},{lk}", "1011 1111 0000 1rrr", lambda: "{r} = {w};\n", w2="w"))
    for cm in range(4):
        A(Ins(f"CMPR {cm}", "1011 1111 0100 01" + format(cm, "02b"), (lambda c=cm: cmpr("arcr", c))))
    A(Ins("LACC {lk},{s}", "1011 1111 1000 ssss", lambda: ext16(g, "_v", "{w}") + "ACC = _v << {s};\n", w2="w"))
    A(Ins("ADD {lk},{s}", "1011 1111 1001 ssss", lambda: ext16(g, "_v", "{w}") + acc_add(g, "_v << {s}"), w2="w"))
    A(Ins("SUB {lk},{s}", "1011 1111 1010 ssss", lambda: ext16(g, "_v", "{w}") + acc_sub(g, "_v << {s}"), w2="w"))
    A(Ins("AND {lk},{s}", "1011 1111 1011 ssss", lambda: "ACC = ACC & (zext({w}) << {s});\n", w2="w"))
    A(Ins("OR {lk},{s}", "1011 1111 1100 ssss", lambda: "ACC = ACC | (zext({w}) << {s});\n", w2="w"))
    A(Ins("XOR {lk},{s}", "1011 1111 1101 ssss", lambda: "ACC = ACC ^ (zext({w}) << {s});\n", w2="w"))
    A(Ins("BSAR {s1}", "1011 1111 1110 ssss", lambda: sxsel(g, "ACC = ACC s>> ({s} + 1);\n", "ACC = ACC >> ({s} + 1);\n")))
    A(Ins("MPY #{k13}", "110k kkkk kkkk kkkk", lambda: "PREG = sext(TREG0) * {k13};\n"))
    # conditional group
    A(Ins("BCND {pma},{c}", "1110 00cc cccc cccc",
          lambda: "local _t:1 = {c};\nbuild ovclr;\nif (_t) goto {pma};\n", w2="a"))
    A(Ins("XC {n},{c}", "111n 01cc cccc cccc", lambda: "local _t:1 = {c};\nif (!_t) goto {skp};\n"))
    A(Ins("CC {pma},{c}", "1110 10cc cccc cccc",
          lambda: "local _t:1 = {c};\nif (!_t) goto <nt>;\n" + push("c5x", "{ret}") + "call {pma};\n<nt>\n",
          w2="a"))
    A(Ins("RET", "1110 1111 0000 0000", lambda: "local _r:2 = STK0;\n" + POP + "return [_r];\n"))
    A(Ins("RETC {c}", "1110 11cc cccc cccc",
          lambda: "local _t:1 = {c};\nif (!_t) goto <nt>;\nlocal _r:2 = STK0;\n" + POP +
          "return [_r];\n<nt>\n"))
    A(Ins("BCNDD {pma},{c}", "1111 00cc cccc cccc",
          lambda: "local _t:1 = {c};\nbuild ovclr;\ndelayslot(4);\nif (_t) goto {pma};\n",
          w2="a", delay=2))
    A(Ins("CCD {pma},{c}", "1111 10cc cccc cccc",
          lambda: "local _t:1 = {c};\nif (!_t) goto <nt>;\n" + push("c5x", "{retd}") +
          "<nt>\ndelayslot(4);\nif (!_t) goto <nt2>;\ncall {pma};\n<nt2>\n", w2="a", delay=2))
    A(Ins("RETD", "1111 1111 0000 0000",
          lambda: "local _r:2 = STK0;\n" + POP + "delayslot(4);\nreturn [_r];\n", delay=2))
    A(Ins("RETCD {c}", "1111 11cc cccc cccc",
          lambda: "local _t:1 = {c};\nlocal _r:2 = STK0;\ndelayslot(4);\nif (!_t) goto <nt>;\n" + POP +
          "return [_r];\n<nt>\n", delay=2))
    return T, g


def special5(g, code):
    if code == "ADDB":
        return acc_add(g, "ACCB")
    if code == "ADCB":
        return acc_addc(g, "ACCB")
    if code == "SBB":
        return acc_sub(g, "ACCB")
    if code == "SBBB":
        return acc_subb(g, "ACCB")
    if code == "SFRB":
        return ("C = ACCB[0,1];\nACCB = (ACCB >> 1) | (ACC << 31);\n" +
                sxsel(g, "ACC = ACC s>> 1;\n", "ACC = ACC >> 1;\n"))
    if code in ("VEC22", "VEC24"):
        v = 0x22 if code == "VEC22" else 0x24
        s = f"local _v:2 = (PMST & 0xf800) | {v:#x};\n" + push("c5x", "{ret}")
        if v == 0x24:
            s += "INTM = 1;\n"
        return s + "call [_v];\n"
    if code == "RETI":
        return "local _r:2 = STK0;\n" + POP + "restore_context();\nreturn [_r];\n"
    if code == "RETE":
        return "local _r:2 = STK0;\n" + POP + "restore_context();\nINTM = 0;\nreturn [_r];\n"
    if code == "SATH":
        return ("local _n:4 = zext((TREG1 & 0x10) != 0) * 16;\n" +
                sxsel(g, "ACC = ACC s>> _n;\n", "ACC = ACC >> _n;\n"))
    if code == "SATL":
        return ("local _n:4 = zext(TREG1 & 0xf);\n" +
                sxsel(g, "ACC = ACC s>> _n;\n", "ACC = ACC >> _n;\n"))
    return special(g, code, "c5x")


# --------------------------------------------------------------------------------------------
# SLEIGH emission
# --------------------------------------------------------------------------------------------

W2OPS = ("w16", "lk16", "pma16", "pmai16", "dlk16", "dlki16", "pa16", "rptbm1")


def runs(pat):
    """Contiguous runs (hi, lo, text): fixed bits together, otherwise same letter together."""
    out = []
    i = 0
    while i < 16:
        j = i + 1
        fixed = pat[i] in "01"
        while j < 16 and ((pat[j] in "01") if fixed else pat[j] == pat[i]):
            j += 1
        out.append((15 - i, 15 - (j - 1), pat[i:j]))
        i = j
    return out


class Emitter:
    def __init__(self, fam):
        self.fam = fam
        self.fields = {}

    def field(self, hi, lo, signed=False, dec=False):
        name = f"f{hi}_{lo}" + ("s" if signed else "") + ("d" if dec else "")
        attrs = (" signed" if signed else "") + (" dec" if dec else "")
        self.fields[name] = f"{name}=({lo},{hi}){attrs}"
        return name


MEMKINDS = {"M": "mem", "P": "memp0", "Q": "mmr", "A": "mema"}


def build_constructor(em, ins, g):
    """One constructor per combination of the mode bits the semantics consults."""
    for k in MODE:
        MODE[k] = None
    USED.clear()
    ins.sem()
    combos = [{}]
    for m in sorted(USED):
        vals = [None, 0, 1, 2, 3] if m == "pm" else ([0, 1] if m == "circ" else [None, 0, 1])
        combos = [dict(c, **{m: v}) for c in combos for v in vals]
    out = []
    for c in combos:
        for k in MODE:
            MODE[k] = c.get(k)
        extra = [f"circ={v}" if m == "circ" else (f"{m}_k=0" if v is None else f"{m}_k=1 & {m}_v={v}")
                 for m, v in sorted(c.items())]
        out.append(build_one(em, ins, g, extra))
    return "".join(out)


def build_one(em, ins, g, extra):
    pat = ins.pat
    cons = []
    ops = {}
    for hi, lo, s in runs(pat):
        c = s[0]
        if c in "01":
            cons.append(f"{em.field(hi, lo)}={int(s, 2):#x}")
        elif c in MEMKINDS:
            assert lo == 0 and hi in (6, 7), ins.disp
            ops["M"] = MEMKINDS[c]
            ops["nx"] = "nxt"
        elif c == "B":
            assert (hi, lo) == (6, 0)
            ops["B"] = "bmod"
        elif c == "N":
            ops["N"] = "nmod"
        elif c == "s":
            ops["s"] = em.field(hi, lo, dec=True)
            ops["s1"] = "bsh"
        elif c == "x":
            ops["x"] = em.field(hi, lo, dec=True)
        elif c == "r":
            ops["r"] = "arx" if (hi, lo) == (10, 8) else "arx0"
        elif c == "k":
            width = hi - lo + 1
            if width == 13:
                ops["k13"] = "k13"
            elif width == 9:
                ops["k9"] = em.field(hi, lo)
            elif width == 5:
                ops["k5"] = em.field(hi, lo, dec=True)
            else:
                ops["k"] = em.field(hi, lo)
        elif c == "b":
            ops["b"] = em.field(hi, lo, dec=True)
        elif c == "p":
            if (hi, lo) == (11, 8):
                ops["pa"] = "port4"
            else:
                ops["lp"] = em.field(hi, lo, dec=True)
        elif c in "mf":
            ops[c] = em.field(hi, lo, dec=True)
        elif c == "c":
            ops["c"] = "cond"
            ops["vm"] = "vmf"
        elif c == "n":
            ops["n"] = "xcnum"
            ops["skp"] = "xcskip"
        else:
            raise ValueError(c)
    if ins.w2:
        ops.update(w="w16", lk="lk16", pma="pma16", pmai="pmai16", dlk="dlk16", dlki="dlki16",
                   pa16="pa16", pm1="rptbm1")
    ops.update(ret="retaddr", retd="retaddrd", tv="trapvec")
    used = []

    def sub(m, disp=False):
        k = m.group(1)
        if k not in ops:
            raise KeyError(f"{k} in {ins.disp}")
        v = ops[k]
        if v not in used:
            used.append(v)
        if disp and k in ("nx", "B"):
            return "^" + v
        return v

    sem = ins.sem()
    mn0, _, rest0 = ins.disp.partition(" ")
    # quote literal text (register names, '#', digits) so SLEIGH does not read it as operands
    parts = re.split(r"(\{\w+\}|,)", rest0)
    q = []
    for i, p in enumerate(parts):
        if p == "" or p == "," or re.fullmatch(r"\{\w+\}", p):
            q.append(p)
        else:
            nxt_op = i + 1 < len(parts) and re.fullmatch(r"\{\w+\}", parts[i + 1] or "")
            q.append('"' + p + '"' + ("^" if nxt_op else ""))
    disp = mn0 + (" " + "".join(q) if rest0 else "")
    disp_s = re.sub(r"\{(\w+)\}", lambda m: sub(m, True), disp).replace("^^", "^")
    sem_s = re.sub(r"\{(\w+)\}", sub, sem)
    ctx = re.sub(r"\{(\w+)\}", sub, ins.ctx)
    for tok in ("arcur", "rpti", "trmc", "arcr", "idx", "ovclr", "arnum"):
        if re.search(r"\b" + tok + r"\b", sem_s) and tok not in used:
            used.append(tok)
    # operand p-code order: memory operand (AR update), then next-ARP change
    mk = ops.get("M")
    if mk and "nxt" in used:
        if f"build {mk};" in sem_s:
            sem_s = sem_s.replace(f"build {mk};", f"build {mk};\nbuild nxt;", 1)
        else:
            sem_s = f"build {mk};\nbuild nxt;\n" + sem_s
    mn, _, rest = disp_s.partition(" ")
    first = cons[:] + extra
    second = []
    for o in used:
        if o in W2OPS:
            second.append(o)
        elif o not in first:
            first.append(o)
    pattern = " & ".join(first)
    if ins.w2:
        pattern += " ; " + (" & ".join(second) if second else "w16")
    ctxs = f" [ {ctx} ]" if ctx else ""
    return f":{mn} {rest} is {pattern}{ctxs} {{\n{indent(sem_s)}}}\n"


def indent(s):
    return "".join("\t" + l + "\n" for l in s.strip("\n").split("\n") if l.strip() != "") if s.strip() else ""


# ---------------------------------------------------------------- common header
def header(fam, em):
    c5 = fam == "c5x"
    s = []
    A = s.append
    A(f"# GENERATED by tools/gen_tms320.py -- do not edit. Family: TMS320{fam.upper()}\n")
    A("define endian=$(ENDIAN);\ndefine alignment=2;\n")
    A("define space prog type=ram_space size=2 wordsize=2 default;\n")
    A("define space data type=ram_space size=2 wordsize=2;\n")
    A("define space io type=ram_space size=2 wordsize=2;\n")
    A("define space register type=register_space size=2;\n\n")
    A("define register offset=0x00 size=2 [ PC RPTI ];\n")
    A("@if ENDIAN == \"big\"\n")
    A("define register offset=0x04 size=2 [ ACCH ACCL BH BL PH PL ];\n")
    A("@else\n")
    A("define register offset=0x04 size=2 [ ACCL ACCH BL BH PL PH ];\n")
    A("@endif\n")
    A("define register offset=0x04 size=4 [ ACC ACCB PREG ];\n")
    A("define register offset=0x10 size=2 [ DP STK0 STK1 STK2 STK3 STK4 STK5 STK6 STK7 ];\n")
    A("define register offset=0x30 size=1 [ ARP ARB OV OVM INTM CNF TC SXM C HM FSM XF FO TXM PM BIO ];\n")
    if c5:
        A("# memory-mapped CPU registers (data page 0); offsets are byte offsets (word address * 2)\n")
        A("define data offset=0x08 size=2 [ IMR GREG IFR PMST RPTC BRCR PASR PAER TREG0 TREG1 TREG2 DBMR\n"
          "                                 AR0 AR1 AR2 AR3 AR4 AR5 AR6 AR7 INDX ARCR CBSR1 CBER1 CBSR2 CBER2 CBCR BMAR ];\n")
    else:
        A("define register offset=0x40 size=2 [ TREG RPTC ];\n")
        A("define register offset=0x50 size=2 [ AR0 AR1 AR2 AR3 AR4 AR5 AR6 AR7 ];\n")
    A("\ndefine register offset=0x100 size=8 contextreg;\n")
    A("""define context contextreg
\tphase = (0,0)
\tarp_k = (1,1)
\tarp_v = (2,4)
\tdp_k = (5,5)
\tdp_v = (6,14)
\tsxm_k = (15,15)
\tsxm_v = (16,16)
\tovm_k = (17,17)
\tovm_v = (18,18)
\tpm_k = (19,19)
\tpm_v = (20,21)
\tndx = (22,22)
\ttrm = (23,23)
\tarpkc = (24,24) noflow
\tarpvc = (25,27) noflow
\tarpreg = (25,27) noflow
\tdpkc = (28,28) noflow
\tdpvc = (29,37) noflow
\trpt = (38,38) noflow
\trbe1 = (39,39) noflow
\trbe2 = (40,40) noflow
\trbs = (41,56) noflow
\tcirc = (57,57)
;
""")
    A("define pcodeop idle;\ndefine pcodeop idle2;\ndefine pcodeop restore_context;\n")
    if c5:
        for nm in ("trapd", "estop", "estpd", "emret", "etrap", "empsd", "ehwbs", "ehwbt"):
            A(f"define pcodeop emulation_{nm};\n")
    A("\n")
    return "".join(s)


def tokens(em):
    f = sorted(em.fields.values())
    base = ["iw7=(7,7)", "aru=(4,6)", "nbit=(3,3)", "narv=(0,2)", "narn=(0,2)", "off7=(0,6)",
            "arx=(8,10)", "arx0=(0,2)", "paf=(8,11)", "k13=(0,12) signed", "bshf=(0,3)", "cndf=(0,9)", "xcnf=(12,12)", "vmf=(1,1)"]
    s = "define token iw(16)\n" + "".join(f"\t{x}\n" for x in base + f) + ";\n"
    s += "define token w2(16)\n\twv=(0,15)\n\twvs=(0,15) signed\n;\n\n"
    s += "attach variables [ arx arx0 ] [ AR0 AR1 AR2 AR3 AR4 AR5 AR6 AR7 ];\n"
    s += "attach variables [ arpreg ] [ AR0 AR1 AR2 AR3 AR4 AR5 AR6 AR7 ];\n"
    s += 'attach names [ narn ] [ "AR0" "AR1" "AR2" "AR3" "AR4" "AR5" "AR6" "AR7" ];\n\n'
    return s


def operands(fam):
    c5 = fam == "c5x"
    s = []
    A = s.append
    # mode values: constants when the context knows them, registers otherwise
    # current auxiliary register
    A("arcur: is arpkc=1 & arpreg { export arpreg; }\n")
    A("port4: paf is paf { export *[io]:2 paf; }\n")
    A("ilen: l is epsilon [ l = inst_next - inst_start; ] { export *[const]:1 l; }\n")
    A("ovclr: is vmf=0 { }\novclr: is vmf=1 { OV = 0; }\n")
    if c5:
        A("arcur: is arpkc=0 { local p:2 = 0x10 + zext(ARP); export *[data]:2 p; }\n")
        A("idx: is ndx=0 { export AR0; }\nidx: is ndx=1 { export INDX; }\n")
        A("arnum: is arpkc=1 & arpvc { export *[const]:2 arpvc; }\n"
          "arnum: is arpkc=0 { local n:2 = zext(ARP); export n; }\n")
        A("arcr: is ndx=0 { export AR0; }\narcr: is ndx=1 { export ARCR; }\n")
        A("trmc: is trm=0 { TREG1 = TREG0 & 0x1f; TREG2 = TREG0 & 0xf; }\ntrmc: is trm=1 { }\n")
    else:
        A("arcur: is arpkc=0 { local p:2 = &:2 AR0 + zext(ARP) * 2; export *[register]:2 p; }\n")
        A("idx: is epsilon { export AR0; }\n")
    A("rpti: is rpt=1 { export RPTI; }\nrpti: is rpt=0 { export 0:2; }\n")
    A("""
macro rcadd(dst, a, b) {
\tlocal x:2 = a; local y:2 = b;
\tx = ((x & 0x5555) << 1) | ((x >> 1) & 0x5555); x = ((x & 0x3333) << 2) | ((x >> 2) & 0x3333);
\tx = ((x & 0x0f0f) << 4) | ((x >> 4) & 0x0f0f); x = (x << 8) | (x >> 8);
\ty = ((y & 0x5555) << 1) | ((y >> 1) & 0x5555); y = ((y & 0x3333) << 2) | ((y >> 2) & 0x3333);
\ty = ((y & 0x0f0f) << 4) | ((y >> 4) & 0x0f0f); y = (y << 8) | (y >> 8);
\tlocal r:2 = x + y;
\tr = ((r & 0x5555) << 1) | ((r >> 1) & 0x5555); r = ((r & 0x3333) << 2) | ((r >> 2) & 0x3333);
\tr = ((r & 0x0f0f) << 4) | ((r >> 4) & 0x0f0f); r = (r << 8) | (r >> 8);
\tdst = r;
}
macro rcsub(dst, a, b) {
\tlocal x:2 = a; local y:2 = b;
\tx = ((x & 0x5555) << 1) | ((x >> 1) & 0x5555); x = ((x & 0x3333) << 2) | ((x >> 2) & 0x3333);
\tx = ((x & 0x0f0f) << 4) | ((x >> 4) & 0x0f0f); x = (x << 8) | (x >> 8);
\ty = ((y & 0x5555) << 1) | ((y >> 1) & 0x5555); y = ((y & 0x3333) << 2) | ((y >> 2) & 0x3333);
\ty = ((y & 0x0f0f) << 4) | ((y >> 4) & 0x0f0f); y = (y << 8) | (y >> 8);
\tlocal r:2 = x - y;
\tr = ((r & 0x5555) << 1) | ((r >> 1) & 0x5555); r = ((r & 0x3333) << 2) | ((r >> 2) & 0x3333);
\tr = ((r & 0x0f0f) << 4) | ((r >> 4) & 0x0f0f); r = (r << 8) | (r >> 8);
\tdst = r;
}
""")
    # AR update per ARU (reserved 011 has no constructor)
    newv = {1: "nv = t - 1;", 2: "nv = t + 1;", 4: "rcsub(nv, t, idx);", 5: "nv = t - idx;",
            6: "nv = t + idx;", 7: "rcadd(nv, t, idx);"}
    disp = {0: "\"*\"", 1: "\"*-\"", 2: "\"*+\"", 4: "\"*BR0-\"", 5: "\"*0-\"", 6: "\"*0+\"", 7: "\"*BR0+\""}
    cnt = [0]

    def updcode(aru, circ):
        if aru == 0:
            return ""
        s = "local nv:2 = 0; " + newv[aru] + " "
        if circ:
            cnt[0] += 1
            s += circ_check(cnt[0]).replace("\n", " ")
        return s + "arcur = nv;"

    # (aru, circ) -> (display, code, extra pattern); C2x has no circular buffers
    upd = {}
    for aru in disp:
        for circ in ((0, 1) if c5 else (None,)):
            if aru == 0 and circ == 1:
                continue
            cpat = "" if circ is None or aru == 0 else f" & circ={circ}" + (" & arnum" if circ else "")
            upd[(aru, circ)] = (disp[aru], updcode(aru, circ == 1), cpat)
    # data-memory operands
    for tab, direct_known, direct_unknown, indaddr in (
            ("mem", "dmaddr", "off7", "t"),
            ("memp0", "off7", "off7", "t"),
            ("mmr", "off7", "off7", "t & 0x7f")):
        if tab == "mmr" and not c5:
            continue
        if tab == "mem":
            A("mem: dmaddr is iw7=0 & off7 & dpkc=1 & dpvc [ dmaddr = (dpvc << 7) | off7; ] "
              "{ export *[data]:2 dmaddr; }\n")
            A("mem: off7 is iw7=0 & off7 & dpkc=0 { local a:2 = (DP << 7) | off7; export *[data]:2 a; }\n")
        else:
            A(f"{tab}: off7 is iw7=0 & off7 {{ export *[data]:2 off7; }}\n")
        for (aru, circ), (d, code, cpat) in upd.items():
            idxop = " & idx" if "idx" in code else ""
            if indaddr == "t":
                A(f"{tab}: {d} is iw7=1 & aru={aru}{cpat} & arcur{idxop} {{ local t:2 = arcur; {code} "
                  f"export *[data]:2 t; }}\n")
            else:
                A(f"{tab}: {d} is iw7=1 & aru={aru}{cpat} & arcur{idxop} {{ local t:2 = arcur; {code} "
                  f"local m:2 = {indaddr}; export *[data]:2 m; }}\n")
    # address-valued variant for instructions that also touch dma + 1 (DMOV, LTD, MACD, MADD)
    A("mema: dmaddr is iw7=0 & off7 & dpkc=1 & dpvc [ dmaddr = (dpvc << 7) | off7; ] "
      "{ export *[const]:2 dmaddr; }\n")
    A("mema: off7 is iw7=0 & off7 & dpkc=0 { local a:2 = (DP << 7) | off7; export a; }\n")
    for (aru, circ), (d, code, cpat) in upd.items():
        idxop = " & idx" if "idx" in code else ""
        A(f"mema: {d} is iw7=1 & aru={aru}{cpat} & arcur{idxop} {{ local t:2 = arcur; {code} export t; }}\n")
    if not c5:
        A("trapvec: a is epsilon [ a = 0x1e; ] { export *[prog]:2 a; }\n")
    # next-ARP suffix (context for following instructions)
    A("nxt: is iw7=0 { }\nnxt: is iw7=1 & nbit=0 { }\n")
    A("nxt: \",\"^narn is iw7=1 & nbit=1 & narn & narv [ arp_k=1; arp_v=narv; globalset(inst_next, arp_k); "
      "globalset(inst_next, arp_v); ] { ARB = ARP; ARP = narv; }\n")
    # branch AR modification
    for (aru, circ), (d, code, cpat) in upd.items():
        idxop = " & idx" if "idx" in code else ""
        dd = d.strip('"')
        for nb in (0, 1):
            if aru == 0 and nb == 0:
                A("bmod: is aru=0 & nbit=0 { }\n")
                continue
            pre, arc = ("local t:2 = arcur; ", " & arcur") if code else ("", "")
            if nb == 0:
                A(f"bmod: \",{dd}\" is aru={aru}{cpat} & nbit=0{arc}{idxop} {{ {pre}{code} }}\n")
            else:
                A(f"bmod: \",{dd},\"^narn is aru={aru}{cpat} & nbit=1 & narn & narv{arc}{idxop} "
                  f"[ arp_k=1; arp_v=narv; globalset(inst_next, arp_k); globalset(inst_next, arp_v); ] "
                  f"{{ {pre}{code} ARB = ARP; ARP = narv; }}\n")
    # NORM indirect (AR update applied only when the accumulator shifts)
    for (aru, circ), (d, code, cpat) in upd.items():
        idxop = " & idx" if "idx" in code else ""
        pre, arc = ("local t:2 = arcur; ", " & arcur") if code else ("", "")
        if c5:
            A(f"nmod: {d} is aru={aru}{cpat} & nbit=0{arc}{idxop} {{ {pre}{code} }}\n")
            A(f"nmod: {d}^\",\"^narn is aru={aru}{cpat} & nbit=1 & narn & narv{arc}{idxop} "
              f"[ arp_k=1; arp_v=narv; globalset(inst_next, arp_k); globalset(inst_next, arp_v); ] "
              f"{{ {pre}{code} ARB = ARP; ARP = narv; }}\n")
        else:
            A(f"nmod: {d} is aru={aru}{arc}{idxop} {{ {pre}{code} }}\n")
    # second-word operands
    A("w16: wv is wv { export *[const]:2 wv; }\n")
    A("lk16: \"#\"^wv is wv { export *[const]:2 wv; }\n")
    A("pma16: wv is wv { export *[prog]:2 wv; }\n")
    A("pmai16: \"#\"^wv is wv { export *[prog]:2 wv; }\n")
    A("dlk16: wv is wv { export *[data]:2 wv; }\n")
    A("dlki16: \"#\"^wv is wv { export *[data]:2 wv; }\n")
    A("pa16: wv is wv { export *[io]:2 wv; }\n")
    A("retaddr: r is epsilon [ r = inst_next; ] { export *[const]:2 r; }\n")
    A("retaddrd: r is epsilon [ r = inst_next + 2; ] { export *[const]:2 r; }\n")
    A("bsh: v is bshf [ v = bshf + 1; ] { export *[const]:1 v; }\n")
    if c5:
        A("xcnum: \"1\" is xcnf=0 { }\nxcnum: \"2\" is xcnf=1 { }\n")
        A("xcskip: a is xcnf [ a = inst_next + xcnf + 1; ] { export *[prog]:2 a; }\n")
        # block-repeat end: PAER = pma; mark the end instruction(s) via context
        A("rptbm1: a is wv [ a = wv - 1; ] { export *[prog]:2 a; }\n")
        A("rbsaddr: is rbs { export *[prog]:2 rbs; }\n")
        s.append(conditions())
    return "".join(s)


def conditions():
    s = []
    for tp in range(4):
        for b in range(256):
            zs, ls, vs, cs = (b >> 7) & 1, (b >> 6) & 1, (b >> 5) & 1, (b >> 4) & 1
            zm, lm, vm, cm = (b >> 3) & 1, (b >> 2) & 1, (b >> 1) & 1, b & 1
            names, exprs = [], []
            # Z/L select a set of accumulator sign classes. L picks "< 0" (state 1) or "> 0"
            # (state 0); Z with state 1 adds "= 0". Z alone tests = 0 / != 0. This reproduces the
            # assembler encodings of SPRU056D (EQ 88h, NEQ 08h, LT 44h, GT 04h, LEQ CCh, GEQ 8Ch).
            if lm:
                cls = {"neg"} if ls else {"pos"}
                if zm and zs:
                    cls.add("zero")
            elif zm:
                cls = {"zero"} if zs else {"neg", "pos"}
            else:
                cls = None
            if cls:
                nm, ex = {frozenset({"zero"}): ("EQ", "(ACC == 0)"),
                          frozenset({"neg", "pos"}): ("NEQ", "(ACC != 0)"),
                          frozenset({"neg"}): ("LT", "(ACC s< 0)"),
                          frozenset({"pos"}): ("GT", "(ACC s> 0)"),
                          frozenset({"neg", "zero"}): ("LEQ", "(ACC s<= 0)"),
                          frozenset({"pos", "zero"}): ("GEQ", "(ACC s>= 0)")}[frozenset(cls)]
                names.append(nm)
                exprs.append(ex)
            if vm:
                names.append("OV" if vs else "NOV")
                exprs.append("(OV != 0)" if vs else "(OV == 0)")
            if cm:
                names.append("C" if cs else "NC")
                exprs.append("(C != 0)" if cs else "(C == 0)")
            if tp == 0:
                names.append("BIO")
                exprs.append("(BIO == 0)")
            elif tp == 1:
                names.append("TC")
                exprs.append("(TC != 0)")
            elif tp == 2:
                names.append("NTC")
                exprs.append("(TC == 0)")
            if not names:
                names, exprs = ["UNC"], ["1:1"]
            disp = "\",\"".join(names)
            s.append(f"cond: \"{disp}\" is cndf={(tp << 8) | b:#x} {{ local c:1 = {' && '.join(exprs)}; export c; }}\n")
    return "".join(s)


def root(fam):
    c5 = fam == "c5x"
    s = []
    copy = "phase=1; arpkc=arp_k; arpvc=arp_v; dpkc=dp_k; dpvc=dp_v;"
    combos = [(0, 0, 0), (1, 0, 0)]
    if c5:
        combos += [(r, 1, 0) for r in (0, 1)] + [(r, 0, 1) for r in (0, 1)]
    for rp, e1, e2 in combos:
        cons = f"phase=0 & rpt={rp}"
        if c5:
            cons += f" & rbe1={e1}" + (f" & rbe2={e2}" if not e1 else "")
        body = []
        if rp:
            body += ["RPTI = 0;", "<top>", "build instruction;", "if (RPTC == 0) goto <rdone>;",
                     "RPTC = RPTC - 1;", "RPTI = RPTI + 1;", "goto <top>;", "<rdone>"]
        else:
            body += ["build instruction;"]
        if e1 or e2:
            cons += " & rbsaddr"
            if not e1:
                body += ["if (ilen != 2) goto <bdone>;"]; cons += " & ilen"
            body += ["if ((PMST & 1) == 0) goto <bdone>;", "if (BRCR == 0) goto <bclr>;",
                     "BRCR = BRCR - 1;", "goto rbsaddr;", "<bclr>", "PMST = PMST & 0xfffe;", "<bdone>"]
        s.append(f":^instruction is {cons} & instruction [ {copy} ] {{\n" +
                 "".join("\t" + b + "\n" for b in body) + "}\n")
    return "".join(s)


def generate(fam):
    em = Emitter(fam)
    T, g = (c2x_table() if fam == "c2x" else c5x_table())
    body = []
    for ins in T:
        body.append(build_constructor(em, ins, g))
    out = header(fam, em) + tokens(em) + operands(fam) + "\n" + root(fam) + "\nwith : phase=1 {\n\n" + \
        "".join(body) + "\n}\n"
    # drop operand tables this family never references
    for name in ("ilen", "ovclr", "pmai16", "dlki16", "pa16", "retaddrd", "bsh", "port4", "trapvec", "dlk16"):
        defs = [l for l in out.split("\n") if l.startswith(name + ":")]
        uses = len(re.findall(r"\b" + name + r"\b", out))
        if defs and uses == len(defs):
            out = "\n".join(l for l in out.split("\n") if not l.startswith(name + ":"))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    for fam in ("c2x", "c5x"):
        with open(os.path.join(OUT, f"tms320{fam}.sinc"), "w") as f:
            f.write(generate(fam))
        for end, suf in (("big", ""), ("little", "_le")):
            with open(os.path.join(OUT, f"tms320{fam}{suf}.slaspec"), "w") as f:
                f.write(f"# TMS320{fam.upper()}, {end}-endian word order. Generated by tools/gen_tms320.py.\n"
                        f"@define ENDIAN \"{end}\"\n@include \"tms320{fam}.sinc\"\n")


if __name__ == "__main__":
    main()
