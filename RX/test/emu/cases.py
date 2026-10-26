#!/usr/bin/env python3
"""Emulator cases for the RX module: assembled code (the GNU assembler, -mcpu=rxv3-dfpu, was used
as a black box to encode the source lines quoted in each comment) with expected results worked
out by hand from the RX Family Software Manual (section 3: operation and flag change tables).

    cases.py > cases.txt            all cases
    cases.py --broken > bad.txt     the same with one deliberately wrong expectation (the test
                                    harness must report it)

Code is placed at ram:00001000 and runs until the PC reaches the end of the main code ("main"
bytes); subroutines follow it. R0 (SP) starts at 8000h. Flags "v2"/"v3": RXv2/RXv3 and later only.
"""
import sys

CASES = []


def case(name, code, sets=(), expect=(), flags="", main=None):
    CASES.append((name, code, sets, expect, flags, main))


# add r1, r2
case('add_reg_overflow', '4b12', [('R1', 2147483647), ('R2', 1)], [('R2', 2147483648), ('C', 0), ('Z', 0), ('S', 1), ('O', 1)])
# add r1, r2
case('add_carry_zero', '4b12', [('R1', 4294967295), ('R2', 1)], [('R2', 0), ('C', 1), ('Z', 1), ('S', 0), ('O', 0)])
# add #-100, r3, r4
case('add3_imm', '71349c', [('R3', 50)], [('R4', 4294967246), ('C', 0), ('Z', 0), ('S', 1), ('O', 0)])
# sub r1, r2
case('sub_borrow', '4312', [('R1', 5), ('R2', 3)], [('R2', 4294967294), ('C', 0), ('Z', 0), ('S', 1), ('O', 0)])
# sub #3, r2
case('sub_noborrow_sets_c', '6032', [('R2', 3)], [('R2', 0), ('C', 1), ('Z', 1), ('S', 0), ('O', 0)])
# cmp r1, r2
case('cmp_unsigned_lt', '4712', [('R1', 10), ('R2', 9)], [('R2', 9), ('C', 0), ('Z', 0), ('S', 1), ('O', 0)])
# add r1, r3 ; adc r2, r4
case('adc_chain', '4b13fc0b24', [('R1', 4294967295), ('R2', 0), ('R3', 1), ('R4', 5)], [('R3', 0), ('R4', 6), ('C', 0)])
# sbb r1, r2
case('sbb_borrow', 'fc0312', [('C', 0), ('R1', 1), ('R2', 1)], [('R2', 4294967295), ('C', 0), ('Z', 0), ('S', 1), ('O', 0)])
# neg r1
case('neg_min', '7e11', [('R1', 2147483648)], [('R1', 2147483648), ('C', 0), ('Z', 0), ('S', 1), ('O', 1)])
# abs r1, r2
case('abs_neg', 'fc0f12', [('R1', 4294967286)], [('R2', 10), ('Z', 0), ('S', 0), ('O', 0)])
# and #0xff, r1 ; or #0x100, r1 ; xor #0x1, r1 ; not r1
case('and_or_xor_not', '7621ff0076310001fd74d1017e01', [('R1', 305419896)], [('R1', 4294966918), ('Z', 0), ('S', 1)])
# mul #3, r1 ; div #-2, r1 ; divu #4, r2
case('mul_div_divu', '6331fd7481fefd749204', [('R1', 7), ('R2', 17)], [('R1', 4294967286), ('R2', 4), ('O', 0)])
# div r2, r1
case('div_by_zero_sets_o', 'fc2321', [('R1', 7), ('R2', 0)], [('R1', 7), ('O', 1)])
# emul r1, r4
case('emul_pair', 'fc1b14', [('R1', 4294967294), ('R4', 3)], [('R4', 4294967290), ('R5', 4294967295)])
# emulu #0x10000, r4
case('emulu_pair', 'fd7c74000001', [('R4', 305419896)], [('R4', 1450704896), ('R5', 4660)])
# max #5, r1 ; min r3, r2
case('max_min', 'fd744105fc1732', [('R1', 4294967280), ('R2', 9), ('R3', 4294967295)], [('R1', 5), ('R2', 4294967295)])
# shll #1, r1
case('shll_overflow', '6c11', [('R1', 1073741824)], [('R1', 2147483648), ('C', 0), ('Z', 0), ('S', 1), ('O', 1)])
# shar #2, r1
case('shar_carry', '6a21', [('R1', 2147483654)], [('R1', 3758096385), ('C', 1), ('Z', 0), ('S', 1), ('O', 0)])
# shlr #4, r1, r2
case('shlr_3op', 'fd8412', [('R1', 4026531855)], [('R1', 4026531855), ('R2', 251658240), ('C', 1), ('Z', 0), ('S', 0)])
# rotl #4, r1 ; rotr #8, r2
case('rotl_rotr', 'fd6e41fd6c82', [('R1', 4026531841), ('R2', 255)], [('R1', 31), ('R2', 4278190080), ('C', 1), ('S', 1)])
# rolc r1 ; rorc r2
case('rolc_rorc', '7e517e42', [('C', 1), ('R1', 2147483648), ('R2', 2)], [('R1', 1), ('R2', 2147483649), ('C', 0)])
# mov.l #0x11223344, r1 ; mov.l r1, 8[r2] ; mov.b 9[r2], r3 ; movu.w 10[r2], r4 ; mov.w r1, [r5, r2]
case('mov_mem_modes', 'fb1244332211a0a18a2bb92cfe1521', [('R2', 8192), ('R5', 2)], [('ram:2008/4', 287454020), ('R3', 51), ('R4', 4386), ('ram:2004/2', 13124)])
# mov.l r1, [r2+] ; mov.w r1, [r2+] ; mov.w [-r2], r3
case('mov_postinc_predec', 'fd2221fd2121fd2d23', [('R1', 32769), ('R2', 8192)], [('R2', 8196), ('R3', 4294934529), ('ram:2000/4', 32769)])
# add 2[r2].uw, r1
case('memex_add_uw', '06c92101', [('R1', 1), ('R2', 8192), ('ram:2002/2', 65535)], [('R1', 65536)])
# sub [r2].b, r1
case('memex_sub_b', '060021', [('R1', 1), ('R2', 8192), ('ram:2000', 255)], [('R1', 2), ('C', 0), ('Z', 0), ('S', 0), ('O', 0)])
# mov.w 2[r1], 4[r2]
case('mov_mem_to_mem', 'd5120102', [('R1', 8192), ('R2', 8448), ('ram:2002/2', 48879)], [('ram:2104/2', 48879)])
# bset #3, [r2].b ; bclr #0, 1[r2].b ; bnot #31, r1 ; btst #3, [r2].b
case('bit_ops', 'f023f12801fdfff1f423', [('R2', 8192), ('ram:2001', 255), ('R1', 0)], [('ram:2000', 8), ('ram:2001', 254), ('R1', 2147483648), ('C', 1), ('Z', 0)])
# cmp #5, r1 ; bmeq #2, r3 ; scgtu.l r4 ; sceq.b [r2]
case('bmcnd_scc', '6151fde203fcdb44fcd020', [('R1', 5), ('R2', 8192), ('R3', 0), ('R4', 7)], [('R3', 4), ('R4', 0), ('ram:2000', 1)])
# cmp #0, r1 ; stz #9, r2 ; stnz #7, r3
case('stz_stnz', '6101fd74e209fd74f307', [('R1', 0), ('R2', 0), ('R3', 0)], [('R2', 9), ('R3', 0)])
# cmp r1, r2 ; beq.b 1f ; mov.l #1, r3 ; 1: nop
case('beq_taken', '47122004661303', [('R1', 4), ('R2', 4), ('R3', 0)], [('R3', 0)])
# cmp #9, r2 ; bgt.b 1f ; mov.l #1, r3 ; 1: nop
case('bgt_not_taken', '61922a04661303', [('R2', 4), ('R3', 0)], [('R3', 1)])
# bsr.w sub1 ; add #1, r1   | then: nop ; sub1: add #0x10, r1 ; rts
case('bsr_rts', '39060062110371111002', [('R1', 0)], [('R1', 17), ('R0', 32768)], main=5)
# jsr r5 ; add #1, r1   | then: nop ; add #2, r1 ; rts
case('jsr_reg', '7f156211030000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000622102', [('R1', 0), ('R5', 4352)], [('R1', 3), ('R0', 32768)], main=4)
# pushm r6-r8 ; mov.l #0, r6 ; mov.l #0, r7 ; popm r6-r7 ; pop r9
case('pushm_popm', '6e68660666076f677eb9', [('R6', 6), ('R7', 7), ('R8', 8)], [('R6', 6), ('R7', 7), ('R9', 8), ('R0', 32768), ('ram:7ff4/4', 6), ('ram:7ffc/4', 8)])
# bsr.w sub1   | then: nop ; sub1: pushm r6-r7 ; sub #8, r0 ; mov.l #1, r6 ; add r6, r7, r1 ; add #5, r1 ; rtsd #16, r6-r7
case('rtsd_frame', '390400036e6760806616ff216762513f6704', [('R6', 6), ('R7', 7)], [('R6', 6), ('R7', 7), ('R1', 13), ('R0', 32768)], main=3)
# setpsw c ; setpsw o ; pushc psw ; clrpsw c ; popc psw ; mvfc psw, r1
case('push_pop_psw', '7fa07fa37ec07fb07ee0fd6a01', [('C', 0), ('O', 0)], [('C', 1), ('O', 1), ('R1', 9)])
# smovf
case('smovf', '7f8f', [('R1', 8448), ('R2', 8192), ('R3', 3), ('ram:2000/4', 1144201745)], [('ram:2100/4', 3351057), ('R1', 8451), ('R2', 8195), ('R3', 0)])
# sstr.l
case('sstr_l', '7f8a', [('R1', 8192), ('R2', 2864434397), ('R3', 2)], [('ram:2000/4', 2864434397), ('ram:2004/4', 2864434397), ('R1', 8200), ('R3', 0)])
# suntil.b
case('suntil_b', '7f80', [('R1', 8192), ('R2', 51), ('R3', 10), ('ram:2000/4', 1144201745)], [('R1', 8195), ('R3', 7), ('Z', 1), ('C', 1)])
# scmpu
case('scmpu_diff', '7f83', [('R1', 8192), ('R2', 8448), ('R3', 8), ('ram:2000/4', 6513249), ('ram:2100/4', 6578785)], [('Z', 0), ('C', 0), ('R3', 5)])
# rmpa.w
case('rmpa_w', '7f8d', [('R1', 8192), ('R2', 8448), ('R3', 2), ('R4', 0), ('R5', 0), ('R6', 0), ('ram:2000/4', 4294836227), ('ram:2100/4', 327684)], [('R4', 2), ('R5', 0), ('R6', 0), ('R3', 0), ('S', 0), ('O', 0)])
# revl r1, r2 ; revw r1, r3
case('revl_revw', 'fd6712fd6513', [('R1', 287454020)], [('R2', 1144201745), ('R3', 571556915)])
# add r1, r2 ; sat r2
case('sat_overflow', '4b127e32', [('R1', 2147483647), ('R2', 1)], [('R2', 2147483647)])
# xchg [r2].l, r1
case('xchg_mem', '06a01021', [('R1', 5), ('R2', 8192), ('ram:2000/4', 9)], [('R1', 9), ('ram:2000/4', 5)])
# mulhi r1, r2 ; machi r1, r2 ; mvfachi r3 ; mvfacmi r4
case('mulhi_machi_mvfac', 'fd0012fd0412fd1f03fd1f24', [('R1', 196608), ('R2', 262144)], [('R3', 0), ('R4', 24)])
# mvtachi r1 ; mvtaclo r2 ; racw #1 ; mvfachi r3
case('mvtac_racw', 'fd1701fd1712fd1800fd1f03', [('R1', 16384), ('R2', 2147483648)], [('R3', 32767)])
# fadd r1, r2 ; fmul #0x40000000, r2 ; ftoi r2, r3 ; fcmp r1, r2
case('fpu_basic', 'fc8b12fd723200000040fc9723fc8712', [('R1', 1069547520), ('R2', 1074790400)], [('R2', 1089470464), ('R3', 7), ('Z', 0), ('S', 0), ('O', 0)])
# itof r1, r2 ; round r2, r3
case('itof_round', 'fc4712fc9b23', [('R1', 4294967293)], [('R2', 3225419776), ('R3', 4294967293), ('S', 1)])
# utof r1, r2 ; ftou r2, r3
case('utof_ftou', 'fc5712fca723', [('R1', 2147483648)], [('R2', 1325400064), ('R3', 2147483648)], flags='v2')
# fadd r1, r2, r3 ; fsqrt r3, r4
case('fadd3_fsqrt', 'ffa312fca334', [('R1', 1073741824), ('R2', 1088421888)], [('R3', 1091567616), ('R4', 1077936128)], flags='v2')
# movli [r2], r1 ; add #1, r1 ; movco r1, [r2] ; movco r3, [r2]
case('movli_movco', 'fd2f216211fd2721fd2723', [('R2', 8192), ('R3', 7), ('ram:2000/4', 41)], [('ram:2000/4', 42), ('R1', 0), ('R3', 1)], flags='v2')
# emula r1, r2, a1 ; emaca r1, r1, a1 ; mvfacgu #0, a1, r3 ; mvfaclo #0, a1, r4 ; mvfachi #0, a1, r5
case('dsp_v2_acc1', 'fd0b12fd0f11fd1fb3fd1f94fd1f85', [('R1', 2147483648), ('R2', 2147483648)], [('R3', 0), ('R4', 0), ('R5', 2147483648)], flags='v2')
# bfmov #4, #8, #8, r1, r2 ; bfmovz #0, #4, #4, r1, r3
case('bfmov_v3', 'fc5e120441fc5a138420', [('R1', 2736), ('R2', 4294967295), ('R3', 4294967295)], [('R2', 4294945791), ('R3', 0)], flags='v3')
# xor r1, r2, r3
case('xor3_v3', 'ff6312', [('R1', 4278255360), ('R2', 267390960)], [('R3', 4042322160), ('S', 1), ('Z', 0)], flags='v3')
# dmov.d #0x40080000, drh1 ; dmov.d #0x3ff80000, drh2 ; dmul dr1, dr2, dr3 ; dtoi dr3, dr4 ; dmov.l drl4, r5 ; dcmplt dr1, dr2 ; mvfdr
case('dfpu_v3', 'f9031300000840f903230000f83f7690223176903d48fd7585407690284175901b', [], [('R5', 4), ('Z', 1)], flags='v3')
# round r1, r3 ; round r2, r4 ; mvtc #1, fpsw ; round r2, r5
case('round_ties_even', 'fc9b13fc9b24fd770301fc9b25', [('R1', 1075838976), ('R2', 1080033280)], [('R3', 2), ('R4', 4), ('R5', 3)])
# bra.l r5 ; mov.l #1, r3 ; mov.l #2, r3 ; nop
case('bra_l_relative', '7f456613662303', [('R5', 4), ('R3', 0)], [('R3', 2)])
# div r2, r1
case('div_overflow', 'fc2321', [('R1', 2147483648), ('R2', 4294967295)], [('R1', 2147483648), ('O', 1)])
# shll r2, r1
case('shll_reg_count0', 'fd6221', [('R1', 2147483648), ('R2', 32), ('C', 1), ('O', 1)], [('R1', 2147483648), ('C', 0), ('O', 0), ('S', 1), ('Z', 0)])
# fcmp r1, r2
case('fcmp_nan', 'fc8712', [('R1', 1065353216), ('R2', 2143289344)], [('O', 1), ('Z', 0), ('S', 0)])
# ftoi r1, r2
case('ftoi_negative', 'fc9712', [('R1', 3236954112)], [('R2', 4294967289), ('S', 1)])
# mov.w r1, 6[r2] ; movu.b 7[r2], r3 ; mov.b 6[r2], r4
case('mov_dsp5_movu', '90a9b1ab89a4', [('R1', 43981), ('R2', 8192)], [('ram:2006/2', 43981), ('R3', 171), ('R4', 4294967245)])
# push.w 2[r2] ; pop r3
case('push_mem_w', 'f529017eb3', [('R2', 8192), ('ram:2002/2', 4660)], [('R3', 4660), ('R0', 32768)])
# cmp r1, r1 ; scge.w 2[r2]
case('scc_w_mem', '4711fcd52801', [('R1', 5), ('R2', 8192), ('ram:2002/2', 21845)], [('ram:2002/2', 1)])
# adc 4[r2].l, r1
case('adc_mem_l', '06a1022101', [('C', 1), ('R1', 1), ('R2', 8192), ('ram:2004/4', 2)], [('R1', 4), ('C', 0)])
# mvtipl #7 ; mvfc psw, r1
case('mvtipl', '757007fd6a01', [], [('IPL', 7), ('R1', 117440512)])
# mvtachi r1, a0 ; mvtaclo r2, a0 ; racl #1, a0 ; mvfachi #0, a0, r3 ; mvfaclo #0, a0, r4
case('racl_v2', 'fd1701fd1712fd1900fd1f03fd1f14', [('R1', 305419896), ('R2', 2147483648)], [('R3', 610839793), ('R4', 0)], flags='v2')
# mullo r1, r2, a0 ; msblo r1, r1, a0 ; mvfacmi #0, a0, r3
case('msblo_v2', 'fd0112fd4511fd1f23', [('R1', 3), ('R2', 4)], [('R3', 3)], flags='v2')
# dmov.d #0x40080000, drh1 ; dpushm.d dr1-dr2 ; dmov.l #0, drh1 ; dpopm.d dr1-dr2 ; dmov.l drh1, r5
case('dpushm_dpopm_v3', 'f903130000084075b011f903120000000075b811fd758512', [], [('R5', 1074266112), ('R0', 32768)], flags='v3')
# mvtachi r1, a0 ; mvtaclo r2, a0 ; mvtacgu r2, a0 ; racl #1, a0 ; mvfachi #0, a0, r3 ; mvfacgu #0, a0, r4
case('racl_saturate_pos_v2', 'fd1701fd1712fd1732fd1900fd1f03fd1f34', [('R1', 1073741824), ('R2', 0)], [('R3', 2147483647), ('R4', 0)], flags='v2')
# mvtacgu r5, a1 ; mvtachi r1, a1 ; mvtaclo r2, a1 ; rdacw #2, a1 ; mvfachi #0, a1, r3 ; mvfacgu #0, a1, r4
case('rdacw_saturate_neg_v2', 'fd17b5fd1781fd1792fd18d0fd1f83fd1fb4', [('R1', 4294901760), ('R2', 0), ('R5', 4294967295)], [('R3', 4294934528), ('R4', 4294967295)], flags='v2')
# mvtacgu r2, a0 ; mvtachi r1, a0 ; mvtaclo r2, a0 ; mvfacmi #2, a0, r3 ; mvfacgu #1, a0, r4
case('mvfacmi_shift_v2', 'fd1732fd1701fd1712fd1e23fd1f74', [('R1', 1073746484), ('R2', 0)], [('R3', 1221591040), ('R4', 0)], flags='v2')


def main():
    broken = "--broken" in sys.argv
    print("# generated by test/emu/cases.py; do not edit")
    for i, (name, code, sets, expect, flags, main) in enumerate(CASES):
        print(f"case {name} {flags}".rstrip())
        print(f"code {code}")
        if main is not None:
            print(f"main {main}")
        for k, v in sets:
            print(f"set {k} {v:#x}")
        for j, (k, v) in enumerate(expect):
            if broken and i == 0 and j == 0:
                v ^= 1
            print(f"expect {k} {v:#x}")
        print("end")


if __name__ == "__main__":
    main()
