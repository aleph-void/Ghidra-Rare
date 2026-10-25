#!/usr/bin/env python3
"""P-code semantic tests for the RL78 module, run in Ghidra's emulator by EmuCheck.java.

  emu_tests.py <outdir> [--break NAME]   -> emu.s, emu.bin (assembled with rl78-elf-as/ld), emu.txt

Each test is a short instruction sequence at its own label. emu.txt has one line per test:
  <name> <start-hex> <stop-hex> <init: key=val,...|-> <expect: key=val,...>
Keys are register names (A, AX, CY, SP, RB1_A, ...) or m1:/m2:/m3:<addr> for memory bytes,
words and 3-byte values. Values are hex. Before every test the bank-0 registers and PSW are 0
and SP is FE80 (stack in FFE7C..). Expected values were worked out by hand from the RL78
Software manual (R01US0015). --break NAME makes that test's first expectation wrong, to show
that the harness can fail.
"""
import os
import subprocess
import sys

TESTS = [
    # name, asm, init, expect
    ("mov_imm", ["mov a, #0x12", "mov x, a", "movw bc, #0xbeef"], {}, {"A": 0x12, "X": 0x12, "BC": 0xbeef}),
    ("add_carry", ["add a, #0x80"], {"A": 0x90}, {"A": 0x10, "CY": 1, "Z": 0, "AC": 0}),
    ("add_halfcarry", ["add a, #0x0f"], {"A": 0x01}, {"A": 0x10, "CY": 0, "AC": 1, "Z": 0}),
    ("addc_zero", ["addc a, #0"], {"A": 0xff, "PSW": 0x01}, {"A": 0x00, "CY": 1, "Z": 1, "AC": 1}),
    ("sub_borrow", ["sub a, #1"], {"A": 0x00}, {"A": 0xff, "CY": 1, "AC": 1, "Z": 0}),
    ("subc_borrow", ["subc a, #0x10"], {"A": 0x10, "PSW": 0x01}, {"A": 0xff, "CY": 1, "AC": 1}),
    ("cmp_eq", ["cmp a, #5"], {"A": 5}, {"A": 5, "Z": 1, "CY": 0}),
    ("cmp_lt", ["cmp a, #6"], {"A": 5}, {"Z": 0, "CY": 1}),
    ("logic", ["and a, #0x0f", "mov x, a", "or a, #0xa0", "mov c, a", "xor a, #0xaf", ], {"A": 0x5a},
     {"X": 0x0a, "C": 0xaa, "A": 0x05, "Z": 0}),
    ("xor_zero", ["xor a, a"], {"A": 0x77}, {"A": 0, "Z": 1}),
    ("addw_carry", ["addw ax, #0x8001"], {"AX": 0x8000}, {"AX": 0x0001, "CY": 1, "Z": 0}),
    ("subw_bc", ["subw ax, bc"], {"AX": 0x1000, "BC": 0x1001}, {"AX": 0xffff, "CY": 1}),
    ("cmpw_eq", ["cmpw ax, #0x1234"], {"AX": 0x1234}, {"Z": 1, "CY": 0}),
    ("inc_dec", ["inc a", "dec x"], {"A": 0xff, "X": 0x10, "PSW": 0x01},
     {"A": 0, "X": 0x0f, "Z": 0, "AC": 1, "CY": 1}),
    ("incw_decw", ["incw hl", "decw de"], {"HL": 0xffff, "DE": 0}, {"HL": 0, "DE": 0xffff}),
    ("mem_hl_disp", ["movw ax, #0x1234", "movw [hl+2], ax", "mov a, [hl+3]", "mov x, a", "mov a, [hl+2]"],
     {"HL": 0xfe00}, {"X": 0x12, "A": 0x34, "m2:ffe02": 0x1234}),
    ("mem_de", ["mov a, #0x5a", "mov [de], a", "incw de", "mov [de+1], a"], {"DE": 0xfe10},
     {"m1:ffe10": 0x5a, "m1:ffe12": 0x5a, "DE": 0xfe11}),
    ("mem_abs", ["mov !0xfe20, #0x77", "mov a, !0xfe20", "movw ax, #0xcafe", "movw !0xfe22, ax"], {},
     {"A": 0xca, "m1:ffe20": 0x77, "m2:ffe22": 0xcafe}),
    ("mem_es", ["mov es, #1", "mov a, #0x3c", "mov es:[hl], a", "mov es:!0x2000, a"], {"HL": 0x1000},
     {"m1:11000": 0x3c, "m1:12000": 0x3c, "ES": 1}),
    ("mem_index", ["mov a, 0xfe00[b]", "mov x, a", "mov a, [hl+c]"], {"B": 5, "C": 2, "HL": 0xfe10, "m1:ffe05": 0x91,
     "m1:ffe12": 0x92}, {"X": 0x91, "A": 0x92}),
    ("mem_wordbc", ["movw ax, 0xfe00[bc]"], {"BC": 0x40, "m2:ffe40": 0x4321}, {"AX": 0x4321}),
    ("saddr", ["mov 0xffe20, #0x55", "mov a, 0xffe20", "mov 0xfff10, #0x66", "mov x, 0xfff10"], {},
     {"A": 0x55, "X": 0x66, "m1:ffe20": 0x55, "m1:fff10": 0x66}),
    ("sfr_psw", ["set1 cy", "mov a, psw"], {}, {"A": 0x01, "CY": 1}),
    ("sp_rel", ["mov a, #0x42", "mov [sp+2], a", "movw ax, sp"], {"SP": 0xfe80}, {"m1:ffe82": 0x42, "AX": 0xfe80}),
    ("shifts", ["shl a, 3", "mov x, a", "shr a, 4", "mov c, a"], {"A": 0x31}, {"X": 0x88, "C": 0x08, "A": 0x08, "CY": 1}),
    ("sar", ["sar a, 2"], {"A": 0x86}, {"A": 0xe1, "CY": 1}),
    ("shlw_sarw", ["shlw bc, 4", "sarw ax, 1"], {"BC": 0x1234, "AX": 0x8001}, {"BC": 0x2340, "AX": 0xc000, "CY": 1}),
    ("rotates", ["rol a, 1", "mov x, a", "rorc a, 1", "mov c, a", "rolc a, 1"], {"A": 0x81},
     {"X": 0x03, "C": 0x81, "A": 0x03, "CY": 1}),
    ("rolwc", ["rolwc ax, 1"], {"AX": 0x8000, "PSW": 0x01}, {"AX": 0x0001, "CY": 1}),
    ("bits", ["set1 0xffe20.3", "clr1 a.0", "mov1 cy, a.7", "and1 cy, 0xffe20.3", "set1 [hl].1"],
     {"A": 0x81, "HL": 0xfe30}, {"m1:ffe20": 0x08, "A": 0x80, "CY": 1, "m1:ffe30": 0x02}),
    ("bit_or_xor", ["or1 cy, a.1", "xor1 cy, a.0", "mov1 a.6, cy"], {"A": 0x03},
     {"CY": 0, "A": 0x03}),
    ("bt_taken", ["bt a.2, $1f", "mov x, #1", "1: nop"], {"A": 0x04}, {"X": 0}),
    ("bf_not_taken", ["bf a.2, $1f", "mov x, #1", "1: nop"], {"A": 0x04}, {"X": 1}),
    ("btclr", ["btclr 0xffe20.7, $1f", "mov x, #1", "1: nop"], {"m1:ffe20": 0x81}, {"X": 0, "m1:ffe20": 0x01}),
    ("bz_bnz", ["cmp a, #3", "bz $1f", "mov x, #1", "1: bnz $2f", "mov c, #1", "2: nop"], {"A": 3}, {"X": 0, "C": 1}),
    ("bh", ["cmp a, #2", "bh $1f", "mov x, #1", "1: nop"], {"A": 3}, {"X": 0}),
    ("bnh_eq", ["cmp a, #3", "bnh $1f", "mov x, #1", "1: nop"], {"A": 3}, {"X": 0}),
    ("skz", ["cmp a, #3", "skz", "mov x, #1", "mov c, #2"], {"A": 3}, {"X": 0, "C": 2}),
    ("sknz_noskip", ["cmp a, #3", "sknz", "mov x, #1", "mov c, #2"], {"A": 3}, {"X": 1, "C": 2}),
    ("call_ret", ["call $!sub_seven", "mov x, a"], {"SP": 0xfe80}, {"A": 7, "X": 7, "SP": 0xfe80}),
    ("call_frame", ["call !!sub_sp"], {"SP": 0xfe80}, {"BC": 0xfe7c, "SP": 0xfe80}),
    ("callt", ["callt [0x80]"], {"SP": 0xfe80}, {"A": 7, "SP": 0xfe80}),
    ("call_ax", ["movw ax, #sub_seven", "call ax"], {"SP": 0xfe80, "CS": 0}, {"A": 7}),
    ("push_pop", ["push ax", "pop bc", "push psw", "pop de"], {"AX": 0x1234, "SP": 0xfe80, "PSW": 0x41},
     {"BC": 0x1234, "D": 0x41, "SP": 0xfe80}),
    ("xch", ["xch a, x", "xchw ax, de", "xch a, 0xffe20"], {"A": 1, "X": 2, "DE": 0x3344, "m1:ffe20": 9},
     {"X": 0x44, "A": 9, "DE": 0x0201, "m1:ffe20": 0x33}),
    ("mulu", ["mulu x"], {"A": 0x12, "X": 0x34}, {"AX": 0x03a8}),
    ("mulhu", ["mulhu"], {"AX": 0xffff, "BC": 0x0002}, {"AX": 0xfffe, "BC": 0x0001}),
    ("mulh", ["mulh"], {"AX": 0xffff, "BC": 0x0002}, {"AX": 0xfffe, "BC": 0xffff}),
    ("divhu", ["divhu"], {"AX": 1000, "DE": 7}, {"AX": 142, "DE": 6}),
    ("divwu", ["divwu"], {"AX": 0x0000, "BC": 0x0001, "DE": 0x0003, "HL": 0}, {"AX": 0x5555, "BC": 0, "DE": 1, "HL": 0}),
    ("machu", ["machu"], {"AX": 0x100, "BC": 0x100, "m2:ffff0": 0xffff, "m2:ffff2": 0}, {"m2:ffff0": 0xffff, "m2:ffff2": 0x1, "CY": 0}),
    ("sel_bank", ["sel rb1", "mov a, #5", "sel rb0", "mov a, #6"], {}, {"RB1_A": 5, "A": 6, "PSW": 0}),
    ("cmp0_oneb_clrw", ["cmp0 a", "oneb x", "clrw bc", "onew ax"], {"A": 0, "BC": 0x1234, "PSW": 0x11},
     {"Z": 1, "CY": 0, "AC": 0, "X": 0x01, "AX": 1, "BC": 0}),
    ("movs_cmps", ["movs [hl+1], x", "cmps x, [hl+1]"], {"A": 1, "X": 0, "HL": 0xfe40}, {"m1:ffe41": 0, "Z": 1, "CY": 1}),
    ("br_ax", ["movw ax, #1f", "br ax", "mov c, #1", "1: nop"], {"CS": 0}, {"C": 0}),
    ("addw_sp", ["subw sp, #4", "movw ax, sp", "addw sp, #4"], {"SP": 0xfe80}, {"AX": 0xfe7c, "SP": 0xfe80}),
]

SUBS = """
sub_seven:
	mov a, #7
	ret
sub_sp:
	movw ax, sp
	movw bc, ax
	ret
"""


def main():
    out = sys.argv[1]
    brk = sys.argv[sys.argv.index("--break") + 1] if "--break" in sys.argv else None
    s = ["\t.text", "\t.org 0x80", "\t.word sub_seven", "\t.org 0x200"]
    for i, (name, asm, init, exp) in enumerate(TESTS):
        s.append("t%d:" % i)
        for a in asm:
            if ":" in a.split(";")[0] and not a.strip().startswith(("mov es:", "mov a, es:")) and a.split(":")[0].strip().isdigit():
                lab, ins = a.split(":", 1)
                s.append("%s:" % lab.strip())
                s.append("\t" + ins.strip())
            else:
                s.append("\t" + a)
        s.append("t%d_end:" % i)
        s.append("\tbr $t%d_end" % i)
    s.append(SUBS)
    src = os.path.join(out, "emu.s")
    open(src, "w").write("\n".join(s) + "\n")
    obj, elf, binf = (os.path.join(out, "emu" + e) for e in (".o", ".elf", ".bin"))
    subprocess.check_call(["rl78-elf-as", "-mg14", src, "-o", obj])
    lds = os.path.join(out, "emu.ld")
    open(lds, "w").write("SECTIONS { .text 0 : { *(.text) } .plt 0x8000 : { *(.plt) } }\n")
    subprocess.check_call(["rl78-elf-ld", "-T", lds, "-e", "0", obj, "-o", elf])
    subprocess.check_call(["rl78-elf-objcopy", "-O", "binary", "-j", ".text", elf, binf])
    syms = {}
    for line in subprocess.check_output(["rl78-elf-nm", elf], text=True).splitlines():
        p = line.split()
        if len(p) == 3:
            syms[p[2]] = int(p[0], 16)
    with open(os.path.join(out, "emu.txt"), "w") as f:
        for i, (name, asm, init, exp) in enumerate(TESTS):
            exp = dict(exp)
            if name == brk:
                k = next(iter(exp))
                exp[k] = exp[k] ^ 1
            kv = lambda d: ",".join("%s=%x" % (k, v) for k, v in d.items()) or "-"
            f.write("%s %x %x %s %s\n" % (name, syms["t%d" % i], syms["t%d_end" % i], kv(init), kv(exp)))
    print("%d emulator tests -> %s" % (len(TESTS), out))


if __name__ == "__main__":
    main()
