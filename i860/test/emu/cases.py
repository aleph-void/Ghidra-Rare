#!/usr/bin/env python3
"""Emulator cases for the i860 module: small programs (encoded by enc.py from the manual's
appendix B) with results worked out by hand from the Programmer's Reference Manual
(chapter 7 for core instructions, chapter 8 for floating-point, graphics, pipelines and
dual-instruction mode).

    cases.py > cases.txt            all cases
    cases.py --broken > bad.txt     the same with one deliberately wrong expectation (the
                                    harness must report it)

Code starts at ram:1000 and runs until the PC reaches the end of the main code ("main" bytes,
default the whole code); subroutines may follow it. Floating-point values are written as
numbers and stored as IEEE bit patterns; 64-bit registers (fdN, pipeline stages, KR, KI, T,
MERGE) hold single-precision values in their low 32 bits.
"""
import struct
import sys

from enc import *   # noqa: F401,F403

B = 0x1000
CASES = []


def f32(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def f64(x):
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def case(name, words, sets=(), expect=(), flags="", main=None):
    CASES.append((name, words, sets, expect, flags, main))


def at(i):
    return B + 4 * i


# ---------------------------------------------------------------- integer arithmetic (7.7)
case("addu_carry", [alu("addu", 4, 5, 6)], [("r4", 0xffffffff), ("r5", 1)],
     [("r6", 0), ("CC", 1), ("OF", 1)])
case("addu_plain", [alu("addu", 4, 5, 6)], [("r4", 1), ("r5", 2), ("CC", 1), ("OF", 1)],
     [("r6", 3), ("CC", 0), ("OF", 0)])
case("adds_overflow", [alu("adds", 4, 5, 6)], [("r4", 0x7fffffff), ("r5", 1)],
     [("r6", 0x80000000), ("OF", 1), ("CC", 0)])          # true sum 2^31 is not negative
case("adds_negative", [alu("adds", 4, 5, 6)], [("r4", 0xfffffffb), ("r5", 3)],
     [("r6", 0xfffffffe), ("OF", 0), ("CC", 1)])
case("subu_borrow", [alu("subu", 4, 5, 6)], [("r4", 5), ("r5", 7)],
     [("r6", 0xfffffffe), ("CC", 0), ("OF", 1)])          # CC set iff src2 <= src1 unsigned
case("subu_equal", [alu("subu", 4, 5, 6)], [("r4", 5), ("r5", 5)],
     [("r6", 0), ("CC", 1), ("OF", 0)])
case("subs_less", [alu("subs", 4, 5, 6)], [("r4", 0xffffffff), ("r5", 1)],
     [("r6", 0xfffffffe), ("CC", 1), ("OF", 0)])          # CC set iff src2 > src1 signed
case("subs_overflow", [alu("subs", 4, 5, 6)], [("r4", 0x80000000), ("r5", 1)],
     [("r6", 0x7fffffff), ("CC", 1), ("OF", 1)])
case("adds_imm_mov", [alu("adds", -3, 0, 6, True)], [("r6", 7)],
     [("r6", 0xfffffffd), ("CC", 1)])                      # mov -3,r6
case("subu_imm_minuend", [alu("subu", 2, 5, 6, True)], [("r5", 7)],
     [("r6", 0xfffffffb), ("CC", 0)])                      # r6 = 2 - r5
case("r0_reads_zero", [alu("addu", 0, 0, 6), alu("or", 0x1234, 0, 0, True), alu("addu", 0, 7, 8)],
     [("r6", 9), ("r7", 5)], [("r6", 0), ("r8", 5)])
# ---------------------------------------------------------------- logical (7.10)
case("and_zero_cc", [alu("and", 0x00f0, 4, 6, True)], [("r4", 0x0f0f)],
     [("r6", 0), ("CC", 1)])
case("orh_or_const32", [alu("orh", 0x1234, 0, 6), alu("or", 0xabcd, 6, 6, True)], [],
     [("r6", 0x1234abcd), ("CC", 0)])
case("andnoth", [alu("andnoth", 0xffff, 4, 6)], [("r4", 0x12345678)], [("r6", 0x5678)])
case("xor_andnot", [alu("xor", 4, 5, 6), alu("andnot", 4, 5, 7)],
     [("r4", 0xff00ff00), ("r5", 0x0ff00ff0)], [("r6", 0xf0f0f0f0), ("r7", 0x00f000f0)])
case("xorh_cc", [alu("xorh", 0x8000, 4, 6)], [("r4", 0x80000000)], [("r6", 0), ("CC", 1)])
# ---------------------------------------------------------------- shifts (7.8)
case("shr_sets_sc", [alu("shr", 4, 4, 6, True)], [("r4", 0x80000010)],
     [("r6", 0x08000001), ("SC", 4)])
case("shra", [alu("shra", 4, 4, 6, True)], [("r4", 0x80000010)], [("r6", 0xf8000001)])
case("shl_count_mod32", [alu("shl", 5, 4, 6)], [("r4", 3), ("r5", 33)], [("r6", 6)])
case("shrd_rotate", [alu("shr", 8, 0, 0, True), shrd(4, 5, 6)],
     [("r4", 0x11223344), ("r5", 0x55667788)], [("r6", 0x44556677), ("SC", 8)])
# ---------------------------------------------------------------- loads and stores (7.1-7.5)
case("ld_b_sign", [ld("b", 1, 4, 6)], [("r4", 0x2000), ("ram:2000/4", 0x00008000)],
     [("r6", 0xffffff80)])
case("ld_s_l", [ld("s", 2, 4, 6), ld("l", 4, 4, 7)],
     [("r4", 0x2000), ("ram:2000/8", 0x8000000080010000)],
     [("r6", 0xffff8001), ("r7", 0x80000000)])
case("ld_index", [ld("l", 5, 4, 6, index=True)], [("r4", 0x2000), ("r5", 8), ("ram:2008/4", 0xcafef00d)],
     [("r6", 0xcafef00d)])
case("st_split_offset", [st("l", 5, 0x1004, 4), st("s", 5, -2, 4), st("b", 5, -0x801, 4)],
     [("r4", 0x2000), ("r5", 0x11223344)],
     [("ram:3004/4", 0x11223344), ("ram:1ffe/2", 0x3344), ("ram:17ff/1", 0x44)])
case("fld_d_autoinc", [fld("d", 8, 4, 2, inc=True)],
     [("r4", 0x2000), ("ram:2008/8", 0x0123456789abcdef)],
     [("fd2", 0x0123456789abcdef), ("f2", 0x89abcdef), ("f3", 0x01234567), ("r4", 0x2008)])
case("fst_l_index", [fst("l", 5, 6, 4, index=True), fst("d", 0, 0, 4)],
     [("r4", 0x2000), ("r6", 0x10), ("f5", 0x3f800000), ("ram:2000/8", 0xffffffffffffffff)],
     [("ram:2010/4", 0x3f800000), ("ram:2000/8", 0)])     # f0:f1 store zeros
case("fld_q", [fld("q", 16, 4, 4)],
     [("r4", 0x2000), ("ram:2010/8", 0x1111111122222222), ("ram:2018/8", 0x3333333344444444)],
     [("f4", 0x22222222), ("f5", 0x11111111), ("f6", 0x44444444), ("f7", 0x33333333)])
case("ixfr_fxfr", [ixfr(4, 2), fp("fxfr", 2, 0, 6)], [("r4", 0x40490fdb)],
     [("f2", 0x40490fdb), ("r6", 0x40490fdb)])
# ---------------------------------------------------------------- control registers (7.12)
case("psr_fields", [stc(4, 1), ldc(1, 6)], [("r4", 0x0f440004)],
     [("CC", 1), ("SC", 2), ("PS", 1), ("PM", 0x0f), ("r6", 0x0f440004)])
case("epsr_of", [alu("addu", 4, 4, 0), ldc(5, 6)], [("r4", 0x80000000)],
     [("OF", 1), ("r6", 0x01000000)])
case("fsr_dirbase", [stc(4, 4), stc(5, 2), ldc(4, 6), ldc(2, 7)], [("r4", 0x0c), ("r5", 0x1001)],
     [("fsr", 0x0c), ("r6", 0x0c), ("r7", 0x1001)])
# ---------------------------------------------------------------- control transfer (7.11)
case("br_delay_slot", [br(at(0), at(3)), alu("addu", 1, 4, 4, True), alu("addu", 100, 4, 4, True),
                       alu("addu", 10, 4, 4, True)], [("r4", 0)], [("r4", 11)])
case("call_link_and_return",
     [call(at(0), at(5)), alu("addu", 1, 4, 4, True), alu("addu", 2, 4, 4, True),
      br(at(3), at(8)), NOP,
      alu("addu", 0x10, 4, 4, True), bri(1), alu("addu", 0x20, 4, 4, True)],
     [("r4", 0)], [("r4", 0x33), ("r1", at(2))], main=4 * 8)
case("bc_t_taken", [bct(at(0), at(3)), alu("addu", 1, 4, 4, True), alu("addu", 100, 4, 4, True)],
     [("CC", 1), ("r4", 0)], [("r4", 1)])
case("bc_t_not_taken_skips_slot",
     [bct(at(0), at(4)), alu("addu", 1, 4, 4, True), alu("addu", 2, 4, 4, True), alu("addu", 4, 4, 4, True)],
     [("CC", 0), ("r4", 0)], [("r4", 6)])
case("bnc_t_taken", [bnct(at(0), at(3)), alu("addu", 1, 4, 4, True), alu("addu", 100, 4, 4, True)],
     [("CC", 0), ("r4", 0)], [("r4", 1)])
case("bc_bnc_no_delay", [bc(at(0), at(2)), alu("addu", 1, 4, 4, True), bnc(at(2), at(4)),
                         alu("addu", 2, 4, 4, True)],
     [("CC", 1), ("r4", 0)], [("r4", 2)])
case("bte_btne", [bte(5, 4, at(0), at(2), immediate=True), alu("addu", 1, 6, 6, True),
                  btne(7, 4, at(2), at(4)), alu("addu", 2, 6, 6, True)],
     [("r4", 5), ("r7", 5), ("r6", 0)], [("r6", 2)])
# bla loop (7.11, example 7-1): r5 = -1, r6 = 3; a first bla initialises LCC, then the loop body
# runs r6 + 1 = 4 times (each pass adds 1 to r8 in the delay slot).
case("bla_loop",
     [bla(5, 6, at(0), at(2)), NOP,
      bla(5, 6, at(2), at(2)), alu("addu", 1, 8, 8, True)],
     [("r5", 0xffffffff), ("r6", 3), ("r8", 0)], [("r8", 4), ("r6", 0xfffffffe), ("LCC", 0)])
case("calli_bri", [calli(5), alu("addu", 1, 4, 4, True), alu("addu", 2, 4, 4, True),
                   NOP, bri(1), alu("addu", 0x10, 4, 4, True)],
     [("r5", at(4)), ("r4", 0)], [("r4", 0x13), ("r1", at(2))], main=4 * 3)
case("intovr_no_trap", [esc(4), alu("addu", 1, 4, 4, True)], [("OF", 0), ("r4", 0)], [("r4", 1)])
# ---------------------------------------------------------------- floating point, scalar (8.2, 8.3)
case("fadd_ss", [fp("fadd", 2, 3, 4)], [("f2", f32(1.5)), ("f3", f32(2.25))],
     [("f4", f32(3.75)), ("A3", f32(3.75))])
case("fmul_dd", [fp("fmul", 2, 4, 6, "dd")], [("fd2", f64(3.0)), ("fd4", f64(0.5))],
     [("fd6", f64(1.5))])
case("fsub_sd", [fp("fsub", 2, 3, 4, "sd")], [("f2", f32(1.0)), ("f3", f32(0.25))],
     [("fd4", f64(0.75))])
case("famov_ds", [fp("famov", 2, 0, 5, "ds")], [("fd2", f64(2.5))], [("f5", f32(2.5))])
case("famov_sd", [fp("famov", 5, 0, 2, "sd")], [("f5", f32(-0.375))], [("fd2", f64(-0.375))])
case("fix_ftrunc", [fp("fix", 2, 0, 4, "dd"), fp("ftrunc", 6, 0, 8, "dd")],
     [("fd2", f64(2.75)), ("fd6", f64(-2.75))], [("f4", 3), ("f8", 0xfffffffe)])
case("frcp_frsqr", [fp("frcp", 0, 2, 4, "dd"), fp("frsqr", 0, 6, 7)],
     [("fd2", f64(4.0)), ("f6", f32(16.0))], [("fd4", f64(0.25)), ("f7", f32(0.25))])
case("pfgt_pfle_cc", [fp("pfgt", 2, 3, 0, P=1), fp("pfle", 2, 3, 0, P=1), ldc(1, 6)],
     [("f2", f32(2.0)), ("f3", f32(1.0)), ("CC", 0)],
     [("CC", 1), ("r6", 4)])                                # 2 <= 1 is false: pfle sets CC
case("pfeq_dd", [fp("pfeq", 2, 4, 0, "dd", P=1)], [("fd2", f64(1.25)), ("fd4", f64(1.25))], [("CC", 1)])
case("fmlow_integer_multiply", [fp("fmlow", 2, 4, 6, "dd")],
     [("fd2", 123456), ("fd4", 1000)], [("f6", 123456000), ("f7", 0)])
case("fiadd_fisub", [fp("fiadd", 2, 4, 6, "dd"), fp("fisub", 9, 10, 8, "ss")],
     [("fd2", 0x00000001ffffffff), ("fd4", 1), ("f9", 0), ("f10", 3)],
     [("fd6", 0x0000000200000000), ("f8", 0xfffffffd)])
# ---------------------------------------------------------------- pipelines (8.1)
# Figure 8-1: three pipelined adds, then a fourth stores the first sum.
case("pfadd_pipeline",
     [fp("fadd", 2, 3, 0, P=1), fp("fadd", 4, 5, 0, P=1), fp("fadd", 6, 7, 0, P=1),
      fp("fadd", 0, 0, 8, P=1), fp("fadd", 0, 0, 9, P=1)],
     [("f2", f32(1.0)), ("f3", f32(2.0)), ("f4", f32(4.0)), ("f5", f32(8.0)), ("f6", f32(16.0)),
      ("f7", f32(32.0))],
     [("f8", f32(3.0)), ("f9", f32(12.0)), ("A3", f32(48.0)), ("A2", 0), ("A1", 0)])
case("pfmul_dd_two_stages",
     [fp("fmul", 2, 4, 0, "dd", P=1), fp("fmul", 6, 8, 0, "dd", P=1), fp("fmul", 0, 0, 10, "dd", P=1)],
     [("fd2", f64(3.0)), ("fd4", f64(5.0)), ("fd6", f64(2.0)), ("fd8", f64(0.5))],
     [("fd10", f64(15.0)), ("M2", f64(1.0)), ("M1", 0)])
case("pfmul_ss_three_stages",
     [fp("fmul", 2, 3, 0, P=1), fp("fmul", 2, 2, 0, P=1), fp("fmul", 3, 3, 0, P=1),
      fp("fmul", 0, 0, 4, P=1)],
     [("f2", f32(3.0)), ("f3", f32(-2.0))], [("f4", f32(-6.0))])
case("pfld_pipeline",
     [pfld("l", 0, 4, 0), pfld("l", 4, 4, 0), pfld("l", 8, 4, 0), pfld("l", 12, 4, 2),
      pfld("d", 16, 4, 4, inc=True)],
     [("r4", 0x2000), ("ram:2000/8", 0x2222222211111111), ("ram:2008/8", 0x4444444433333333),
      ("ram:2010/8", 0x6666666655555555)],
     [("f2", 0x11111111), ("f4", 0x22222222), ("r4", 0x2010)])
case("pfiadd_one_stage", [fp("fiadd", 2, 3, 0, P=1), fp("fiadd", 0, 0, 4, P=1)],
     [("f2", 5), ("f3", 6)], [("f4", 11)])
# ---------------------------------------------------------------- dual operations (8.4)
# r2p1.ss: M = KR * src2, A = src1 + M-last; fdest gets the A-pipeline result.
case("r2p1_ss",
     [dual(0, 0, 2, 3, 4)],
     [("KR", f32(2.0)), ("f2", f32(1.0)), ("f3", f32(3.0)), ("M3", f32(5.0)), ("A3", f32(7.0))],
     [("f4", f32(7.0)), ("A1", f32(6.0)), ("M1", f32(6.0)), ("A3", 0), ("M3", 0)])
# i2apt.dd (DPC 7): KI <- src1 (K load), M = KI * src2, A = T + A-last, T <- M-last (T load).
case("i2apt_dd",
     [dual(7, 0, 2, 4, 6, "dd")],
     [("T", f64(1.0)), ("A3", f64(2.0)), ("M2", f64(4.0)), ("fd2", f64(3.0)), ("fd4", f64(5.0))],
     [("fd6", f64(2.0)), ("KI", f64(3.0)), ("M1", f64(15.0)), ("A1", f64(3.0)), ("T", f64(4.0))])
# mm12msm.ss (PFMSM DPC 9): M = src1 * src2, A = M-last - M-last; fdest gets the M result.
case("mm12msm_ss",
     [dual(9, 1, 2, 3, 4, P=0)],
     [("f2", f32(2.0)), ("f3", f32(4.0)), ("M3", f32(1.5)), ("A3", f32(9.0))],
     [("f4", f32(1.5)), ("M1", f32(8.0)), ("A1", 0)])
# ---------------------------------------------------------------- graphics (8.5)
case("faddp_8bit_pixels", [fp("faddp", 2, 4, 6, "dd")],
     [("PS", 0), ("MERGE", 0x1111111111111111), ("fd2", 0x0180028003800480), ("fd4", 0x0080008000800080)],
     [("fd6", 0x0200030004000500), ("MERGE", 0x0211031104110511)])
case("faddz_form", [fp("faddz", 2, 4, 0, "dd"), fp("form", 6, 0, 8, "dd")],
     [("MERGE", 0xaaaabbbbccccdddd), ("fd2", 0x0001000000020000), ("fd4", 0x0001800000018000),
      ("fd6", 0x0000000000000003)],
     [("fd8", 0x0002aaaa0003cccf), ("MERGE", 0)])
case("fzchks_pm", [fp("fzchks", 2, 4, 6, "dd")],
     [("PM", 0xa0), ("fd2", 0x0005000a00010004), ("fd4", 0x0006000900010003)],
     [("fd6", 0x0005000900010003), ("PM", 0x7a)])
case("pst_d_16bit", [pst(2, 8, 4)],
     [("PS", 1), ("PM", 0x35), ("r4", 0x2000), ("fd2", 0x1111222233334444),
      ("ram:2008/8", 0xaaaabbbbccccdddd)],
     [("ram:2008/8", 0xaaaa2222cccc4444), ("PM", 0x03)])
# ---------------------------------------------------------------- dual-instruction mode (8.6)
# d.fnop at an aligned address, one more single instruction, then pairs. In the pair the
# floating-point compare and the core bc run in parallel: bc tests the CC from before the
# compare (8.6.1, rule 1), so it is not taken and both increments run (r6 = 7; a taken branch
# would give 4). The last addu leaves CC clear. A call in the core word links the address
# after the delay pair.
case("dual_mode_compare_and_branch",
     [DFNOP, NOP,
      fp("pfgt", 2, 3, 0, P=1, D=1), bc(at(3), at(8)),
      fp("fadd", 2, 3, 4), alu("addu", 1, 6, 6, True),
      FNOP, alu("addu", 2, 6, 6, True),
      alu("addu", 4, 6, 6, True)],
     [("f2", f32(2.0)), ("f3", f32(1.0)), ("CC", 0), ("r6", 0)],
     [("CC", 0), ("r6", 7), ("f4", f32(3.0))])
case("dual_mode_core_sets_cc",
     [DFNOP, NOP,
      fp("pfeq", 2, 3, 0, P=1, D=1), alu("subu", 4, 4, 0),
      FNOP, NOP, FNOP, NOP, NOP],
     [("f2", f32(2.0)), ("f3", f32(1.0)), ("r4", 1), ("CC", 1)],
     [("CC", 0)])                                          # rule 4: pfeq's CC wins
case("dual_mode_call_link",
     [DFNOP, NOP,
      fp("fadd", 2, 2, 2, D=1), call(at(3), at(12)),
      fp("fadd", 3, 3, 3, D=1), alu("addu", 1, 6, 6, True),
      FNOP, alu("addu", 2, 6, 6, True),
      FNOP, NOP, NOP, NOP,
      alu("addu", 0x10, 6, 6, True)],
     [("f2", f32(1.0)), ("f3", f32(2.0)), ("r6", 0)],
     [("r1", at(6)), ("r6", 0x11), ("f2", f32(2.0)), ("f3", f32(4.0))], main=4 * 13)
# ---------------------------------------------------------------- XP I/O space (7.15)
case("ldio_stio", [esc(9, s1=5, s2=4, sz=2), esc(8, s2=4, d=6, sz=1)],
     [("r4", 0x40), ("r5", 0x1234fedc)], [("io:40/4", 0x1234fedc), ("r6", 0xfffffedc)], flags="xp")


def main():
    broken = "--broken" in sys.argv
    out = []
    for i, (name, words, sets, expect, flags, mainlen) in enumerate(CASES):
        out.append(f"case {name} {flags}".rstrip())
        out.append("code " + "".join(struct.pack("<I", w).hex() for w in words))
        if mainlen is not None:
            out.append(f"main {mainlen}")
        for k, v in sets:
            out.append(f"set {k} {v:#x}")
        for j, (k, v) in enumerate(expect):
            if broken and i == 0 and j == 0:
                v ^= 1
            out.append(f"expect {k} {v:#x}")
        out.append("end")
    print("\n".join(out))


if __name__ == "__main__":
    main()
