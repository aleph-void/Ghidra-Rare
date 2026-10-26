#!/usr/bin/env python3
"""ADSP-218x emulator cases.  Every expected value was worked out by hand from the ADSP-2100
Family User's Manual (3rd ed.) descriptions cited in the comments; the encoder (asm.py) only
packs fields.  Code is placed at pm:0100 and runs until the PC reaches the end of the main
code (default: the last word + 1).

  cases.py [--broken]   (--broken flips one expectation so the harness must report a failure)
  cases.py --listing    one line per code word (word, case) for checking with unidasm

Output format (read by ADSPEmuTest.java):
  case <name> / code <24-bit words as 6 hex digits each> / main <n words>
  set|expect <reg> <value>  or  set|expect <space>:<hex word address> <value>
  end
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asm import *  # noqa: E402,F403

B = 0x100
CASES = []


def case(name, code, sets=(), expects=(), main=None):
    CASES.append((name, code, dict(sets), dict(expects), main))


# ---------------- loads and register widths (15-64..15-66, 15-63) ----------------
case("load dreg immediate", [t6("AX0", 0x1234)], expects={"AX0": 0x1234})
case("MR1 load sign-extends into MR2", [t6("MR1", 0x8000)], sets={"MR2": 0},
     expects={"MR1": 0x8000, "MR2": 0xffff})
case("I/M/L are 14 bits: I3=AX0, M3=AX0, L3=AX0",
     [t17("I3", "AX0"), t17("M3", "AX0"), t17("L3", "AX0")], sets={"AX0": 0xffff},
     expects={"I3": 0x3fff, "M3": 0xffff, "L3": 0x3fff})
case("load non-data register 14-bit immediate", [t7("I5", 0x1234), t7("M2", 0x3ffe)],
     expects={"I5": 0x1234, "M2": 0xfffe})
case("register move from MR2 (sign-extended)", [t17("AX0", "MR2")], sets={"MR2": 0xff80},
     expects={"AX0": 0xff80})
case("direct DM write and read into I1", [t3("AX0", 0x123, write=True), t3("I1", 0x123)],
     sets={"AX0": 0xc005}, expects={"dm:0123": 0xc005, "I1": 0x0005})
case("ASTAT write sets flags, read rebuilds it", [t7("ASTAT", 0x0009), t17("AX0", "ASTAT")],
     expects={"AZ": 1, "AC": 1, "AN": 0, "AX0": 0x0009})

# ---------------- ALU (15-21..15-40) ----------------
case("add overflow 7fff+1", [t9(alu("X+Y"))], sets={"AX0": 0x7fff, "AY0": 1},
     expects={"AR": 0x8000, "AV": 1, "AN": 1, "AC": 0, "AZ": 0})
case("subtract with borrow 5-7", [t9(alu("X-Y"))], sets={"AX0": 5, "AY0": 7},
     expects={"AR": 0xfffe, "AC": 0, "AN": 1, "AV": 0})
case("X-Y+C-1 with C=1", [t9(alu("X-Y+C-1"))], sets={"AX0": 0x10, "AY0": 1, "AC": 1},
     expects={"AR": 0x000f, "AC": 1})
case("Y-X into AF", [t9(alu("Y-X"), z=1)], sets={"AX0": 5, "AY0": 3},
     expects={"AF": 0xfffe, "AC": 0, "AN": 1})
case("AND constant 0x0010", [t9(alu("AND"), const=0x0010)], sets={"AX0": 0x00ff, "AC": 1},
     expects={"AR": 0x0010, "AZ": 0, "AC": 0, "AV": 0})
case("PASS constant 3 via Y+1 (constant 2)", [t9(alu("Y+1"), const=0x0002)],
     expects={"AR": 3})
case("X + constant 0x1000 (YY=11)", [t9(alu("X+Y"), const=0x1000)], sets={"AX0": 0x0234},
     expects={"AR": 0x1234})
case("ABS 0x8000", [t9(alu("ABS"))], sets={"AX0": 0x8000},
     expects={"AR": 0x8000, "AV": 1, "AN": 1, "AS": 1, "AC": 0})
case("NOT AY0 into AF", [t9(alu("NOTY"), z=1)], sets={"AY0": 0x00f0}, expects={"AF": 0xff0f})
case("IF EQ taken, then IF EQ skipped (the add cleared AZ)",
     [t9(alu("X+Y"), cond="EQ"), t9(alu("Y+1", y="AY1"), z=1, cond="EQ")],
     sets={"AZ": 1, "AX0": 2, "AY0": 3, "AY1": 7, "AF": 0x55},
     expects={"AR": 5, "AF": 0x55})
case("AR_SAT positive overflow saturates", [t9(alu("X+Y"))],
     sets={"AR_SAT": 1, "AX0": 0x7fff, "AY0": 1}, expects={"AR": 0x7fff, "AV": 1})
case("AR_SAT negative overflow saturates", [t9(alu("X+Y"))],
     sets={"AR_SAT": 1, "AX0": 0x8000, "AY0": 0x8000}, expects={"AR": 0x8000, "AV": 1, "AC": 1})
case("AV_LATCH keeps AV", [t9(alu("X+Y"))], sets={"AV_LATCH": 1, "AV": 1, "AX0": 1, "AY0": 1},
     expects={"AR": 2, "AV": 1})
case("NONE = AX0 - AY0 sets flags only", [t8(alu("X-Y"), 0, "AR", "AR") | 0xaa],
     sets={"AR": 0x77, "AX0": 4, "AY0": 4}, expects={"AR": 0x77, "AZ": 1, "AC": 1})

# ---------------- MAC (15-41..15-49, 2.3) ----------------
case("MAC SS fractional 0.5*0.5", [t9(mac("SS"))], sets={"MX0": 0x4000, "MY0": 0x4000},
     expects={"MR2": 0, "MR1": 0x2000, "MR0": 0, "MV": 0})
case("MAC integer mode 3*5", [t9(mac("SS"))], sets={"M_MODE": 1, "MX0": 3, "MY0": 5},
     expects={"MR0": 15, "MR1": 0, "MR2": 0})
case("MR + (-1)*3 integer", [t9(mac("MR+SS"))],
     sets={"M_MODE": 1, "MR0": 10, "MR1": 0, "MR2": 0, "MX0": 0xffff, "MY0": 3},
     expects={"MR0": 7, "MR1": 0, "MR2": 0})
case("UU ffff*ffff sets MV", [t9(mac("UU"))], sets={"M_MODE": 1, "MX0": 0xffff, "MY0": 0xffff},
     expects={"MR0": 0x0001, "MR1": 0xfffe, "MR2": 0, "MV": 1})
case("MR - (SU) -2 * 65535", [t9(mac("MR-SU"))],
     sets={"M_MODE": 1, "MR0": 0, "MR1": 0, "MR2": 0, "MX0": 0xfffe, "MY0": 0xffff},
     expects={"MR0": 0xfffe, "MR1": 0x0001, "MR2": 0, "MV": 0})
case("MR = MR (RND) midpoint rounds to even", [t9((MAC["MR+RND"], 3, 0))],
     sets={"MR2": 0, "MR1": 0x1234, "MR0": 0x8000}, expects={"MR1": 0x1234, "MR0": 0})
case("MR = MR (RND) above midpoint", [t9((MAC["MR+RND"], 3, 0))],
     sets={"MR2": 0, "MR1": 0x1234, "MR0": 0x8001}, expects={"MR1": 0x1235, "MR0": 0x0001})
case("MF = MX0*MY0 integer", [t9(mac("SS"), z=1)], sets={"M_MODE": 1, "MX0": 0x100, "MY0": 0x100},
     expects={"MF": 0x0001})
case("SAT MR positive", [SATMR], sets={"MV": 1, "MR2": 0, "MR1": 0x8000, "MR0": 0},
     expects={"MR2": 0, "MR1": 0x7fff, "MR0": 0xffff})
case("SAT MR negative", [SATMR], sets={"MV": 1, "MR2": 0xfffe, "MR1": 0x1234, "MR0": 0},
     expects={"MR2": 0xffff, "MR1": 0x8000, "MR0": 0})
case("xop*xop -3 squared", [t9(mac("SS"), square=True)], sets={"M_MODE": 1, "MX0": 0xfffd},
     expects={"MR0": 9, "MR1": 0, "MR2": 0})
case("fractional 0x8000*0x8000 overflows (MV)", [t9(mac("SS"))],
     sets={"MX0": 0x8000, "MY0": 0x8000}, expects={"MR2": 0, "MR1": 0x8000, "MR0": 0, "MV": 1})

# ---------------- shifter (2.4, Table 2.4/2.5, 15-50..15-62) ----------------
case("ASHIFT SI (HI) by SE=-1", [t16("ASHIFT HI", "SI")], sets={"SI": 0x8001, "SE": 0xffff},
     expects={"SR1": 0xc000, "SR0": 0x8000})
case("SR OR LSHIFT SI (LO) by 4", [t16("LSHIFT LO OR", "SI")],
     sets={"SR1": 0x1234, "SR0": 0, "SI": 0x00f0, "SE": 4}, expects={"SR1": 0x1234, "SR0": 0x0f00})
case("LSHIFT BY -4 (HI)", [t15("LSHIFT HI", "SI", -4)], sets={"SI": 0xf000},
     expects={"SR1": 0x0f00, "SR0": 0})
case("ASHIFT BY -4 (LO)", [t15("ASHIFT LO", "SI", -4)], sets={"SI": 0x8000},
     expects={"SR1": 0xffff, "SR0": 0xf800})
case("EXP 0x0100 (HI)", [t16("EXP HI", "SI")], sets={"SI": 0x0100, "SS": 1},
     expects={"SE": 0xfffa, "SS": 0})
case("EXP 0xff00 (HI)", [t16("EXP HI", "SI")], sets={"SI": 0xff00}, expects={"SE": 0xfff9, "SS": 1})
case("NORM 0x0100 (HI) with SE=-6", [t16("NORM HI", "SI")], sets={"SI": 0x0100, "SE": 0xfffa},
     expects={"SR1": 0x4000, "SR0": 0})
case("EXP (HIX) with AV set", [t16("EXP HIX", "AR")], sets={"AR": 0x8000, "AV": 1},
     expects={"SE": 1, "SS": 0})
case("EXP (LO) after all-sign upper half", [t16("EXP LO", "SI")],
     sets={"SE": 0xfff1, "SS": 0, "SI": 0x00ff}, expects={"SE": 0xffe9})
case("EXPADJ updates SB", [t16("EXPADJ", "SI")], sets={"SB": 0xfff0, "SI": 0x0fff},
     expects={"SB": 0xfffd})

# ---------------- divide primitives (2.2.7) ----------------
case("DIVS AY1,AX0", [t24("AY1", "AX0")], sets={"AY1": 0, "AY0": 0x8001, "AX0": 0x8000},
     expects={"AQ": 1, "AF": 1, "AY0": 3})
case("DIVQ AX0 (AQ=0 subtracts)", [t23("AX0")],
     sets={"AQ": 0, "AF": 0x0010, "AX0": 3, "AY0": 0x8000},
     expects={"AQ": 0, "AF": 0x001b, "AY0": 0x0001})
case("unsigned 100/7 with 16 DIVQ in a DO loop",
     [t7("CNTR", 16), t11(B + 2, "CE"), t23("AX0")],
     sets={"AF": 0, "AY0": 200, "AX0": 7, "AQ": 0}, expects={"AY0": 14})

# ---------------- data address generators (4.2) ----------------
case("DM read with post-modify", [t4(None, 0, "AX0", 0, 0)],
     sets={"I0": 0x10, "M0": 2, "L0": 0, "dm:0010": 0xbeef}, expects={"AX0": 0xbeef, "I0": 0x12})
case("circular buffer 5,6,4 (manual 4.2.4.3)", [t21(0, 0), t21(0, 0)],
     sets={"I0": 5, "M0": 1, "L0": 3}, expects={"I0": 4})
case("circular buffer 9,12,10,8 (manual 4.2.4.4)", [t21(0, 0)] * 3,
     sets={"I0": 9, "M0": 3, "L0": 5}, expects={"I0": 8})
case("circular buffer M=-1: 5,4,6", [t21(0, 0)] * 2,
     sets={"I0": 5, "M0": 0xffff, "L0": 3}, expects={"I0": 6})
case("bit-reversed DAG1 address", [t4(None, 0, "AX0", 0, 0)],
     sets={"BIT_REV": 1, "I0": 1, "M0": 0, "L0": 0, "dm:2000": 0x5555},
     expects={"AX0": 0x5555, "I0": 1})
case("DAG2 not bit-reversed", [t4(None, 0, "AX0", 4, 4)],
     sets={"BIT_REV": 1, "I4": 1, "M4": 0, "L4": 0, "dm:0001": 0x6666}, expects={"AX0": 0x6666})
case("DM(I4,M4) = immediate", [t2(4, 0, 0x1234)], sets={"I4": 0x20, "M4": 1, "L4": 0},
     expects={"dm:0020": 0x1234, "I4": 0x21})
case("PM read: upper 16 bits to dreg, low 8 to PX", [t5(None, 0, "AX0", 4, 0)],
     sets={"I4": 0x50, "M4": 0, "L4": 0, "pm:0050": 0xabcdef}, expects={"AX0": 0xabcd, "PX": 0xef})
case("PM write from MY0 and PX", [t5(None, 0, "MY0", 5, 1, write=True)],
     sets={"I5": 0x60, "M5": 1, "L5": 0, "PX": 0x12, "MY0": 0x3456},
     expects={"pm:0060": 0x345612, "I5": 0x61})

# ---------------- multifunction (15.4, read first / write last) ----------------
case("ALU with DM read reads AX0 before the load", [t4(alu("X+Y"), 0, "AX0", 0, 0)],
     sets={"AX0": 1, "AY0": 2, "I0": 0x30, "M0": 0, "L0": 0, "dm:0030": 7},
     expects={"AR": 3, "AX0": 7})
case("DM write of old AR, then AR = AX0 + AY0", [t4(alu("X+Y"), 0, "AR", 0, 0, write=True)],
     sets={"AR": 9, "AX0": 1, "AY0": 2, "I0": 0x31, "M0": 0, "L0": 0},
     expects={"dm:0031": 9, "AR": 3})
case("MAC with dual memory read",
     [t1(mac("MR+SS"), "MX0", "MY0", 0, 0, 4, 4)],
     sets={"M_MODE": 1, "MX0": 2, "MY0": 3, "MR0": 1, "MR1": 0, "MR2": 0,
           "I0": 0x40, "M0": 1, "L0": 0, "I4": 0x70, "M4": 1, "L4": 0,
           "dm:0040": 5, "pm:0070": 0x000700},
     expects={"MR0": 7, "MX0": 5, "MY0": 7, "PX": 0, "I0": 0x41, "I4": 0x71})
case("ALU with register move", [t8(alu("X+Y"), 0, "AX0", "MR0")],
     sets={"AX0": 1, "AY0": 2, "MR0": 0x44}, expects={"AR": 3, "AX0": 0x44})
case("shift with DM read uses the old SI", [t12("LSHIFT LO", "SI", "SI", 0, 0)],
     sets={"SI": 0x0003, "SE": 1, "I0": 0x50, "M0": 0, "L0": 0, "dm:0050": 0x0100},
     expects={"SR0": 0x0006, "SR1": 0, "SI": 0x0100})

# ---------------- sequencer (3.2, 15-74..15-91) ----------------
case("CNTR load pushes, POP CNTR restores", [t7("CNTR", 5), t7("CNTR", 7), t26(cp=1)],
     sets={"CNTR": 0, "CNTSP": 0}, expects={"CNTR": 5, "CNTSP": 1})
case("DO UNTIL CE: 3 passes",
     [t7("CNTR", 3), t11(B + 2, "CE"), t9(alu("X+Y", x="AR"))],
     sets={"AR": 0, "AY0": 1, "CNTR": 0}, expects={"AR": 3, "CNTR": 0, "LPSP": 0, "PCSP": 0, "CNTSP": 0})
case("nested DO loops 2 x 3",
     [t7("CNTR", 2), t11(B + 5, "CE"), t7("CNTR", 3), t11(B + 4, "CE"),
      t9(alu("X+Y", x="AR")), t9(alu("Y+1", y="AF"), z=1)],
     sets={"AR": 0, "AF": 0, "AY0": 1}, expects={"AR": 6, "AF": 2, "LPSP": 0, "PCSP": 0})
case("DO UNTIL EQ tests the status of the previous pass",
     [t11(B + 1, "EQ"), t9(alu("X-Y", x="AR"))],
     sets={"AR": 3, "AY0": 1, "AZ": 0}, expects={"AR": 0xffff, "LPSP": 0, "PCSP": 0})
case("CALL / RTS",
     [t10(B + 3, call=True), t6("AX1", 0x22), t10(B + 5), t6("AX0", 0x11), t20()],
     expects={"AX0": 0x11, "AX1": 0x22, "PCSP": 0}, main=5)
case("conditional jump not taken, then taken",
     [t10(B + 3, cond="NE"), t10(B + 3, cond="EQ"), t6("AX0", 0xdead), t6("AX1", 1)],
     sets={"AZ": 1, "AX0": 0}, expects={"AX0": 0, "AX1": 1})
case("IF NOT CE JUMP counts down",
     [t7("CNTR", 3), t9(alu("X+Y", x="AR")), t10(B + 1, cond="NOTCE")],
     sets={"AR": 0, "AY0": 1, "CNTR": 0}, expects={"AR": 3, "CNTR": 0})
case("indirect JUMP (I4)", [t19(4), t6("AX0", 0xdead), t6("AX1", 2)],
     sets={"I4": B + 2, "AX0": 0}, expects={"AX0": 0, "AX1": 2})
case("indirect CALL (I5) and RTS",
     [t19(5, call=True), t10(B + 4), t6("AX0", 0x33), t20()],
     sets={"I5": B + 2}, expects={"AX0": 0x33, "PCSP": 0}, main=4)
case("IF FLAG_IN JUMP", [t27(B + 2, flag_in=True), t6("AX0", 0xdead), t6("AX1", 3)],
     sets={"FI": 1, "AX0": 0}, expects={"AX0": 0, "AX1": 3})
case("IF NOT FLAG_IN JUMP falls through when FI=1", [t27(B + 2, flag_in=False), t6("AX0", 4)],
     sets={"FI": 1}, expects={"AX0": 4})
case("RTS IF NE not taken", [t20(cond="NE"), t6("AX0", 5)], sets={"AZ": 1}, expects={"AX0": 5})
case("SET FL1, TOGGLE FLAG_OUT", [t28(fo=1, fl1=3)], sets={"FO": 0, "FL1": 0},
     expects={"FO": 1, "FL1": 1})
case("ENA AR_SAT, DIS M_MODE; MSTAT reads back", [t18(AS=True, MM=False), t17("AX0", "MSTAT")],
     sets={"M_MODE": 1}, expects={"AR_SAT": 1, "M_MODE": 0, "AX0": 0x0008})
case("PUSH STS / POP STS restores ASTAT",
     [t26(spp=2), t9(alu("Y+1", y="AY0")), t26(spp=3)],
     sets={"AZ": 1, "AN": 0, "AY0": 5}, expects={"AZ": 1, "AR": 6, "STSP": 0})
case("TOPPCSTACK push and pop", [t17("TOPPCSTACK", "AX0"), t17("AY0", "TOPPCSTACK")],
     sets={"AX0": 0xffff}, expects={"AY0": 0x3fff, "PCSP": 0})
case("I/O space write and read", [t29("AX0", 5, write=True), t29("AY0", 5)],
     sets={"AX0": 0x7777}, expects={"io:0005": 0x7777, "AY0": 0x7777})
case("RTI restores the status stack",
     [t10(B + 2, call=True), t10(B + 5), t26(spp=2), t18(AS=True), t20(rti=True)],
     sets={"AR_SAT": 0}, expects={"AR_SAT": 0, "PCSP": 0, "STSP": 0}, main=5)


def emit(broken=False):
    out = []
    for n, (name, code, sets, exps, main) in enumerate(CASES):
        out.append(f"case {name.replace(' ', '_')}")
        out.append("code " + "".join(f"{w:06x}" for w in code))
        out.append(f"main {main if main is not None else len(code)}")
        for k, v in sets.items():
            out.append(f"set {k} 0x{v:x}")
        for k, v in exps.items():
            if broken and n == 0:
                v ^= 1
            out.append(f"expect {k} 0x{v:x}")
        out.append("end")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    if "--listing" in sys.argv:
        for name, code, *_ in CASES:
            for w in code:
                print(f"{w:06x} {name}")
    else:
        sys.stdout.write(emit("--broken" in sys.argv))
