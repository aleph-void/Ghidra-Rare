#!/usr/bin/env python3
"""Emulator cases for the DSP56156 language: code assembled with Motorola ASM56100 (run as a
black box; the source line is kept with each case), expectations worked out by hand from the
DSP56100 Family Manual (instruction pages, condition codes, Table 5-2 saturation, rounding).

    cases156.py > cases156.txt          all cases
    cases156.py --broken > bad.txt      the same with one deliberately wrong expectation

Code is placed at p:0100 and runs until the PC reaches the end of the main code ("main" words,
default all). Registers not set start at 0 except M0-M3 = FFFFh."""
import sys

CASES = [
    # add x0,a
    ('add_x0_a', '4a04', None, [('X0', 16384), ('A', 536870912)], [('A', 1610612736), ('N', 0), ('Z', 0), ('V', 0), ('C', 0)]),
    # add b,a
    ('add_acc_overflow', '4a00', None, [('A', 549755813888), ('B', 549755813888)], [('A', 0), ('C', 1), ('V', 1), ('Z', 1), ('L', 1)]),
    # sub x0,a
    ('sub_borrow', '4a44', None, [('A', 0), ('X0', 1)], [('A', 1099511562240), ('C', 1), ('N', 1), ('V', 0), ('Z', 0)]),
    # mpy x0,y0,a
    ('mpy_half_half', '4a84', None, [('X0', 16384), ('Y0', 16384)], [('A', 536870912), ('N', 0), ('V', 0)]),
    # mac -x0,y0,a
    ('mac_negated', '4ae4', None, [('X0', 16384), ('Y0', 16384), ('A', 1073741824)], [('A', 536870912)]),
    # macr x0,y0,a
    ('macr_convergent_even', '4ab4', None, [('X0', 16384), ('Y0', 1), ('A', 0)], [('A', 0)]),
    # macr x0,y0,a
    ('macr_twos_complement', '4ab4', None, [('X0', 16384), ('Y0', 1), ('A', 0), ('OMR', 32)], [('A', 65536)]),
    # rnd a
    ('rnd_up', '4a20', None, [('A', 305430529)], [('A', 305463296)]),
    # clr a
    ('clr', '4a01', None, [('A', 78187493520)], [('A', 0), ('Z', 1), ('N', 0), ('U', 1), ('E', 0)]),
    # tst a
    ('tst_negative', '4a21', None, [('A', 1097364144128), ('C', 1)], [('N', 1), ('Z', 0), ('E', 0), ('U', 0), ('V', 0), ('C', 0)]),
    # asl a
    ('asl_into_extension', '4a31', None, [('A', 1073741824)], [('A', 2147483648), ('C', 0), ('V', 0), ('E', 1)]),
    # asr a
    ('asr_carry', '4a30', None, [('A', 3)], [('A', 1), ('C', 1)]),
    # lsl a
    ('lsl_a1', '4a33', None, [('A', 3221230132)], [('A', 2147488308), ('C', 1), ('N', 1), ('Z', 0)]),
    # and x0,a
    ('and_x0', '4a64', None, [('A', 4278190080), ('X0', 3855)], [('A', 251658240), ('N', 0), ('Z', 0), ('V', 0)]),
    # neg a
    ('neg', '4a60', None, [('A', 65536)], [('A', 1099511562240), ('N', 1)]),
    # abs a
    ('abs', '4a71', None, [('A', 1099511562240)], [('A', 65536), ('N', 0)]),
    # move a,x0
    ('move_a_x0_limited', '2880', None, [('A', 4294967296)], [('X0', 32767), ('L', 1)]),
    # move x:(r0)+,x0
    ('move_postinc', '3c04', None, [('R0', 16), ('x:0010', 4660)], [('X0', 4660), ('R0', 17)]),
    # move y0,x:(r1)+n1
    ('move_store_plus_n', '382d', None, [('R1', 32), ('N1', 5), ('Y0', 43981)], [('x:0020', 43981), ('R1', 37)]),
    # move x:(r0)+,x0
    ('modulo_wrap', '3c04', None, [('R0', 19), ('M0', 3), ('x:0013', 119)], [('X0', 119), ('R0', 16)]),
    # move x:(r0)+n0,x0
    ('bit_reverse', '3c0c', None, [('R0', 8), ('N0', 8), ('M0', 0)], [('R0', 4)]),
    # move x:(r0)+,x0 / chkaau
    ('chkaau_after_wrap', '3c04 0004', None, [('R0', 19), ('M0', 3)], [('R0', 16), ('V', 1), ('Z', 0)]),
    # move x:(r2+n2),lc
    ('movec_indexed_no_update', '3d12', None, [('R2', 64), ('N2', 2), ('x:0042', 9)], [('LC', 9), ('R2', 64)]),
    # add x0,a x:(r0)+,b x:(r3)+,x0
    ('dual_read_uses_old_x0', '6000', None, [('X0', 1), ('A', 0), ('R0', 48), ('R3', 64), ('x:0030', 4369), ('x:0040', 8738)], [('A', 65536), ('B', 286326784), ('X0', 8738), ('R0', 49), ('R3', 65)]),
    # rep #3 / inc a
    ('rep_inc', '0f03 4a22', None, [('A', 0), ('LC', 7)], [('A', 3), ('LC', 7)]),
    # do #4,endl / inc a / endl nop
    ('do_loop', '0e04 0001 4a22 0000', None, [('A', 0)], [('A', 4), ('SP', 0), ('MR', 0)]),
    # jsr fn / nop / nop / fn inc a / rts
    ('jsr_rts', '0130 0104 0000 0000 4a22 0006', 3, [('A', 0)], [('A', 1), ('SP', 0)]),
    # bfset #$00f0,x:$5
    ('bfset_aa', '14c5 38f0', None, [('x:0005', 259)], [('x:0005', 499), ('C', 0)]),
    # bftstl #$0f00,x0
    ('bftstl_reg', '1400 800f', None, [('X0', 4608), ('C', 1)], [('C', 0)]),
    # bfclr #$1200,x:(r1)
    ('bfclr_rn', '14b1 8412', None, [('R1', 80), ('x:0050', 4660)], [('x:0050', 52), ('C', 0), ('R1', 80)]),
    # movep x:$ffe5,x0
    ('movep_read', '1925', None, [('x:ffe5', 85)], [('X0', 85)]),
    # teq x0,a r0,r2
    ('tcc_taken', '12a4', None, [('Z', 1), ('X0', 4660), ('R0', 119)], [('A', 305397760), ('R2', 119)]),
    # teq x0,a r0,r2
    ('tcc_not_taken', '12a4', None, [('Z', 0), ('X0', 4660), ('R0', 119), ('A', 5)], [('A', 5), ('R2', 0)]),
    # lea (r0)+n0,r1
    ('lea', '01dc', None, [('R0', 16), ('N0', 3)], [('R1', 19), ('R0', 16)]),
    # andi #$fe,ccr
    ('andi_ccr', '1efe', None, [('C', 1), ('Z', 1)], [('C', 0), ('Z', 1)]),
    # ext a
    ('ext', '1552', None, [('A', 2147483648)], [('A', 1097364144128)]),
    # swap a
    ('swap', '1571', None, [('A', 78187493530)], [('A', 79332783190)]),
    # move p:(r0)+,x0
    ('movem_p_read', '0308', None, [('R0', 512), ('p:0200', 48879)], [('X0', 48879), ('R0', 513)]),
    # add b,a
    ('saturation_mode', '4a00', None, [('OMR', 16), ('A', 2147418112), ('B', 65536)], [('A', 2147483647), ('L', 1)]),
    # inc24 a
    ('inc24', '4a23', None, [('A', 78187493530)], [('A', 78187559066)]),
    # tfr3 a,x0 x0,x:(r0)+
    ('tfr3_store_old_x0', '2400', None, [('A', 305397760), ('X0', 21845), ('R0', 96)], [('X0', 4660), ('x:0060', 21845), ('R0', 97)]),
    # mpy x0,y0,a b,x:(r0)+n0 x1,b
    ('mpy_write_move', '1624', None, [('X0', 16384), ('Y0', 16384), ('B', 286326784), ('X1', 8738), ('R0', 112), ('N0', 2)], [('A', 536870912), ('x:0070', 4369), ('B', 572653568), ('R0', 114)]),
    # move x:(r2-3),y1
    ('move_r2_disp', '05fd 3c60', None, [('R2', 32), ('x:001d', 17185)], [('Y1', 17185), ('R2', 32)]),
    # add x0,a x:(r2+5),y0
    ('parallel_r2_disp', '0505 8304', None, [('R2', 32), ('x:0025', 257), ('X0', 1), ('A', 0)], [('Y0', 257), ('A', 65536)]),
    # bcc tgt / inc a / tgt nop
    ('bcc_taken', '0730 0001 4a22 0000', None, [('C', 0), ('A', 0)], [('A', 0)]),
    # asr16 a
    ('asr16', '1570', None, [('A', 724379674724)], [('A', 1099505903716), ('C', 1)]),
    # norm r0,a
    ('norm_left', '1520', None, [('A', 268435456), ('R0', 5)], [('A', 536870912), ('R0', 4)]),
    # move #-3,y1
    ('move_i', '23fd', None, [], [('Y1', 65533)]),
    # inc a x:(r0)+,y0
    ('parallel_x_move', '8322', None, [('A', 0), ('R0', 128), ('x:0080', 17476)], [('A', 1), ('Y0', 17476), ('R0', 129)]),
    # tfr x0,a b,x:(r1)+n1
    ('parallel_x_store_acc', 'da14', None, [('X0', 4096), ('B', 1431633920), ('R1', 144), ('N1', 4)], [('A', 268435456), ('x:0090', 21845), ('R1', 148)]),
    # repcs / asl a
    ('repcs_until_carry', '0158 4a31', None, [('A', 1), ('C', 0)], [('A', 0), ('C', 1)]),
    # repeq / inc a
    ('repeq_skips_when_true', '015a 4a22', None, [('A', 0), ('Z', 1)], [('A', 0)]),
    # do forever,endf / dec b / brkeq / nop / nop / endf nop
    ('do_forever_brk', '0002 0004 4a6a 011a 0000 0000 0000', None, [('B', 3)], [('B', 0), ('Z', 1), ('SP', 0), ('MR', 0)]),
    # dmacss y0,x0,a
    ('dmacss', '1590', None, [('A', 305397760), ('X0', 16384), ('Y0', 16384)], [('A', 536875572)]),
]


def main():
    broken = "--broken" in sys.argv
    print("# generated by test/emu/cases156.py; do not edit")
    for i, (name, code, main_, sets, exp) in enumerate(CASES):
        print("case %s" % name)
        print("code %s" % code)
        if main_ is not None:
            print("main %d" % main_)
        for k, v in sets:
            print("set %s 0x%x" % (k, v))
        for j, (k, v) in enumerate(exp):
            if broken and i == 0 and j == 0:
                v ^= 1
            print("expect %s 0x%x" % (k, v))
        print("end")


if __name__ == "__main__":
    main()
