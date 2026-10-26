# Renesas RX (RXv1, RXv2, RXv3) for Ghidra

An independent SLEIGH module for the Renesas RX 32-bit microcontroller core in its three
instruction set versions: RXv1 (RX100/RX200/RX600 series), RXv2 (RX64M, RX71M, RX230, ...) and
RXv3 (RX72M, RX66T, RX72N, ...), little endian. It targets Ghidra 12.1.4 and also compiles on
12.1.3 and 12.2. Encodings and behavior were implemented from the Renesas *RX Family RXv1/RXv2/RXv3
Instruction Set Architecture User's Manual: Software*. GNU objdump (`-m rx`, `rx:v2`, `rx:v3`)
and the GNU assembler were used as black boxes for checking; no binutils source or opcode table
was read.

## Languages

| Language | Instruction set |
|---|---|
| `RX:LE:32:RXv1` | RXv1: integer, string, single-precision FPU, one 64-bit accumulator (MULHI/MACHI/RACW/MVFACHI...) |
| `RX:LE:32:RXv2` | RXv1 + FSQRT, FTOU, UTOF, three-operand FADD/FSUB/FMUL, register STZ/STNZ, MOVLI/MOVCO, two 72-bit accumulators A0/A1 and the extended DSP instructions (EMACA, MSBHI, RDACL, MVFACGU, ...), EXTB |
| `RX:LE:32:RXv3` | RXv2 + BFMOV/BFMOVZ, three-operand XOR, SAVE/RSTR (register bank save) and the double-precision coprocessor (DR0-DR15, DPSW/DCMR/DECNT/DEPC, DADD ... UTOD) |

Each language has the `default` compiler spec (GCC/CC-RX convention, 32-bit doubles) and `d64`
(the same with 64-bit doubles, `gcc -m64bit-doubles`). The ELF opinion (EM_RX = 173) reads
`e_flags`: bit 8 selects RXv2, bit 9 RXv3, bit 0 the `d64` spec. GCC's start files carry no
version bit and GNU ld drops the bit when it links RXv2/RXv3 objects with them, so a file without
a version bit is loaded as **RXv3**, which decodes every RXv1/RXv2 instruction identically. Pick
RXv1 or RXv2 by hand to have the later instructions rejected. Raw images (BinaryLoader) need the
language chosen by hand; the pspec labels the fixed/exception vector table at FFFFFF80h-FFFFFFFFh
and marks the reset vector entry.

Registers: R0-R15 (R0 is the stack pointer), PSW kept as the flags C, Z, S, O, I, U, PM and IPL
(MVFC/PUSHC rebuild it, MVTC/POPC/RTE/RTFI unpack it), PC, USP, ISP, INTB, BPC, BPSW, FINTV,
FPSW, EXTB, the accumulators A0/A1 (bits 63-0) with guard bytes A0G/A1G (bits 71-64), the MOVLI
link flag LI, and on RXv3 DR0-DR15 with their halves DRH/DRL and the four DFPU control registers.

All instructions have p-code except INT/BRK (`software_interrupt`), WAIT, and SAVE/RSTR
(`register_bank_save`/`_restore`), which are user ops. That includes:
- arithmetic and flags, including ADC/SBB, the shifts' C/O rules and NEG's C flag
- multiply, divide and EMUL/EMULU register pairs
- every addressing mode with scaled displacements, memex sizes, `[Ri,Rb]` and `[Rn+]`/`[-Rn]`
- bit operations, BMCnd, SCCnd, STZ/STNZ
- branches, BSR/JSR/RTS/RTSD frames, PUSHM/POPM, PUSHC/POPC, RTE/RTFI
- string instructions and RMPA as loops
- the accumulator operations with 72-bit arithmetic (rounding and saturation in RACW/RACL/RDACW/RDACL, the shift of MVFACxx)
- single-precision FPU operations and flags; ROUND/DROUND follow FPSW.RM/DPSW.DRM, with ties to even
- MOVLI/MOVCO
- BFMOV/BFMOVZ
- the double-precision operations, moves and DPUSHM/DPOPM

`lib/RX.jar` adds an ELF relocation handler for relocatable objects (the DIR, ABS and SYM/OP
expression-stack relocations, read off GNU readelf's names) and an ELF extension that loads the
toolchains' standard sections (`B`, `D`, `C`, `P`, ...). GCC emits `B` without SHF_ALLOC.
`rx.dwarf` maps the DWARF registers (0-15 = R0-R15, CFA = R0 + 4 at entry).

## Verification

- **Decode vs GNU objdump** (binutils 2.45): sixteen slot corpora of 65,536 instructions each:
  - every first/second byte pair with three tails
  - every second/third byte after 06h, 75h, 76h, F9h, FCh and FDh (with random and with fixed tails)
  - every third/fourth byte after 7690h, FD75h, FD76h and FD77h
  - 65,536 random instructions

  Each corpus was decoded in each language and compared with `objdump -m rx`, `rx:v2` and
  `rx:v3`: 1,048,576 records per language, **0 unexplained differences**:

  | | agree | both invalid | explained |
  |---|---|---|---|
  | RXv3 | 485,991 | 516,298 | 46,287 |
  | RXv2 | 462,661 | 516,346 | 69,569 |
  | RXv1 | 448,779 | 516,346 | 83,451 |

  The explained differences are of three kinds:
  - **Reserved encodings (about 45,800 per language).** objdump decodes encodings the manual does
    not define. Ghidra rejects them. They are:
    - MOV.B/.W `#imm` with an immediate size the manual does not list
    - the 06h memex prefix with a register operand
    - BMCnd/BSET/BCLR/BTST/PUSH with ld = 11b
    - PUSHM/POPM/RTSD register ranges outside R1-R15 or decreasing
    - SCCnd.B/.W with a register
    - reserved control register numbers, flag numbers, condition codes and DCMPcm conditions
    - EMUL/EMULU to R15
    - the MVFACxx shift field 01b
    - opcode 01h, which objdump calls `dbt` and the manual does not have

    Each one is bucketed by rule in `test/explain.py`.
  - **Version (RXv1 and RXv2 only).** The instruction exists only in a later ISA version: 23,804
    RXv3 instructions, plus 14,020 RXv2 instructions in RXv1.
  - **objdump bugs.** Two, confirmed against the manual (listed below).
- **Every entry:** 1,246/1,246 (RXv1), 1,346/1,346 (RXv2) and 1,681/1,681 (RXv3) SLEIGH
  constructors are reached.
- **Emulator:** 59/59 (RXv1), 68/68 (RXv2) and 72/72 (RXv3) hand-computed cases pass. They cover:
  - flags of ADD/SUB/ADC/SBB/NEG/ABS/shifts/rotates
  - MUL/DIV/DIVU/EMUL/EMULU, including divide by zero and overflow
  - all addressing modes, memex sizes, memory-to-memory MOV, post-increment/pre-decrement
  - bit operations, BMCnd, SCCnd, STZ/STNZ
  - branches, BRA.L, BSR/JSR/RTS, PUSHM/POPM, RTSD frames, PUSHC/POPC PSW, MVTIPL
  - SMOVF/SSTR/SUNTIL/SCMPU, RMPA, SAT
  - MULHI/MACHI/MVFACxx, RACW/RACL/RDACW saturation
  - FPU arithmetic, comparison with NaN, ROUND ties-to-even and RM modes, ITOF/UTOF/FTOU, FSQRT
  - MOVLI/MOVCO, BFMOV/BFMOVZ, XOR3
  - DMUL/DTOI/DCMP/MVFDR, DPUSHM/DPOPM

  A deliberately broken expectation is reported as a failure.
- **Real code**: programs built locally from public source with GNU rx-elf GCC 14.3.0 and newlib
  4.5 (`test/real/fetch-and-build.sh`):
  - the newlib test program `tour.c` in four configurations: rx610 -O2, rx600 -O1, rx200 -Os
    without FPU, and rx610 -O2 with 64-bit doubles
  - zlib 1.3.1 `example` and `minigzip` (pinned tarball, SHA-256 checked)
  - two programs calling hand-written RXv2 and RXv3 routines (accumulator FIR filter, MOVLI/MOVCO
    atomic add, EMACA, FSQRT/FTOU, double-precision polynomial, BFMOV, SAVE/RSTR), assembled with
    gas `-mcpu=rxv2`/`rxv3-dfpu`

  Results:
  - Every instruction the analysis found is identical to objdump at the same address:
    23,430 + 23,446 + 23,969 + 27,732 (tour), 28,091 + 28,631 (zlib), 10,162 + 10,205 (asm
    programs). No other differences.
  - 1,760/1,760 functions decompile, with 0 failures and 0 timeouts.
  - 0 bad-instruction and 0 relocation bookmarks.
  - The ELF opinion picks `d64` for the 64-bit-double build.
  - Relocatable objects (zlib `deflate.o`, `inflate.o`, `trees.o` and the two assembled objects)
    import with 0 relocation errors; all 65 of their functions decompile and calls resolve to the
    external symbols. The objects with V2/V3 flags select RXv2/RXv3.

objdump bugs confirmed against the manual:
- BFMOV/BFMOVZ: objdump derives slsb wrongly whenever slsb > dlsb, and prints the width without
  the modulo-32 rule (`#-13`). gas encodes `bfmov #20, #4, #3, r1, r2` as FC 5E 12 90 1C, which
  matches the manual's formula, and objdump disassembles that as `#12, #4, #3`.
- MVTDC: objdump (and gas) take the general register from the fourth byte and the DFPU control
  register from the third. The manual has `FD 77 | 1000 rs | rd 0100`, the same layout as
  MVFDC/DMOV, so the module follows the manual. gas assembles `mvtdc r3, decnt` as FD 77 82 34; the
  module shows that as `mvtdc R2, DEPC`.

## Known gaps

- **Not modelled:**
  - USP/ISP switching by PSW.U (R0 is always the active stack pointer).
  - User-mode write protection of PSW bits and control registers.
  - FPSW/DPSW exception cause and sticky flags (results and the C/Z/S/O flags are modelled; ROUND
    reads RM).
  - The ACC0 side effects of MUL/EMUL/FMUL/RMPA, which the manual leaves undefined.
  - The register banks of SAVE/RSTR, and exception entry for INT/BRK (user ops).
  - Interrupts and peripherals.
- **Reserved encodings** are decoded as invalid (see above), including the 06h memex prefix with a
  register operand, which some cores may execute.
- **Big-endian data mode** (`elf32-rx-be`, code stored in byte-swapped words) is not supported.
- **RXv1 by default:** unmarked ELF files load as RXv3. Choose RXv1/RXv2 by hand to reject the
  later instructions (see Languages).
- **Ghidra DWARF line tables:** gas emits line tables with line_range 242, and Ghidra's DWARF reader
  gets line steps above 127 wrong. Each GCC-built image with `-g` gets about 100-130 "Error/DWARF ...
  source map entry" bookmarks with negative line numbers. This is in Ghidra's DWARF reader, not the
  module, and it does not affect disassembly or decompilation.
- **Relocatable objects:** the section-relative stack operators (OPsctsize, OPscttop, OPromtop,
  OPramtop) and the linker-relaxation hints (RH_*) are reported, not applied. GCC/gas output for
  normal C does not use them.
- **Unverified:**
  - No freely licensed third-party RX firmware was found.
  - GCC 14 compiles only for RXv1 CPUs, so RXv2/RXv3 code was tested with assembled routines and
    the slot corpora.
  - Behavior has not been compared with hardware.

## Sources

- Renesas Electronics, *RX Family RXv3 Instruction Set Architecture User's Manual: Software*,
  R01US0316EJ0100 Rev.1.00 (Nov 2018), `renesas.com/en/document/mah/rx-family-rxv3-instruction-set-architecture-users-manual-software-rev100`,
  SHA-256 `829815515a57d077bdfa418e0e167b512f2a04b3db3613329a4d8980399cf74c`. Sections 3 and 4
  (operations, flags, instruction codes), 1.2 (registers) and 1.10 (DFPU).
- Renesas Electronics, *RX Family RXv2 Instruction Set Architecture User's Manual: Software*,
  R01US0071EJ0100 Rev.1.00 (Nov 2013), SHA-256
  `c12fc8d16adf1530f2cad3f75974d2a29062580a984a71fd9461417b66bba18a`.
- Renesas Electronics, *RX Family RXv1 Instruction Set Architecture User's Manual: Software*,
  R01US0032EJ0130 Rev.1.30 (Dec 2019), SHA-256
  `e659dd509141da6bb1cfabf26c9f9ab5996d02060acaad2b5702963116834415`. RXv1 accumulator and DSP
  encodings.
- GNU binutils 2.45 `objdump`, `as`, `ld` and `readelf` (GPL), run as black boxes: decode
  reference, assembler for the test code, ELF `e_flags` bits, relocation type numbers and names,
  and the PC-relative relocation base. GNU GCC 14.3.0 and newlib 4.5.0.20241231 build the test
  programs (`test/real/build-toolchain.sh`, pinned tarballs). Nothing from these tools' source is
  in the module.
- zlib 1.3.1 (zlib license), `github.com/madler/zlib/releases/download/v1.3.1/zlib-1.3.1.tar.gz`,
  SHA-256 `9a93b2b7dfdac77ceba5a558a580e74667dd6fede4585b91eefb60f03b72df23`: real-code test
  input, downloaded and built locally, not committed.

## Build and test

```sh
export GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC
python3 RX/tools/gen_rx.py tokens > RX/data/languages/rx_tokens.sinc
python3 RX/tools/gen_rx.py > RX/data/languages/rx_gen.sinc
for v in 1 2 3; do "$GHIDRA_INSTALL_DIR/support/sleigh" RX/data/languages/rx_v$v.slaspec; done
(cd RX && gradle buildExtension)      # or RX/test/build-jar.sh (JAVA_HOME with javac) for a linked install
RX/test/real/build-toolchain.sh <workdir> <prefix>     # once; or point RX_TC at an rx-elf toolchain
RX_TC=<prefix> RX/test/run-tests.sh --real "$HOME/.cache/ghidra-rare-scratch/rx-real" "$HOME/.cache/ghidra-rare-scratch/rx-tests"
```

`run-tests.sh` runs these steps:
- generator check
- SLEIGH compile of the three languages
- emulator cases (`test/emu-test.sh`, cases in `test/emu/cases.py`)
- every-entry test
- decode differential (`test/run-decode.sh`, `compare.py`, `explain.py`)
- with `--real`, the real-code build and checks (`test/real-check.sh`, `real_compare.py`)

This module is MIT-licensed; see [LICENSE](LICENSE).
