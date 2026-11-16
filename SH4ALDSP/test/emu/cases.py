#!/usr/bin/env python3
"""Emulator cases for the SH4AL-DSP module.

Each case is a short assembly program (encoded by GNU as 2.45, sh-elf, -isa=sh4al-dsp, used only
as an encoder) plus register/memory expectations worked out by hand from the Renesas SH4AL-DSP
Software Manual (REJ09B0002-0150).  Where the manual gives a worked example ("Before execution /
After execution" in section 11, figures 6.6, 6.7, 6.9 and the modulo example of 6.4.3) the case
uses those values; the rest are computed by hand from the operation descriptions.  Expected values
are literals written here, never produced by the module.

    cases.py > cases.txt

Run-time layout: the code is placed at ram:00001000 and runs until the PC reaches the symbol
main_end (default: the end of the code); data lives around ram:2000; R15 starts at 8000h.
40-bit accumulators are checked as A0E/A1E (A0G:A0).  langs: all (both byte orders), be, le.
Adapted from the case generator of aleph-void/ghidra-sh (MIT).
"""
import os
import subprocess
import sys
import tempfile

TOOLS = os.environ.get("SH_TOOLS", os.path.expanduser("~/.cache/ghidra-rare-scratch/tools/x-sh-elf/bin"))
AS = os.path.join(TOOLS, "sh-elf-as")
NM = os.path.join(TOOLS, "sh-elf-nm")
OBJCOPY = os.path.join(TOOLS, "sh-elf-objcopy")
LANGS = {"all": "be le", "be": "be", "le": "le"}
CASES = []
BASE = 0x1000


def case(name, asm, sets=(), expect=(), langs="all"):
    CASES.append((name, asm, list(sets), list(expect), langs))


def assemble(asm):
    d = tempfile.mkdtemp(prefix="sh4alcase", dir=os.environ.get("TMPDIR"))
    src = os.path.join(d, "a.s")
    open(src, "w").write(".text\n" + asm + "\n")
    subprocess.check_call([AS, "-isa=sh4al-dsp", "-big", src, "-o", d + "/a.o"])
    subprocess.check_call([OBJCOPY, "-O", "binary", "-j", ".text", d + "/a.o", d + "/a.bin"])
    code = open(d + "/a.bin", "rb").read()
    syms = {}
    for line in subprocess.check_output([NM, d + "/a.o"]).decode().splitlines():
        p = line.split()
        if len(p) == 3:
            syms[p[2]] = int(p[0], 16) + BASE
    return code, syms


def val(v, syms):
    return v(syms) if callable(v) else v


# ------------------------------------------------------------------ integer core (SH-4A)
case("addc_carry_in_and_out", "addc r1,r2", [("R1", 0xffffffff), ("R2", 0), ("T", 1)],
     [("R2", 0), ("T", 1)])
case("subc_borrow", "subc r1,r2", [("R1", 5), ("R2", 3), ("T", 0)], [("R2", 0xfffffffe), ("T", 1)])
case("shad_negative_count", "shad r1,r2", [("R1", 0xfffffffc), ("R2", 0x80000000)],
     [("R2", 0xf8000000)])
case("movli_movco_atomic_increment", """movli.l @r1,r0
add #1,r0
movco.l r0,@r1""", [("R1", 0x2000), ("ram:2000/4", 41), ("T", 0)],
     [("ram:2000/4", 42), ("T", 1), ("R0", 42)])
# MOVCO without a preceding MOVLI (LDST = 0): T = 0 and nothing is stored (11.1.36)
case("movco_without_link_fails", "movco.l r0,@r1", [("R1", 0x2000), ("R0", 7), ("ram:2000/4", 5), ("T", 1)],
     [("ram:2000/4", 5), ("T", 0)])
# MOVCO clears LDST: a second MOVCO after a successful one fails
case("movco_twice", """movli.l @r1,r0
movco.l r0,@r1
movt r3
movco.l r0,@r1
movt r4""", [("R1", 0x2000), ("ram:2000/4", 9)], [("R3", 1), ("R4", 0)])
# MOVUA.L from 2001h: bytes 22 33 44 55 (big endian) / 33 22 11 88 read as a little-endian word
case("movua_unaligned_postinc_be", "movua.l @r1+,r0", [("R1", 0x2001), ("ram:2000/4", 0x11223344),
     ("ram:2004/4", 0x55667788)], [("R0", 0x22334455), ("R1", 0x2005)], langs="be")
case("movua_unaligned_postinc_le", "movua.l @r1+,r0", [("R1", 0x2001), ("ram:2000/4", 0x11223344),
     ("ram:2004/4", 0x55667788)], [("R0", 0x88112233), ("R1", 0x2005)], langs="le")
# MOVUA.L @R0+,R0: R0 receives the data, no increment (11.1.39 example)
case("movua_r0_postinc", "movua.l @r0+,r0", [("R0", 0x2004), ("ram:2004/4", 0x0badcafe)],
     [("R0", 0x0badcafe)])
# TRAPA: TRA = imm << 2, EXPEVT = 160h, SPC = next PC, SSR = SR, SGR = R15, MD = BL = RB = 1,
# PC = VBR + 100h (11.1.78); VBR is chosen so that the handler is main_end
case("trapa", """trapa #0x21
main_end:""", [("VBR", lambda s: s["main_end"] - 0x100), ("R15", 0x7ff0), ("T", 1), ("S", 1)],
     [("ram:ff000020/4", 0x84), ("ram:ff000024/4", 0x160), ("SPC", lambda s: s["main_end"]),
      ("SSR", 0x3), ("SGR", 0x7ff0), ("MD", 1), ("BL", 1), ("RB", 1)])
# SR with the DSP fields: MD, RC = 123h, DSP, DMX, M, IMASK = Fh, RF = 2, S, T
case("ldc_stc_sr_dsp_fields", """ldc r1,sr
stc sr,r2""", [("R1", 0x412316fb)],
     [("R2", 0x412316fb), ("RC", 0x123), ("DSP", 1), ("DMX", 1), ("DMY", 0), ("RF", 2), ("MD", 1),
      ("IMASK", 0xf), ("M", 1), ("Q", 0), ("S", 1), ("T", 1)])
case("setdmx_setdmy_clrdmxy", """setdmx
stc sr,r1
setdmy
stc sr,r2
clrdmxy
stc sr,r3""", [], [("R1", 0x400), ("R2", 0x800), ("R3", 0)])
# DSR: bits 15-0 writable, 31-16 read as 0 (table 2.4)
case("lds_sts_dsr", """lds r1,dsr
sts dsr,r2""", [("R1", 0xffffa5f3)],
     [("R2", 0xa5f3), ("DC", 1), ("CS", 1), ("V", 1), ("N", 1), ("Z", 1), ("GT", 1), ("TC", 1),
      ("TS", 2), ("AV", 0), ("AN", 1), ("AZ", 0), ("AGT", 1)])
# LDS Rm,A0 sign-extends into the guard bits (11.2.8)
case("lds_a0_sign_extends", "lds r1,a0", [("R1", 0x80000001), ("A0G", 0)], [("A0E", 0xff80000001)])
case("sts_l_x0", "sts.l x0,@-r1", [("X0", 0xdeadbeef), ("R1", 0x2004)],
     [("ram:2000/4", 0xdeadbeef), ("R1", 0x2000)])
# BSR with a 32-bit DSP instruction in the delay slot: PR = PC + 6 (table 3.9 note)
case("bsr_32bit_delay_slot_pr", """bsr main_end
padd x0,y0,a0
nop
main_end:""", [("X0", 1), ("Y0", 2)], [("PR", 0x1006), ("A0E", 3)])

# ------------------------------------------------------------------ DSP data transfers
case("movx_movy_parallel", "movx.w @r4+,x0 movy.w @r6+r9,y0",
     [("R4", 0x2000), ("R6", 0x3000), ("R9", 6), ("ram:2000/2", 0x1234), ("ram:3000/2", 0xabcd),
      ("X0", 0x5555), ("Y0", 0x7777)],
     [("X0", 0x12340000), ("Y0", 0xabcd0000), ("R4", 0x2002), ("R6", 0x3006)])
case("movx_index_minus2_store", "movx.w a1,@r5+r8", [("R5", 0x2010), ("R8", 0xfffffffe),
     ("A1E", 0x12abcd5678)], [("ram:2010/2", 0xabcd), ("R5", 0x200e)])
# Y pointer updates change only the low word (6.4.2)
case("movy_postinc_low_word_only", "movy.w @r6+,y0", [("R6", 0x1234fffe), ("ram:1234fffe/2", 0x4321)],
     [("R6", 0x12340000), ("Y0", 0x43210000)])
# extended forms (other side NOPY/NOPX): MOVX.L into Y1 via R0, MOVY.L store of A0 via R2+R9
case("movx_l_extended", "movx.l @r0+,y1", [("R0", 0x2000), ("ram:2000/4", 0x89abcdef)],
     [("Y1", 0x89abcdef), ("R0", 0x2004)])
case("movy_l_extended_store", "movy.l a0,@r2+r9", [("R2", 0x2020), ("R9", 8), ("A0E", 0x7f01234567)],
     [("ram:2020/4", 0x01234567), ("R2", 0x2028)])
# modulo addressing, manual 6.4.3 example: MS = 7000h, ME = 7004h, DMX = 1;
# R4: A5007000 -> 7002 -> 7004 -> 7000 (matches ME, reloads MS)
case("movx_modulo_x", """setdmx
movx.w @r4+,x0
movx.w @r4+,x0
movx.w @r4+,x0
mov r4,r1
movx.w @r4+,x0""", [("MOD", 0x70047000), ("R4", 0xa5007000)], [("R1", 0xa5007000), ("R4", 0xa5007002)])
# modulo is per side: with DMY the X pointer increments past ME, the Y pointer wraps
case("movy_modulo_y", """setdmy
movx.w @r4+,x0 movy.w @r6+,y0""", [("MOD", 0x10041000), ("R4", 0x1004), ("R6", 0x1004)],
     [("R4", 0x1006), ("R6", 0x1000)])
# MOVS (11.3.3 examples): MOVS.W @R4+,A0 with (R4) = 8765h gives FF87650000;
# MOVS.L A1,@-R3 stores 3456789Ah at 7FCh
case("movs_w_load_a0", "movs.w @r4+,a0", [("R4", 0x400), ("ram:400/2", 0x8765), ("A0E", 0x123456789a)],
     [("R4", 0x402), ("A0E", 0xff87650000)])
case("movs_l_store_a1_predec", "movs.l a1,@-r3", [("R3", 0x800), ("A1E", 0x123456789a)],
     [("R3", 0x7fc), ("ram:7fc/4", 0x3456789a)])
# a guard register stores sign-extended, loads take bits 7-0 of the data
case("movs_guard_registers", """movs.w a0g,@r2
movs.l @r3,a1g""", [("R2", 0x2000), ("A0G", 0x80), ("R3", 0x2004), ("ram:2004/4", 0x123456c3),
     ("A1E", 0x0011112222)], [("ram:2000/2", 0xff80), ("A1E", 0xc311112222)])
case("movs_index", "movs.l @r5+r8,x1", [("R5", 0x2000), ("R8", 0x10), ("ram:2000/4", 0xfeedface)],
     [("X1", 0xfeedface), ("R5", 0x2010)])

# ------------------------------------------------------------------ DSP operations
# PADD X0,Y0,A0 (11.4.2 example): 22222222h + 33333333h = 0055555555h; CS = 0: no carry
case("padd_example", "padd x0,y0,a0", [("X0", 0x22222222), ("Y0", 0x33333333), ("A0E", 0x123456789a),
     ("DC", 1)], [("A0E", 0x0055555555), ("DC", 0), ("N", 0), ("Z", 0), ("V", 1 - 1), ("GT", 1)])
# figure 6.6: flag accumulation with DSR = 0200h (TS = 001): PADD of 7FFFFFFFh + 7FFFFFFFh gives
# AGT AZ AN AV = 1001, GT Z N V = 1001; PCLR A0 then gives 1101 / 0100
case("flag_accumulation_fig_6_6", """mov.w dsrv,r0
lds r0,dsr
padd x0,y0,a0
sts dsr,r1
pclr a0
sts dsr,r2
bra main_end
nop
.align 2
dsrv: .word 0x0200
main_end:""", [("X0", 0x7fffffff), ("Y0", 0x7fffffff)],
     [("R1", 0x9290), ("R2", 0xd240), ("A0E", 0)])
# figure 6.7: T bit link, DSR = 0500h (TS = 010 zero, TC = 1, CS = 000): 0 + 0 gives T = 1, DC = 0
case("t_bit_link_fig_6_7", """lds r0,dsr
padd x0,y0,a0""", [("R0", 0x500), ("X0", 0), ("Y0", 0), ("T", 0)], [("T", 1), ("DC", 0), ("Z", 1)])
# PCMP X0,Y0 (11.4.8 example): 22222222h - 33333333h: N = 1, Z = 0, V = 0, GT = 0; CS = 0: borrow
case("pcmp_example", "pcmp x0,y0", [("X0", 0x22222222), ("Y0", 0x33333333)],
     [("N", 1), ("Z", 0), ("V", 0), ("GT", 0), ("DC", 1)])
# signed greater-or-equal mode (CS = 101) after PCMP 5 - 3
case("pcmp_ge_mode", """lds r0,dsr
pcmp x0,y0""", [("R0", 0xa), ("X0", 5), ("Y0", 3)], [("DC", 1), ("GT", 1)])
# PMULS fractional (11.4.14 examples): 0001h * 0002h -> 4; FFFEh * 0001h -> FFFFFFFFFCh in A0
case("pmuls_fractional", """pmuls x0,y0,m0
pmuls x1,y1,a0""", [("X0", 0x00010000), ("Y0", 0x00020000), ("M0", 0x33333333), ("X1", 0xfffe2222),
     ("Y1", 0x0001aaaa), ("A0E", 0x4444444444)], [("M0", 4), ("A0E", 0xfffffffffc)])
# PMULS -1.0 * -1.0: 80000000h without S, saturated 7FFFFFFFh with S (6.5.7)
case("pmuls_minus_one_squared", """pmuls x0,y0,m0
sets
pmuls x0,y0,m1""", [("X0", 0x80000000), ("Y0", 0x80000000)], [("M0", 0x80000000), ("M1", 0x7fffffff)])
# PADD PMULS (11.4.3 example): M0 = 0000000Ch, A0 = 0077777777h (PADD reads the old M0)
case("padd_pmuls_example", "padd a0,m0,a0 pmuls x0,y0,m0", [("X0", 0x00020000), ("Y0", 0x00030000),
     ("M0", 0x22222222), ("A0E", 0x0055555555)], [("M0", 0xc), ("A0E", 0x0077777777)])
# figure 6.9: DCT PADD X0,Y0,A0 MOVX.W @R4+,X0 MOVY.W A0,@R6+R9, condition true and false
case("dct_padd_parallel_true_fig_6_9", "dct padd x0,y0,a0 movx.w @r4+,x0 movy.w a0,@r6+r9",
     [("DC", 1), ("X0", 0x33333333), ("Y0", 0x55555555), ("A0E", 0x123456789a), ("R4", 0x8000),
      ("R6", 0x5000), ("R9", 4), ("ram:8000/2", 0x1111), ("ram:5000/2", 0x2222)],
     [("X0", 0x11110000), ("A0E", 0x0088888888), ("R4", 0x8002), ("R6", 0x5004), ("ram:5000/2", 0x3456),
      ("DC", 1)])
case("dct_padd_parallel_false_fig_6_9", "dct padd x0,y0,a0 movx.w @r4+,x0 movy.w a0,@r6+r9",
     [("DC", 0), ("X0", 0x33333333), ("Y0", 0x55555555), ("A0E", 0x123456789a), ("R4", 0x8000),
      ("R6", 0x5000), ("R9", 4), ("ram:8000/2", 0x1111), ("ram:5000/2", 0x2222)],
     [("X0", 0x11110000), ("A0E", 0x123456789a), ("R4", 0x8002), ("R6", 0x5004), ("ram:5000/2", 0x3456),
      ("DC", 0)])
case("dcf_pclr", """dcf pclr a1
dct pclr a0""", [("DC", 0), ("A1E", 0x5555555555), ("A0E", 0x6666666666)], [("A1E", 0), ("A0E", 0x6666666666)])
# PADDC (11.4.4 examples): B3333333h + 55555555h + 0 -> 08888888h, DC = 1;
# 33333333h + 55555555h + 1 -> 88888889h, DC = 0
case("paddc_examples", """paddc x0,y0,m0
paddc x1,y0,m1""", [("X0", 0xb3333333), ("Y0", 0x55555555), ("X1", 0x33333333), ("DC", 0)],
     [("M0", 0x08888888), ("M1", 0x88888889), ("DC", 0)])
case("psubc_borrow", "psubc x0,y0,m0", [("X0", 1), ("Y0", 2), ("DC", 1)], [("M0", 0xfffffffe), ("DC", 1)])
# PSUB Sy,Sx form: 5 - 3
case("psub_reverse_operands", "psub y0,x0,a0", [("X0", 3), ("Y0", 5)], [("A0E", 2)])
# PSHA (11.4.18 examples): FF88888888h << 2 -> FE22222220h (the manual prints FE22222222h, which
# a left shift cannot produce: its low two bits must be 0); AAAAAAAAAAh >> 5 -> FD55555555h
case("psha_examples", """psha x0,y0,a0
psha #-5,a1""", [("X0", 0x88888888), ("Y0", 0x00020000), ("A0E", 0x123456789a), ("A1E", 0xaaaaaaaaaa)],
     [("A0E", 0xfe22222220), ("A1E", 0xfd55555555)])
# PSHL (11.4.19 examples): 2222h << 3 -> 0011100000h; CCCCh >> 2 -> 3333h; 5555h << 7 -> AA80h
case("pshl_examples", """pshl x0,y0,a0
pshl x1,y1,x1
pshl #7,a1""", [("X0", 0x22222222), ("Y0", 0x00030000), ("A0E", 0x123456789a), ("X1", 0xcccccccc),
     ("Y1", 0xfffe0000), ("A1E", 0x0055555555)],
     [("A0E", 0x0011100000), ("X1", 0x33330000), ("A1E", 0x00aa800000)])
# PDMSB (11.4.11 examples): 0052330Fh -> 8; FC342855h -> 5
case("pdmsb_examples", """pdmsb x0,m0
pdmsb x1,x1""", [("X0", 0x0052330f), ("M0", 0x12345678), ("X1", 0xfc342855)],
     [("M0", 0x00080000), ("X1", 0x00050000)])
# PRND (11.4.17 examples)
case("prnd_examples", """prnd x0,m0
prnd x1,x1""", [("X0", 0x0052330f), ("M0", 0x12345678), ("X1", 0xfc34c087)],
     [("M0", 0x00520000), ("X1", 0xfc350000)])
# PDEC (11.4.10 examples) and PINC
case("pdec_pinc", """pdec x0,m0
pdec x1,x1
pinc y0,m1""", [("X0", 0x0052330f), ("M0", 0x12345678), ("X1", 0xfc342855), ("Y0", 0x7ffe1234)],
     [("M0", 0x00510000), ("X1", 0xfc330000), ("M1", 0x7fff0000)])
# PNEG X0,A0 (11.4.15 example) and PABS (11.4.1 examples)
case("pneg_pabs_examples", """pneg x0,a0
pabs x1,x1
pabs x0,m0""", [("X0", 0x55555555), ("A0E", 0xa987654321), ("X1", 0xdddddddd), ("M0", 0x12345678)],
     [("A0E", 0xffaaaaaaab), ("X1", 0x22222223), ("M0", 0x55555555)])
# PCOPY X0,A0 (11.4.9 example), PSWAP (11.4.24), PAND (11.4.5)
case("pcopy_pswap_pand", """pcopy x0,a0
pswap x1,m0
pand x0,y0,a1""", [("X0", 0x55555555), ("A0E", 0xffffffffff), ("X1", 0x12345678), ("Y0", 0x33333333),
     ("A1E", 0x123456789a)], [("A0E", 0x0055555555), ("M0", 0x56781234), ("A1E", 0x0011110000)])
# PLDS A0,MACH (11.4.13 example) and PSTS MACH,A0 (11.4.20 example)
case("plds_psts", """plds a0,mach
psts macl,a1""", [("A0E", 0x123456789a), ("MACH", 0x66666666), ("MACL", 0x88888888)],
     [("MACH", 0x3456789a), ("A1E", 0xff88888888)])
# overflow protection: with S = 1 a sum past 32 bits saturates to 007FFFFFFFh and V stays 0;
# the AV accumulation and the T-bit overflow mode still see it (DSR = 0700h: TS = 011, TC = 1)
case("padd_saturation", """sets
lds r0,dsr
padd x0,y0,a0""", [("R0", 0x700), ("X0", 0x7fffffff), ("Y0", 0x7fffffff)],
     [("A0E", 0x007fffffff), ("V", 0), ("AV", 1), ("T", 1)])
# without S the guard bits hold the overflow; overflow mode (CS = 011) puts it in DC.  The 40-bit
# sum 7FFFFFFFFFh + 1 is also over-range, so GT = ~((N ^ over-range) | Z) = 1
case("padd_guard_bits_overflow", """lds r0,dsr
padd a0,y0,a0""", [("R0", 0x6), ("A0E", 0x7fffffffff), ("Y0", 1)],
     [("A0E", 0x8000000000), ("DC", 1), ("N", 1), ("V", 1), ("GT", 1)])

# ------------------------------------------------------------------ repeat loops (6.3)
# extended repeat: LDRS start, LDRE end, LDRC #3: the two-instruction body runs three times
case("repeat_extended_ldrc", """ldrs L1
ldre L2
ldrc #3
nop
L1: add #1,r1
L2: add #2,r2""", [("R1", 0), ("R2", 0)], [("R1", 3), ("R2", 6), ("RC", 0)])
# conventional repeat, four instructions: RS = start, RE = (start + 4) since the repeat
# detection instruction is three before the end (example 1); SETRC #2
case("repeat_conventional_four", """ldrs L1
ldre L1+4
setrc #2
nop
L1: add #1,r1
add #1,r2
add #1,r3
add #1,r4""", [], [("R1", 2), ("R2", 2), ("R3", 2), ("R4", 2), ("RC", 0)])
# conventional repeat, one instruction: RS = D + 8, RE = D + 4 (table 6.5), SETRC #4
case("repeat_conventional_one", """ldrs D+8
ldre D+4
setrc #4
D: nop
add #3,r1""", [], [("R1", 12), ("RC", 0)])


def emit():
    out = ["# generated by test/emu/cases.py; do not edit"]
    for name, asm, sets, expect, langs in CASES:
        code, syms = assemble(asm)
        if len(code) % 2:
            code += b"\0"
        words = " ".join("%02x%02x" % (code[j], code[j + 1]) for j in range(0, len(code), 2))
        mainlen = (syms["main_end"] - BASE) if "main_end" in syms else len(code)
        out.append("case %s langs %s" % (name, LANGS[langs]))
        out.append("code " + words)
        out.append("main %d" % mainlen)
        hs = {n: "%x" % a for n, a in syms.items()}
        for k, v in sets:
            out.append("set %s 0x%x" % (k.format(**hs), val(v, syms)))
        for k, v in expect:
            out.append("expect %s 0x%x" % (k.format(**hs), val(v, syms)))
        out.append("end")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    sys.stdout.write(emit())
