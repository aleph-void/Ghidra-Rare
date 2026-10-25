#!/usr/bin/env python3
"""P-code semantic tests for Ghidra's emulator (EmuCheck.java), LM32.

  emu_tests.py <outdir> [--break N]   -> emu_be.bin, emu_le.bin, emu_be.txt, emu_le.txt

Each test is a short instruction sequence at its own 0x100-aligned address. The .txt files have
one line per test:  <name> <start-hex> <stop-hex> <init: reg=val,...|-> <expect: reg=val,...>
Values are hex. Data scratch area: 0x8000. --break N makes the expectation of test N wrong.
"""
import struct
import sys

out = sys.argv[1]
brk = int(sys.argv[sys.argv.index("--break") + 1]) if "--break" in sys.argv else -1
M = 0xffffffff
GP, FP, SP, RA, EA, BA = 26, 27, 28, 29, 30, 31


def RI(op, d, a, imm):  # rs1 = rs0 op imm
    return (op << 26) | (a << 21) | (d << 16) | (imm & 0xffff)


def RR(op, d, a, b):  # rs2 = rs0 op rs1
    return (op << 26) | (a << 21) | (b << 16) | (d << 11)


def ST(op, base, val, imm):
    return (op << 26) | (base << 21) | (val << 16) | (imm & 0xffff)


def BR(op, a, b, off):
    return (op << 26) | (a << 21) | (b << 16) | ((off >> 2) & 0xffff)


addi = lambda d, a, i: RI(0x0d, d, a, i)
ori = lambda d, a, k: RI(0x0e, d, a, k)
mvhi = lambda d, k: RI(0x1e, d, 0, k)
lw = lambda d, a, i: RI(0x0a, d, a, i)
sw = lambda a, v, i: ST(0x16, a, v, i)
bi = lambda off: (0x38 << 26) | ((off >> 2) & 0x3ffffff)
calli = lambda off: (0x3e << 26) | ((off >> 2) & 0x3ffffff)
RET = (0x30 << 26) | (RA << 21)
NOP = 0x34000000

T = [
    ("addi", [addi(1, 0, 5), addi(1, 1, -1)], {}, {"r1": 4}),
    ("mvhi_ori", [mvhi(1, 0x1234), ori(1, 1, 0x5678)], {}, {"r1": 0x12345678}),
    ("add_sub_wrap", [RR(0x2d, 1, 2, 3), RR(0x32, 4, 3, 2)], {"r2": M, "r3": 2},
     {"r1": 1, "r4": 3}),
    ("logic_rr", [RR(0x28, 1, 2, 3), RR(0x2e, 4, 2, 3), RR(0x26, 5, 2, 3), RR(0x21, 6, 2, 3),
                  RR(0x29, 7, 2, 3)], {"r2": 0xf0f0, "r3": 0xff00},
     {"r1": 0xf000, "r4": 0xfff0, "r5": 0x0ff0, "r6": 0xffff000f, "r7": 0xfffff00f}),
    ("logic_imm_zext", [RI(0x08, 1, 2, 0x8001), RI(0x06, 3, 2, 0x8000), RI(0x01, 4, 2, 0x8000),
                        RI(0x09, 5, 2, 0xffff)], {"r2": 0xffff0001},
     {"r1": 1, "r3": 0xffff8001, "r4": 0x00007ffe, "r5": 0x00000001}),
    ("andhi_orhi", [RI(0x18, 1, 2, 0x00ff), RI(0x1e, 3, 2, 0x1200)], {"r2": 0x12345678},
     {"r1": 0x00340000, "r3": 0x12345678}),
    ("shift_reg", [RR(0x2f, 1, 2, 3), RR(0x25, 4, 2, 3), RR(0x20, 5, 2, 3)],
     {"r2": 0x80000010, "r3": 33}, {"r1": 0x00000020, "r4": 0xc0000008, "r5": 0x40000008}),
    ("shift_imm", [RI(0x0f, 1, 2, 4), RI(0x05, 4, 2, 4), RI(0x00, 5, 2, 4)],
     {"r2": 0x80000013}, {"r1": 0x00000130, "r4": 0xf8000001, "r5": 0x08000001}),
    ("mul", [RR(0x22, 1, 2, 3), RI(0x02, 4, 2, -3)], {"r2": 7, "r3": 0xfffffffe},
     {"r1": 0xfffffff2, "r4": 0xffffffeb}),
    ("divu_modu", [RR(0x23, 1, 2, 3), RR(0x31, 4, 2, 3)], {"r2": 0xfffffff6, "r3": 3},
     {"r1": 0x55555552, "r4": 0}),
    ("div_mod", [RR(0x27, 1, 2, 3), RR(0x35, 4, 2, 3)], {"r2": 0xfffffff5, "r3": 3},
     {"r1": 0xfffffffd, "r4": 0xfffffffe}),
    ("cmp_rr", [RR(0x39, 1, 2, 3), RR(0x3a, 4, 2, 3), RR(0x3b, 5, 2, 2), RR(0x3c, 6, 2, 3),
                RR(0x3d, 7, 2, 3), RR(0x3f, 8, 2, 3)], {"r2": M, "r3": 1},
     {"r1": 0, "r4": 0, "r5": 1, "r6": 1, "r7": 1, "r8": 1}),
    ("cmp_imm", [RI(0x19, 1, 2, -1), RI(0x1a, 4, 2, 0), RI(0x1b, 5, 2, -1), RI(0x1c, 6, 2, 0xffff),
                 RI(0x1d, 7, 2, 0xffff), RI(0x1f, 8, 2, 5)], {"r2": M},
     {"r1": 1, "r4": 0, "r5": 1, "r6": 1, "r7": 1, "r8": 1}),
    ("sext", [RR(0x2c, 1, 2, 0), RR(0x37, 3, 2, 0)], {"r2": 0x1234f680},
     {"r1": 0xffffff80, "r3": 0xfffff680}),
    ("mem", [sw(8, 2, -4), lw(1, 8, -4), RI(0x04, 3, 8, -4), RI(0x10, 4, 8, -4),
             RI(0x07, 5, 8, -4), RI(0x0b, 6, 8, -2), ST(0x0c, 8, 7, -3), ST(0x03, 8, 7, -2),
             lw(9, 8, -4)],
     {"r2": 0x8899aabb, "r8": 0x8010, "r7": 0x1234},
     {"be": {"r1": 0x8899aabb, "r3": 0xffffff88, "r4": 0x88, "r5": 0xffff8899, "r6": 0xaabb,
             "r9": 0x88341234},
      "le": {"r1": 0x8899aabb, "r3": 0xffffffbb, "r4": 0xbb, "r5": 0xffffaabb, "r6": 0x8899,
             "r9": 0x123434bb}}),
    ("gp_rel", [sw(GP, 2, 0x10), lw(1, GP, 0x10), RI(0x0d, 3, GP, 0x10)], {"gp": 0x8000, "r2": 77},
     {"r1": 77, "r3": 0x8010}),
    ("mv_not", [RR(0x2e, 1, 2, 0), RR(0x29, 3, 2, 0)], {"r2": 0x0f0f0f0f},
     {"r1": 0x0f0f0f0f, "r3": 0xf0f0f0f0}),
    ("csr", [(0x34 << 26) | (0 << 21) | (2 << 16), (0x24 << 26) | (0 << 21) | (1 << 11),
             (0x34 << 26) | (1 << 21) | (2 << 16), (0x24 << 26) | (1 << 21) | (3 << 11)],
     {"r2": 5}, {"IE": 5, "r1": 5, "IM": 5, "r3": 5}),
]

FLOW = [  # (name, words, init, expect, stop offset, base-relative expectations)
    ("be_taken", [BR(0x11, 1, 2, 8), addi(3, 3, 1), addi(3, 3, 10)], {"r1": 4, "r2": 4},
     {"r3": 10}, 0xc, {}),
    ("bne_not_taken", [BR(0x17, 1, 2, 8), addi(3, 3, 1), addi(3, 3, 10)], {"r1": 4, "r2": 4},
     {"r3": 11}, 0xc, {}),
    ("bg_signed_bgu_unsigned", [BR(0x12, 1, 2, 8), addi(3, 3, 1), BR(0x15, 1, 2, 8), addi(3, 3, 10),
                                addi(3, 3, 100)], {"r1": M, "r2": 1}, {"r3": 101}, 0x14, {}),
    ("loop", [addi(1, 1, 3), addi(2, 2, -1), BR(0x17, 2, 0, -8)], {"r2": 4},
     {"r1": 12, "r2": 0}, 0xc, {}),
    ("calli_ret", [calli(0xc), addi(1, 1, 10), bi(0xc), addi(1, 1, 100), RET, addi(1, 1, 5000)],
     {}, {"r1": 110}, 0x14, {"ra": 4}),
    ("call_reg", [lambda b: ori(2, 0, b + 0x14), (0x36 << 26) | (2 << 21), addi(1, 1, 1), bi(0x10),
                  NOP, addi(1, 1, 100), RET], {}, {"r1": 101}, 0x1c, {"ra": 8}),
    ("b_reg", [lambda b: ori(2, 0, b + 0xc), (0x30 << 26) | (2 << 21), addi(1, 1, 1), addi(1, 1, 10)],
     {}, {"r1": 10}, 0x10, {}),
    ("eret", [lambda b: ori(EA, 0, b + 0x8), (0x30 << 26) | (EA << 21), addi(1, 1, 1)],
     {"IE": 2}, {"r1": 1, "IE": 3}, 0xc, {}),
]

for e, fmt in (("be", ">I"), ("le", "<I")):
    img = bytearray(0x9000)
    lines = []
    tests = [(n, w, i, x, None, {}) for n, w, i, x in T] + list(FLOW)
    for k, (name, words, init, expect, stop, rel) in enumerate(tests):
        base = 0x100 * (k + 1)
        for i, wd in enumerate(words):
            wd = wd(base) if callable(wd) else wd
            struct.pack_into(fmt, img, base + 4 * i, wd)
        stop = base + (stop if stop is not None else 4 * len(words))
        exp = dict(expect[e] if e in expect else expect)
        exp.update({r: (v + base) & M for r, v in rel.items()})
        if k == brk:
            r0 = next(iter(exp))
            exp[r0] = (exp[r0] + 1) & M
        ini = ",".join(f"{r}={v & M:x}" for r, v in init.items()) or "-"
        ex = ",".join(f"{r}={v & M:x}" for r, v in exp.items())
        lines.append(f"{e}_{name} {base:x} {stop:x} {ini} {ex}")
    open(f"{out}/emu_{e}.bin", "wb").write(img)
    open(f"{out}/emu_{e}.txt", "w").write("\n".join(lines) + "\n")
    print(f"{e}: {len(lines)} tests")
