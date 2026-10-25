#!/usr/bin/env python3
"""P-code semantic tests for Ghidra's emulator (EmuCheck.java).

  emu_tests.py <outdir> [--break N]   -> emu_be.bin, emu_le.bin, emu_be.txt, emu_le.txt

BE is OpenRISC:BE:32:default (delay slots); LE is OpenRISC:LE:32:default (no delay slot).
Each test is a short instruction sequence at its own 0x100-aligned address. The .txt files have
one line per test:  <name> <start-hex> <stop-hex> <init: reg=val,...|-> <expect: reg=val,...>
Values are hex; registers are r0..r31, F, CY, OV, MACHI, MACLO. Data scratch area: 0x8000.
--break N makes the expectation of test N wrong (to show that the check can fail).
"""
import struct
import sys

out = sys.argv[1]
brk = int(sys.argv[sys.argv.index("--break") + 1]) if "--break" in sys.argv else -1
M = 0xffffffff


def R(d, a, b, low):
    return (0x38 << 26) | (d << 21) | (a << 16) | (b << 11) | low


def I(op, d, a, imm):
    return (op << 26) | (d << 21) | (a << 16) | (imm & 0xffff)


def S(op, a, b, imm):
    return (op << 26) | (((imm >> 11) & 0x1f) << 21) | (a << 16) | (b << 11) | (imm & 0x7ff)


def BR(op, off):
    return (op << 26) | ((off >> 2) & 0x3ffffff)


def SF(cond, a, b):
    return (0x39 << 26) | (cond << 21) | (a << 16) | (b << 11)


def SFI(cond, a, imm):
    return (0x2f << 26) | (cond << 21) | (a << 16) | (imm & 0xffff)


def SHI(d, a, mod, n):
    return (0x2e << 26) | (d << 21) | (a << 16) | (mod << 6) | n


def FP(d, a, b, op):
    return (0x32 << 26) | (d << 21) | (a << 16) | (b << 11) | op


addi = lambda d, a, i: I(0x27, d, a, i)
ori = lambda d, a, k: I(0x2a, d, a, k)
movhi = lambda d, k: (0x06 << 26) | (d << 21) | k
lwz = lambda d, a, i: I(0x21, d, a, i)
lbs = lambda d, a, i: I(0x24, d, a, i)
lbz = lambda d, a, i: I(0x23, d, a, i)
lhs = lambda d, a, i: I(0x26, d, a, i)
lhz = lambda d, a, i: I(0x25, d, a, i)
sw = lambda a, b, i: S(0x35, a, b, i)
sb = lambda a, b, i: S(0x36, a, b, i)
sh = lambda a, b, i: S(0x37, a, b, i)
j = lambda off: BR(0x00, off)
jal = lambda off: BR(0x01, off)
bnf = lambda off: BR(0x03, off)
bf = lambda off: BR(0x04, off)
jr = lambda b: (0x11 << 26) | (b << 11)
jalr = lambda b: (0x12 << 26) | (b << 11)
NOP = 0x15000000
add = lambda d, a, b: R(d, a, b, 0x000)
addc = lambda d, a, b: R(d, a, b, 0x001)
sub = lambda d, a, b: R(d, a, b, 0x002)
and_ = lambda d, a, b: R(d, a, b, 0x003)
or_ = lambda d, a, b: R(d, a, b, 0x004)
xor = lambda d, a, b: R(d, a, b, 0x005)

# Tests common to both languages. Branch offsets are relative to the branch instruction.
T = [
    ("addi", [addi(3, 0, 5), addi(3, 3, -1)], {}, {"r3": 4}),
    ("movhi_ori", [movhi(3, 0x1234), ori(3, 3, 0x5678)], {}, {"r3": 0x12345678}),
    ("add_carry", [add(3, 4, 5)], {"r4": M, "r5": 1}, {"r3": 0, "CY": 1, "OV": 0}),
    ("add_overflow", [add(3, 4, 5)], {"r4": 0x7fffffff, "r5": 1}, {"r3": 0x80000000, "CY": 0, "OV": 1}),
    ("addc", [addc(3, 4, 5)], {"r4": 1, "r5": 2, "CY": 1}, {"r3": 4, "CY": 0}),
    ("addic_carry_in", [I(0x28, 3, 4, -1)], {"r4": 1, "CY": 1}, {"r3": 1, "CY": 1}),
    ("sub_borrow", [sub(3, 4, 5)], {"r4": 1, "r5": 2}, {"r3": M, "CY": 1, "OV": 0}),
    ("logic", [and_(3, 4, 5), or_(6, 4, 5), xor(7, 4, 5), I(0x29, 8, 4, 0xff00), I(0x2b, 9, 4, -1)],
     {"r4": 0xf0f0, "r5": 0xff00},
     {"r3": 0xf000, "r6": 0xfff0, "r7": 0x0ff0, "r8": 0xf000, "r9": 0xffff0f0f}),
    ("shift_reg", [R(3, 4, 5, 0x008), R(6, 4, 5, 0x048), R(7, 4, 5, 0x088), R(8, 4, 5, 0x0c8)],
     {"r4": 0x80000010, "r5": 33},  # amount uses the low 5 bits: 33 -> 1
     {"r3": 0x00000020, "r6": 0x40000008, "r7": 0xc0000008, "r8": 0x40000008}),
    ("shift_imm", [SHI(3, 4, 0, 4), SHI(6, 4, 1, 4), SHI(7, 4, 2, 4), SHI(8, 4, 3, 4)],
     {"r4": 0x80000013}, {"r3": 0x00000130, "r6": 0x08000001, "r7": 0xf8000001, "r8": 0x38000001}),
    ("mul_ov", [R(3, 4, 5, 0x306), R(6, 4, 5, 0x30b)], {"r4": 0x80000000, "r5": 2},
     {"r3": 0, "OV": 1, "r6": 0, "CY": 1}),
    ("muli", [I(0x2c, 3, 4, -3)], {"r4": 7}, {"r3": 0xffffffeb, "OV": 0}),
    ("div", [R(3, 4, 5, 0x309), R(6, 4, 5, 0x30a)], {"r4": 0xfffffff6, "r5": 3},
     {"r3": 0xfffffffd, "r6": 0x55555552}),
    ("ext", [R(3, 4, 0, 0x00c), R(6, 4, 0, 0x04c), R(7, 4, 0, 0x08c), R(8, 4, 0, 0x0cc)],
     {"r4": 0x1234f680}, {"r3": 0xfffff680, "r6": 0xffffff80, "r7": 0xf680, "r8": 0x80}),
    ("ff1_fl1", [R(3, 4, 0, 0x00f), R(6, 4, 0, 0x10f), R(7, 0, 0, 0x00f), R(8, 0, 0, 0x10f)],
     {"r4": 0x00f00100}, {"r3": 9, "r6": 24, "r7": 0, "r8": 0}),
    ("cmov", [R(3, 4, 5, 0x00e), SFI(0, 0, 0), R(6, 4, 5, 0x00e)], {"r4": 1, "r5": 2, "F": 0},
     {"r3": 2, "r6": 1, "F": 1}),
    ("sf_signed_unsigned", [SFI(0xa, 4, 1), R(5, 0, 0, 0), SFI(0x2, 4, 1)], {"r4": M},
     {"F": 1}),  # sfgtsi -1 > 1 is false, sfgtui 0xffffffff > 1 is true (last one wins)
    ("sf_lts", [SF(0xc, 4, 5)], {"r4": M, "r5": 1}, {"F": 1}),
    ("mem_word", [sw(8, 4, -4), lwz(3, 8, -4)], {"r4": 0x11223344, "r8": 0x8010}, {"r3": 0x11223344}),
    ("mem_byte_half", [sw(8, 4, 0), lbs(3, 8, 0), lbz(5, 8, 0), lhs(6, 8, 0), lhz(7, 8, 2),
                       sb(8, 9, 1), sh(8, 9, 2), lwz(10, 8, 0)],
     {"r4": 0x8899aabb, "r8": 0x8000, "r9": 0x1234},
     {"be": {"r3": 0xffffff88, "r5": 0x88, "r6": 0xffff8899, "r7": 0xaabb, "r10": 0x88341234},
      "le": {"r3": 0xffffffbb, "r5": 0xbb, "r6": 0xffffaabb, "r7": 0x8899, "r10": 0x123434bb}}),
    ("mac", [(0x31 << 26) | (4 << 16) | (5 << 11) | 1, (0x31 << 26) | (4 << 16) | (5 << 11) | 1,
             (0x06 << 26) | (3 << 21) | 0x10000],
     {"r4": 0x10000, "r5": 0x30001}, {"r3": 0x20000, "MACHI": 0, "MACLO": 0}),
    ("muldu", [R(0, 4, 5, 0x30c)], {"r4": M, "r5": 2}, {"MACHI": 1, "MACLO": 0xfffffffe}),
    ("mtspr_mfspr", [S(0x30, 0, 4, 0x2802), (0x2d << 26) | (3 << 21) | (0 << 16) | 0x2802],
     {"r4": 0xabcd}, {"MACHI": 0xabcd, "r3": 0xabcd}),  # SPR 0x2802 = MACHI
    ("fp_single", [FP(3, 4, 5, 0x00), FP(6, 4, 5, 0x02), FP(7, 8, 0, 0x04), FP(9, 6, 0, 0x05),
                   FP(0, 4, 5, 0x0c)],
     {"r4": 0x3fc00000, "r5": 0x40100000, "r8": 7},
     {"r3": 0x40700000, "r6": 0x40580000, "r7": 0x40e00000, "r9": 3, "F": 1}),
    ("fp_double_pair", [FP(8, 4, 6, 0x10), FP(0, 4, 6, 0x1c)],
     {"r4": 0x3ff80000, "r5": 0, "r6": 0x40020000, "r7": 0},
     {"r8": 0x400e0000, "r9": 0, "F": 1}),
    ("fp_double_pair_plus2", [FP(10, 4, 6, 0x10) | (1 << 10) | (1 << 9), FP(3, 10, 0, 0x35) | (1 << 9)],
     # rA pair r4,r6 (+2), rB pair r6,r7, rD pair r10,r12 (+2); dtos of r10,r12 -> r3
     {"r4": 0x3ff00000, "r6": 0x40000000, "r7": 0},
     # (1.000000238418579 + 2.0 = 3.000000238418579; as float 0x40400001)
     {"r10": 0x40080000, "r12": 0x20000000, "r3": 0x40400001}),
]

# Flow tests differ: BE has a delay slot after every jump/branch, LE has none.
FLOW_BE = [
    ("call_ret", [jal(0x14), addi(3, 3, 1), addi(3, 3, 10), j(0x18), NOP,
                  addi(3, 3, 100), jr(9), addi(3, 3, 1000), addi(3, 3, 5000)],
     {}, {"r3": 1111}, 0x24, {"r9": 8}),
    ("jalr", [lambda b: ori(4, 0, b + 0x14), jalr(4), addi(3, 3, 1), j(0x18), NOP,
              addi(3, 3, 100), jr(9), NOP],
     {}, {"r3": 101}, 0x24, {"r4": 0x14, "r9": 0x0c}),
    ("bf_taken_delay", [SFI(0, 4, 5), bf(0xc), addi(3, 3, 1), addi(3, 3, 10), addi(3, 3, 100)],
     {"r4": 5}, {"r3": 101, "F": 1}, 0x14, {}),
    ("bnf_not_taken", [SFI(0, 4, 5), bnf(0xc), addi(3, 3, 1), addi(3, 3, 10), addi(3, 3, 100)],
     {"r4": 5}, {"r3": 111}, 0x14, {}),
    ("loop", [addi(3, 3, 3), addi(4, 4, -1), SFI(1, 4, 0), bf(-0xc), NOP],
     {"r4": 4}, {"r3": 12, "r4": 0}, 0x14, {}),
    ("pc_read", [jal(8), movhi(17, 0), ori(17, 17, 0x10), add(17, 17, 9)],
     {}, {"r17": 0x18}, 0x10, {"r9": 8}),
    ("adrp", [NOP, (0x02 << 26) | (3 << 21) | 2], {}, {}, 0x8, {"r3": 0x4000}),
]
FLOW_LE = [
    ("call_ret", [jal(0x10), addi(3, 3, 10), j(0x14), NOP,
                  addi(3, 3, 100), jr(9), addi(3, 3, 5000)],
     {}, {"r3": 110}, 0x1c, {"r9": 4}),
    ("jalr", [lambda b: ori(4, 0, b + 0x10), jalr(4), addi(3, 3, 1), j(0x10),
              addi(3, 3, 100), jr(9)],
     {}, {"r3": 101}, 0x1c, {"r4": 0x10, "r9": 0x08}),
    ("bf_taken", [SFI(0, 4, 5), bf(0x8), addi(3, 3, 1), addi(3, 3, 10)],
     {"r4": 5}, {"r3": 10, "F": 1}, 0x10, {}),
    ("bnf_not_taken", [SFI(0, 4, 5), bnf(0x8), addi(3, 3, 1), addi(3, 3, 10)],
     {"r4": 5}, {"r3": 11}, 0x10, {}),
    ("loop", [addi(3, 3, 3), addi(4, 4, -1), SFI(1, 4, 0), bf(-0xc)],
     {"r4": 4}, {"r3": 12, "r4": 0}, 0x10, {}),
    ("pc_read", [jal(4), movhi(17, 0), ori(17, 17, 0x10), add(17, 17, 9)],
     {}, {"r17": 0x14}, 0x10, {"r9": 4}),
    ("adrp", [NOP, (0x02 << 26) | (3 << 21) | 2], {}, {}, 0x8, {"r3": 0x4000}),
]

for e, fmt, flow in (("be", ">I", FLOW_BE), ("le", "<I", FLOW_LE)):
    img = bytearray(0x9000)
    lines = []
    tests = [(n, w, i, x, None, {}) for n, w, i, x in T] + \
            [(n, w, i, x, stop, rel) for n, w, i, x, stop, rel in flow]
    for k, (name, words, init, expect, stop, rel) in enumerate(tests):
        base = 0x100 * (k + 1)
        assert base + 4 * len(words) < 0x8000
        for i, wd in enumerate(words):
            wd = wd(base) if callable(wd) else wd
            struct.pack_into(fmt, img, base + 4 * i, wd)
        stop = base + (stop if stop is not None else 4 * len(words))
        exp = dict(expect[e] if e in expect else expect)
        exp.update({r: (v + base) & M for r, v in rel.items()})
        if name == "adrp":  # page of the l.adrp itself, plus 2 pages
            exp["r3"] = ((base + 4) & ~0x1fff) + 0x4000
        if name == "pc_read":
            exp["r17"] = (base + rel["r9"] + 0x10) & M
        if k == brk:
            r0 = next(iter(exp))
            exp[r0] = (exp[r0] + 1) & M
        ini = ",".join(f"{r}={v & M:x}" for r, v in init.items()) or "-"
        ex = ",".join(f"{r}={v & M:x}" for r, v in exp.items())
        lines.append(f"{e}_{name} {base:x} {stop:x} {ini} {ex}")
    open(f"{out}/emu_{e}.bin", "wb").write(img)
    open(f"{out}/emu_{e}.txt", "w").write("\n".join(lines) + "\n")
    print(f"{e}: {len(lines)} tests")
