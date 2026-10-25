#!/usr/bin/env python3
"""Generate the ST9 / ST9+ SLEIGH instruction set.

    tools/gen_st9.py [languages dir]

writes st9_gen.sinc (ST9) and st9p_gen.sinc (ST9+) next to the hand-written st9.sinc.

Encodings come from the opcode map (section 2) and the instruction pages (section 3) of the
"ST9+ Family Programming Manual" (STMicroelectronics) and the "ST9 Family 8/16 Bit MCU
Programming Manual" (SGS-Thomson, 1991). MAME's unidasm was only run as a black-box reference
to check the decode; where it disagrees with the manual's encoding examples the manual wins (see
README "Confirmed oracle bugs").

The output is deterministic.
"""
import sys
from pathlib import Path

SYSNAMES = ["P0DR", "P1DR", "P2DR", "P3DR", "P4DR", "P5DR", "CICR", "FLAGR",
            "RP0R", "RP1R", "PPR", "MODER", "USPHR", "USPLR", "SSPHR", "SSPLR"]
SYSPAIRS = {0xE8: "RPR", 0xEC: "USPR", 0xEE: "SSPR"}

# ALU operation selected by the K nibble (ALD/ALDW); the two-operand opcodes use the same value
# in the high opcode nibble. 7 and B-E are reserved.
KOPS = [(0x0, "or"), (0x1, "and"), (0x2, "sbc"), (0x3, "adc"), (0x4, "add"), (0x5, "sub"),
        (0x6, "xor"), (0x8, "tcm"), (0x9, "cp"), (0xA, "tm"), (0xF, "ld")]
PLAIN = [k for k in KOPS if k[0] != 0xF]

# condition codes (Table 11)
CC = [(0x0, "f", None), (0x1, "lt", "(SF != VF)"), (0x2, "le", "(ZF || (SF != VF))"),
      (0x3, "ule", "(CF || ZF)"), (0x4, "ov", "VF"), (0x5, "mi", "SF"), (0x6, "eq", "ZF"),
      (0x7, "c", "CF"), (0x8, "", "1"), (0x9, "ge", "(SF == VF)"),
      (0xA, "gt", "(!ZF && (SF == VF))"), (0xB, "ugt", "(!CF && !ZF)"), (0xC, "nov", "!VF"),
      (0xD, "pl", "!SF"), (0xE, "ne", "!ZF"), (0xF, "nc", "!CF")]


def regname(v):
    return SYSNAMES[v - 0xE0] if 0xE0 <= v <= 0xEF else "R%02X" % v


def pairname(v):
    return SYSPAIRS.get(v, "RR%02X" % v)


def alu(op, sz, d, s):
    """p-code for one ALU operation: d = d op s (flags per the instruction summary)."""
    if op == "ld":
        return "%s = %s;" % (d, s)
    w2 = sz * 2
    msb = "0x80" if sz == 1 else "0x8000"
    L = ["local t_a:%d = %s;" % (sz, d), "local t_b:%d = %s;" % (sz, s)]
    store = True
    zs = ["ZF = (t_r == 0);", "SF = (t_r & %s) != 0;" % msb]
    if op in ("add", "adc"):
        cin = "zext(CF)" if op == "adc" else "0"
        L += ["local t_w:%d = zext(t_a) + zext(t_b) + %s;" % (w2, cin),
              "local t_r:%d = t_w:%d;" % (sz, sz),
              "VF = ((t_a ^ t_r) & (t_b ^ t_r) & %s) != 0;" % msb]
        if sz == 1:
            L += ["HF = ((t_a & 0xf) + (t_b & 0xf) + %s) > 0xf;" % ("CF" if op == "adc" else "0"),
                  "DF = 0;"]
        L += ["CF = (t_w >> %d) != 0;" % (8 * sz)] + zs
    elif op in ("sub", "sbc", "cp"):
        cin = "zext(CF)" if op == "sbc" else "0"
        L += ["local t_c:%d = %s;" % (w2, cin),
              "local t_r:%d = t_a - t_b - t_c:%d;" % (sz, sz),
              "VF = ((t_a ^ t_b) & (t_a ^ t_r) & %s) != 0;" % msb]
        if sz == 1 and op != "cp":
            L += ["HF = zext(t_a & 0xf) < zext(t_b & 0xf) + t_c;", "DF = 1;"]
        L += ["CF = zext(t_a) < zext(t_b) + t_c;"] + zs
        store = op != "cp"
    elif op in ("and", "or", "xor", "tm", "tcm"):
        expr = {"and": "t_a & t_b", "or": "t_a | t_b", "xor": "t_a ^ t_b", "tm": "t_a & t_b",
                "tcm": "~t_a & t_b"}[op]
        L += ["local t_r:%d = %s;" % (sz, expr), "VF = 0;"] + zs
        store = op in ("and", "or", "xor")
    else:
        raise ValueError(op)
    if store:
        L.append("%s = t_r;" % d)
    return " ".join(L)


def unary(op, sz, d):
    """One-operand byte/word operations."""
    msb = "0x80" if sz == 1 else "0x8000"
    top = 8 * sz - 1
    L = ["local t_a:%d = %s;" % (sz, d)]
    zs = ["ZF = (t_r == 0);", "SF = (t_r & %s) != 0;" % msb]
    if op == "inc":
        L += ["local t_r:%d = t_a + 1;" % sz, "VF = t_r == %s;" % msb] + zs
    elif op == "dec":
        L += ["local t_r:%d = t_a - 1;" % sz, "VF = t_a == %s;" % msb] + zs
    elif op == "cpl":
        L += ["local t_r:%d = ~t_a;" % sz, "VF = 0;"] + zs
    elif op == "clr":
        return "%s = 0;" % d
    elif op == "rol":
        L += ["local t_c:1 = (t_a & %s) != 0;" % msb, "local t_r:%d = (t_a << 1) | zext(t_c);" % sz,
              "CF = t_c;", "VF = ((t_a ^ t_r) & %s) != 0;" % msb] + zs
    elif op == "ror":
        L += ["local t_c:1 = t_a:1 & 1;", "local t_r:%d = (t_a >> 1) | (zext(t_c) << %d);" % (sz, top),
              "CF = t_c;", "VF = ((t_a ^ t_r) & %s) != 0;" % msb] + zs
    elif op in ("rlc", "rlcw"):
        L += ["local t_c:1 = (t_a & %s) != 0;" % msb, "local t_r:%d = (t_a << 1) | zext(CF);" % sz,
              "CF = t_c;", "VF = ((t_a ^ t_r) & %s) != 0;" % msb] + zs
    elif op in ("rrc", "rrcw"):
        L += ["local t_c:1 = t_a:1 & 1;", "local t_r:%d = (t_a >> 1) | (zext(CF) << %d);" % (sz, top),
              "CF = t_c;", "VF = ((t_a ^ t_r) & %s) != 0;" % msb] + zs
    elif op in ("sra", "sraw"):
        L += ["CF = t_a:1 & 1;", "local t_r:%d = t_a s>> 1;" % sz, "VF = 0;"] + zs
    elif op == "swap":
        L += ["local t_r:1 = (t_a << 4) | (t_a >> 4);"] + zs
    elif op == "da":
        L += ["local t_lo:1 = t_a & 0xf;",
              "local t_k:1 = 0;",
              "if (DF) goto <sub>;",
              "t_k = 6 * (HF || (t_lo > 9));",
              "local t_c:1 = CF || (t_a > 0x99);",
              "t_k = t_k | (0x60 * t_c);",
              "CF = t_c;",
              "local t_r:1 = t_a + t_k;",
              "goto <done>;",
              "<sub>",
              "t_k = (6 * HF) | (0x60 * CF);",
              "t_r = t_a - t_k;",
              "<done>"] + zs
    else:
        raise ValueError(op)
    L.append("%s = t_r;" % d)
    return " ".join(L)


class Gen:
    def __init__(self, plus):
        self.plus = plus
        self.subs = []
        self.done = set()
        self.ins = []
        self.nlocal = 0

    # ------------------------------------------------------------------ plumbing
    def table(self, name, lines):
        if name not in self.done:
            self.done.add(name)
            self.subs.append("\n".join(lines) + "\n")
        return name

    def I(self, s):
        self.ins.append(s)

    def loc(self, base):
        self.nlocal += 1
        return "%s%d" % (base, self.nlocal)

    def code_addr(self, v16, sz=2):
        """(pre, varnode) for a code address made from a 16-bit value in the current segment."""
        if not self.plus:
            return "", v16
        t = self.loc("t_ca")
        return "local %s:3 = (inst_start & 0x3f0000) | zext(%s);" % (t, v16), t

    # ------------------------------------------------------------------ working registers
    def W(self, nib, slot="x"):
        """Working register r0-r15 in the low (L) or high (H) nibble."""
        n = "W%s_%s" % (nib, slot)
        h = self.WA(nib, 1, slot)
        d = "rlo" if nib == "L" else "rhi"
        return self.table(n, ["%s: %s is %s & %s { export %s; }" % (n, d, d, h, h)])

    def WA(self, nib, sz, slot):
        """Address of working register (sz 1) or pair (sz 2): static when the context knows the
        register pointers, else computed from RP0R/RP1R."""
        n = "WA%s%d_%s" % (nib, sz, slot)
        if sz == 1:
            f, b3 = ("lo", "lob3") if nib == "L" else ("hi", "hib3")
            v = f
        else:
            f, b3 = ("pl", "lob3") if nib == "L" else ("ph", "hib3")
            v = "(%s << 1)" % f
        return self.table(n, [
            "%s: wa is rmode=1 & rpk0=1 & %s=0 & %s [ wa = ((rp0 >> 1) << 4) + %s; ] { export *[rf]:%d wa; }" % (n, b3, f, v, sz),
            "%s: wa is rmode=1 & rpk0=1 & %s=1 & %s [ wa = ((rp0 >> 1) << 4) + %s; ] { export *[rf]:%d wa; }" % (n, b3, f, v, sz),
            "%s: wa is rmode=2 & rpk0=1 & %s=0 & %s [ wa = (rp0 << 3) + %s; ] { export *[rf]:%d wa; }" % (n, b3, f, v, sz),
            "%s: wa is rmode=2 & rpk1=1 & %s=1 & %s [ wa = (rp1 << 3) + %s - 8; ] { export *[rf]:%d wa; }" % (n, b3, f, v, sz),
            "%s: %s is %s=0 & %s { local a:2 = 0; wreg_lo(a, %s); export *[rf]:%d a; }" % (n, f, b3, f, v, sz),
            "%s: %s is %s=1 & %s { local a:2 = 0; wreg_hi(a, %s); export *[rf]:%d a; }" % (n, f, b3, f, v, sz),
        ])

    def P(self, nib, slot="x"):
        """Working register pair rr0-rr14: 3-bit field in bits 1-3 (L) or 5-7 (H)."""
        n = "P%s_%s" % (nib, slot)
        h = self.WA(nib, 2, slot)
        d = "rrlo" if nib == "L" else "rrhi"
        return self.table(n, ["%s: %s is %s & %s { export %s; }" % (n, d, d, h, h)])

    # ------------------------------------------------------------------ register file operands
    def R(self, slot="x"):
        """8-bit register R0-R255 (Dx = working register, Ex = system register, Fx = paged)."""
        n = "R_%s" % slot
        w = self.W("L", slot + "i")
        return self.table(n, [
            "%s: %s is hi=0xd & %s { export %s; }" % (n, w, w, w),
            "%s: sysr is hi=0xe & sysr { export sysr; }" % n,
            "%s: sysr is b=0xe7 & sysr { packflags(); export FLAGR; }" % n,
            "%s: rname is hi=0xf & ppk=1 & rname & %s { export %s; }" % (n, self.PA(1, slot), self.PA(1, slot)),
            "%s: rname is hi=0xf & rname & lo { local a:2 = 0; preg(a, lo); export *[rf]:1 a; }" % n,
            "%s: rname is rname & b { export *[rf]:1 b; }" % n,
        ])

    def PA(self, kind, slot):
        """Helpers computing register-file addresses for paged and pair operands."""
        n = "PA%d_%s" % (kind, slot)
        return self.table(n, [{
            1: "%s: pa is ppk=1 & lo [ pa = 0x100 + (page << 4) + lo; ] { export *[rf]:1 pa; }",
            2: "%s: pa is ppk=1 & pl [ pa = 0x100 + (page << 4) + (pl << 1); ] { export *[rf]:2 pa; }",
            3: "%s: pa is pl [ pa = pl << 1; ] { local a:2 = 0; preg(a, pa); export *[rf]:2 a; }",
            4: "%s: pa is pb [ pa = pb << 1; ] { export *[rf]:2 pa; }",
        }[kind] % n])

    def RW(self, slot="x"):
        """Post-write hook for an 8-bit register operand (unpack FLAGR)."""
        n = "RW_%s" % slot
        return self.table(n, ["%s: is b=0xe7 { unpackflags(); }" % n, "%s: is b { }" % n])

    def RR(self, slot="x"):
        """Register pair RR0-RR254 in bits 1-7 (bit 0 belongs to the instruction)."""
        n = "RR_%s" % slot
        p = self.P("L", slot + "i")
        return self.table(n, [
            "%s: %s is hi=0xd & %s { export %s; }" % (n, p, p, p),
            "%s: syspr is hi=0xe & syspr { export syspr; }" % n,
            "%s: syspr is hi=0xe & pl=3 & syspr { packflags(); export RRE6; }" % n,
            "%s: rrname is hi=0xf & ppk=1 & rrname & %s { export %s; }" % (n, self.PA(2, slot), self.PA(2, slot)),
            "%s: rrname is hi=0xf & rrname & %s { export %s; }" % (n, self.PA(3, slot), self.PA(3, slot)),
            "%s: rrname is rrname & %s { export %s; }" % (n, self.PA(4, slot), self.PA(4, slot)),
        ])

    def RRW(self, slot="x"):
        n = "RRW_%s" % slot
        return self.table(n, ["%s: is hi=0xe & pl=3 { unpackflags(); }" % n, "%s: is b { }" % n])

    def IR(self, slot="x"):
        """(R): register-file byte addressed by a register."""
        n = "IR_%s" % slot
        r = self.R(slot + "i")
        return self.table(n, ['%s: "("^%s^")" is %s { local a:2 = zext(%s); export *[rf]:1 a; }' % (n, r, r, r)])

    def IW(self, nib, sz, slot="x"):
        """(r): register-file byte/word addressed by a working register."""
        n = "IW%s%d_%s" % (nib, sz, slot)
        w = self.W(nib, slot + "i")
        return self.table(n, ['%s: "("^%s^")" is %s { local a:2 = zext(%s); export *[rf]:%d a; }' % (n, w, w, w, sz)])

    def IWPI(self, nib, slot="x"):
        """(r)+: register-file byte addressed by a working register, post-increment."""
        n = "IWPI%s_%s" % (nib, slot)
        w = self.W(nib, slot + "i")
        return self.table(n, ['%s: "("^%s^")+" is %s { local a:2 = zext(%s); %s = %s + 1; export *[rf]:1 a; }'
                              % (n, w, w, w, w, w)])

    def RIX(self, sz, slot="x"):
        """N(rx): register file at N + rx (rx in the low nibble of this byte, N in the next)."""
        n = "RIX%d_%s" % (sz, slot)
        w = self.W("L", slot + "i")
        return self.table(n, ['%s: simm8^"("^%s^")" is %s; simm8 { local o:1 = %s + simm8; local a:2 = zext(o); export *[rf]:%d a; }'
                              % (n, w, w, w, sz)])

    # ------------------------------------------------------------------ memory operands
    def mem(self, name, disp, pattern, pre, addr, sz):
        """Memory operand: data memory after SDM (dp=1) or program memory after SPM (dp=0)."""
        L = ["%s: %s is dp=1 & %s { %s export *[data]:%d %s; }" % (name, disp, pattern, pre, sz, addr)]
        if self.plus:
            L.append("%s: %s is dp=0 & %s { %s local ca:3 = (inst_start & 0x3f0000) | zext(%s); export *[code]:%d ca; }"
                     % (name, disp, pattern, pre, addr, sz))
        else:
            L.append("%s: %s is dp=0 & %s { %s export *[code]:%d %s; }" % (name, disp, pattern, pre, sz, addr))
        return self.table(name, L)

    def M(self, nib, sz, slot="x"):
        """(rr)"""
        p = self.P(nib, slot + "i")
        return self.mem("M%s%d_%s" % (nib, sz, slot), '"("^%s^")"' % p, p, "", p, sz)

    def MPI(self, nib, sz, slot="x"):
        """(rr)+"""
        p = self.P(nib, slot + "i")
        return self.mem("MPI%s%d_%s" % (nib, sz, slot), '"("^%s^")+"' % p, p,
                        "local ea:2 = %s; %s = %s + %d;" % (p, p, p, sz), "ea", sz)

    def MPD(self, nib, sz, slot="x"):
        """-(rr)"""
        p = self.P(nib, slot + "i")
        return self.mem("MPD%s%d_%s" % (nib, sz, slot), '"-("^%s^")"' % p, p,
                        "%s = %s - %d; local ea:2 = %s;" % (p, p, sz, p), "ea", sz)

    def MN(self, sz, slot="x"):
        """N(rrx): pair in bits 1-3 of this byte, signed 8-bit offset in the next byte."""
        p = self.P("L", slot + "i")
        return self.mem("MN%d_%s" % (sz, slot), 'simm8^"("^%s^")"' % p, "%s; simm8" % p,
                        "local ea:2 = %s + simm8;" % p, "ea", sz)

    def MNN(self, sz, slot="x"):
        """NN(rrx): pair in bits 1-3 of this byte, 16-bit offset in the next two."""
        p = self.P("L", slot + "i")
        return self.mem("MNN%d_%s" % (sz, slot), 'imm16^"("^%s^")"' % p, "%s; imm16" % p,
                        "local ea:2 = %s + imm16;" % p, "ea", sz)

    def MRX(self, sz, slot="x"):
        """rr(rrx): offset pair in bits 5-7, index pair in bits 1-3."""
        a, b = self.P("H", slot + "i"), self.P("L", slot + "j")
        return self.mem("MRX%d_%s" % (sz, slot), '%s^"("^%s^")"' % (a, b), "%s & %s" % (a, b),
                        "local ea:2 = %s + %s;" % (b, a), "ea", sz)

    def MDIR(self, sz, slot="x"):
        """NN: direct 16-bit address."""
        name = "MD%d_%s" % (sz, slot)
        if not self.plus:
            return self.table(name, ["%s: imm16 is dp=1 & imm16 { export *[data]:%d imm16; }" % (name, sz),
                                     "%s: imm16 is dp=0 & imm16 { export *[code]:%d imm16; }" % (name, sz)])
        return self.table(name, ["%s: imm16 is dp=1 & imm16 { export *[data]:%d imm16; }" % (name, sz),
                                 "%s: imm16 is dp=0 & imm16 & %s { export %s; }" % (name, self.CSEG(sz), self.CSEG(sz))])

    def CSEG(self, sz):
        n = "CSEG%d" % sz
        return self.table(n, ["%s: ca is imm16 [ ca = (inst_start & 0x3f0000) | imm16; ] { export *[code]:%d ca; }" % (n, sz)])

    def MRR(self, sz, slot="x"):
        """(RR): addressed by a general register pair (bit 0 belongs to the instruction)."""
        r = self.RR(slot + "i")
        return self.mem("MRR%d_%s" % (sz, slot), '"("^%s^")"' % r, r, "", r, sz)

    # ------------------------------------------------------------------ flow operands
    def REL(self, slot="x"):
        n = "REL_%s" % slot
        if self.plus:
            return self.table(n, ["%s: ra is simm8 [ ra = (inst_start & 0x3f0000) | ((inst_next + simm8) & 0xffff); ] { export *:1 ra; }" % n])
        return self.table(n, ["%s: ra is simm8 [ ra = (inst_next + simm8) & 0xffff; ] { export *:1 ra; }" % n])

    def CADDR(self, slot="x"):
        n = "CA_%s" % slot
        if self.plus:
            return self.table(n, ["%s: ca is imm16 [ ca = (inst_start & 0x3f0000) | imm16; ] { export *:1 ca; }" % n])
        return self.table(n, ["%s: imm16 is imm16 { export *:1 imm16; }" % n])

    # ------------------------------------------------------------------ stack
    def push(self, which, sz, val, reg):
        sp, spl = ("SSPR", "SSPLR") if which == "s" else ("USPR", "USPLR")
        pre = ""
        if val == "t_ret:2":
            pre = "local t_ret:%d = inst_next; " % (3 if self.plus else 2)
            if not self.plus:
                val = "t_ret"
        if pre:
            return pre + self.push(which, sz, val if val != "t_ret:2" else "t_ret:2", reg) if False else pre + self._push(which, sz, val, reg)
        return self._push(which, sz, val, reg)

    def _push(self, which, sz, val, reg):
        sp, spl = ("SSPR", "SSPLR") if which == "s" else ("USPR", "USPLR")
        if not reg:
            return "%s = %s - %d; *[data]:%d %s = %s;" % (sp, sp, sz, sz, sp, val)
        t = self.loc("t_sa")
        return "%s = %s - %d; local %s:2 = zext(%s); *[rf]:%d %s = %s;" % (spl, spl, sz, t, spl, sz, t, val)

    def pop(self, which, sz, dst, reg):
        sp, spl = ("SSPR", "SSPLR") if which == "s" else ("USPR", "USPLR")
        if not reg:
            return "%s = *[data]:%d %s; %s = %s + %d;" % (dst, sz, sp, sp, sp, sz)
        t = self.loc("t_sa")
        return "local %s:2 = zext(%s); %s = *[rf]:%d %s; %s = %s + %d;" % (t, spl, dst, sz, t, spl, spl, sz)

    def stk(self, which, head, pattern, body_fn):
        """Emit a constructor once per stack location (context sstk/ustk)."""
        ctx = "sstk" if which == "s" else "ustk"
        for reg in (0, 1):
            self.nlocal = 0
            pat = pattern.replace("@S@", "%s=%d" % (ctx, reg))
            self.I("%s is %s { %s }" % (head, pat, body_fn(reg)))

    # ------------------------------------------------------------------ instruction set
    def build(self):
        I = self.I
        plus = self.plus

        # ---------------- two-operand byte ALU: x2 r,r  x3 r,(r)  x4 R,R  x5 R,#N
        for k, op in PLAIN:
            wh, wl = self.W("H", "a"), self.W("L", "b")
            iwl = self.IW("L", 1, "b")
            I(":%s %s,%s is op8=0x%x2 ; %s & %s { %s }" % (op, wh, wl, k, wh, wl, alu(op, 1, wh, wl)))
            I(":%s %s,%s is op8=0x%x3 ; %s & %s { %s }" % (op, wh, iwl, k, wh, iwl, alu(op, 1, wh, iwl)))
            ra, rb, rwb = self.R("a"), self.R("b"), self.RW("b")
            I(":%s %s,%s is op8=0x%x4 ; %s ; %s & %s { %s build %s; }" % (op, rb, ra, k, ra, rb, rwb, alu(op, 1, rb, ra), rwb))
            rwa = self.RW("a")
            I(':%s %s,"#"^imm8 is op8=0x%x5 ; %s & %s ; imm8 { %s build %s; }' % (op, ra, k, ra, rwa, alu(op, 1, ra, "imm8:1"), rwa))
        # byte loads
        wh, wl = self.W("H", "a"), self.W("L", "b")
        I(":ld %s,%s is op8=0xe4 ; %s & %s { %s = %s; }" % (wh, self.IW("L", 1, "b"), wh, self.IW("L", 1, "b"), wh, self.IW("L", 1, "b")))
        I(":ld %s,%s is op8=0xe5 ; %s & %s { %s = %s; }" % (self.IW("H", 1, "a"), wl, self.IW("H", 1, "a"), wl, self.IW("H", 1, "a"), wl))
        ra, rb, rwa, rwb = self.R("a"), self.R("b"), self.RW("a"), self.RW("b")
        I(":ld %s,%s is op8=0xf4 ; %s ; %s & %s { %s = %s; build %s; }" % (rb, ra, ra, rb, rwb, rb, ra, rwb))
        I(':ld %s,"#"^imm8 is op8=0xf5 ; %s & %s ; imm8 { %s = imm8:1; build %s; }' % (ra, ra, rwa, ra, rwa))
        # LD RP0R/RP1R/PPR,#N also update the register pointer context
        I(':ld sysr,"#"^imm8 is op8=0xf5 ; b=0xe8 & sysr ; imm8 & w5 & l3 [ rp0 = w5; rpk0 = 1; rmode = 1 + ((imm8 >> 2) & 1); '
          'globalset(inst_next, rp0); globalset(inst_next, rpk0); globalset(inst_next, rmode); ] { RP0R = imm8; }')
        I(':ld sysr,"#"^imm8 is op8=0xf5 ; b=0xe9 & sysr ; imm8 & w5 [ rp1 = w5; rpk1 = 1; globalset(inst_next, rp1); globalset(inst_next, rpk1); ] { RP1R = imm8; }')
        I(':ld sysr,"#"^imm8 is op8=0xf5 ; b=0xea & sysr ; imm8 & p6 [ page = p6; ppk = 1; globalset(inst_next, page); globalset(inst_next, ppk); ] { PPR = imm8 & 0xfc; }')
        I(':ld sysr,"#"^imm8 is op8=0xf5 ; b=0xeb & sysr ; imm8 [ sstk = (imm8 >> 7) & 1; ustk = (imm8 >> 6) & 1; '
          'globalset(inst_next, sstk); globalset(inst_next, ustk); ] { MODER = imm8; }')
        I(":xch %s,%s is op8=0x16 ; %s & %s ; %s & %s { local t:1 = %s; %s = %s; %s = t; build %s; build %s; }"
          % (rb, ra, ra, rwa, rb, rwb, ra, ra, rb, rb, rwa, rwb))
        # opcode-nibble working register forms: x8 ld r,R  x9 ld R,r  xA djnz  xB jr  xC ld r,#N  xD jp
        wo = self.W("H", "o")
        rel, ca = self.REL("a"), self.CADDR("a")
        I(":ld %s,%s is %s & lo=0x8 ; %s { %s = %s; }" % (wo, ra, wo, ra, wo, ra))
        I(":ld %s,%s is %s & lo=0x9 ; %s & %s { %s = %s; build %s; }" % (ra, wo, wo, ra, rwa, ra, wo, rwa))
        I(":djnz %s,%s is %s & lo=0xa ; %s { %s = %s - 1; if (%s != 0) goto %s; }" % (wo, rel, wo, rel, wo, wo, wo, rel))
        I(':ld %s,"#"^imm8 is %s & lo=0xc ; imm8 { %s = imm8:1; }' % (wo, wo, wo))
        for c, nm, ex in CC:
            if ex is None:
                I(":jr%s %s is hi=0x%x & lo=0xb ; %s { }" % (nm, rel, c, rel))
                I(":jp%s %s is hi=0x%x & lo=0xd ; %s { }" % (nm, ca, c, ca))
            elif ex == "1":
                I(":jr %s is hi=0x%x & lo=0xb ; %s { goto %s; }" % (rel, c, rel, rel))
                I(":jp %s is hi=0x%x & lo=0xd ; %s { goto %s; }" % (ca, c, ca, ca))
            else:
                I(":jr%s %s is hi=0x%x & lo=0xb ; %s { if %s goto %s; }" % (nm, rel, c, rel, ex, rel))
                I(":jp%s %s is hi=0x%x & lo=0xd ; %s { if %s goto %s; }" % (nm, ca, c, ca, ex, ca))

        # ---------------- word ALU: x7 RR,RR / RR,#NN   xE rr,rr / (rr),rr / rr,(rr) / (rr),(rr)
        WORDOPS = [(0x0, "or", 0x07, 0x0e), (0x1, "and", 0x17, 0x1e), (0x2, "sbc", 0x27, 0x2e),
                   (0x3, "adc", 0x37, 0x3e), (0x4, "add", 0x47, 0x4e), (0x5, "sub", 0x57, 0x5e),
                   (0x6, "xor", 0x67, 0x6e), (0x8, "tcm", 0x87, 0x8e), (0x9, "cp", 0x97, 0x9e),
                   (0xA, "tm", 0xa7, 0xae), (0xF, "ld", 0xef, 0xe3)]
        rra, rrb, rrwa, rrwb = self.RR("a"), self.RR("b"), self.RRW("a"), self.RRW("b")
        ph, pl = self.P("H", "a"), self.P("L", "b")
        mh, ml = self.M("H", 2, "a"), self.M("L", 2, "b")
        for k, op, o7, oE in WORDOPS:
            m = op + "w"
            I(":%s %s,%s is op8=0x%02x ; %s & bit0=0 ; %s & %s & bit0=0 { %s build %s; }"
              % (m, rrb, rra, o7, rra, rrb, rrwb, alu(op, 2, rrb, rra), rrwb))
            if op != "ld":
                I(':%s %s,"#"^imm16 is op8=0x%02x ; %s & %s & bit0=1 ; imm16 { %s build %s; }'
                  % (m, rra, o7, rra, rrwa, alu(op, 2, rra, "imm16:2"), rrwa))
            I(":%s %s,%s is op8=0x%02x ; %s & bit4=0 & %s & bit0=0 { %s }" % (m, ph, pl, oE, ph, pl, alu(op, 2, ph, pl)))
            I(":%s %s,%s is op8=0x%02x ; %s & bit4=1 & %s & bit0=0 { %s }" % (m, mh, pl, oE, mh, pl, alu(op, 2, mh, pl)))
            I(":%s %s,%s is op8=0x%02x ; %s & bit4=0 & %s & bit0=1 { %s }" % (m, ph, ml, oE, ph, ml, alu(op, 2, ph, ml)))
            I(":%s %s,%s is op8=0x%02x ; %s & bit4=1 & %s & bit0=1 { %s }" % (m, mh, ml, oE, mh, ml, alu(op, 2, mh, ml)))
        I(':ldw %s,"#"^imm16 is op8=0xbf ; %s & %s & bit0=0 ; imm16 { %s = imm16:2; build %s; }' % (rra, rra, rrwa, rra, rrwa))

        # ---------------- ALD / ALDW (K selects the operation)
        for k, op in KOPS:
            mw = op + "w"
            b = lambda d, s: alu(op, 1, d, s)
            w = lambda d, s: alu(op, 2, d, s)
            # 06: N(rr),#NN / NN(rr),#NN
            mn2, mnn2 = self.MN(2, "a"), self.MNN(2, "a")
            I(':%s %s,"#"^imm16 is op8=0x06 ; ((kf=%d & bit0=1) ... & %s) ; imm16 { %s }' % (mw, mn2, k, mn2, w(mn2, "imm16:2")))
            I(':%s %s,"#"^imm16 is op8=0x06 ; ((kf=%d & bit0=0) ... & %s) ; imm16 { %s }' % (mw, mnn2, k, mnn2, w(mnn2, "imm16:2")))
            # 26: N(rr),R / NN(rr),R
            mn1, mnn1 = self.MN(1, "a"), self.MNN(1, "a")
            rb = self.R("b")
            I(":%s %s,%s is op8=0x26 ; ((kf=%d & bit0=1) ... & %s) ; %s { %s }" % (op, mn1, rb, k, mn1, rb, b(mn1, rb)))
            I(":%s %s,%s is op8=0x26 ; ((kf=%d & bit0=0) ... & %s) ; %s { %s }" % (op, mnn1, rb, k, mnn1, rb, b(mnn1, rb)))
            # 2F: NN,#N   36: NN,#NN   (byte 1 = K,0001; source first)
            md1, md2 = self.MDIR(1, "a"), self.MDIR(2, "a")
            I(':%s %s,"#"^imm8 is op8=0x2f ; kf=%d & lo=1 ; imm8 ; %s { %s }' % (op, md1, k, md1, b(md1, "imm8:1")))
            I(':%s %s,"#"^imm16 is op8=0x36 ; kf=%d & lo=1 ; imm16 ; %s { %s }' % (mw, md2, k, md2, w(md2, "imm16:2")))
            # 60: rr(rrx) ; byte 1 = rr,bsize|rrx,dir  byte 2 = K,r / K,rr
            mrx1, mrx2 = self.MRX(1, "a"), self.MRX(2, "a")
            wl, plb = self.W("L", "b"), self.P("L", "b")
            I(":%s %s,%s is op8=0x60 ; %s & bit4=1 & bit0=0 ; kf=%d & %s { %s }" % (op, wl, mrx1, mrx1, k, wl, b(wl, mrx1)))
            I(":%s %s,%s is op8=0x60 ; %s & bit4=1 & bit0=1 ; kf=%d & %s { %s }" % (op, mrx1, wl, mrx1, k, wl, b(mrx1, wl)))
            I(":%s %s,%s is op8=0x60 ; %s & bit4=0 & bit0=0 ; kf=%d & %s & bit0=0 { %s }" % (mw, plb, mrx2, mrx2, k, plb, w(plb, mrx2)))
            I(":%s %s,%s is op8=0x60 ; %s & bit4=0 & bit0=1 ; kf=%d & %s & bit0=0 { %s }" % (mw, mrx2, plb, mrx2, k, plb, w(mrx2, plb)))
            # 72: R,(rr) / (rr),R
            ml1, rwb = self.M("L", 1, "a"), self.RW("b")
            I(":%s %s,%s is op8=0x72 ; kf=%d & %s & bit0=1 ; %s & %s { %s build %s; }" % (op, rb, ml1, k, ml1, rb, rwb, b(rb, ml1), rwb))
            I(":%s %s,%s is op8=0x72 ; kf=%d & %s & bit0=0 ; %s { %s }" % (op, ml1, rb, k, ml1, rb, b(ml1, rb)))
            # 73: (RR),(rr)
            mrr1 = self.MRR(1, "b")
            I(":%s %s,%s is op8=0x73 ; kf=%d & %s & bit0=0 ; %s & bit0=0 { %s }" % (op, mrr1, ml1, k, ml1, mrr1, b(mrr1, ml1)))
            # 7E: RR,(rr)
            ml2, rrb, rrwb = self.M("L", 2, "a"), self.RR("b"), self.RRW("b")
            I(":%s %s,%s is op8=0x7e ; kf=%d & %s & bit0=0 ; %s & %s & bit0=0 { %s build %s; }" % (mw, rrb, ml2, k, ml2, rrb, rrwb, w(rrb, ml2), rrwb))
            # 7F: R,N(rr) / R,NN(rr)
            I(":%s %s,%s is op8=0x7f ; ((kf=%d & bit0=1) ... & %s) ; %s & %s { %s build %s; }" % (op, rb, mn1, k, mn1, rb, rwb, b(rb, mn1), rwb))
            I(":%s %s,%s is op8=0x7f ; ((kf=%d & bit0=0) ... & %s) ; %s & %s { %s build %s; }" % (op, rb, mnn1, k, mnn1, rb, rwb, b(rb, mnn1), rwb))
            # 86: N(rr),RR / RR,N(rr) / NN(rr),RR / RR,NN(rr)
            I(":%s %s,%s is op8=0x86 ; ((kf=%d & bit0=1) ... & %s) ; %s & bit0=1 { %s }" % (mw, mn2, rrb, k, mn2, rrb, w(mn2, rrb)))
            I(":%s %s,%s is op8=0x86 ; ((kf=%d & bit0=1) ... & %s) ; %s & %s & bit0=0 { %s build %s; }" % (mw, rrb, mn2, k, mn2, rrb, rrwb, w(rrb, mn2), rrwb))
            I(":%s %s,%s is op8=0x86 ; ((kf=%d & bit0=0) ... & %s) ; %s & bit0=1 { %s }" % (mw, mnn2, rrb, k, mnn2, rrb, w(mnn2, rrb)))
            I(":%s %s,%s is op8=0x86 ; ((kf=%d & bit0=0) ... & %s) ; %s & %s & bit0=0 { %s build %s; }" % (mw, rrb, mnn2, k, mnn2, rrb, rrwb, w(rrb, mnn2), rrwb))
            # 96: (r),RR  byte 1 = RR,0  byte 2 = K,r      A6: RR,(r)  byte 1 = K,r  byte 2 = RR,0
            iw2 = self.IW("L", 2, "b")
            rra = self.RR("a")
            I(":%s %s,%s is op8=0x96 ; %s & bit0=0 ; kf=%d & %s { %s }" % (mw, iw2, rra, rra, k, iw2, w(iw2, rra)))
            iw2a = self.IW("L", 2, "a")
            I(":%s %s,%s is op8=0xa6 ; kf=%d & %s ; %s & %s & bit0=0 { %s build %s; }" % (mw, rrb, iw2a, k, iw2a, rrb, rrwb, w(rrb, iw2a), rrwb))
            # B4: R,(rr)+ / (rr)+,R
            mpi1 = self.MPI("L", 1, "a")
            I(":%s %s,%s is op8=0xb4 ; kf=%d & %s & bit0=1 ; %s & %s { %s build %s; }" % (op, rb, mpi1, k, mpi1, rb, rwb, b(rb, mpi1), rwb))
            I(":%s %s,%s is op8=0xb4 ; kf=%d & %s & bit0=0 ; %s { %s }" % (op, mpi1, rb, k, mpi1, rb, b(mpi1, rb)))
            # BE: (rr),RR / (rr),#NN
            I(":%s %s,%s is op8=0xbe ; kf=%d & %s & bit0=1 ; %s & bit0=0 { %s }" % (mw, ml2, rrb, k, ml2, rrb, w(ml2, rrb)))
            I(':%s %s,"#"^imm16 is op8=0xbe ; kf=%d & %s & bit0=0 ; imm16 { %s }' % (mw, ml2, k, ml2, w(ml2, "imm16:2")))
            # C2: R,-(rr) / -(rr),R    C3: RR,-(rr) / -(rr),RR
            mpd1, mpd2 = self.MPD("L", 1, "a"), self.MPD("L", 2, "a")
            I(":%s %s,%s is op8=0xc2 ; kf=%d & %s & bit0=1 ; %s & %s { %s build %s; }" % (op, rb, mpd1, k, mpd1, rb, rwb, b(rb, mpd1), rwb))
            I(":%s %s,%s is op8=0xc2 ; kf=%d & %s & bit0=0 ; %s { %s }" % (op, mpd1, rb, k, mpd1, rb, b(mpd1, rb)))
            I(":%s %s,%s is op8=0xc3 ; kf=%d & %s & bit0=1 ; %s & %s & bit0=0 { %s build %s; }" % (mw, rrb, mpd2, k, mpd2, rrb, rrwb, w(rrb, mpd2), rrwb))
            I(":%s %s,%s is op8=0xc3 ; kf=%d & %s & bit0=0 ; %s & bit0=0 { %s }" % (mw, mpd2, rrb, k, mpd2, rrb, w(mpd2, rrb)))
            # C4: r,NN   C5: NN,r
            wla, mdb = self.W("L", "a"), self.MDIR(1, "b")
            I(":%s %s,%s is op8=0xc4 ; kf=%d & %s ; %s { %s }" % (op, wla, mdb, k, wla, mdb, b(wla, mdb)))
            I(":%s %s,%s is op8=0xc5 ; kf=%d & %s ; %s { %s }" % (op, mdb, wla, k, wla, mdb, b(mdb, wla)))
            # D5: RR,(rr)+ / (rr)+,RR
            mpi2 = self.MPI("L", 2, "a")
            I(":%s %s,%s is op8=0xd5 ; kf=%d & %s & bit0=1 ; %s & %s & bit0=0 { %s build %s; }" % (mw, rrb, mpi2, k, mpi2, rrb, rrwb, w(rrb, mpi2), rrwb))
            I(":%s %s,%s is op8=0xd5 ; kf=%d & %s & bit0=0 ; %s & bit0=0 { %s }" % (mw, mpi2, rrb, k, mpi2, rrb, w(mpi2, rrb)))
            # E2: rr,NN / NN,rr
            pla, md2b = self.P("L", "a"), self.MDIR(2, "b")
            I(":%s %s,%s is op8=0xe2 ; kf=%d & %s & bit0=0 ; %s { %s }" % (mw, pla, md2b, k, pla, md2b, w(pla, md2b)))
            I(":%s %s,%s is op8=0xe2 ; kf=%d & %s & bit0=1 ; %s { %s }" % (mw, md2b, pla, k, pla, md2b, w(md2b, pla)))
            # E6: (r),R  byte 1 = R  byte 2 = K,r      E7: R,(r)  byte 1 = K,r  byte 2 = R
            iw1b, ra = self.IW("L", 1, "b"), self.R("a")
            I(":%s %s,%s is op8=0xe6 ; %s ; kf=%d & %s { %s }" % (op, iw1b, ra, ra, k, iw1b, b(iw1b, ra)))
            iw1a = self.IW("L", 1, "a")
            I(":%s %s,%s is op8=0xe7 ; kf=%d & %s ; %s & %s { %s build %s; }" % (op, rb, iw1a, k, iw1a, rb, rwb, b(rb, iw1a), rwb))
            # F3: (rr),#N
            I(':%s %s,"#"^imm8 is op8=0xf3 ; kf=%d & %s & bit0=0 ; imm8 { %s }' % (op, ml1, k, ml1, b(ml1, "imm8:1")))

        # ---------------- other loads
        rix1, rix2 = self.RIX(1, "b"), self.RIX(2, "b")
        wh = self.W("H", "a")
        I(":ld %s,%s is op8=0xb2 ; (%s ... & %s) { %s = %s; }" % (rix1, wh, wh, rix1, rix1, wh))
        I(":ld %s,%s is op8=0xb3 ; (%s ... & %s) { %s = %s; }" % (wh, rix1, wh, rix1, wh, rix1))
        ph = self.P("H", "a")
        I(":ldw %s,%s is op8=0xde ; ((%s & bit4=0) ... & %s) { %s = %s; }" % (ph, rix2, ph, rix2, ph, rix2))
        I(":ldw %s,%s is op8=0xde ; ((%s & bit4=1) ... & %s) { %s = %s; }" % (rix2, ph, ph, rix2, rix2, ph))
        ml1b = self.M("L", 1, "b")
        I(":ld %s,%s is op8=0xb5 ; %s & %s & bit0=0 { %s = %s; }" % (wh, ml1b, wh, ml1b, wh, ml1b))
        I(":ld %s,%s is op8=0xb5 ; %s & %s & bit0=1 { %s = %s; }" % (ml1b, wh, wh, ml1b, ml1b, wh))
        iwpi, mpib = self.IWPI("H", "a"), self.MPI("L", 1, "b")
        I(":ld %s,%s is op8=0xd7 ; %s & %s & bit0=1 { %s = %s; }" % (iwpi, mpib, iwpi, mpib, iwpi, mpib))
        I(":ld %s,%s is op8=0xd7 ; %s & %s & bit0=0 { %s = %s; }" % (mpib, iwpi, iwpi, mpib, mpib, iwpi))
        # D6: LDPP / LDPD / LDDP / LDDD: dst pair,flag | src pair,flag (flag 1 = data memory)
        pha, plb = self.P("H", "a"), self.P("L", "b")
        for fd in (0, 1):
            for fs in (0, 1):
                nm = "ld" + ("d" if fd else "p") + ("d" if fs else "p")
                spre, sexp = self.space_ref(fs, plb, "t_s")
                dpre, dexp = self.space_ref(fd, pha, "t_d")
                I(':%s "("^%s^")+","("^%s^")+" is op8=0xd6 ; %s & bit4=%d & %s & bit0=%d { %s %s %s = %s; %s = %s + 1; %s = %s + 1; }'
                  % (nm, pha, plb, pha, fd, plb, fs, spre, dpre, dexp, sexp, pha, pha, plb, plb))

        # ---------------- one-operand byte ops (x0 R / x1 (R))
        ra, rwa, ira = self.R("a"), self.RW("a"), self.IR("a")
        ONE = [(0x40, "dec"), (0x50, "inc"), (0x70, "da"), (0x80, "cpl"), (0x90, "clr"),
               (0xa0, "rol"), (0xb0, "rlc"), (0xc0, "ror"), (0xd0, "rrc"), (0xe0, "sra"), (0xf0, "swap")]
        for o, nm in ONE:
            I(":%s %s is op8=0x%02x ; %s & %s { %s build %s; }" % (nm, ra, o, ra, rwa, unary(nm, 1, ra), rwa))
            I(":%s %s is op8=0x%02x ; %s { %s }" % (nm, ira, o + 1, ira, unary(nm, 1, ira)))
        # one-operand word ops (byte 1 = RR,0)
        rra, rrwa = self.RR("a"), self.RRW("a")
        for o, nm in [(0x2f, "sraw"), (0x36, "rrcw"), (0x8f, "rlcw")]:
            I(":%s %s is op8=0x%02x ; %s & %s & bit0=0 { %s build %s; }" % (nm, rra, o, rra, rrwa, unary(nm, 2, rra), rrwa))
        for o, nm in [(0xcf, "decw"), (0xdf, "incw")]:
            I(":%s %s is op8=0x%02x ; %s & %s & bit0=0 { %s build %s; }" % (nm, rra, o, rra, rrwa, unary(nm[:3], 2, rra), rrwa))
        I(":ext %s is op8=0xc6 ; %s & %s & bit0=1 { %s = sext(%s:1); build %s; }" % (rra, rra, rrwa, rra, rra, rrwa))
        rel = self.REL("b")
        I(":dwjnz %s,%s is op8=0xc6 ; %s & %s & bit0=0 ; %s { %s = %s - 1; build %s; if (%s != 0) goto %s; }"
          % (rra, rel, rra, rrwa, rel, rra, rra, rrwa, rra, rel))

        # ---------------- bit operations (working registers)
        wla, wlb = self.W("L", "a"), self.W("L", "b")
        bd = '%s^"."^btn' % wla
        for o, one, two, oper in [(0x0f, "bset", "bor", "|"), (0x1f, "bres", "band", "&"), (0x6f, "bcpl", "bxor", "^")]:
            body1 = {"bset": "%s = %s | (1 << btn);", "bres": "%s = %s & ~(1 << btn);", "bcpl": "%s = %s ^ (1 << btn);"}[one] % (wla, wla)
            I(":%s %s is op8=0x%02x ; %s & bit4=0 & btn { %s }" % (one, bd, o, wla, body1))
            for neg in (0, 1):
                bs = '%s^"%s"^btn2' % (wlb, ".!" if neg else ".")
                I(":%s %s,%s is op8=0x%02x ; %s & bit4=1 & btn ; %s & bit4=%d & btn2 { local t_s:1 = ((%s >> btn2) & 1) ^ %d; local t_d:1 = (%s >> btn) & 1; t_d = t_d %s t_s; %s = (%s & ~(1 << btn)) | (t_d << btn); }"
                  % (two, bd, bs, o, wla, wlb, neg, wlb, neg, wla, oper, wla, wla))
        I(":btset %s is op8=0xf2 ; %s & bit4=0 & btn { local t_v:1 = (%s >> btn) & 1; ZF = (t_v == 0); local t_b7:1 = btn; SF = (t_b7 == 7) && (t_v == 1); VF = 0; %s = %s | (1 << btn); }"
          % (bd, wla, wla, wla, wla))
        # BLD: byte 1 = source bit (flag 1), byte 2 = destination bit with the negate flag
        for neg in (0, 1):
            src = '%s^"%s"^btn' % (wla, ".!" if neg else ".")
            dst = '%s^"."^btn2' % wlb
            I(":bld %s,%s is op8=0xf2 ; %s & bit4=1 & btn ; %s & bit4=%d & btn2 { local t_s:1 = ((%s >> btn) & 1) ^ %d; %s = (%s & ~(1 << btn2)) | (t_s << btn2); }"
              % (dst, src, wla, wlb, neg, wla, neg, wlb, wlb))
        mbt = self.M("L", 1, "a")
        I(':btset %s^"."^btn is op8=0xf6 ; %s & bit4=0 & bit0=0 & btn { local t_v:1 = (%s >> btn) & 1; ZF = (t_v == 0); local t_b7:1 = btn; SF = (t_b7 == 7) && (t_v == 1); VF = 0; %s = %s | (1 << btn); }'
          % (mbt, mbt, mbt, mbt, mbt))
        rel = self.REL("b")
        I(':btjt %s^"."^btn,%s is op8=0xaf ; %s & bit4=0 & btn ; %s { if (((%s >> btn) & 1) != 0) goto %s; }' % (wla, rel, wla, rel, wla, rel))
        I(':btjf %s^"."^btn,%s is op8=0xaf ; %s & bit4=1 & btn ; %s { if (((%s >> btn) & 1) == 0) goto %s; }' % (wla, rel, wla, rel, wla, rel))
        mh1 = self.M("H", 1, "b")
        ph = self.P("H", "c")
        I(":cpjfi %s,%s,%s is op8=0x9f ; %s & bit4=0 & %s & %s ; %s { local t_v:1 = %s; if (%s != t_v) goto %s; %s = %s + 1; }"
          % (wla, mh1, rel, wla, mh1, ph, rel, mh1, wla, rel, ph, ph))
        I(":cpjti %s,%s,%s is op8=0x9f ; %s & bit4=1 & %s & %s ; %s { local t_v:1 = %s; if (%s == t_v) goto %s; %s = %s + 1; }"
          % (wla, mh1, rel, wla, mh1, ph, rel, mh1, wla, rel, ph, ph))

        # ---------------- multiply / divide
        pha, wlb = self.P("H", "a"), self.W("L", "b")
        I(":mul %s,%s is op8=0x4f ; %s & bit4=0 & %s { local t_r:2 = zext(%s:1) * zext(%s); CF = t_r:1 & 1; ZF = (t_r >> 8) == 0; SF = (t_r >> 15) != 0; VF = (t_r & 0xff) == 0; DF = 0; %s = t_r; }"
          % (pha, wlb, pha, wlb, pha, wlb, pha))
        # DIV: a zero divisor traps through the vector at program address 0002 like a CALL
        tpre, tvec = self.code_addr("t_vec")
        ret = self.push("s", 2, "t_ret:2", 0)
        reg = self.push("s", 2, "t_ret:2", 1)
        div_body = ("local t_d:1 = %s; if (t_d != 0) goto <divide>; local t_vec:2 = *[code]:2 2:%d; " % (wlb, 3 if plus else 2)
                    + "@PUSH@ " + tpre + (" call [%s];" % tvec) + " goto <end>; <divide> "
                    "local t_n:2 = %s; DF = 1; if ((t_n >> 8) >= zext(t_d)) goto <ovf>; "
                    "local t_q:2 = t_n / zext(t_d); local t_m:2 = t_n %% zext(t_d); "
                    "%s = (t_m << 8) | (t_q & 0xff); CF = 1; ZF = (t_q == 0); SF = (t_m == 0); goto <end>; "
                    "<ovf> CF = 0; <end>") % (pha, pha)
        I(":div %s,%s is op8=0x5f ; %s & bit4=0 & %s & sstk=0 { %s }" % (pha, wlb, pha, wlb, div_body.replace("@PUSH@", ret)))
        I(":div %s,%s is op8=0x5f ; %s & bit4=0 & %s & sstk=1 { %s }" % (pha, wlb, pha, wlb, div_body.replace("@PUSH@", reg)))
        # DIVWS: one step of the 32/16 division the manual's DIVSTEP routine performs (16 steps
        # then RLCW on the low pair): the quotient bit of each step is carried in C into the next.
        rra, pha, plb = self.RR("a"), self.P("H", "b"), self.P("L", "c")
        I(":divws %s,%s,%s is op8=0x56 ; %s & bit0=0 ; %s & bit4=0 & %s & bit0=0 { "
          "local t_h:2 = %s; local t_l:2 = %s; local t_s:2 = %s; local t_o:1 = (t_h >> 15) != 0; "
          "t_h = (t_h << 1) | (t_l >> 15); t_l = (t_l << 1) | zext(CF); "
          "CF = t_o || (t_h >= t_s); t_h = t_h - t_s * zext(CF); %s = t_h; %s = t_l; ZF = 1; SF = 0; VF = 0; HF = 0; }"
          % (pha, plb, rra, rra, pha, plb, pha, plb, rra, pha, plb))

        # ---------------- register pointers, page pointer, memory selection
        I(':srp "#"^w5 is op8=0xc7 ; w5 & l3=0 [ rp0 = w5; rpk0 = 1; rmode = 1; '
          'globalset(inst_next, rp0); globalset(inst_next, rpk0); globalset(inst_next, rmode); ] { RP0R = w5 << 3; }')
        I(':srp0 "#"^w5 is op8=0xc7 ; w5 & l3=4 [ rpk1 = rpk1 & (rmode >> 1); rp0 = w5; rpk0 = 1; rmode = 2; '
          'globalset(inst_next, rp0); globalset(inst_next, rpk0); globalset(inst_next, rpk1); globalset(inst_next, rmode); ] '
          '{ RP0R = (w5 << 3) | 4; RP1R = RP1R | 4; }')
        I(':srp1 "#"^w5 is op8=0xc7 ; w5 & l3=5 [ rpk0 = rpk0 & (rmode >> 1); rp1 = w5; rpk1 = 1; rmode = 2; '
          'globalset(inst_next, rp1); globalset(inst_next, rpk1); globalset(inst_next, rpk0); globalset(inst_next, rmode); ] '
          '{ RP1R = (w5 << 3) | 4; RP0R = RP0R | 4; }')
        I(':spp "#"^p6 is op8=0xc7 ; p6 & l2=2 [ page = p6; ppk = 1; globalset(inst_next, page); globalset(inst_next, ppk); ] { PPR = p6 << 2; }')
        I(':sdm is op8=0xfe [ dp = 1; globalset(inst_next, dp); ] { FLAGR = FLAGR | 1; }')
        I(':spm is op8=0xee [ dp = 0; globalset(inst_next, dp); ] { FLAGR = FLAGR & 0xfe; }')

        # ---------------- misc
        I(":ei is op8=0x00 { CICR = CICR | 0x10; }")
        I(":di is op8=0x10 { CICR = CICR & 0xef; }")
        I(":scf is op8=0x01 { CF = 1; }")
        I(":rcf is op8=0x11 { CF = 0; }")
        I(":ccf is op8=0x61 { CF = !CF; }")
        I(":nop is op8=0xff { }")
        I(":halt is op8=0xbf ; b=0x01 { halt(); }")
        I(":wfi is op8=0xef ; b=0x01 { wait_for_interrupt(); }")
        I(":etrap is op8=0xce { emulator_trap(); }")
        if plus:
            I(":eret is op8=0xef ; b=0x31 { local t_ra:3 = emulator_return(); return [t_ra]; }")
        else:
            I(":eret is op8=0xef ; b=0x31 { local t_ra:2 = emulator_return(); return [t_ra]; }")

        # ---------------- stack
        ra, rwa, ira = self.R("a"), self.RW("a"), self.IR("a")
        rra, rrwa = self.RR("a"), self.RRW("a")
        S = self.stk
        S("s", ":push %s" % ra, "op8=0x66 & @S@ ; %s" % ra, lambda r: self.push("s", 1, ra, r))
        S("s", ":push %s" % ira, "op8=0xf7 & @S@ ; %s" % ira, lambda r: self.push("s", 1, ira, r))
        S("s", ":pop %s" % ra, "op8=0x76 & @S@ ; %s & %s" % (ra, rwa), lambda r: self.pop("s", 1, ra, r) + " build %s;" % rwa)
        S("s", ":pop %s" % ira, "op8=0x77 & @S@ ; %s" % ira, lambda r: self.pop("s", 1, ira, r))
        S("u", ":pushu %s" % ra, "op8=0x30 & @S@ ; %s" % ra, lambda r: self.push("u", 1, ra, r))
        S("u", ":pushu %s" % ira, "op8=0x31 & @S@ ; %s" % ira, lambda r: self.push("u", 1, ira, r))
        S("u", ":popu %s" % ra, "op8=0x20 & @S@ ; %s & %s" % (ra, rwa), lambda r: self.pop("u", 1, ra, r) + " build %s;" % rwa)
        S("u", ":popu %s" % ira, "op8=0x21 & @S@ ; %s" % ira, lambda r: self.pop("u", 1, ira, r))
        S("s", ":pushw %s" % rra, "op8=0x74 & @S@ ; %s & bit0=0" % rra, lambda r: self.push("s", 2, rra, r))
        S("s", ":popw %s" % rra, "op8=0x75 & @S@ ; %s & %s & bit0=0" % (rra, rrwa), lambda r: self.pop("s", 2, rra, r) + " build %s;" % rrwa)
        S("u", ":pushuw %s" % rra, "op8=0xb6 & @S@ ; %s & bit0=0" % rra, lambda r: self.push("u", 2, rra, r))
        S("u", ":popuw %s" % rra, "op8=0xb7 & @S@ ; %s & %s & bit0=0" % (rra, rrwa), lambda r: self.pop("u", 2, rra, r) + " build %s;" % rrwa)
        S("s", ':push "#"^imm8', "op8=0x8f & @S@ ; b=0xf1 ; imm8", lambda r: self.push("s", 1, "imm8:1", r))
        S("u", ':pushu "#"^imm8', "op8=0x8f & @S@ ; b=0xf3 ; imm8", lambda r: self.push("u", 1, "imm8:1", r))
        S("s", ':pushw "#"^imm16', "op8=0x8f & @S@ ; b=0xc1 ; imm16", lambda r: self.push("s", 2, "imm16:2", r))
        S("u", ':pushuw "#"^imm16', "op8=0x8f & @S@ ; b=0xc3 ; imm16", lambda r: self.push("u", 2, "imm16:2", r))
        pn = self.table("PEAN", ['PEAN: simm8^"("^%s^")" is %s & bit0=0 ; simm8 { local ea:2 = %s + simm8; export ea; }' % (rra, rra, rra)])
        pnn = self.table("PEANN", ['PEANN: imm16le^"("^%s^")" is %s & bit0=1 ; imm16le { local ea:2 = %s + imm16le; export ea; }' % (rra, rra, rra)])
        for which, x, nm in (("s", 1, "pea"), ("u", 3, "peau")):
            for t, pair_bit in ((pn, 0), (pnn, 1)):
                # SLEIGH does not backtrack from a root constructor when its subtable
                # cannot match. Test the pair register's mode bit at the root so the
                # short and long displacement forms cannot shadow each other.
                S(which, ":%s %s" % (nm, t),
                  "op8=0x8f & @S@ ; b=0x%02x ; ((bit0=%d) ... & %s)" % (x, pair_bit, t),
                  lambda r, w=which, t=t: self.push(w, 2, t, r))

        # ---------------- calls, jumps, returns
        ca = self.CADDR("a")
        S("s", ":call %s" % ca, "op8=0xd2 & @S@ ; %s" % ca, lambda r: self.push("s", 2, "t_ret:2", r) + " call %s;" % ca)

        def callind(r):
            pre, t = self.code_addr("t_ct")
            return "local t_ct:2 = %s; %s %s call [%s];" % (rra, self.push("s", 2, "t_ret:2", r), pre, t)
        S("s", ':call "("^%s^")"' % rra, "op8=0x74 & @S@ ; %s & bit0=1" % rra, callind)
        pre, t = self.code_addr("t_jt")
        I(':jp "("^%s^")" is op8=0xd4 ; %s & bit0=0 { local t_jt:2 = %s; %s goto [%s]; }' % (rra, rra, rra, pre, t))

        def ret(r):
            pre, t = self.code_addr("t_rpc")
            return "local t_rpc:2 = 0; %s %s return [%s];" % (self.pop("s", 2, "t_rpc", r), pre, t)
        S("s", ":ret", "op8=0x46 & @S@", ret)

        def iret(r, csr):
            s = self.pop("s", 1, "FLAGR", r) + " unpackflags();"
            if csr:
                s += " " + self.pop("s", 1, "CSR", r)
            s += " local t_rpc:2 = 0; " + self.pop("s", 2, "t_rpc", r) + " CICR = CICR | 0x10;"
            if plus:
                s += " local t_ra:3 = (zext(CSR) << 16) | zext(t_rpc); return [t_ra];"
            else:
                s += " return [t_rpc];"
            return s
        if plus:
            S("s", ":iret", "op8=0xd3 & @S@ & encsr=0", lambda r: iret(r, False))
            S("s", ":iret", "op8=0xd3 & @S@ & encsr=1", lambda r: iret(r, True))
        else:
            S("s", ":iret", "op8=0xd3 & @S@", lambda r: iret(r, False))

        if plus:
            # far calls / jumps (CSR = code segment)
            self.table("FARA", ["FARA: ft is seg6 ; imm16 [ ft = (seg6 << 16) | imm16; ] { export *:1 ft; }"])
            self.table("FAR", ['FAR: seg6^","^imm16 is (seg6 ; imm16) & FARA { CSR = seg6; export FARA; }'])
            S("s", ":calls FAR", "op8=0x3f & @S@ ; top2=1 ... & FAR",
              lambda r: self.push("s", 2, "t_ret:2", r) + " " + self.push("s", 1, "CSR", r)
              + " build FAR; call FAR;")
            I(":jps FAR is op8=0x3f ; top2=3 ... & FAR { build FAR; goto FAR; }")
            pl, rb = self.P("L", "a"), self.R("b")
            S("s", ':calls "("^%s^")","("^%s^")"' % (rb, pl), "op8=0x73 & @S@ ; kf=4 & %s & bit0=1 ; %s" % (pl, rb),
              lambda r: self.push("s", 2, "t_ret:2", r) + " " + self.push("s", 1, "CSR", r)
              + " CSR = %s; local t_ft:3 = (zext(CSR) << 16) | zext(%s); call [t_ft];" % (rb, pl))
            I(':jps "("^%s^")","("^%s^")" is op8=0x73 ; kf=0xc & %s & bit0=1 ; %s { CSR = %s; local t_ft:3 = (zext(CSR) << 16) | zext(%s); goto [t_ft]; }'
              % (rb, pl, pl, rb, rb, pl))
            S("s", ":rets", "op8=0xf6 & @S@ ; b=0x01",
              lambda r: self.pop("s", 1, "CSR", r) + " local t_rpc:2 = 0; " + self.pop("s", 2, "t_rpc", r)
              + " local t_ra:3 = (zext(CSR) << 16) | zext(t_rpc); return [t_ra];")
            # frame pointers
            for which, o, nm in (("s", 0xd4, "link"), ("u", 0xb6, "linku")):
                S(which, ':%s %s,"#"^imm8' % (nm, rra), "op8=0x%02x & @S@ ; %s & %s & bit0=1 ; imm8" % (o, rra, rrwa),
                  lambda r, w=which: self.link(w, r, rra) + " build %s;" % rrwa)
            for which, o, nm in (("s", 0x75, "unlink"), ("u", 0xb7, "unlinku")):
                S(which, ":%s %s" % (nm, rra), "op8=0x%02x & @S@ ; %s & %s & bit0=1" % (o, rra, rrwa),
                  lambda r, w=which: self.unlink(w, r, rra) + " build %s;" % rrwa)

    def link(self, which, reg, rr):
        sp, spl = ("SSPR", "SSPLR") if which == "s" else ("USPR", "USPLR")
        if not reg:
            return "%s = %s - 2; *[data]:2 %s = %s; %s = %s; %s = %s - zext(imm8:1);" % (sp, sp, sp, rr, rr, sp, sp, sp)
        return ("%s = %s - 1; local t_sa:2 = zext(%s); *[rf]:1 t_sa = %s:1; %s = (%s & 0xff00) | zext(%s); %s = %s - imm8:1;"
                % (spl, spl, spl, rr, rr, rr, spl, spl, spl))

    def unlink(self, which, reg, rr):
        sp, spl = ("SSPR", "SSPLR") if which == "s" else ("USPR", "USPLR")
        if not reg:
            return "%s = %s; %s = *[data]:2 %s; %s = %s + 2;" % (sp, rr, rr, sp, sp, sp)
        return ("%s = %s:1; local t_sa:2 = zext(%s); local t_lo:1 = *[rf]:1 t_sa; %s = (%s & 0xff00) | zext(t_lo); %s = %s + 1;"
                % (spl, rr, spl, rr, rr, spl, spl))

    def space_ref(self, data, rr, tag):
        """(pre, deref) for an explicit data/program memory reference (LDPP family)."""
        if data:
            return "", "*[data]:1 %s" % rr
        if self.plus:
            return "local %s:3 = (inst_start & 0x3f0000) | zext(%s);" % (tag, rr), "*[code]:1 %s" % tag
        return "", "*[code]:1 %s" % rr

    # ------------------------------------------------------------------ output
    def render(self):
        self.build()
        hdr = ["# Generated by tools/gen_st9.py (%s). Do not edit." % ("ST9+" if self.plus else "ST9"), ""]
        names = ['"%s"' % regname(v) for v in range(256)]
        pnames = ['"%s"' % pairname(v * 2) for v in range(128)]
        hdr.append("attach names [ rname ] [ %s ];" % " ".join(names))
        hdr.append("attach names [ rrname ] [ %s ];" % " ".join(pnames))
        hdr.append("")
        hdr.append("define token opb (8) op8 = (0,7);")
        hdr.append("")
        return "\n".join(hdr + self.subs + [""] + self.ins) + "\n"


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data" / "languages")
    for plus, name in ((False, "st9_gen.sinc"), (True, "st9p_gen.sinc")):
        (out / name).write_text(Gen(plus).render())


if __name__ == "__main__":
    main()
