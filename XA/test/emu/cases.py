#!/usr/bin/env python3
"""Emulator cases for the XA module: hand-assembled code with expected results worked out by
hand from the XA User Guide (instruction pages in chapter 6, stack frames in 4.7/4.8).

    cases.py > cases.txt            all cases
    cases.py --broken > bad.txt     the same with one deliberately wrong expectation (the test
                                    harness must report it)

Code is placed at code:001000 and runs until the PC reaches the end of the main code ("main"
bytes, default the whole code); subroutines and data may follow. R7 (SP) starts at 8000h.
Byte registers: R0L=0 R0H=1 R1L=2 ... R7H=15 in register fields.
"""
import sys

CASES = []


def case(name, code, sets=(), expect=(), flags="", main=None):
    CASES.append((name, code.replace(" ", ""), sets, expect, flags, main))


F0 = [("C", 0), ("AC", 0), ("V", 0), ("N", 0), ("Z", 0)]

# ---------------------------------------------------------------- arithmetic and flags
case("add_w_overflow", "09 12",                      # ADD.w R1,R2
     [("R1", 0x7fff), ("R2", 0x0001)],
     [("R1", 0x8000), ("C", 0), ("AC", 1), ("V", 1), ("N", 1), ("Z", 0)])
case("add_b_carry_zero", "01 01",                    # ADD.b R0L,R0H
     [("R0", 0x01ff)],
     [("R0", 0x0100), ("C", 1), ("AC", 1), ("V", 0), ("N", 0), ("Z", 1)])
case("addc_w", "19 12",                              # ADDC.w R1,R2
     [("C", 1), ("R1", 0x1234), ("R2", 0x0001)],
     [("R1", 0x1236), ("C", 0), ("AC", 0), ("V", 0), ("N", 0), ("Z", 0)])
case("sub_b_borrow", "21 23",                        # SUB.b R1L,R1H
     [("R1", 0x2010)],
     [("R1", 0x20f0), ("C", 1), ("AC", 0), ("V", 0), ("N", 1), ("Z", 0)])
case("subb_w_overflow", "39 01",                     # SUBB.w R0,R1
     [("C", 1), ("R0", 0x8000), ("R1", 0)],
     [("R0", 0x7fff), ("C", 0), ("AC", 1), ("V", 1), ("N", 0), ("Z", 0)])
case("cmp_b_imm_equal", "91 44 5a",                  # CMP.b R2L,#5Ah
     [("R2", 0x005a), ("C", 1), ("N", 1)],
     [("R2", 0x005a), ("C", 0), ("AC", 0), ("V", 0), ("N", 0), ("Z", 1)])
case("add32_with_addc", "09 02 19 13",               # ADD.w R0,R2 ; ADDC.w R1,R3
     [("R0", 0xffff), ("R1", 0x0001), ("R2", 0x0001), ("R3", 0)],
     [("R0", 0), ("R1", 0x0002), ("C", 0), ("Z", 0)])
case("sub_w_direct_dest", "2e 08 60",                # SUB.w 060h,R0
     [("data:000060/2", 0x0100), ("R0", 1)],
     [("data:000060/2", 0x00ff), ("C", 0), ("AC", 1), ("N", 0), ("Z", 0)])
case("adds_w_minus1_keeps_carry", "a9 1f",           # ADDS.w R1,#-1
     [("R1", 0), ("C", 1)],
     [("R1", 0xffff), ("C", 1), ("N", 1), ("Z", 0)])
case("da_after_add", "01 01 90 08",                  # ADD.b R0L,R0H ; DA R0L   (38 + 45)
     [("R0", 0x4538)],
     [("R0", 0x4583), ("C", 0), ("N", 1), ("Z", 0)])
case("da_carry", "01 01 90 08",                      # 99 + 99 = 198
     [("R0", 0x9999)],
     [("R0", 0x9998), ("C", 1)])
case("neg_b_overflow", "90 0b",                      # NEG.b R0L
     [("R0", 0x0080)],
     [("R0", 0x0080), ("V", 1), ("N", 1), ("Z", 0)])
case("cpl_w", "98 2a",                               # CPL.w R2
     [("R2", 0x00ff)],
     [("R2", 0xff00), ("N", 1), ("Z", 0)])
case("sext_w_after_negative_move", "91 08 80 98 19",  # MOV.b R0L,#80h ; SEXT.w R1
     [("R1", 0x1234)],
     [("R0", 0x0080), ("R1", 0xffff), ("N", 1)])
case("sext_b_positive", "90 19",                     # SEXT.b R0H with N = 0
     [("R0", 0x5566), ("N", 0)],
     [("R0", 0x0066)])

# ---------------------------------------------------------------- logic, moves, addressing
case("and_w_imm", "99 35 0f f0",                     # AND.w R3,#0FF0h
     [("R3", 0x1234)],
     [("R3", 0x0230), ("N", 0), ("Z", 0)])
case("or_b_indirect", "62 01",                       # OR.b R0L,[R1]
     [("R0", 0x00f0), ("R1", 0x0100), ("data:000100", 0x0f)],
     [("R0", 0x00ff), ("N", 1), ("Z", 0)])
case("xor_w_indirect_dest", "7a 0a",                 # XOR.w [R2],R0
     [("R2", 0x0200), ("data:000200/2", 0xffff), ("R0", 0x00ff)],
     [("data:000200/2", 0xff00), ("N", 1)])
case("mov_w_postinc", "8b 01",                       # MOV.w R0,[R1+]
     [("R1", 0x0100), ("data:000100/2", 0xbeef)],
     [("R0", 0xbeef), ("R1", 0x0102), ("N", 1), ("Z", 0)])
case("mov_b_negative_offset", "84 01 fe",            # MOV.b R0L,[R1-2]
     [("R1", 0x0102), ("R0", 0x00ff), ("data:000100", 0)],
     [("R0", 0x0000), ("Z", 1), ("N", 0)])
case("mov_w_offset16_store", "8d 2b 10 00",          # MOV.w [R3+1000h],R2
     [("R3", 0x0100), ("R2", 0x1234)],
     [("data:001100/2", 0x1234)])
case("mov_w_direct", "8e 41 24",                     # MOV.w R4,124h
     [("data:000124/2", 0xcafe)],
     [("R4", 0xcafe)])
case("mov_ds_then_direct_store", "96 48 41 01 86 08 50",   # MOV.b DS,#1 ; MOV.b 050h,R0L
     [("R0", 0x0077)],
     [("DS", 1), ("data:010050", 0x77), ("data:000050", 0)])
case("es_through_ssel", "08 12 1a 82 02",            # SETB SSEL.2 ; MOV.b R0L,[R2]
     [("ES", 2), ("R2", 0x0010), ("data:020010", 0x99), ("data:000010", 0x11)],
     [("SSEL", 0x04), ("R0", 0x0099)])
case("movx_segment0", "a7 01",                       # MOVX.b R0L,[R1]  (DS ignored)
     [("DS", 5), ("R1", 0x0300), ("data:000300", 0x42), ("data:050300", 0x24)],
     [("R0", 0x0042)])
case("movc_postinc", "80 01",                        # MOVC.b R0L,[R1+]
     [("R1", 0x1000)],
     [("R0", 0x0080), ("R1", 0x1001), ("N", 1)])
case("movc_a_dptr", "90 4e 00 77",                   # MOVC A,[A+DPTR]
     [("R4", 0x0003), ("R6", 0x1000)],
     [("R4", 0x0077)], main=2)
case("lea_offset8", "40 12 10",                      # LEA R1,R2+10h
     [("R2", 0x0ff8)],
     [("R1", 0x1008)])
case("xch_b_direct", "a0 08 40",                     # XCH.b R0L,040h
     [("R0", 0x0011), ("data:000040", 0x22)],
     [("R0", 0x0022), ("data:000040", 0x11)])
case("movs_b_indirect", "b2 2d",                     # MOVS.b [R2],#-3
     [("R2", 0x0200)],
     [("data:000200", 0xfd), ("N", 1)])
case("mov_w_direct_direct", "9f 00 40 42",           # MOV.w 040h,042h
     [("data:000042/2", 0x5678)],
     [("data:000040/2", 0x5678)])
case("mov_b_indirect_direct", "a0 10 41",            # MOV.b [R1],041h
     [("R1", 0x0200), ("data:000041", 0x33)],
     [("data:000200", 0x33)])
case("mov_b_direct_indirect", "a0 90 45",            # MOV.b 045h,[R1]
     [("R1", 0x0200), ("data:000200", 0x44)],
     [("data:000045", 0x44)])
case("mov_b_postinc_both", "90 12",                  # MOV.b [R1+],[R2+]
     [("R1", 0x0300), ("R2", 0x0200), ("data:000200", 0x5a)],
     [("data:000300", 0x5a), ("R1", 0x0301), ("R2", 0x0201)])
case("cmp_b_ds_sfr", "46 04 41",                     # CMP.b R0L,DS
     [("R0", 0x0003), ("DS", 3)],
     [("Z", 1), ("C", 0)])

# ---------------------------------------------------------------- PSW and bits
case("pswl_explicit_write_wins", "96 48 00 81",      # MOV.b PSWL,#81h
     [("N", 0), ("Z", 0)],
     [("C", 1), ("AC", 0), ("V", 0), ("N", 0), ("Z", 1)])
case("pswl_read", "86 04 00",                        # MOV.b R0L,PSWL
     [("C", 1), ("Z", 1), ("AC", 0), ("V", 0), ("N", 0)],
     [("R0", 0x0081)])
case("pop_b_pswl", "87 14 00",                       # POP.b PSWL
     [("R7", 0x7ffe), ("data:007ffe", 0x03)],
     [("Z", 1), ("N", 1), ("C", 0), ("R7", 0x8000)])
case("setb_data_bit", "08 11 0d",                    # SETB 21h.5
     [("data:000021", 0)],
     [("data:000021", 0x20)])
case("mov_c_sfr_bit", "08 23 8c",                    # MOV C,431h.4 (P1.4)
     [("sfr:0431", 0x10), ("C", 0)],
     [("C", 1)])
case("anl_c_not_register_bit", "08 50 13",           # ANL C,/R1L.3
     [("C", 1), ("R1", 0x0000)],
     [("C", 1)])
case("orl_c_register_bit", "08 60 1b",               # ORL C,R1H.3
     [("C", 0), ("R1", 0x0800)],
     [("C", 1)])
case("clr_flag_z", "08 02 00",                       # CLR Z (bit 200h = PSWL.0)
     [("Z", 1)],
     [("Z", 0)])
case("mov_bit_c", "08 30 0f",                        # MOV R0H.7,C
     [("C", 1), ("R0", 0)],
     [("R0", 0x8000)])

# ---------------------------------------------------------------- shifts, rotates, NORM
case("asl_w_imm", "d9 14",                           # ASL.w R1,#4
     [("R1", 0x1234)],
     [("R1", 0x2340), ("C", 1), ("V", 1), ("N", 0), ("Z", 0)])
case("asl_b_sticky_v", "d1 02",                      # ASL.b R0L,#2
     [("R0", 0x0040)],
     [("R0", 0x0000), ("C", 1), ("V", 1), ("Z", 1), ("N", 0)])
case("lsr_b_reg_count", "c0 01",                     # LSR.b R0L,R0H
     [("R0", 0x0381), ("C", 1)],
     [("R0", 0x0310), ("C", 0), ("N", 0), ("Z", 0)])
case("asr_d_imm", "de 04",                           # ASR.d R0,#4
     [("R0", 0x0010), ("R1", 0x8000)],
     [("R0", 0x0001), ("R1", 0xf800), ("C", 0), ("N", 1)])
case("lsr_d_reg_count_5bits", "cc 20",               # LSR.d R2,R0L with R0L = 33 (count 1)
     [("R0", 33), ("R2", 3), ("R3", 0)],
     [("R2", 1), ("R3", 0), ("C", 1)])
case("rl_b", "d3 01",                                # RL.b R0L,#1
     [("R0", 0x0081)],
     [("R0", 0x0003), ("N", 0)])
case("rlc_w", "df 11",                               # RLC.w R1,#1
     [("C", 1), ("R1", 0x8000)],
     [("R1", 0x0001), ("C", 1)])
case("rrc_b", "b7 01",                               # RRC.b R0L,#1
     [("C", 0), ("R0", 0x0001)],
     [("R0", 0x0000), ("C", 1), ("Z", 1)])
case("rr_w_4", "b8 04",                              # RR.w R0,#4
     [("R0", 0x1234)],
     [("R0", 0x4123)])
case("norm_w", "cb 02",                              # NORM.w R0,R1L
     [("R0", 0x0010), ("R1", 0)],
     [("R0", 0x8000), ("R1", 11), ("N", 1), ("Z", 0)])

# ---------------------------------------------------------------- multiply and divide
case("mulu_b", "e0 01",                              # MULU.b R0L,R0H
     [("R0", 0x2010)],
     [("R0", 0x0200), ("V", 1), ("C", 0), ("Z", 0)])
case("mul_w_signed", "e6 02",                        # MUL.w R0,R2
     [("R0", 0xffff), ("R2", 2), ("C", 1)],
     [("R0", 0xfffe), ("R1", 0xffff), ("V", 0), ("N", 1), ("C", 0)])
case("mulu_w_imm", "e9 20 10 00",                    # MULU.w R2,#1000h
     [("R2", 0x0123)],
     [("R2", 0x3000), ("R3", 0x0012), ("V", 1)])
case("divu_b", "e1 02",                              # DIVU.b R0L,R1L   100 / 7
     [("R0", 100), ("R1", 7)],
     [("R0", 0x020e), ("V", 0), ("C", 0)])
case("div_w_signed", "e7 02",                        # DIV.w R0,R1L   -100 / 7
     [("R0", 0xff9c), ("R1", 7)],
     [("R0", 0xfef2), ("V", 0), ("N", 1)])
case("divu_d", "ed 02",                              # DIVU.d R0,R2   12345h / 100h
     [("R0", 0x2345), ("R1", 0x0001), ("R2", 0x0100)],
     [("R0", 0x0123), ("R1", 0x0045), ("V", 0)])
case("divu_w_imm_overflow", "e8 03 02",              # DIVU.w R0,#2   400h / 2
     [("R0", 0x0400)],
     [("V", 1), ("C", 0)])

# ---------------------------------------------------------------- branches and loops
case("cjne_taken", "e3 00 01 05 b1 21",              # CJNE.b R0L,#5,+1 ; MOVS.b R1L,#1
     [("R0", 3), ("R1", 0)],
     [("R1", 0), ("C", 1), ("N", 1), ("Z", 0)])
case("cjne_not_taken", "e3 00 01 05 b1 21",
     [("R0", 5), ("R1", 0)],
     [("R1", 1), ("C", 0), ("Z", 0), ("N", 0)])      # Z from the MOVS that follows
case("djnz_b_loop", "b1 03 b9 10 a9 12 87 08 fe",    # R0L=3; R1=0; loop: ADDS R1,#2; DJNZ R0L
     [],
     [("R1", 6), ("R0", 0), ("Z", 1)])
case("djnz_w_direct", "a9 11 ea 08 40 fd",           # loop: ADDS.w R1,#1 ; DJNZ.w 040h
     [("R1", 0), ("data:000040/2", 3)],
     [("R1", 3), ("data:000040/2", 0)])
case("bg_unsigned_taken", "49 01 f8 01 b1 41",       # CMP.w R0,R1 ; BG +1 ; MOVS.b R2L,#1
     [("R0", 5), ("R1", 3), ("R2", 0)],
     [("R2", 0)])
case("blt_signed_taken", "49 01 fb 01 b1 41",        # CMP.w R0,R1 ; BLT
     [("R0", 0xffff), ("R1", 1), ("R2", 0)],
     [("R2", 0)])
case("bg_not_taken_when_equal", "49 01 f8 01 b1 41",
     [("R0", 3), ("R1", 3), ("R2", 0)],
     [("R2", 1)])
case("jb_carry", "00 08 12 07 97 82 07 01 b1 41",    # NOP ; SETB C ; JB C,+1 ; MOVS.b R2L,#1
     [("R2", 0), ("C", 0)],
     [("R2", 0), ("C", 1)])
case("jbc_register_bit", "97 c0 13 01 b1 41",        # JBC R1L.3,+1
     [("R1", 0x0008), ("R2", 0)],
     [("R1", 0), ("R2", 0)])
case("jnb_not_taken", "97 a0 13 01 b1 41",           # JNB R1L.3,+1 with the bit set
     [("R1", 0x0008), ("R2", 0)],
     [("R1", 0x0008), ("R2", 1)])
case("jnz_accumulator", "ee 01 b1 41",               # JNZ +1 (A = R4L)
     [("R4", 0x0001), ("R2", 0)],
     [("R2", 0)])

# ---------------------------------------------------------------- stack, calls, traps
case("push_pop_word_lists", "0f 06 2f 18",           # PUSH.w R1,R2 ; POP.w R3,R4
     [("R1", 0x1111), ("R2", 0x2222)],
     [("R3", 0x1111), ("R4", 0x2222), ("R7", 0x8000),
      ("data:007ffc/2", 0x1111), ("data:007ffe/2", 0x2222)])
case("push_byte_leaves_high_byte", "07 01",          # PUSH.b R0L
     [("R0", 0x00ab), ("data:007fff", 0x55)],
     [("R7", 0x7ffe), ("data:007ffe", 0xab), ("data:007fff", 0x55)])
case("pushu_via_usp", "98 1f 1f 04 90 3f",           # MOV USP,R1 ; PUSHU.w R2 ; MOV R3,USP
     [("R1", 0x0400), ("R2", 0xbeef)],
     [("USP", 0x03fe), ("data:0003fe/2", 0xbeef), ("R3", 0x03fe), ("R7", 0x8000)])
case("call_ret_native", "c5 00 01 00 b1 05 d6 80",   # CALL +1 ; NOP | sub: MOVS R0L,#5 ; RET
     [],
     [("R0", 5), ("R7", 0x8000), ("data:007ffc/2", 0x0000), ("data:007ffe/2", 0x1003)],
     flags="native", main=3)
case("call_ret_page0", "c5 00 01 00 b1 05 d6 80",
     [],
     [("R0", 5), ("R7", 0x8000), ("data:007ffe/2", 0x1003)],
     flags="page0", main=3)
case("fcall", "c4 10 06 00 00 00 b1 07 d6 80",       # FCALL 001006h | sub: MOVS R0L,#7 ; RET
     [],
     [("R0", 7), ("R7", 0x8000)], main=4)
case("call_indirect", "c6 02 00 00 b1 06 d6 80",     # CALL [R2] | sub at 1004h
     [("R2", 0x1004)],
     [("R0", 6), ("R7", 0x8000)], main=2)
case("jmp_double_indirect", "d6 61 00 00 b1 03" + "00" * 10 + "04 10",   # JMP [[R1+]]
     [("R1", 0x1010)],
     [("R1", 0x1012), ("R0", 3)], main=6)
case("trap_reti_native", "d6 31 00 00 b1 04 d6 90",  # TRAP #1 | handler: MOVS R0L,#4 ; RETI
     [("code:000044/2", 0x8f00), ("code:000046/2", 0x1004), ("C", 1), ("Z", 0), ("PSWH", 0)],
     [("R0", 0x04), ("R7", 0x8000), ("C", 1), ("Z", 0), ("PSWH", 0),
      ("data:007ffa/2", 0x0080), ("data:007ffc/2", 0x0000), ("data:007ffe/2", 0x1002)],
     flags="native", main=2)
case("trap_reti_page0", "d6 31 00 00 b1 04 d6 90",
     [("code:000044/2", 0x8f00), ("code:000046/2", 0x1004), ("C", 1), ("Z", 0), ("PSWH", 0)],
     [("R0", 0x04), ("R7", 0x8000), ("C", 1), ("Z", 0), ("PSWH", 0),
      ("data:007ffc/2", 0x0080), ("data:007ffe/2", 0x1002)],
     flags="page0", main=2)


def main():
    broken = "--broken" in sys.argv
    print("# generated by test/emu/cases.py; do not edit")
    for i, (name, code, sets, expect, flags, main_len) in enumerate(CASES):
        print(f"case {name} {flags}".rstrip())
        print(f"code {code}")
        if main_len is not None:
            print(f"main {main_len}")
        for k, v in sets:
            print(f"set {k} {v:#x}")
        for j, (k, v) in enumerate(expect):
            if broken and i == 0 and j == 0:
                v ^= 1
            print(f"expect {k} {v:#x}")
        print("end")


if __name__ == "__main__":
    main()
