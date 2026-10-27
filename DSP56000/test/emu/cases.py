#!/usr/bin/env python3
"""Emulator cases for the DSP56000 language: hand-assembled code with expected results worked
out by hand from the DSP56000 Family Manual (instruction pages in Appendix A, condition codes
in A.5, data shifter/limiter in 3.x, address modifiers in 4.x).

    cases.py > cases.txt            all cases
    cases.py --broken > bad.txt     the same with one deliberately wrong expectation
    cases.py --asm                  the assembler text of every case (asl syntax), used by
                                    check-encodings.sh to confirm the hand encodings

Code is placed at p:0100 and runs until the PC reaches the end of the main code ("main"
words, default the whole code); subroutines may follow. Accumulators are written as
0xA2_A1A1A1_A0A0A0 (56 bits). Unset registers are 0, except M0-M7 = FFFFh (linear).
"""
import sys

CASES = []


def case(name, asm, words, sets=(), expect=(), main=None):
    CASES.append((name, asm, words, sets, expect, main))


def acc(a2, a1, a0):
    return ((a2 & 0xff) << 48) | ((a1 & 0xffffff) << 24) | (a0 & 0xffffff)


# ---------------------------------------------------------------- data ALU and flags
case("add_x0_a", "add x0,a", [0x200040],
     [("X0", 0x400000), ("A", acc(0, 0x200000, 0))],
     [("A", acc(0, 0x600000, 0)), ("N", 0), ("Z", 0), ("V", 0), ("C", 0), ("E", 0), ("U", 0)])
case("add_into_extension", "add x0,a", [0x200040],
     [("X0", 0x400000), ("A", acc(0, 0x400000, 0))],
     [("A", acc(0, 0x800000, 0)), ("E", 1), ("U", 0), ("N", 0), ("V", 0), ("L", 0)])
case("sub_borrow", "sub x0,a", [0x200044],
     [("X0", 0x000001), ("A", 0)],
     [("A", acc(0xff, 0xffffff, 0)), ("C", 1), ("N", 1), ("Z", 0), ("E", 0), ("U", 1)])
case("cmp_equal", "cmp x0,a", [0x200045],
     [("X0", 0x123456), ("A", acc(0, 0x123456, 0)), ("C", 1)],
     [("A", acc(0, 0x123456, 0)), ("Z", 1), ("C", 0), ("N", 0)])
case("tfr_negative_x0_b", "tfr x0,b", [0x200049],
     [("X0", 0x800000), ("B", acc(0x12, 0x345678, 0x9abcde))],
     [("B", acc(0xff, 0x800000, 0))])
case("mpy_half_half", "mpy x0,x0,a", [0x200080],
     [("X0", 0x400000), ("A", acc(0x12, 0x345678, 0x9abcde))],
     [("A", acc(0, 0x200000, 0)), ("V", 0), ("N", 0)])
case("mpy_negated", "mpy -x0,x0,a", [0x200084],
     [("X0", 0x400000)],
     [("A", acc(0xff, 0xe00000, 0)), ("N", 1)])
case("mac_y0_x0", "mac y0,x0,a", [0x2000d2],
     [("X0", 0x400000), ("Y0", 0x200000), ("A", acc(0, 0x100000, 0))],
     [("A", acc(0, 0x200000, 0))])
case("macr_convergent_down", "macr y0,x0,a", [0x2000d3],
     [("X0", 0x000001), ("Y0", 0x400000), ("A", 0)],
     [("A", 0), ("Z", 1)])
case("macr_convergent_up", "macr y0,x0,a", [0x2000d3],
     [("X0", 0x000001), ("Y0", 0x400000), ("A", acc(0, 0x000001, 0))],
     [("A", acc(0, 0x000002, 0))])
case("rnd", "rnd a", [0x200011],
     [("A", acc(0, 0x123456, 0x900000))],
     [("A", acc(0, 0x123457, 0))])
case("asl_into_extension", "asl a", [0x200032],
     [("A", acc(0, 0x400000, 0x000001))],
     [("A", acc(0, 0x800000, 0x000002)), ("C", 0), ("V", 0), ("E", 1)])
case("asl_overflow_carry", "asl a", [0x200032],
     [("A", acc(0x80, 0, 0))],
     [("A", 0), ("C", 1), ("V", 1), ("L", 1), ("Z", 1)])
case("asr_carry", "asr a", [0x200022],
     [("A", acc(0xff, 0x000000, 0x000001))],
     [("A", acc(0xff, 0x800000, 0)), ("C", 1), ("N", 1)])
case("lsl_a1_only", "lsl a", [0x200033],
     [("A", acc(0x12, 0x800001, 0x345678))],
     [("A", acc(0x12, 0x000002, 0x345678)), ("C", 1), ("N", 0), ("Z", 0)])
case("lsr", "lsr a", [0x200023],
     [("A", acc(0, 0x000003, 0))],
     [("A", acc(0, 0x000001, 0)), ("C", 1), ("N", 0)])
case("rol_through_carry", "rol a", [0x200037],
     [("A", acc(0, 0x400000, 0)), ("C", 1)],
     [("A", acc(0, 0x800001, 0)), ("C", 0), ("N", 1)])
case("ror_to_zero", "ror a", [0x200027],
     [("A", acc(0, 0x000001, 0)), ("C", 0)],
     [("A", 0), ("C", 1), ("Z", 1)])
case("and_x0", "and x0,a", [0x200046],
     [("X0", 0x0ff00f), ("A", acc(0xff, 0xf0f0f0, 0x123456))],
     [("A", acc(0xff, 0x00f000, 0x123456)), ("N", 0), ("Z", 0), ("V", 0)])
case("not", "not a", [0x200017],
     [("A", acc(0, 0x00ff00, 0))],
     [("A", acc(0, 0xff00ff, 0)), ("N", 1)])
case("neg", "neg a", [0x200036],
     [("A", acc(0, 0x000001, 0))],
     [("A", acc(0xff, 0xffffff, 0)), ("N", 1)])
case("abs", "abs a", [0x200026],
     [("A", acc(0xff, 0xffffff, 0))],
     [("A", acc(0, 0x000001, 0)), ("N", 0)])
case("adc_long", "adc x,a", [0x200021],
     [("X", 0x000000000001), ("A", 0), ("C", 1)],
     [("A", 2), ("C", 0)])
case("addl", "addl b,a", [0x200012],
     [("A", acc(0, 0x100000, 0)), ("B", acc(0, 0x010000, 0))],
     [("A", acc(0, 0x210000, 0))])
case("addr", "addr b,a", [0x200002],
     [("A", acc(0, 0x200000, 0)), ("B", acc(0, 0x010000, 0))],
     [("A", acc(0, 0x110000, 0))])
case("cmpm_equal_magnitudes", "cmpm x0,a", [0x200047],
     [("X0", 0x400000), ("A", acc(0xff, 0xc00000, 0))],
     [("Z", 1)])
case("clr", "clr a", [0x200013],
     [("A", acc(0x12, 0x345678, 0x9abcde)), ("N", 1), ("V", 1)],
     [("A", 0), ("Z", 1), ("U", 1), ("E", 0), ("N", 0), ("V", 0)])
case("tst_keeps_carry", "tst a", [0x200003],
     [("A", acc(0xff, 0x800000, 0)), ("C", 1), ("V", 1)],
     [("N", 1), ("Z", 0), ("V", 0), ("C", 1)])
case("div_24_steps", "rep #24 / div x0,a", [0x0618a0, 0x018040],
     [("X0", 0x400000), ("A", acc(0, 0x100000, 0)), ("C", 0)],
     [("A0", 0x200000)])
case("norm_shift_left", "norm r0,a", [0x01d815],
     [("A", acc(0, 0x100000, 0)), ("R0", 5)],
     [("A", acc(0, 0x200000, 0)), ("R0", 4)])

# ---------------------------------------------------------------- parallel moves
case("move_loads_after_alu_reads", "add x0,a x:(r0)+,x0", [0x44d840],
     [("X0", 0x100000), ("A", 0), ("R0", 0x10), ("x:0010", 0x300000)],
     [("A", acc(0, 0x100000, 0)), ("X0", 0x300000), ("R0", 0x11)])
case("move_stores_old_accumulator", "add x0,a a,x:(r1)+", [0x565940],
     [("X0", 0x100000), ("A", acc(0, 0x100000, 0)), ("R1", 0x20)],
     [("x:0020", 0x100000), ("A", acc(0, 0x200000, 0)), ("R1", 0x21)])
case("limit_positive", "move a,x0", [0x21c400],
     [("A", acc(0x01, 0, 0))],
     [("X0", 0x7fffff), ("L", 1)])
case("limit_negative", "move a,x0", [0x21c400],
     [("A", acc(0xfe, 0, 0))],
     [("X0", 0x800000), ("L", 1)])
case("no_limit", "move a,x0", [0x21c400],
     [("A", acc(0, 0x123456, 0x789abc))],
     [("X0", 0x123456), ("L", 0)])
case("move_mem_to_a_sign_extends", "move x:(r0),a", [0x56e000],
     [("R0", 0x30), ("x:0030", 0x800000), ("A", acc(0x12, 0x345678, 0x9abcde))],
     [("A", acc(0xff, 0x800000, 0))])
case("imm_short_x0_left", "move #$12,x0", [0x241200], [], [("X0", 0x120000)])
case("imm_short_a0_right", "move #$12,a0", [0x281200],
     [("A", acc(0x11, 0x222222, 0x333333))], [("A", acc(0x11, 0x222222, 0x000012))])
case("imm_short_a_signed", "move #$80,a", [0x2e8000], [], [("A", acc(0xff, 0x800000, 0))])
case("imm_short_r3", "move #$12,r3", [0x331200], [], [("R3", 0x12)])
case("long_load_a", "move l:(r0)+,a", [0x48d800],
     [("R0", 0x40), ("x:0040", 0x123456), ("y:0040", 0x789abc)],
     [("A", acc(0, 0x123456, 0x789abc)), ("R0", 0x41)])
case("long_store_limited", "move a,l:(r0)", [0x486000],
     [("R0", 0x40), ("A", acc(0x01, 0, 0))],
     [("x:0040", 0x7fffff), ("y:0040", 0xffffff), ("L", 1)])
case("xy_move", "move x:(r0)+,x0 y:(r4)+,y0", [0xf09800],
     [("R0", 0x10), ("R4", 0x20), ("x:0010", 0x111111), ("y:0020", 0x222222)],
     [("X0", 0x111111), ("Y0", 0x222222), ("R0", 0x11), ("R4", 0x21)])
case("xy_move_upper_bank_for_x", "move x:(r4)-,x1 y1,y:(r1)+n1", [0x95b400],
     [("R4", 0x10), ("R1", 0x20), ("N1", 4), ("x:0010", 0x0abcde), ("Y1", 0x654321)],
     [("X1", 0x0abcde), ("y:0020", 0x654321), ("R4", 0x0f), ("R1", 0x24)])
case("class1_x_r", "move x:(r2)+,x1 a,y0", [0x149a00],
     [("R2", 0x50), ("x:0050", 0x0a0a0a), ("A", acc(0, 0x111111, 0x222222))],
     [("X1", 0x0a0a0a), ("Y0", 0x111111), ("R2", 0x51)])
case("class2_a_to_x_x0_to_a", "move a,x:(r0)+ x0,a", [0x081800],
     [("R0", 0x60), ("A", acc(0, 0x123456, 0)), ("X0", 0x400000)],
     [("x:0060", 0x123456), ("A", acc(0, 0x400000, 0)), ("R0", 0x61)])

# ---------------------------------------------------------------- address generation
case("ea_post_minus_n", "move x:(r0)-n0,x0", [0x44c000],
     [("R0", 0x20), ("N0", 3), ("x:0020", 0x5)], [("X0", 0x5), ("R0", 0x1d)])
case("ea_indexed", "move x:(r1+n1),x0", [0x44e900],
     [("R1", 0x20), ("N1", 3), ("x:0023", 0x7)], [("X0", 0x7), ("R1", 0x20)])
case("ea_predecrement", "move x:-(r2),x0", [0x44fa00],
     [("R2", 0x20), ("x:001f", 0x9)], [("X0", 0x9), ("R2", 0x1f)])
case("modulo_wrap_up", "move x:(r0)+,x0", [0x44d800],
     [("M0", 3), ("R0", 0x0007), ("x:0007", 0x1)], [("X0", 0x1), ("R0", 0x0004)])
case("modulo_wrap_down", "move x:(r0)-,x0", [0x44d000],
     [("M0", 3), ("R0", 0x0004)], [("R0", 0x0007)])
case("modulo_plus_n", "move x:(r0)+n0,x0", [0x44c800],
     [("M0", 4), ("R0", 0x0013), ("N0", 3)], [("R0", 0x0011)])
case("modulo_block_jump", "move x:(r0)+n0,x0", [0x44c800],
     [("M0", 20), ("R0", 0x0045), ("N0", 32)], [("R0", 0x0065)])
case("multiple_wrap_modulo_8", "move x:(r0)+n0,x0", [0x44c800],
     [("M0", 0x8007), ("R0", 0x0046), ("N0", 3)], [("R0", 0x0041)])
case("bit_reverse_fft_order", "move x:(r0)+n0,x0 / move x:(r0)+n0,x0", [0x44c800, 0x44c800],
     [("M0", 0), ("R0", 0), ("N0", 8)], [("R0", 0x0004)])
case("update_only", "move (r3)+n3", [0x204b00], [("R3", 0x10), ("N3", 5)], [("R3", 0x15)])
case("lua", "lua (r3)+n3,r5", [0x044b15], [("R3", 0x10), ("N3", 5)], [("R5", 0x15), ("R3", 0x10)])

# ---------------------------------------------------------------- loops and flow
case("rep_add", "rep #3 / add x0,a", [0x0603a0, 0x200040],
     [("X0", 0x000001), ("LC", 0x77)], [("A", acc(0, 0x000003, 0)), ("LC", 0x77)])
case("do_loop", "do #3,end / add x0,a / end:", [0x060380, 0x000102, 0x200040],
     [("X0", 0x000002), ("LA", 0x1234), ("LC", 0x55)],
     [("A", acc(0, 0x000006, 0)), ("SP", 0), ("LA", 0x1234), ("LC", 0x55), ("MR", 0)])
case("do_loop_two_word_last", "do #2,end / add x1,a / move #>3,x1 / end:",
     [0x060280, 0x000104, 0x200060, 0x45f400, 0x000003],
     [("X1", 0x000001)],
     [("A", acc(0, 0x000004, 0)), ("SP", 0), ("MR", 0)])
case("jsr_rts", "jsr sub / nop / sub: add x0,a / rts", [0x0d0102, 0, 0x200040, 0x00000c],
     [("X0", 0x000005)], [("A", acc(0, 0x000005, 0)), ("SP", 0)], main=1)
case("jeq_taken", "cmp x0,a / jeq skip / add x0,a / skip:", [0x200045, 0x0ea103, 0x200040],
     [("X0", 0x100000), ("A", acc(0, 0x100000, 0))], [("A", acc(0, 0x100000, 0))])
case("jeq_not_taken", "cmp x0,a / jeq skip / add x0,a / skip:", [0x200045, 0x0ea103, 0x200040],
     [("X0", 0x100000), ("A", acc(0, 0x200000, 0))], [("A", acc(0, 0x300000, 0))])
case("jclr_taken", "jclr #3,x:(r0),skip / add x0,a / skip:", [0x0a6083, 0x000103, 0x200040],
     [("R0", 0x10), ("x:0010", 0xfff7), ("X0", 1)], [("A", 0), ("C", 0)])
case("jset_not_taken", "jset #3,x:(r0),skip / add x0,a / skip:", [0x0a60a3, 0x000103, 0x200040],
     [("R0", 0x10), ("x:0010", 0xfff7), ("X0", 0x000001)], [("A", acc(0, 0x000001, 0))])

# ---------------------------------------------------------------- bits, control registers
case("bset_memory", "bset #4,x:<$10", [0x0a1024], [("x:0010", 0)], [("x:0010", 0x10), ("C", 0)])
case("btst_memory", "btst #23,x:<$10", [0x0b1037], [("x:0010", 0x800000)], [("x:0010", 0x800000), ("C", 1)])
case("bchg_register", "bchg #0,r0", [0x0bd040], [("R0", 0x10)], [("R0", 0x11), ("C", 0)])
case("movec_imm_sr", "movec #$09,sr", [0x0509b9], [("MR", 0x03)], [("C", 1), ("N", 1), ("Z", 0), ("MR", 0)])
case("ori_ccr", "ori #$04,ccr", [0x0004f9], [], [("Z", 1)])
case("andi_ccr", "andi #$fe,ccr", [0x00feb9], [("C", 1), ("N", 1)], [("C", 0), ("N", 1)])
case("tgt_with_r_move", "tgt x0,a r0,r1", [0x037041],
     [("X0", 0x400000), ("R0", 0x33), ("A", acc(0, 0x100000, 0))],
     [("A", acc(0, 0x400000, 0)), ("R1", 0x33)])
case("tgt_false", "tgt x0,a r0,r1", [0x037041],
     [("X0", 0x400000), ("R0", 0x33), ("Z", 1), ("A", acc(0, 0x100000, 0))],
     [("A", acc(0, 0x100000, 0)), ("R1", 0)])
case("movep_mem_to_peripheral", "movep x:(r0),x:$ffc5", [0x08e085],
     [("R0", 0x10), ("x:0010", 0xabcdef)], [("x:ffc5", 0xabcdef)])
case("movem_p_to_x0", "movem p:(r0),x0", [0x07e084],
     [("R0", 0x0100)], [("X0", 0x07e084)])
case("scale_down_move", "ori #$04,mr / move a,x0", [0x0004f8, 0x21c400],
     [("A", acc(0, 0x400000, 0))], [("X0", 0x200000), ("MR", 0x04)])
case("scale_up_long_store", "ori #$08,mr / move a,l:(r0)", [0x0008f8, 0x486000],
     [("R0", 0x40), ("A", acc(0, 0x123456, 0x789abc))],
     [("x:0040", 0x2468ac), ("y:0040", 0xf13578), ("L", 0), ("MR", 0x08)])
case("scale_down_long_store", "ori #$04,mr / move a,l:(r0)", [0x0004f8, 0x486000],
     [("R0", 0x40), ("A", acc(0, 0x123456, 0x789abc))],
     [("x:0040", 0x091a2b), ("y:0040", 0x3c4d5e), ("L", 0), ("MR", 0x04)])
case("ssh_push_pop", "movec x0,ssh / movec ssh,x1", [0x04c4bc, 0x0445bc],
     [("X0", 0x00abcd)], [("X1", 0x00abcd), ("SP", 0)])
case("inc_56002", "inc a", [0x000008], [("A", acc(0, 0, 0xffffff))], [("A", acc(0, 1, 0))])
case("mpy_imm_shift_56002", "mpy x0,#1,a", [0x0101d0], [("X0", 0x400000)], [("A", acc(0, 0x200000, 0))])


def emit(broken=False):
    out = ["# generated by test/emu/cases.py; do not edit"]
    for i, (name, asm, words, sets, expect, main) in enumerate(CASES):
        out.append("case " + name)
        out.append("code " + " ".join("%06x" % w for w in words))
        if main is not None:
            out.append("main %d" % main)
        for r, v in sets:
            out.append("set %s 0x%x" % (r, v))
        for j, (r, v) in enumerate(expect):
            if broken and i == 0 and j == 0:
                v ^= 1
            out.append("expect %s 0x%x" % (r, v))
        out.append("end")
    print("\n".join(out))


if __name__ == "__main__":
    if "--asm" in sys.argv:
        for name, asm, words, sets, expect, main in CASES:
            print("%s\t%s\t%s" % (name, asm, " ".join("%06x" % w for w in words)))
    else:
        emit("--broken" in sys.argv)
