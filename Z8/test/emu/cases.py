#!/usr/bin/env python3
"""Z8 p-code emulation cases. Each case is assembled at 1000h with the libasm assembler
(Apache-2.0, https://github.com/tgtakaoka/libasm, used as a black box) and written to
cases.txt, which test/Z8EmuTest.java runs with Ghidra's emulator. Expected values were worked
out by hand from Zilog UM0016 (instruction descriptions, flag tables, the manual's examples).

    LIBASM_ASM=/path/to/libasm/cli/asm test/emu/cases.py > test/emu/cases.txt

Case flags:
  static  only run with the register pointer known to the disassembler (context rpv=1);
          the RP-unknown path computes working-register addresses at run time and cannot route
          them to FLAGS/SPH/SPL or the expanded register file (see README, known gaps)
  int     only for the internal-stack language Z8:BE:16:default
  ext     only for the external-stack language Z8:BE:16:extstack

Locations: a register name (C Z S V D H SPL SPH SP PC), or space:hexaddr (rf, erf, data, code).
"rf:fd" (RP) sets the register pointer; it defaults to 00h. Every case starts with all
registers and memory zero except what it sets. The flags not listed are not checked.
"""
import os
import re
import subprocess
import sys
import tempfile

CASES = [
    # name, flags, setup, asm, expect
    ("add_rr", "", {"rf:fd": 0x10, "rf:15": 0x16, "rf:1b": 0x20},
     "add r5,r11",
     {"rf:15": 0x36, "C": 0, "Z": 0, "S": 0, "V": 0, "D": 0, "H": 0}),
    # UM0016 ADD example 3: 2Eh + 1Bh = 49h, H set
    ("add_RR_halfcarry", "", {"rf:34": 0x2E, "rf:12": 0x1B},
     "add 0x34,0x12",
     {"rf:34": 0x49, "H": 1, "C": 0, "Z": 0, "S": 0, "V": 0, "D": 0}),
    ("add_imm_overflow", "", {"rf:fd": 0x20, "rf:20": 0x7F},
     "add r0,#1",
     {"rf:20": 0x80, "V": 1, "S": 1, "C": 0, "Z": 0, "H": 1}),
    ("adc_carry_in", "", {"rf:fd": 0x20},
     "scf\n adc r1,#0xff",
     {"rf:21": 0x00, "C": 1, "Z": 1, "H": 1, "V": 0, "S": 0, "D": 0}),
    ("adc_IR", "", {"rf:fd": 0x20, "rf:22": 0x40, "rf:23": 0x50, "rf:50": 0x0F},
     "rcf\n adc r2,@r3",
     {"rf:22": 0x4F, "C": 0, "H": 0, "Z": 0}),
    ("sub_borrow", "", {"rf:fd": 0x20, "rf:22": 0x10},
     "sub r2,#0x20",
     {"rf:22": 0xF0, "C": 1, "S": 1, "Z": 0, "V": 0, "H": 0, "D": 1}),
    ("sbc_halfborrow", "", {"rf:fd": 0x20, "rf:23": 0x50},
     "scf\n sbc r3,#0x10",
     {"rf:23": 0x3F, "C": 0, "H": 1, "V": 0, "S": 0, "Z": 0, "D": 1}),
    ("sub_overflow", "", {"rf:44": 0x80, "rf:45": 0x01},
     "sub 0x44,0x45",
     {"rf:44": 0x7F, "V": 1, "C": 0, "S": 0, "Z": 0}),
    ("cp_equal", "", {"rf:fd": 0x20, "rf:24": 0x42},
     "cp r4,#0x42",
     {"rf:24": 0x42, "Z": 1, "C": 0, "S": 0, "V": 0}),
    ("cp_signed", "", {"rf:fd": 0x20, "rf:24": 0x80},
     "cp r4,#1",
     {"rf:24": 0x80, "Z": 0, "C": 0, "S": 0, "V": 1}),
    ("logic_and_or_xor", "", {"rf:fd": 0x20, "rf:25": 0xF0},
     "and r5,#0x3c\n or r5,#1\n xor r5,#0xff",
     {"rf:25": 0xCE, "S": 1, "Z": 0, "V": 0}),
    ("tm_tcm", "", {"rf:fd": 0x20, "rf:26": 0x81},
     "tm r6,#2",
     {"rf:26": 0x81, "Z": 1}),
    ("tcm_ones", "", {"rf:fd": 0x20, "rf:26": 0x81},
     "tcm r6,#0x81",
     {"rf:26": 0x81, "Z": 1, "V": 0}),
    ("inc_dec_overflow", "", {"rf:fd": 0x20, "rf:27": 0x7F},
     "inc r7\n dec r7",
     {"rf:27": 0x7F, "V": 1, "S": 0, "Z": 0}),
    ("inc_R_long", "", {"rf:47": 0xFF},
     "inc 0x47",
     {"rf:47": 0x00, "Z": 1, "V": 0}),
    ("incw_rr", "", {"rf:fd": 0x20, "rf:28": 0x00, "rf:29": 0xFF},
     "incw rr8",
     {"rf:28": 0x01, "rf:29": 0x00, "Z": 0, "S": 0, "V": 0}),
    ("decw_wrap", "", {"rf:fd": 0x20},
     "decw rr8",
     {"rf:28": 0xFF, "rf:29": 0xFF, "S": 1, "Z": 0, "V": 0}),
    ("decw_overflow_IR", "", {"rf:40": 0x80, "rf:41": 0x00, "rf:30": 0x40},
     "decw @0x30",
     {"rf:40": 0x7F, "rf:41": 0xFF, "V": 1, "S": 0}),
    ("rl", "", {"rf:fd": 0x20, "rf:20": 0x81},
     "rl r0",
     {"rf:20": 0x03, "C": 1, "S": 0, "V": 1, "Z": 0}),
    ("rlc", "", {"rf:fd": 0x20, "rf:20": 0x81},
     "rcf\n rlc r0",
     {"rf:20": 0x02, "C": 1, "V": 1}),
    ("rr", "", {"rf:fd": 0x20, "rf:20": 0x01},
     "rr r0",
     {"rf:20": 0x80, "C": 1, "S": 1, "V": 1}),
    ("rrc", "", {"rf:fd": 0x20, "rf:20": 0x02},
     "scf\n rrc r0",
     {"rf:20": 0x81, "C": 0, "S": 1, "V": 1}),
    ("sra", "", {"rf:fd": 0x20, "rf:20": 0x81},
     "sra r0",
     {"rf:20": 0xC0, "C": 1, "S": 1, "V": 0}),
    ("swap_com_clr", "", {"rf:fd": 0x20, "rf:20": 0x1F, "rf:21": 0x0F, "rf:40": 0x55},
     "swap r0\n com r1\n clr 0x40",
     {"rf:20": 0xF1, "rf:21": 0xF0, "rf:40": 0x00, "S": 1, "V": 0}),
    # UM0016 DA example: 15h + 27h = 3Ch, DA -> 42h
    ("da_add", "", {"rf:fd": 0x20},
     "ld r0,#0x15\n add r0,#0x27\n da r0",
     {"rf:20": 0x42, "C": 0, "Z": 0, "S": 0}),
    ("da_sub", "", {"rf:fd": 0x20},
     "ld r0,#0x42\n sub r0,#0x15\n da r0",
     {"rf:20": 0x27, "C": 0}),
    ("da_add_carry", "", {"rf:fd": 0x20},
     "ld r0,#0x99\n add r0,#1\n da r0",
     {"rf:20": 0x00, "C": 1, "Z": 1}),
    # UM0016 LD example 11: R0=08h, (2Ch)=4Fh, LD R10,24h(R0) -> R10=4Fh
    ("ld_indexed_load", "", {"rf:fd": 0x10, "rf:10": 0x08, "rf:2c": 0x4F},
     "ld r10,0x24(r0)",
     {"rf:1a": 0x4F}),
    ("ld_indexed_store", "", {"rf:fd": 0x10, "rf:10": 0x0B, "rf:1a": 0x5A},
     "ld 0x30(r0),r10",
     {"rf:3b": 0x5A}),
    ("ld_indirect_r", "", {"rf:fd": 0x10, "rf:11": 0x50, "rf:50": 0x77, "rf:13": 0x11},
     "ld r2,@r1\n ld @r1,r3",
     {"rf:12": 0x77, "rf:50": 0x11}),
    ("ld_R_forms", "", {"rf:44": 0x09, "rf:60": 0x70, "rf:70": 0x05},
     "ld 0x45,0x44\n ld 0x61,@0x60\n ld @0x60,0x44\n ld @0x62,#0x33\n ld 0x63,#0x34",
     {"rf:45": 0x09, "rf:61": 0x05, "rf:70": 0x09, "rf:00": 0x33, "rf:63": 0x34}),
    ("push_pop", "int", {"rf:fd": 0x10, "rf:14": 0xAB, "SPL": 0x80},
     "push r4\n pop 0x60",
     {"rf:60": 0xAB, "rf:7f": 0xAB, "SPL": 0x80}),
    ("call_ret", "int", {"rf:fd": 0x20, "SPL": 0x80},
     "call sub\n ld r0,#1\n jp done\nsub: ld r1,#2\n ret\ndone:",
     {"rf:20": 1, "rf:21": 2, "SPL": 0x80, "rf:7e": 0x10, "rf:7f": 0x03}),
    ("call_indirect", "int", {"rf:fd": 0x20, "SPL": 0x80},
     "ld r4,#(sub>>8)\n ld r5,#(sub&0xff)\n call @rr4\n jp done\nsub: ld r1,#2\n ret\ndone:",
     {"rf:21": 2, "SPL": 0x80, "rf:7e": 0x10, "rf:7f": 0x06}),
    ("djnz_loop", "", {"rf:fd": 0x20},
     "ld r0,#0\n ld r1,#5\nloop: add r0,#3\n djnz r1,loop",
     {"rf:20": 15, "rf:21": 0}),
    ("jr_taken", "", {"rf:fd": 0x20, "rf:21": 0x99},
     "ld r0,#0\n cp r0,#0\n jr z,skip\n ld r1,#1\nskip: ld r2,#2",
     {"rf:21": 0x99, "rf:22": 2}),
    ("jp_not_taken", "", {"rf:fd": 0x20},
     "ld r0,#5\n cp r0,#3\n jp c,skip\n ld r1,#1\nskip: ld r2,#2",
     {"rf:21": 1, "rf:22": 2}),
    ("jr_signed_lt", "", {"rf:fd": 0x20, "rf:21": 0x99},
     "ld r0,#0x80\n cp r0,#1\n jr lt,skip\n ld r1,#1\nskip:",
     {"rf:21": 0x99}),
    ("jr_ugt", "", {"rf:fd": 0x20, "rf:21": 0x99},
     "ld r0,#0x80\n cp r0,#1\n jr ugt,skip\n ld r1,#1\nskip:",
     {"rf:21": 0x99}),
    ("jp_indirect", "", {"rf:fd": 0x10, "rf:11": 0x99},
     "ld r4,#(t>>8)\n ld r5,#(t&0xff)\n jp @rr4\n ld r1,#1\nt: ld r2,#2",
     {"rf:11": 0x99, "rf:12": 2}),
    ("ldc", "", {"rf:fd": 0x20},
     "ld r6,#(tbl>>8)\n ld r7,#(tbl&0xff)\n ldc r8,@rr6\n ldci @r10,@rr6\n jp done\n"
     "tbl: db 0x5a,0xa5\ndone:",
     {"rf:28": 0x5A, "rf:00": 0x5A, "rf:2a": 0x01, "rf:26": 0x10, "rf:27": 0x0C}),
    ("ldei", "", {"rf:fd": 0x20, "rf:24": 0x50, "rf:26": 0x20, "rf:27": 0x00,
                  "data:2000": 0x11, "data:2001": 0x22},
     "ldei @r4,@rr6\n ldei @r4,@rr6",
     {"rf:50": 0x11, "rf:51": 0x22, "rf:24": 0x52, "rf:26": 0x20, "rf:27": 0x02}),
    ("lde_store", "", {"rf:fd": 0x20, "rf:26": 0x30, "rf:27": 0x00, "rf:28": 0x99},
     "lde @rr6,r8\n lde r9,@rr6",
     {"data:3000": 0x99, "rf:29": 0x99}),
    ("srp_context", "", {"rf:fd": 0x10},
     "srp #0x30\n ld r0,#0x42",
     {"rf:30": 0x42, "rf:10": 0x00, "rf:fd": 0x30}),
    ("ld_rp_context", "", {},
     "ld 0xfd,#0x40\n ld r1,#0x33",
     {"rf:41": 0x33, "rf:fd": 0x40}),
    # LD RP,R (not SRP / LD RP,#imm): the known-RP context must be dropped after it
    ("rp_write_invalidates", "", {"rf:fd": 0x10, "rf:50": 0x20},
     "ld 0xfd,0x50\n ld r1,#0x77",
     {"rf:21": 0x77, "rf:11": 0x00}),
    ("flags_register", "", {"rf:fd": 0x20},
     "ld 0xfc,#0x83\n ld r1,#0\n adc r1,#0\n rcf\n ld r0,0xfc",
     {"rf:21": 0x01, "rf:20": 0x03, "C": 0}),
    ("flags_via_wreg", "static", {"rf:fd": 0xF0},
     "ld r12,#0x40",
     {"Z": 1, "C": 0}),
    ("erf_bank", "static", {"rf:fd": 0x0F},
     "ld r0,#0x12\n ld 0x0b,#0x34",
     {"erf:f0": 0x12, "erf:fb": 0x34, "rf:00": 0x00}),
    ("pop_flags", "int", {"SPL": 0x7F, "rf:7f": 0x80},
     "pop 0xfc",
     {"C": 1, "Z": 0, "SPL": 0x80}),
    ("iret", "int", {"SPL": 0x7D, "rf:7d": 0x40, "rf:7e": 0x10, "rf:7f": 0x03, "rf:21": 0x99,
                     "rf:fd": 0x20},
     "iret\n ld r1,#1\n ld r2,#2",
     {"rf:21": 0x99, "rf:22": 2, "Z": 1, "C": 0, "rf:fb": 0x80, "SPL": 0x80}),
    ("ei_di", "", {},
     "ld 0xfb,#5\n ei\n ld 0x40,0xfb\n di",
     {"rf:40": 0x85, "rf:fb": 0x05}),
    ("ext_call_ret", "ext", {"rf:fd": 0x20, "SP": 0x8000},
     "call sub\n ld r0,#1\n jp done\nsub: ld r1,#2\n ret\ndone:",
     {"rf:20": 1, "rf:21": 2, "SP": 0x8000, "data:7ffe": 0x10, "data:7fff": 0x03}),
    ("ext_push_pop", "ext", {"rf:fd": 0x10, "rf:14": 0xAB, "SP": 0x8000},
     "push r4\n pop 0x60",
     {"rf:60": 0xAB, "data:7fff": 0xAB, "SP": 0x8000}),
]


def assemble(asm_bin, text):
    src = "\tcpu z86c\n\torg 0x1000\n" + "\n".join(
        l if re.match(r"^\w+:", l.strip()) else "\t" + l.strip()
        for l in text.split("\n")) + "\n"
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "c.asm")
        open(p, "w").write(src)
        r = subprocess.run([asm_bin, "-C", "z86c", "-o", os.path.join(d, "c.hex"), p],
                           capture_output=True, text=True)
        if r.returncode or "error" in r.stderr + r.stdout:
            sys.exit(f"assembly failed:\n{src}\n{r.stdout}{r.stderr}")
        code = bytearray()
        for line in open(os.path.join(d, "c.hex")):
            n = int(line[1:3], 16)
            if line[7:9] == "00":
                a = int(line[3:7], 16) - 0x1000
                rec = bytes.fromhex(line[9:9 + 2 * n])
                code[a:a + n] = rec
    return code.hex()


def main():
    asm_bin = os.environ.get("LIBASM_ASM", "asm")
    print("# generated by test/emu/cases.py; do not edit")
    for name, flags, setup, text, expect in CASES:
        print(f"case {name} {flags}".rstrip())
        print(f"code {assemble(asm_bin, text)}")
        for k, v in setup.items():
            print(f"set {k} {v:#x}")
        for k, v in expect.items():
            print(f"expect {k} {v:#x}")
        print("end")


if __name__ == "__main__":
    main()
