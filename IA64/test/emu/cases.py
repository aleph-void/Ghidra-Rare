#!/usr/bin/env python3
"""Emulator cases for the IA-64 module.

Each case is assembler source (GNU as for ia64-linux-gnu, run only as a black box to get the
encodings), initial register/memory values and the expected results, worked out by hand from
the instruction descriptions in the Itanium SDM volume 3 chapter 2 (the arithmetic is written
out below as plain Python next to each case). The code is placed at ram:1000; emulation stops
when the PC reaches the end of the main code (subroutines follow it). sp = r12 = 0xf000, the
register stack backing store ar.bsp = 0xc000.

  cases.py                write cases.txt to stdout (needs ia64-linux-gnu-as/objcopy, see AS)
  cases.py --broken       the same with one deliberately wrong expectation
  cases.py --check FILE   verify that FILE is what this script produces (no assembler needed:
                          the encodings recorded in FILE are reused)
"""
import os, re, subprocess, sys, tempfile

AS = os.environ.get('IA64_AS', os.path.expanduser(
    '~/.cache/ghidra-rare-scratch/tools/x-ia64-linux-gnu/bin/ia64-linux-gnu-as'))
OBJCOPY = os.environ.get('IA64_OBJCOPY', AS.replace('-as', '-objcopy'))
M64 = (1 << 64) - 1

def u(v):
    return v & M64

def sx(v, bits):
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) else v

CASES = []

def case(name, src, sets=None, expect=None, main=None):
    CASES.append(dict(name=name, src=src, set=sets or {}, expect=expect or {}, main=main))

# ---------------------------------------------------------------------------------------------
# Integer ALU (A1-A5)
case('add_sub', '''
    add r8 = r14, r15
    sub r9 = r14, r15
    add r10 = r14, r15, 1
    sub r11 = r14, r15, 1
''', {'r14': 0x10, 'r15': 3},
    {'r8': 0x13, 'r9': 0xd, 'r10': 0x14, 'r11': 0x10 - 3 - 1})

case('logic', '''
    and r8 = r14, r15
    or r9 = r14, r15
    xor r10 = r14, r15
    andcm r11 = r14, r15
    and r16 = -16, r14
    xor r17 = -1, r15
''', {'r14': 0xF0F7, 'r15': 0xFF00},
    {'r8': 0xF000, 'r9': 0xFFF7, 'r10': 0x0FF7, 'r11': 0x00F7, 'r16': 0xF0F0, 'r17': u(~0xFF00)})

case('shladd_addp4', '''
    shladd r8 = r14, 3, r15
    addp4 r9 = r14, r15
    addp4 r10 = 0x10, r15
''', {'r14': 0x21, 'r15': 0xC0001000},
    # addp4: 32-bit sum zero-extended, r3 bits 31:30 copied to bits 62:61
    {'r8': (0x21 << 3) + 0xC0001000, 'r9': (3 << 61) | 0xC0001021, 'r10': (3 << 61) | 0xC0001010})

case('addl_adds_movl', '''
    addl r8 = 0x12345, r1
    adds r9 = -5, r14
    movl r10 = 0x8000000000000001
    mov r11 = -300000
    mov r16 = r14
''', {'r1': 0x100, 'r14': 2},
    {'r8': 0x12445, 'r9': u(-3), 'r10': 0x8000000000000001, 'r11': u(-300000), 'r16': 2})

# ---------------------------------------------------------------------------------------------
# Compares and predication (A6-A8, I16-I17)
case('cmp_predication', '''
    cmp.lt p6, p7 = r14, r15
    cmp.ltu p8, p9 = r14, r15
    ;;
(p6) mov r8 = 1
(p7) mov r8 = 2
(p8) mov r9 = 3
(p9) mov r9 = 4
''', {'r14': u(-1), 'r15': 1, 'r8': 0, 'r9': 0},
    # signed -1 < 1; unsigned 0xff..ff > 1
    {'p6': 1, 'p7': 0, 'p8': 0, 'p9': 1, 'r8': 1, 'r9': 4})

case('cmp4_imm', '''
    cmp4.lt p6, p7 = r14, r15
    cmp.eq p8, p9 = 7, r16
    cmp4.ltu p10, p11 = -1, r15
''', {'r14': 0x100000005, 'r15': 0x200000003, 'r16': 7},
    # cmp4 compares the low 32 bits: 5 < 3 is false; imm -1 = 0xffffffff unsigned > 3
    {'p6': 0, 'p7': 1, 'p8': 1, 'p9': 0, 'p10': 0, 'p11': 1})

case('cmp_unc_qp_false', '''
(p9) cmp.eq.unc p6, p7 = r14, r14
(p9) cmp.eq p10, p11 = r14, r14
''', {'p9': 0, 'p6': 1, 'p7': 1, 'p10': 1, 'p11': 0, 'r14': 5},
    # .unc clears both targets even when the qualifying predicate is 0; the normal form does nothing
    {'p6': 0, 'p7': 0, 'p10': 1, 'p11': 0})

case('cmp_parallel', '''
    cmp.eq.and p6, p7 = r14, r15
    cmp.ne.or p8, p9 = r14, r15
    cmp.eq.or.andcm p10, p11 = r14, r14
    cmp.eq.and p12, p13 = r14, r14
''', {'r14': 1, 'r15': 2, 'p6': 1, 'p7': 1, 'p8': 0, 'p9': 0, 'p10': 0, 'p11': 1, 'p12': 1, 'p13': 1},
    # .and clears both when false; .or sets both when true; .or.andcm sets p1, clears p2 when true;
    # .and leaves the targets alone when true
    {'p6': 0, 'p7': 0, 'p8': 1, 'p9': 1, 'p10': 1, 'p11': 0, 'p12': 1, 'p13': 1})

case('cmp_zero_forms', '''
    cmp.gt.and p6, p7 = r0, r14
    cmp4.ge.or p8, p9 = r0, r15
''', {'r14': u(-5), 'r15': 0x100000000, 'p6': 1, 'p7': 1, 'p8': 0, 'p9': 0},
    # 0 > -5 is true so .and leaves p6/p7; cmp4: low 32 bits of r15 are 0, 0 >= 0 true -> .or sets
    {'p6': 1, 'p7': 1, 'p8': 1, 'p9': 1})

case('tbit_tnat', '''
    tbit.nz p6, p7 = r14, 5
    tbit.z p8, p9 = r14, 4
    tnat.nz p10, p11 = r15
''', {'r14': 0x20, 'r15.nat': 1},
    {'p6': 1, 'p7': 0, 'p8': 1, 'p9': 0, 'p10': 1, 'p11': 0})

# ---------------------------------------------------------------------------------------------
# Shifts, deposit, extract (I10-I15, I5-I7)
X = 0x8765432112345678
case('extr_dep', '''
    extr.u r8 = r14, 4, 8
    extr r9 = r14, 56, 8
    extr r10 = r14, 60, 8
    dep r11 = r15, r14, 8, 16
    dep.z r16 = r15, 4, 8
    shrp r17 = r14, r15, 8
    dep.z r18 = -1, 60, 8
    dep r19 = -1, r14, 0, 4
''', {'r14': X, 'r15': 0xABCD},
    {'r8': (X >> 4) & 0xff,
     'r9': u(sx(X >> 56, 8)),                       # 0x87 sign-extended
     'r10': u(sx(X >> 60, 4)),                      # pos + len > 64: sign fill from bit 63
     'r11': (X & ~(0xffff << 8)) | ((0xABCD & 0xffff) << 8),
     'r16': (0xABCD & 0xff) << 4,
     'r17': u((0xABCD >> 8) | (X << 56)),            # (r2:r3) >> 8 with r2 = r14, r3 = r15
     'r18': u(0xff << 60),                          # truncated at bit 63
     'r19': X | 0xf})

case('shifts', '''
    shl r8 = r14, r15
    shr r9 = r16, r15
    shr.u r10 = r16, r15
    shl r11 = r14, 3
    shr.u r17 = r16, 60
    shl r18 = r14, r19
''', {'r14': 0x81, 'r15': 4, 'r16': u(-256), 'r19': 64},
    {'r8': 0x810, 'r9': u(-16), 'r10': u(-256) >> 4, 'r11': 0x408, 'r17': 0xf, 'r18': 0})

case('ext_czx_popcnt', '''
    sxt1 r8 = r14
    zxt2 r9 = r15
    sxt4 r10 = r15
    czx1.l r11 = r16
    czx1.r r17 = r16
    popcnt r18 = r15
    czx2.r r19 = r16
''', {'r14': 0x80, 'r15': 0x1234F00F, 'r16': 0x1122330044556677},
    # bytes of r16 from the least significant: 77 66 55 44 00 33 22 11 -> first zero byte is
    # index 4 from the right and index 3 from the left; 16-bit lanes 6677 5544 3300 1122: none 0
    {'r8': u(-128), 'r9': 0xF00F, 'r10': 0x1234F00F, 'r11': 3, 'r17': 4,
     'r18': bin(0x1234F00F).count('1'), 'r19': 4})

# ---------------------------------------------------------------------------------------------
# Memory (M1-M5, M16-M17)
case('load_store', '''
    st8 [r14] = r15
    ;;
    ld4 r8 = [r14]
    ld1 r9 = [r14], 1
    ;;
    ld2 r10 = [r14]
    st4 [r16] = r15, 8
    ;;
    ld8 r11 = [r17], r18
''', {'r14': 0x8000, 'r15': 0x1122334455667788, 'r16': 0x8100, 'r17': 0x8000, 'r18': 0x10},
    {'r8@le': 0x55667788, 'r9@le': 0x88, 'r14': 0x8001, 'r10@le': 0x6677, 'r16': 0x8108,
     'ram:8100/4': 0x55667788, 'r11': 0x1122334455667788, 'r17': 0x8010,
     # big-endian data: the same bytes read from the other end
     'r8@be': 0x11223344, 'r9@be': 0x11, 'r10@be': 0x2233})

case('cmpxchg_fetchadd', '''
    mov ar.ccv = 5
    ;;
    cmpxchg8.acq r8 = [r14], r15, ar.ccv
    ;;
    cmpxchg8.acq r9 = [r14], r16, ar.ccv
    ;;
    fetchadd8.acq r10 = [r17], 8
    xchg4 r11 = [r18], r19
''', {'r14': 0x8000, 'ram:8000/8': 5, 'r15': 0x77, 'r16': 0x99, 'r17': 0x8010, 'ram:8010/8': 100,
      'r18': 0x8020, 'ram:8020/4': 0xdead, 'r19': 0xbeef},
    # first compare matches (5) and stores 0x77; the second sees 0x77 != 5 and stores nothing
    {'r8': 5, 'r9': 0x77, 'ram:8000/8': 0x77, 'r10': 100, 'ram:8010/8': 108,
     'r11': 0xdead, 'ram:8020/4': 0xbeef})

case('speculation', '''
    ld8.s r8 = [r14]
    ;;
    add r9 = r8, r15
    ;;
    chk.s r9, recover
back:
    mov r11 = 1
    br.sptk.few done
recover:
    mov r10 = 7
    br.sptk.few back
done:
''', {'r14': 0x8000, 'r14.nat': 1, 'r15': 1, 'r10': 0, 'r11': 0},
    # the address NaT makes the speculative load's result NaT, add propagates it, chk.s branches
    {'r8.nat': 1, 'r9.nat': 1, 'r10': 7, 'r11': 1})

# ---------------------------------------------------------------------------------------------
# Branches, loops, register stack
case('cloop', '''
    mov ar.lc = 4
    mov r8 = 0
    ;;
loop:
    add r8 = 3, r8
    br.cloop.sptk.few loop
    ;;
''', {}, {'r8': 15, 'ar.lc': 0})

case('cond_loop', '''
    mov r8 = 0
    mov r9 = 10
    ;;
top:
    add r8 = r8, r9
    adds r9 = -1, r9
    ;;
    cmp.ne p6, p0 = r9, r0
(p6) br.cond.dptk.few top
    ;;
''', {}, {'r8': sum(range(1, 11)), 'r9': 0})

case('call_ret', '''
    alloc r33 = ar.pfs, 0, 2, 2, 0
    mov r32 = 0x55
    mov r34 = 3
    mov r35 = 4
    ;;
    br.call.sptk.many b0 = sub
    ;;
    add r8 = r8, r32
    ;;
end:
    nop.m 0
    nop.i 0
    nop.i 0
    ;;
sub:
    alloc r34 = ar.pfs, 2, 1, 0, 0
    ;;
    add r8 = r32, r33
    mov ar.pfs = r34
    ;;
    br.ret.sptk.many b0
    ;;
''', {}, {'r8': 3 + 4 + 0x55, 'r32': 0x55, 'ar.bsp': 0xc000}, main='end')

case('br_call_indirect', '''
    alloc r40 = ar.pfs, 0, 8, 1, 0
    movl r14 = 0x1000 + (sub2 - start)
    mov r32 = 9
    mov r40 = 11
    ;;
    mov b6 = r14
    ;;
    br.call.sptk.many b0 = b6
    ;;
    add r8 = r8, r32
    ;;
end:
    nop.m 0
    nop.i 0
    nop.i 0
    ;;
sub2:
    alloc r16 = ar.pfs, 1, 0, 0, 0
    ;;
    shl r8 = r32, 1
    mov ar.pfs = r16
    br.ret.sptk.many b0
    ;;
''', {}, {'r8': 2 * 11 + 9, 'r32': 9}, main='end')

case('pr_moves', '''
    mov pr = r14, -1
    ;;
    mov r8 = pr
    mov pr.rot = 0x30000
    ;;
    mov r9 = pr
''', {'r14': 0xF00000000000ABCC},
    # p0 always reads 1; pr.rot writes p16-p63 from the immediate (bits 16 and 17 set)
    {'r8': 0xF00000000000ABCD, 'r9': (0xABCD & 0xffff) | 0x30000, 'p63': 0})

case('rotation_ctop', '''
    alloc r40 = ar.pfs, 0, 16, 0, 8
    mov ar.lc = 1
    mov ar.ec = 1
    mov r32 = 1
    mov r33 = 2
    mov r39 = 8
    ;;
    mov pr.rot = 0
    ;;
loop:
    nop.m 0
    nop.i 0
    br.ctop.sptk.few loop
    ;;
''', {},
    # iteration 1: LC 1 -> 0, p63 = 1, rotate (r33 = old r32, r32 = old r39, p16 = old p63 = 1),
    # taken. Iteration 2: LC = 0, EC 1 -> 0, p63 = 0, rotate again, EC = 1 was not > 1: fall out.
    {'ar.lc': 0, 'ar.ec': 0, 'r32': 0, 'r33': 8, 'r34': 1, 'r35': 2, 'p16': 0, 'p17': 1})

case('wtop', '''
    alloc r40 = ar.pfs, 0, 8, 0, 8
    mov ar.ec = 2
    mov r32 = 5
    ;;
    cmp.eq p6, p0 = r0, r0
    ;;
loop:
    nop.m 0
    nop.i 0
(p6) br.wtop.sptk.few loop
    ;;
''', {},
    # p6 stays 1 for both passes? No: wtop rotates p6 too only if p6 >= 16 (it is not). First pass
    # p6 = 1: EC unchanged, p63 = 0, rotate, taken (forever while p6 = 1), so use ec to stop:
    {}, main=None)
CASES.pop()   # (kept as documentation of why a qp >= 16 is needed; see wtop2)

case('wtop2', '''
    alloc r40 = ar.pfs, 0, 8, 0, 8
    mov ar.ec = 2
    mov r32 = 5
    mov pr.rot = 0x10000
    ;;
loop:
    nop.m 0
    nop.i 0
(p16) br.wtop.sptk.few loop
    ;;
''', {},
    # pass 1: p16 = 1 -> EC stays 2, p63 = 0, rotate (p17 = 1, p16 = old p63 = 0), taken.
    # pass 2: p16 = 0, EC 2 > 1 -> EC = 1, p63 = 0, rotate, taken (EC was > 1).
    # pass 3: p16 = 0, EC 1 -> EC = 0, p63 = 0, rotate, not taken.
    # r32 rotates three times through r32..r39: ends in r35.
    {'ar.ec': 0, 'r35': 5, 'p20': 0, 'p19': 1})

# ---------------------------------------------------------------------------------------------
# Floating point (M18/M19, F1-F11)
case('int_multiply_xma', '''
    setf.sig f6 = r14
    setf.sig f7 = r15
    ;;
    xmpy.l f8 = f6, f7
    xmpy.hu f9 = f6, f7
    xma.l f10 = f6, f7, f6
    ;;
    getf.sig r8 = f8
    getf.sig r9 = f9
    getf.sig r10 = f10
''', {'r14': 0x123456789, 'r15': 0xFEDCBA987654321},
    {'r8': u(0x123456789 * 0xFEDCBA987654321), 'r9': (0x123456789 * 0xFEDCBA987654321) >> 64,
     'r10': u(0x123456789 * 0xFEDCBA987654321 + 0x123456789)})

case('fp_double', '''
    setf.d f6 = r14
    setf.d f7 = r15
    ;;
    fmpy.d f8 = f6, f7
    fadd.d f9 = f6, f7
    fsub.d f10 = f6, f7
    fma.d f11 = f6, f7, f6
    ;;
    getf.d r8 = f8
    getf.d r9 = f9
    getf.d r10 = f10
    getf.d r11 = f11
    fcmp.lt p6, p7 = f6, f7
''', {'r14': 0x3FF8000000000000, 'r15': 0x4002000000000000},   # 1.5 and 2.25
    # 1.5 * 2.25 = 3.375 = 0x400B000000000000; 3.75 = 0x400E000000000000;
    # -0.75 = 0xBFE8000000000000; 3.375 + 1.5 = 4.875 = 0x4013800000000000
    {'r8': 0x400B000000000000, 'r9': 0x400E000000000000, 'r10': 0xBFE8000000000000,
     'r11': 0x4013800000000000, 'p6': 1, 'p7': 0})

case('fp_convert', '''
    setf.d f6 = r14
    setf.sig f7 = r15
    ;;
    fcvt.fx.trunc f8 = f6
    fcvt.xf f9 = f7
    ;;
    fnorm.d f9 = f9
    getf.sig r8 = f8
    ;;
    getf.d r9 = f9
    setf.s f10 = r16
    ;;
    getf.s r10 = f10
''', {'r14': 0xC00C000000000000, 'r15': u(-6), 'r16': 0x40490FDB},   # -3.5, -6, 3.14159274
    # trunc(-3.5) = -3; -6 as a double is 0xC018000000000000; single round-trips unchanged
    {'r8': u(-3), 'r9': 0xC018000000000000, 'r10': 0x40490FDB})

case('fp_merge_logic', '''
    setf.d f6 = r14
    setf.d f7 = r15
    ;;
    fmerge.ns f8 = f6, f7
    fabs f9 = f6
    for f10 = f6, f7
    ;;
    getf.d r8 = f8
    getf.d r9 = f9
    getf.sig r10 = f10
''', {'r14': 0xC000000000000000, 'r15': 0x4008000000000000},   # -2.0, 3.0
    # fmerge.ns: complemented sign of f6 (+) with exponent/significand of f7 -> +3.0
    # for: OR of the significands (2.0 and 3.0: 0x8000.. and 0xC000..)
    {'r8': 0x4008000000000000, 'r9': 0x4000000000000000, 'r10': 0xC000000000000000})

# ---------------------------------------------------------------------------------------------
# Multimedia (A9, I1-I4)
case('mm_add_sub', '''
    padd2 r8 = r14, r15
    psub1.uuu r9 = r14, r15
    padd1.sss r10 = r14, r15
    pcmp2.gt r11 = r14, r15
    pavg1 r16 = r14, r15
''', {'r14': 0x7F80FF0101020304, 'r15': 0x0102030480808080},
    # 16-bit lanes (lsb first) 0304+8080, 0102+8080, ff01+0304, 7f80+0102 (mod 2^16)
    {'r8': 0x8082020581828384,
     # bytes unsigned saturating r14 - r15: 04-80 0, 03-80 0, 02-80 0, 01-80 0, 01-04 0,
     # ff-03 fc, 80-02 7e, 7f-01 7e
     'r9': 0x7E7EFC0000000000,
     # signed saturating bytes: 04+80=-124 0x84, 03+80 0x83, 02+80 0x82, 01+80 0x81,
     # 01+04 05, ff+03 02, 80+02 82, 7f+01 sat 7f
     'r10': 0x7F82020581828384,
     # 16-bit signed gt: 0304 > 8080(-) yes; 0102 > 8080 yes; ff01(-) > 0304 no; 7f80 > 0102 yes
     'r11': 0xFFFF0000FFFFFFFF,
     # pavg1: (a + b) >> 1 with the low bit set if either low bit of the sum is 1
     'r16': sum((((((0x7F80FF0101020304 >> 8 * i) & 0xff) + ((0x0102030480808080 >> 8 * i) & 0xff)) >> 1) |
                 ((((0x7F80FF0101020304 >> 8 * i) & 0xff) + ((0x0102030480808080 >> 8 * i) & 0xff)) & 1))
                << 8 * i for i in range(8))})

case('mm_permute', '''
    mux1 r8 = r14, @rev
    mix1.l r9 = r14, r15
    unpack2.l r10 = r14, r15
    mux2 r11 = r14, 0x1b
    pmpyshr2.u r16 = r14, r15, 16
    pmin2 r17 = r14, r15
''', {'r14': 0x0807060504030201, 'r15': 0x1817161514131211},
    # mux1 @rev reverses bytes; mix1.l takes the odd bytes x7 y7 x5 y5 x3 y3 x1 y1;
    # unpack2.l interleaves the low halfwords x1 y1 x0 y0; mux2 0x1b = indices 3,2,1,0 reversed
    {'r8': 0x0102030405060708, 'r9': 0x0818061604140212, 'r10': 0x0403141302011211,
     'r11': 0x0201040306050807,
     'r16': ((0x0807 * 0x1817) >> 16) << 48 | ((0x0605 * 0x1615) >> 16) << 32 |
            ((0x0403 * 0x1413) >> 16) << 16 | ((0x0201 * 0x1211) >> 16),
     'r17': 0x0807060504030201})

case('nat_propagation', '''
    add r8 = r14, r15
    or r9 = r15, r16
    ;;
    tnat.nz p6, p7 = r8
    tnat.nz p8, p9 = r9
    ld8 r10 = [r17]
''', {'r14': 1, 'r14.nat': 1, 'r15': 2, 'r16': 3, 'r17': 0x8000, 'r10.nat': 1},
    {'r8.nat': 1, 'r9.nat': 0, 'p6': 1, 'p7': 0, 'p8': 0, 'p9': 1, 'r10.nat': 0})

case('spill_fill', '''
    st8.spill [r14] = r15
    ;;
    ld8.fill r8 = [r14]
    mov r9 = ar.unat
''', {'r14': 0x8018, 'r15': 0x1234, 'r15.nat': 1, 'ar.unat': 0},
    # UNAT bit = address bits 8:3 = 3
    {'ram:8018/8': 0x1234, 'r8': 0x1234, 'r8.nat': 1, 'r9': 1 << 3})

# ---------------------------------------------------------------------------------------------
# More floating point, multimedia, 16-byte memory, nested calls, long branches
def sgl(x):
    import struct
    return struct.unpack('<I', struct.pack('<f', x))[0]

def dbl(x):
    import struct
    return struct.unpack('<Q', struct.pack('<d', x))[0]

case('fp_parallel', """
    setf.sig f6 = r14
    setf.sig f7 = r15
    ;;
    fpmpy f8 = f6, f7
    fpcmp.lt f9 = f7, f6
    fpmax f10 = f6, f7
    fswap f11 = f6, f7
    fmix.lr f12 = f6, f7
    ;;
    getf.sig r8 = f8
    getf.sig r9 = f9
    getf.sig r10 = f10
    getf.sig r11 = f11
    getf.sig r16 = f12
""", {'r14': (sgl(2.0) << 32) | sgl(3.0), 'r15': (sgl(1.5) << 32) | sgl(0.5)},
    # pairs of singles in the significand (high, low): fpmpy multiplies lane-wise; fpcmp.lt is
    # all ones per lane where f2 < f3; fpmax keeps f2 where f3 < f2; fswap = f3 low : f2 high;
    # fmix.lr = f2 high : f3 low
    {'r8': (sgl(3.0) << 32) | sgl(1.5), 'r9': 0xFFFFFFFFFFFFFFFF, 'r10': (sgl(2.0) << 32) | sgl(3.0),
     'r11': (sgl(0.5) << 32) | sgl(2.0), 'r16': (sgl(2.0) << 32) | sgl(0.5)})

case('fp_class_rcp_exp', """
    setf.d f6 = r14
    setf.d f10 = r15
    mov r16 = 0x10001
    ;;
    fclass.m p6, p7 = f6, @pos|@norm
    fclass.m p8, p9 = f6, 0x1e
    frcpa.s0 f8, p10 = f6, f10
    setf.exp f7 = r16
    getf.exp r9 = f6
    ;;
    getf.d r8 = f8
    getf.d r10 = f7
""", {'r14': dbl(1.5), 'r15': dbl(4.0), 'p10': 0},
    # 1.5 is a positive normal; class 0x1e asks for negative values only, so false.
    # frcpa: 1/4 (exact here) and p2 = 1; setf.exp 0x10001 = 2^2 with significand 1.0 -> 4.0;
    # getf.exp of 1.5: biased 17-bit exponent 0xffff
    {'p6': 1, 'p7': 0, 'p8': 0, 'p9': 1, 'p10': 1, 'r8': dbl(0.25), 'r10': dbl(4.0), 'r9': 0xffff})

case('mm_more', """
    mpy4 r8 = r14, r15
    mpyshl4 r9 = r14, r15
    psad1 r10 = r16, r17
    pack2.sss r11 = r16, r17
    pshl2 r18 = r16, 4
    pshr2 r19 = r16, 4
    shrp r20 = r16, r17, 16
""", {'r14': 0x1FFFFFFFF, 'r15': 2, 'r16': 0x00FF_8000_7FFF_0080, 'r17': 0xFF80_0001_0100_FFFE},
    {'r8': 0xFFFFFFFF * 2, 'r9': (1 * 2) << 32,
     'r10': sum(abs(((0x00FF80007FFF0080 >> 8 * i) & 0xff) - ((0xFF8000010100FFFE >> 8 * i) & 0xff))
                for i in range(8)),
     # signed saturation of the 16-bit lanes (r2 lanes low, r3 lanes high) to bytes
     'r11': int.from_bytes(bytes(max(-128, min(127, sx((v >> 16 * i) & 0xffff, 16))) & 0xff
                                 for v in (0x00FF80007FFF0080, 0xFF8000010100FFFE) for i in range(4)),
                           'little'),
     'r18': sum((((0x00FF80007FFF0080 >> 16 * i) & 0xffff) << 4 & 0xffff) << 16 * i for i in range(4)),
     'r19': sum(((sx((0x00FF80007FFF0080 >> 16 * i) & 0xffff, 16) >> 4) & 0xffff) << 16 * i
                for i in range(4)),
     'r20': u((0xFF8000010100FFFE >> 16) | (0x00FF80007FFF0080 << 48))})

case('mem16', """
    mov ar.csd = r16
    ;;
    st16 [r15] = r17, ar.csd
    ;;
    ld16 r8, ar.csd = [r15]
    ;;
    mov r9 = ar.csd
    mov ar.ccv = r17
    ;;
    cmp8xchg16.acq r10 = [r15], r18, ar.csd, ar.ccv
""", {'r15': 0x8040, 'r16': 0x2222, 'r17': 0x1111, 'r18': 0x3333},
    # st16 writes r2 at [r3] and ar.csd at [r3 + 8]; ld16 reads them back; cmp8xchg16 compares
    # [r3] with ar.ccv (equal) and stores r2 at [r3] and ar.csd at [r3 + 8]
    {'r8': 0x1111, 'r9': 0x2222, 'r10': 0x1111, 'ram:8040/8': 0x3333, 'ram:8048/8': 0x2222})

case('nested_calls', """
    alloc r34 = ar.pfs, 0, 3, 1, 0
    mov r32 = 100
    mov r33 = 200
    mov r35 = 5
    ;;
    br.call.sptk.many b0 = func1
    ;;
    add r8 = r8, r32
    ;;
    add r8 = r8, r33
end:
    nop.m 0
    nop.i 0
    nop.i 0
    ;;
func1:
    alloc r35 = ar.pfs, 1, 3, 1, 0
    mov r33 = 7
    mov r34 = b0
    adds r36 = 1, r32
    ;;
    br.call.sptk.many b0 = func2
    ;;
    add r8 = r8, r33
    mov b0 = r34
    mov ar.pfs = r35
    ;;
    br.ret.sptk.many b0
    ;;
func2:
    alloc r16 = ar.pfs, 1, 0, 0, 0
    ;;
    shl r8 = r32, 2
    mov ar.pfs = r16
    br.ret.sptk.many b0
    ;;
""", {}, # func2(6) = 24; func1 adds its local 7 -> 31; main adds its locals 100 + 200
    {'r8': 6 * 4 + 7 + 100 + 200, 'r32': 100, 'r33': 200, 'ar.bsp': 0xc000}, main='end')

case('long_branch', """
    movl r14 = 0x0123456789abcdef
    brl.call.sptk.many b6 = sub3
    ;;
    add r8 = r8, r14
end:
    nop.m 0
    nop.i 0
    nop.i 0
    ;;
sub3:
    mov r8 = 1
    br.ret.sptk.many b6
    ;;
""", {}, {'r8': 0x0123456789abcdef + 1}, main='end')

# ---------------------------------------------------------------------------------------------
def assemble(src):
    with tempfile.TemporaryDirectory() as d:
        s = os.path.join(d, 'c.s')
        o = os.path.join(d, 'c.o')
        b = os.path.join(d, 'c.bin')
        with open(s, 'w') as f:
            f.write('\t.text\nstart:\n' + src + '\n\t.align 16\nzz_end:\n')
        subprocess.run([AS, '-o', o, s], check=True, capture_output=True)
        subprocess.run([OBJCOPY, '-O', 'binary', '-j', '.text', o, b], check=True)
        code = open(b, 'rb').read()
        nm = subprocess.run([AS.replace('-as', '-nm'), o], check=True, capture_output=True, text=True).stdout
        syms = {}
        for line in nm.splitlines():
            p = line.split()
            if len(p) == 3:
                syms[p[2]] = int(p[0], 16)
        return code, syms

def render(broken=False, known=None):
    out = []
    for i, c in enumerate(CASES):
        if known is not None and c['name'] in known:
            code, mainlen = known[c['name']]
        else:
            code, syms = assemble(c['src'])
            mainlen = syms[c['main']] if c['main'] else len(code)
            code = code.hex()
        out.append('case %s' % c['name'])
        out.append('code %s' % code)
        out.append('main %d' % mainlen)
        for k, v in c['set'].items():
            out.append('set %s 0x%x' % (k, u(v)))
        exp = dict(c['expect'])
        if broken and i == 0:
            k = next(iter(exp))
            exp[k] = u(exp[k] + 1)
        for k, v in exp.items():
            out.append('expect %s 0x%x' % (k, u(v)))
        out.append('end')
    return '\n'.join(out) + '\n'

if __name__ == '__main__':
    if '--check' in sys.argv:
        path = sys.argv[sys.argv.index('--check') + 1]
        known, name = {}, None
        for line in open(path):
            p = line.split()
            if p and p[0] == 'case':
                name = p[1]
            elif p and p[0] == 'code':
                code = p[1]
            elif p and p[0] == 'main':
                known[name] = (code, int(p[1]))
        sys.exit(0 if render(known=known) == open(path).read() else 1)
    sys.stdout.write(render('--broken' in sys.argv))
