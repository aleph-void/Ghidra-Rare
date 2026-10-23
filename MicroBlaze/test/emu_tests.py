#!/usr/bin/env python3
"""P-code semantic tests run in Ghidra's emulator (EmuCheck.java).

  emu_tests.py <outdir>   -> emu{32,64}_{be,le}.bin and emu{32,64}.txt

Each test is a short instruction sequence placed at its own address. The .txt file has one
line per test:  <name> <start-hex> <stop-hex> <init: reg=val,...|-> <expect: reg=val,...>
Registers are r0..r31 and C (carry). Values are hex. Data scratch area: 0x3000.
"""
import struct
import sys

out = sys.argv[1]
NOP = 0x80000000  # or r0, r0, r0


def A(op, rd, ra, rb, low=0):
    return (op << 26) | (rd << 21) | (ra << 16) | (rb << 11) | low


def B(op, rd, ra, imm):
    return (op << 26) | (rd << 21) | (ra << 16) | (imm & 0xffff)


def IMM(v):
    return 0xb0000000 | (v & 0xffff)


def IMML(v):
    return 0xb2000000 | (v & 0xffffff)


addik = lambda d, a, i: B(0x0c, d, a, i)
ori = lambda d, a, i: B(0x28, d, a, i)

T32 = [
    ("addik", [addik(3, 0, 5), addik(3, 3, -1)], {}, {"r3": 4}),
    ("imm_addik", [IMM(0x1234), addik(3, 0, 0x5678)], {}, {"r3": 0x12345678}),
    ("imm_ori_neg", [IMM(0xffff), ori(4, 0, 0x8000)], {}, {"r4": 0xffff8000}),
    ("r0_is_zero", [addik(0, 0, 7), addik(3, 0, 0)], {}, {"r3": 0}),
    ("add_carry", [A(0x00, 3, 4, 5), A(0x02, 6, 0, 0)], {"r4": 0xffffffff, "r5": 1}, {"r3": 0, "r6": 1}),
    ("addk_keeps_carry", [A(0x00, 3, 4, 5), A(0x04, 7, 4, 5), A(0x02, 6, 0, 0)],
     {"r4": 0xffffffff, "r5": 1}, {"r3": 0, "r7": 0, "r6": 1}),
    ("rsub", [A(0x01, 3, 4, 5)], {"r4": 3, "r5": 10}, {"r3": 7, "C": 1}),
    ("rsub_borrow", [A(0x01, 3, 4, 5)], {"r4": 10, "r5": 3}, {"r3": 0xfffffff9, "C": 0}),
    ("rsubi", [B(0x09, 3, 4, 0)], {"r4": 1}, {"r3": 0xffffffff}),
    ("cmp_lt", [A(0x05, 3, 4, 5, 1)], {"r4": 5, "r5": 3}, {"r3": 0xfffffffe}),
    ("cmp_ge", [A(0x05, 3, 4, 5, 1)], {"r4": 3, "r5": 5}, {"r3": 2}),
    ("cmpu", [A(0x05, 3, 4, 5, 3)], {"r4": 0xffffffff, "r5": 1}, {"r3": 0x80000002}),
    ("mul", [A(0x10, 3, 4, 5, 0), A(0x10, 6, 4, 5, 1), A(0x10, 7, 4, 5, 3)],
     {"r4": 0x80000000, "r5": 2}, {"r3": 0, "r6": 0xffffffff, "r7": 1}),
    ("muli", [B(0x18, 3, 4, -3)], {"r4": 7}, {"r3": 0xffffffeb}),
    ("idiv", [A(0x12, 3, 4, 5, 0), A(0x12, 6, 4, 7, 2)], {"r4": 3, "r5": 0xfffffff6, "r7": 10},
     {"r3": 0xfffffffd, "r6": 3}),
    ("bs", [A(0x11, 3, 4, 5, 0), A(0x11, 6, 4, 5, 0x200), A(0x11, 7, 4, 5, 0x400)],
     {"r4": 0x80000010, "r5": 4}, {"r3": 0x08000001, "r6": 0xf8000001, "r7": 0x00000100}),
    ("bsi", [B(0x19, 3, 4, 4), B(0x19, 6, 4, 0x200 | 4), B(0x19, 7, 4, 0x400 | 4)],
     {"r4": 0x80000010}, {"r3": 0x08000001, "r6": 0xf8000001, "r7": 0x00000100}),
    ("bsefi", [B(0x19, 3, 4, 0x4000 | (8 << 6) | 4)], {"r4": 0x12345678}, {"r3": 0x67}),
    ("bsifi", [B(0x19, 3, 4, 0x8000 | (11 << 6) | 4)], {"r3": 0xffffffff, "r4": 0xab}, {"r3": 0xfffffabf}),
    ("logic", [A(0x20, 3, 4, 5), A(0x21, 6, 4, 5), A(0x22, 7, 4, 5), A(0x23, 8, 4, 5),
               B(0x2b, 9, 4, 0x00ff)], {"r4": 0xf0f0, "r5": 0xff00},
     {"r3": 0xfff0, "r6": 0xf000, "r7": 0x0ff0, "r8": 0x00f0, "r9": 0xf000}),
    ("pcmp", [A(0x20, 3, 4, 5, 0x400), A(0x22, 6, 4, 4, 0x400), A(0x23, 7, 4, 4, 0x400)],
     {"r4": 0x11223344, "r5": 0x99223355}, {"r3": 2, "r6": 1, "r7": 0}),
    ("sext", [B(0x24, 3, 4, 0x60), B(0x24, 6, 5, 0x61)], {"r4": 0x80, "r5": 0x12348000},
     {"r3": 0xffffff80, "r6": 0xffff8000}),
    ("shift1", [B(0x24, 3, 4, 0x41), B(0x24, 6, 0, 0x21), B(0x24, 7, 5, 0x01)],
     {"r4": 3, "r5": 0x80000000}, {"r3": 1, "r6": 0x80000000, "r7": 0xc0000000, "C": 0}),
    ("clz", [B(0x24, 3, 4, 0xe0)], {"r4": 0x00010000}, {"r3": 15}),
    ("swap", [A(0x24, 3, 4, 0, 0x1e0), A(0x24, 6, 4, 0, 0x1e2)], {"r4": 0x11223344},
     {"r3": 0x44332211, "r6": 0x33441122}),
    ("mem", [B(0x3e, 4, 0, 0x3000), B(0x3a, 3, 0, 0x3000), B(0x3c, 4, 0, 0x3010), B(0x38, 6, 0, 0x3010),
             B(0x39, 7, 0, 0x3000), A(0x36, 4, 8, 9), A(0x32, 10, 8, 9)],
     {"r4": 0x11223344, "r8": 0x3000, "r9": 0x20}, {"r3": 0x11223344, "r6": 0x44, "r10": 0x11223344}),
    ("call_ret", [B(0x2e, 15, 0x14, 12), addik(3, 3, 100), B(0x2e, 0, 0x00, 16),
                  addik(3, 3, 1), B(0x2d, 0x10, 15, 8), addik(3, 3, 10), NOP],
     {"r3": 0}, {"r3": 111}),
    ("beqi_taken", [B(0x2f, 0, 4, 12), addik(3, 0, 1), NOP, addik(5, 0, 9)], {"r4": 0, "r3": 0},
     {"r3": 0, "r5": 9}),
    ("bneid_not_taken", [B(0x2f, 0x11, 4, 12), addik(3, 0, 1), addik(6, 0, 2), addik(5, 0, 9)],
     {"r4": 0}, {"r3": 1, "r6": 2, "r5": 9}),
    ("blti_signed", [B(0x2f, 2, 4, 8), addik(3, 0, 1), addik(5, 0, 9)], {"r4": 0x80000000, "r3": 0},
     {"r3": 0, "r5": 9}),
    ("msr_carry", [B(0x25, 3, 0x10, 4), A(0x02, 5, 0, 0), B(0x25, 6, 0, 0x8001), B(0x25, 7, 0x11, 4),
                   A(0x02, 8, 0, 0)], {}, {"r5": 1, "r8": 0, "C": 0}),
    ("fpu", [A(0x16, 3, 4, 5, 0), A(0x16, 6, 7, 0, 0x280), A(0x16, 8, 4, 0, 0x300), A(0x16, 9, 5, 4, 0x210)],
     {"r4": 0x3f800000, "r5": 0x40000000, "r7": 3}, {"r3": 0x40400000, "r6": 0x40400000, "r8": 1, "r9": 1}),
]

M64 = 0xffffffffffffffff
T64 = T32 + [
    ("imml_addik_long", [IMML(0x12), addik(3, 0, 0x3456)], {}, {"r3": 0x123456}),
    ("imml2_64bit", [IMML(0x123456), IMML(0x789abc), addik(3, 0, 0xdef0 - 0x10000)], {},
     {"r3": 0x123456789abcdef0}),
    ("imml_neg40", [IMML(0xffffff), addik(3, 0, -2)], {}, {"r3": M64 - 1}),
    ("add32_zero_extends", [A(0x00, 3, 4, 5)], {"r4": 0xffffffff00000001, "r5": 1}, {"r3": 2}),
    ("addl", [A(0x00, 3, 4, 5, 0x100)], {"r4": 0xffffffff00000001, "r5": 1}, {"r3": 0xffffffff00000002}),
    ("addli2", [B(0x1a, 3, 4, -1)], {"r3": 0x100000000}, {"r3": 0xffffffff}),
    ("cmpl", [A(0x05, 3, 4, 5, 0x101)], {"r4": 5, "r5": 3}, {"r3": M64 - 1}),
    ("bslll", [A(0x11, 3, 4, 5, 0x500)], {"r4": 1, "r5": 40}, {"r3": 1 << 40}),
    ("sextl32", [B(0x24, 3, 4, 0x162)], {"r4": 0x80000000}, {"r3": 0xffffffff80000000}),
    ("ll_sl", [A(0x36, 4, 8, 9, 0x100), A(0x32, 3, 8, 9, 0x100), IMML(0), B(0x3b, 6, 8, 0x20)],
     {"r4": 0x1122334455667788, "r8": 0x3000, "r9": 0x20}, {"r3": 0x1122334455667788, "r6": 0x1122334455667788}),
    ("lwi_zero_extends", [B(0x3e, 4, 0, 0x3000), B(0x3a, 3, 0, 0x3000)], {"r4": 0xffffffff80000000, "r3": M64},
     {"r3": 0x80000000}),
    ("dfpu", [A(0x16, 3, 4, 5, 0x400), A(0x16, 6, 7, 0, 0x680)],
     {"r4": 0x3ff0000000000000, "r5": 0x4000000000000000, "r7": 3},
     {"r3": 0x4008000000000000, "r6": 0x4008000000000000}),
]

for bits, tests in ((32, T32), (64, T64)):
    mem = {}
    lines = []
    addr = 0x100
    for name, code, init, exp in tests:
        start = addr
        for w in code:
            mem[addr] = w
            addr += 4
        stop = addr
        mem[addr] = NOP
        addr += 0x20
        fmt = lambda d: ",".join("%s=%x" % (k, v) for k, v in d.items()) or "-"
        lines.append("%s %x %x %s %s" % (name, start, stop, fmt(init), fmt(exp)))
    size = 0x4000
    for e, f in (("be", ">I"), ("le", "<I")):
        buf = bytearray(size)
        for a, w in mem.items():
            buf[a:a + 4] = struct.pack(f, w)
        open("%s/emu%d_%s.bin" % (out, bits, e), "wb").write(bytes(buf))
    open("%s/emu%d.txt" % (out, bits), "w").write("\n".join(lines) + "\n")
