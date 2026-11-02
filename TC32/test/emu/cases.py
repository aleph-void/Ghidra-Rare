#!/usr/bin/env python3
"""Emulator cases for TC32 (test/TC32EmuTest.java).

  cases.py [--broken] > cases.txt

Each case is a short program (encoded here from the TC32 format table, cross-checked against
tc32-elf-as by test/check-encodings.sh) with initial registers/memory and the results worked out
by hand from the ARMv4T Thumb instruction descriptions that TC32 follows. Code runs at 0x1000,
sp starts at 0x8000. Flags are NG ZR CY OV. --broken adds one deliberately wrong expectation.
"""
import struct
import sys

# --- encoders (TC32 major opcodes; field layout as Thumb-1) ---
def movs_i(rd, i): return 0xA000 | rd << 8 | i
def cmp_i(rd, i): return 0xA800 | rd << 8 | i
def adds_i8(rd, i): return 0xB000 | rd << 8 | i
def subs_i8(rd, i): return 0xB800 | rd << 8 | i
ALU = dict(ands=0, xors=1, shftls=2, shftrs=3, asrs=4, addcs=5, subcs=6, rotrs=7,
           nand=8, negs=9, cmp=10, cmpn=11, ors=12, muls=13, bclrs=14, movns=15)
def alu(op, rd, rs): return ALU[op] << 6 | rs << 3 | rd
def adds_r(rd, rs, rn): return 0xE800 | rn << 6 | rs << 3 | rd
def subs_r(rd, rs, rn): return 0xEA00 | rn << 6 | rs << 3 | rd
def adds_i3(rd, rs, i): return 0xEC00 | i << 6 | rs << 3 | rd
def subs_i3(rd, rs, i): return 0xEE00 | i << 6 | rs << 3 | rd
def lsl_i(rd, rs, n): return 0xF000 | n << 6 | rs << 3 | rd
def lsr_i(rd, rs, n): return 0xF800 | (n & 31) << 6 | rs << 3 | rd
def asr_i(rd, rs, n): return 0xE000 | (n & 31) << 6 | rs << 3 | rd
def hi(op, rd, rs): return 0x0400 | op << 8 | (rd >> 3) << 7 | (rs >> 3) << 6 | (rs & 7) << 3 | (rd & 7)
def str_i(rd, rb, off): return 0x5000 | (off // 4) << 6 | rb << 3 | rd
def ldr_i(rd, rb, off): return 0x5800 | (off // 4) << 6 | rb << 3 | rd
def strb_i(rd, rb, off): return 0x4000 | off << 6 | rb << 3 | rd
def ldrb_i(rd, rb, off): return 0x4800 | off << 6 | rb << 3 | rd
def strh_i(rd, rb, off): return 0x2000 | (off // 2) << 6 | rb << 3 | rd
def ldrh_i(rd, rb, off): return 0x2800 | (off // 2) << 6 | rb << 3 | rd
RO = dict(storer=0, storerh=1, storerb=2, loadrsb=3, loadr=4, loadrh=5, loadrb=6, loadrsh=7)
def ro(op, rd, rb, rofs): return (0x08 + RO[op]) << 9 | rofs << 6 | rb << 3 | rd
def ldr_pc(rd, off): return 0x0800 | rd << 8 | off // 4
def str_sp(rd, off): return 0x3000 | rd << 8 | off // 4
def ldr_sp(rd, off): return 0x3800 | rd << 8 | off // 4
def add_pc(rd, off): return 0x7000 | rd << 8 | off // 4
def add_sp(rd, off): return 0x7800 | rd << 8 | off // 4
def sp_add(off): return 0x6000 | off // 4
def sp_sub(off): return 0x6080 | off // 4
def rl(regs): return sum(1 << r for r in regs)
def push(regs, lr=False): return 0x6400 | lr << 8 | rl(regs)
def pop(regs, pc=False): return 0x6C00 | pc << 8 | rl(regs)
def reti(regs, pc=False): return 0x6800 | pc << 8 | rl(regs)
def stm(rb, regs): return 0xD000 | rb << 8 | rl(regs)
def ldm(rb, regs): return 0xD800 | rb << 8 | rl(regs)
def b(src, dst): return 0x8000 | ((dst - src - 4) // 2) & 0x7FF
COND = dict(eq=0, ne=1, cs=2, cc=3, mi=4, pl=5, vs=6, vc=7, hi=8, ls=9, ge=10, lt=11, gt=12, le=13)
def bc(c, src, dst): return 0xC000 | COND[c] << 8 | ((dst - src - 4) // 2) & 0xFF
def bl(src, dst):
    o = (dst - src - 4) >> 1
    return [0x9000 | (o >> 11) & 0x7FF, 0x9800 | o & 0x7FF]
def jex(rm): return 0x0700 | rm << 3
def mcsr(rd): return 0x6BC0 | rd
def mrcs(rd): return 0x6BC8 | rd
def mssr(rd): return 0x6BD0 | rd
def mrss(rd): return 0x6BD8 | rd

CASES = []


def case(name, code, sets=(), expect=(), main=None):
    words = []
    for c in code:
        words += c if isinstance(c, list) else [c]
    CASES.append((name, words, main, list(sets), list(expect)))


def flags(n, z, c, v):
    return [("NG", n), ("ZR", z), ("CY", c), ("OV", v)]


M = 0xFFFFFFFF

case("adds_reg_overflow", [adds_r(2, 0, 1)], [("r0", 0x7FFFFFFF), ("r1", 1)],
     [("r2", 0x80000000)] + flags(1, 0, 0, 1))
case("adds_reg_carry_zero", [adds_r(2, 0, 1)], [("r0", M), ("r1", 1)],
     [("r2", 0)] + flags(0, 1, 1, 0))
case("subs_reg_borrow", [subs_r(2, 0, 1)], [("r0", 1), ("r1", 2)],
     [("r2", M)] + flags(1, 0, 0, 0))
case("subs_reg_no_borrow", [subs_r(2, 0, 1)], [("r0", 5), ("r1", 3)],
     [("r2", 2)] + flags(0, 0, 1, 0))
case("subs_imm3", [subs_i3(1, 0, 7)], [("r0", 7)], [("r1", 0)] + flags(0, 1, 1, 0))
case("adds_imm3_mov", [adds_i3(3, 0, 0)], [("r0", 0x80000000), ("CY", 1), ("OV", 1)],
     [("r3", 0x80000000)] + flags(1, 0, 0, 0))
case("cmp_imm_equal", [cmp_i(3, 16)], [("r3", 16)], flags(0, 1, 1, 0))
case("subs_imm8_overflow", [subs_i8(0, 1)], [("r0", 0x80000000)],
     [("r0", 0x7FFFFFFF)] + flags(0, 0, 1, 1))
case("adds_imm8", [adds_i8(5, 0xFF)], [("r5", 0xFFFFFF01)], [("r5", 0)] + flags(0, 1, 1, 0))
case("movs_imm8", [movs_i(6, 0x80)], [("r6", 0x1234), ("CY", 1), ("OV", 1)],
     [("r6", 0x80)] + flags(0, 0, 1, 1))
case("addcs_after_carry", [adds_r(2, 0, 1), alu("addcs", 3, 4)],
     [("r0", M), ("r1", 1), ("r3", 5), ("r4", 6)], [("r2", 0), ("r3", 12)] + flags(0, 0, 0, 0))
case("addcs_overflow", [alu("addcs", 0, 1)], [("r0", 0x7FFFFFFF), ("r1", 0), ("CY", 1)],
     [("r0", 0x80000000)] + flags(1, 0, 0, 1))
case("subcs_after_borrow", [subs_r(5, 6, 7), alu("subcs", 0, 1)],
     [("r6", 0), ("r7", 1), ("r0", 0), ("r1", 0)], [("r5", M), ("r0", M)] + flags(1, 0, 0, 0))
case("subcs_carry_in", [alu("subcs", 0, 1)], [("r0", 10), ("r1", 3), ("CY", 1)],
     [("r0", 7)] + flags(0, 0, 1, 0))
case("lsl_imm_carry", [lsl_i(0, 1, 1)], [("r1", 0x80000001)], [("r0", 2)] + flags(0, 0, 1, 0))
case("movs_reg_keeps_c", [lsl_i(0, 1, 0)], [("r1", 0), ("CY", 1)], [("r0", 0)] + flags(0, 1, 1, 0))
case("lsr_imm_32", [lsr_i(0, 1, 32)], [("r1", 0x80000000)], [("r0", 0)] + flags(0, 1, 1, 0))
case("asr_imm_4", [asr_i(0, 1, 4)], [("r1", 0x80000018)], [("r0", 0xF8000001)] + flags(1, 0, 1, 0))
case("asr_imm_32", [asr_i(2, 3, 32)], [("r3", 0x80000000)], [("r2", M)] + flags(1, 0, 1, 0))
case("lsl_reg_0_keeps_c", [alu("shftls", 0, 1)], [("r0", 5), ("r1", 0x100), ("CY", 1)],
     [("r0", 5)] + flags(0, 0, 1, 0))
case("lsl_reg_32", [alu("shftls", 0, 1)], [("r0", 1), ("r1", 32)], [("r0", 0)] + flags(0, 1, 1, 0))
case("lsl_reg_33", [alu("shftls", 0, 1)], [("r0", 1), ("r1", 33), ("CY", 1)],
     [("r0", 0)] + flags(0, 1, 0, 0))
case("lsr_reg_32", [alu("shftrs", 0, 1)], [("r0", 0x80000000), ("r1", 32)],
     [("r0", 0)] + flags(0, 1, 1, 0))
case("asr_reg_40", [alu("asrs", 0, 1)], [("r0", 0x80000000), ("r1", 40)],
     [("r0", M)] + flags(1, 0, 1, 0))
case("ror_reg_4", [alu("rotrs", 0, 1)], [("r0", 0xF1), ("r1", 4)], [("r0", 0x1000000F)] + flags(0, 0, 0, 0))
case("ror_reg_36", [alu("rotrs", 0, 1)], [("r0", 0x18), ("r1", 36)], [("r0", 0x80000001)] + flags(1, 0, 1, 0))
case("ror_reg_32", [alu("rotrs", 0, 1)], [("r0", 0x80000000), ("r1", 32)],
     [("r0", 0x80000000)] + flags(1, 0, 1, 0))
case("muls", [alu("muls", 0, 1)], [("r0", 7), ("r1", 6)], [("r0", 42)] + [("NG", 0), ("ZR", 0)])
case("logic_ops", [alu("ands", 0, 1), alu("xors", 2, 1), alu("ors", 3, 1), alu("bclrs", 4, 1), alu("movns", 5, 1)],
     [("r0", 0xF0F0), ("r1", 0xFF00), ("r2", 0x0FF0), ("r3", 0x000F), ("r4", 0xFFFF)],
     [("r0", 0xF000), ("r2", 0xF0F0), ("r3", 0xFF0F), ("r4", 0x00FF), ("r5", 0xFFFF00FF)] + [("NG", 1), ("ZR", 0)])
case("negs", [alu("negs", 2, 1)], [("r1", 15)], [("r2", 0xFFFFFFF1)] + flags(1, 0, 0, 0))
case("negs_zero", [alu("negs", 2, 1)], [("r1", 0)], [("r2", 0)] + flags(0, 1, 1, 0))
case("negs_min", [alu("negs", 2, 1)], [("r1", 0x80000000)], [("r2", 0x80000000)] + flags(1, 0, 0, 1))
case("cmpn", [alu("cmpn", 0, 1)], [("r0", 0x80000000), ("r1", 0x80000000)],
     [("r0", 0x80000000)] + flags(0, 1, 1, 1))
case("nand_is_tst", [alu("nand", 0, 1)], [("r0", 0xF0), ("r1", 0x0F)], [("r0", 0xF0)] + [("NG", 0), ("ZR", 1)])
case("cmp_reg_signed", [alu("cmp", 0, 1)], [("r0", 1), ("r1", 0x80000000)], flags(1, 0, 0, 1))
case("store_load_imm", [str_i(1, 0, 4), ldrb_i(2, 0, 5), ldrh_i(3, 0, 6), strb_i(1, 0, 9), strh_i(1, 0, 10), ldr_i(4, 0, 8)],
     [("r0", 0x2000), ("r1", 0x11223344), ("ram:2008/4", 0)],
     [("ram:2004/4", 0x11223344), ("r2", 0x33), ("r3", 0x1122), ("ram:2008/4", 0x33440000 | 0x4400),
      ("r4", 0x33444400)])
case("load_signed_regoff", [ro("loadrsh", 2, 0, 1), ro("loadrsb", 3, 0, 1), ro("loadrh", 4, 0, 1), ro("loadrb", 5, 0, 1)],
     [("r0", 0x2000), ("r1", 0x10), ("ram:2010/2", 0x8180)],
     [("r2", 0xFFFF8180), ("r3", 0xFFFFFF80), ("r4", 0x8180), ("r5", 0x80)])
case("store_regoff", [ro("storer", 1, 0, 2), ro("storerh", 1, 0, 3), ro("storerb", 1, 0, 4), ro("loadr", 5, 0, 2)],
     [("r0", 0x2000), ("r1", 0xA1B2C3D4), ("r2", 0x20), ("r3", 0x24), ("r4", 0x26), ("ram:2024/4", 0)],
     [("ram:2020/4", 0xA1B2C3D4), ("ram:2024/4", 0x00D4C3D4), ("r5", 0xA1B2C3D4)])
case("sp_relative", [sp_sub(16), str_sp(1, 4), ldr_sp(2, 4), add_sp(3, 8), sp_add(8)],
     [("r1", 0xCAFE)], [("sp", 0x7FF8), ("ram:7ff4/4", 0xCAFE), ("r2", 0xCAFE), ("r3", 0x7FF8)])
case("push_pop", [push([4, 5], lr=True), pop([0, 1])],
     [("r4", 1), ("r5", 2), ("lr", 0x1234)],
     [("sp", 0x7FFC), ("ram:7ff4/4", 1), ("ram:7ff8/4", 2), ("ram:7ffc/4", 0x1234), ("r0", 1), ("r1", 2)])
case("stm_ldm", [stm(0, [1, 2]), ldm(3, [4, 5])],
     [("r0", 0x3000), ("r1", 0xA), ("r2", 0xB), ("r3", 0x3000)],
     [("r0", 0x3008), ("ram:3000/4", 0xA), ("ram:3004/4", 0xB), ("r3", 0x3008), ("r4", 0xA), ("r5", 0xB)])
case("ldm_base_in_list", [ldm(1, [0, 1])], [("r1", 0x3000), ("ram:3000/4", 5), ("ram:3004/4", 6)],
     [("r0", 5), ("r1", 6)])
case("pc_relative_load", [ldr_pc(0, 4), 0, 0, 0, 0xBEEF, 0xDEAD], [], [("r0", 0xDEADBEEF)], main=2)
case("pc_relative_load_misaligned", [0x0600, ldr_pc(1, 4), 0, 0, 0xBEEF, 0xDEAD], [], [("r1", 0xDEADBEEF)], main=4)
case("add_pc", [0x0600, 0x0600, add_pc(3, 4)], [], [("r3", 0x100C)], main=6)
case("cond_branch_eq_ne",
     [cmp_i(0, 5), bc("ne", 0x1002, 0x1008), movs_i(1, 1), bc("eq", 0x1006, 0x100A), movs_i(1, 2)],
     [("r0", 5)], [("r1", 2)], main=0xA)  # tmovs r1,#1 clears Z, so tjeq falls through
case("cond_branch_lt_taken",
     [cmp_i(0, 0), bc("lt", 0x1002, 0x1008), movs_i(1, 7), b(0x1006, 0x100A), movs_i(1, 9)],
     [("r0", M)], [("r1", 9)], main=0xA)
case("cond_branch_hi_taken",
     [cmp_i(0, 0), bc("hi", 0x1002, 0x1008), movs_i(1, 7), b(0x1006, 0x100A), movs_i(1, 9)],
     [("r0", M)], [("r1", 9)], main=0xA)
case("cond_branch_gt_not_taken",
     [cmp_i(0, 0), bc("gt", 0x1002, 0x1008), movs_i(1, 7), b(0x1006, 0x100A), movs_i(1, 9)],
     [("r0", M)], [("r1", 7)], main=0xA)
case("call_and_return", [bl(0x1000, 0x1008), adds_i8(0, 1), 0x0600, movs_i(0, 10), jex(14)],
     [], [("r0", 11)], main=6)
case("call_pop_pc", [bl(0x1000, 0x1008), adds_i8(0, 1), 0x0600, push([], lr=True), movs_i(0, 3), pop([], pc=True)],
     [], [("r0", 4), ("sp", 0x8000)], main=6)
case("hireg_add_mov_keep_flags", [hi(0, 8, 0), hi(2, 1, 8), hi(1, 1, 8)],
     [("r8", 0x100), ("r0", 0x23), ("ZR", 0)], [("r8", 0x123), ("r1", 0x123), ("ZR", 1), ("CY", 1)])
case("mov_pc_jump", [hi(2, 15, 2), movs_i(0, 1), movs_i(0, 2)], [("r2", 0x1005), ("r0", 0)], [("r0", 2)], main=6)
case("cpsr_pack_unpack", [mcsr(0), mrcs(1)], [("r0", 0xA0000013)],
     [("r1", 0xA0000013)] + flags(1, 0, 1, 0))
case("spsr_moves", [mssr(2), mrss(3)], [("r2", 0x60000012)], [("r3", 0x60000012), ("SPSR", 0x60000012)])
case("treti_restores_flags", [mssr(0), reti([2], pc=True)],
     [("r0", 0x60000013), ("ram:8000/4", 0x55), ("ram:8004/4", 0x1011)],
     [("r2", 0x55), ("sp", 0x8008)] + flags(0, 1, 1, 0) + [("CPSR", 0x13)], main=0x10)


def main():
    broken = "--broken" in sys.argv
    out = ["# generated by test/emu/cases.py; do not edit"]
    for name, words, mainlen, sets, exp in CASES:
        if broken and name == "muls":
            exp = [("r0", 43)] + exp[1:]
        out.append("case " + name)
        out.append("code " + b"".join(struct.pack("<H", w & 0xFFFF) for w in words).hex())
        if mainlen is not None:
            out.append("main %d" % mainlen)
        for k, v in sets:
            out.append("set %s 0x%x" % (k, v))
        for k, v in exp:
            out.append("expect %s 0x%x" % (k, v))
        out.append("end")
    print("\n".join(out))


if __name__ == "__main__":
    main()
