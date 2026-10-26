# Philips XA (51XA) for Ghidra

An independent SLEIGH module for the Philips/NXP XA ("eXtended Architecture") 16-bit
microcontroller core: XA-G3, XA-S3, XA-G49 and the other 51XA derivatives. It targets Ghidra
12.1.4. Instruction encodings and behavior were implemented from the Philips *XA User Guide*
(1998); MAME `unidasm -arch xa` is a black-box decode reference and the GPL `asxa` assembler is
run as a black box to build test programs. Nothing was taken from either tool's source.

## Languages and memory model

| Language | Mode | Return frame |
|---|---|---|
| `XA:LE:24:default` | Native (SCR.PZ = 0), 24-bit addresses | 4 bytes: PC[15:0], then a word holding PC[23:16] |
| `XA:LE:24:page0` | Page 0 (SCR.PZ = 1), 16-bit addresses | 2 bytes |

Choose the language from the program's `SCR` setting (its first instructions usually write it).
Both languages have a 16 MB `code` space, a 16 MB `data` space (256 segments of 64 KB) and a
1 KB `sfr` space at 400h–7FFh. R0–R7 (R7 is the stack pointer), their byte halves, the PSW flags
and the core SFRs PSWL, PSWH, PSW51, SSEL, SCR, DS, ES and CS are registers. Direct operands that
name a core SFR use those registers. Reading PSWL rebuilds it from the flag registers, and writing
PSWL reloads them, so an explicit PSW write takes precedence over the instruction's flag update
(user guide 4.2.3).

Indirect operands `[Rn]` use DS or ES as selected by SSEL bit n. MOVC and `JMP [[Rn+]]` use
PC[23:16] or CS, and R7 and the stack use segment 0. Direct operands (000h–3FFh) and data-memory
bits use DS. The disassembler context tracks a DS value set by `MOV.b DS,#imm` or `MOVS.b DS,#imm`
(default 0, the reset value), so direct addresses get references. After any other write to DS,
they are computed from DS at run time. Data addresses are formed with a `segment(base, offset)`
user op declared as the pspec's segment operation, as Ghidra does for x86 real mode and the
HCS12X. The decompiler therefore recognises stack variables and folds the segment. It assumes DS
= ES = SSEL = 0 at function entry. Emulating XA code needs a callback for `segment` (base << 16 |
offset); `test/XAEmuTest.java` registers one.

Arithmetic, logic, flags, shifts and rotates, multiply and divide, decimal adjust, bit
operations, branches, calls, traps, stacks and the user stack pointer have p-code. BKPT, RESET
and divide-by-zero traps are user ops. `XAVectorAnalyzer` types the 71-entry vector table at
0000h–011Bh (PSW word, then handler address). It makes functions of the handlers, names them
`reset`, `trap3`, `event8` and so on, and marks the reset handler as an entry point.

## Verification

- **Decode vs MAME:** four 65,536-instruction slot corpora: every first/second byte pair with three operand
  tails, plus random instructions. Each was decoded in three configurations: native with DS
  tracked, native with DS dynamic, and page 0. Every configuration has **0 unexplained
  differences** in 262,144 records. With DS tracked, 224,711 agree, including 68,090 where both
  sides reject the encoding. 9,433 are confirmed MAME bugs (listed below), and 780 are
  FCALL/FJMP to odd addresses, which the module rounds down because the CPU clears PC.0.
  27,220 are encodings MAME accepts but the user guide does not allow:
  - bits the encoding tables fix (20,902)
  - word register lists with H/L = 1 (4,073), and empty register lists (48)
  - 32-bit operands in odd register pairs (1,020)
  - multiply/divide results that would run past R7 (207)
  - the unimplemented word registers R8–R15 (970)
  The page 0 run adds 2,072 FCALL/FJMP targets that use only 16 bits.
- **Every entry:** 3,658/3,658 SLEIGH constructors are reached in both languages.
- **Emulator:** 80 hand-computed cases per language pass in both DS modes (160/160 per language).
  The cases cover flags, every addressing mode, segments through SSEL/ES, the DS-tracked direct
  store, PSW write precedence, bits, shifts, rotates, NORM, DA, multiply/divide, CJNE/DJNZ,
  branches, PUSH/POP lists, the user stack, CALL/FCALL/indirect call frames, `JMP [[R+]]` and
  TRAP/RETI frames. A deliberately broken expectation is reported as a failure.
- **Real code:** the `asxa` 1.12 examples, assembled locally, include:
  - two monitors (one with a disassembler and a debugger, built for both modes)
  - interrupt-driven clock and UART programs
  - a keyboard reader
  - the assembler's instruction test bench
  - Disassembly vs assembler source text, with listing-guided disassembly:
    - monxa: 1,271/1,272 statements identical
    - monxa (page 0): 1,259/1,260
    - small monitor: 263/271
    - clock: 152/152
    - UART: 84/84
    - keyboard: 110/110
    - test bench: 471/475
  - Remaining statements are skipped, not different: one unresolved symbol, two test-bench
    lines that hit an asxa encoding bug and two that asxa expanded into two instructions, and in
    the small monitor seven statements covered by an inline string decoded as code.
  - The same instructions agree with MAME except for the MAME bugs below.
  - No other instruction boundary conflicts with the listings.
  - All 146 functions of the listing-guided runs decompile, with 0 failures and 0 timeouts.
    Three small-monitor functions run into an inline string, as described under known gaps.
  - Auto-analysis alone reaches 152/152 statements of the clock program, 82/84 of the UART
    program and 110/110 of the keyboard program. The two monitors dispatch commands through
    code-memory tables (`MOVC R0,[R1+]`, `JMP [R0]`), so analysis stops at the dispatcher (98 of
    1,272 statements).

Confirmed MAME `xa` disassembler bugs (checked against the user guide encodings and the asxa
listing):
- prints RR/RRC with the wrong count field
- decodes ASR #imm and RLC with shifted fields
- takes the pointer of `MOV [Rd],direct` / `MOV direct,[Rs]` from bits 2–0
- takes the register of `XCH Rd,direct` from bits 3–0
- shows a word source for the 16/8 divides and a byte destination for `DIVU.w/DIV.w #imm`
- names a byte register in `CJNE.w Rd,#imm`
- reads the wrong byte as `#data8` after a 16-bit offset
- adds 20h twice to data-memory bit addresses

asxa 1.12 bug: it assembles `XCH Rd,[Rs]` with the pointer in the wrong bits (`XCH R4L,[R1]`
gives 50 88; the user guide and MAME give 50 81).

## Known gaps

- **Not modeled:**
  - Register banks: PSW.RS1/RS0 bank R0–R3 and the module has one bank.
  - User mode: R7 is treated as the system stack pointer, and USP is a separate register.
  - 80C51 compatibility mode (SCR.CM).
  - The forced word alignment of odd word addresses.
  - Interrupts, peripherals and timing.
- **Analysis limits:**
  - Calls followed by inline arguments, such as the monitors' `call prmsg` followed by a
    string, are decoded past the call. That is inherent to static analysis. Mark such routines
    or clear the bytes by hand.
  - In functions whose stack frame address escapes, the decompiler keeps the return-address
    stores of calls visible.
- **Encodings decoded as invalid:** the reserved encodings listed above. Real code from the
  assembler never uses them.
- **Unverified:**
  - No freely licensed third-party XA firmware or C-compiled XA code was found. SDCC's former
    xa51 port was not built.
  - Behavior has not been compared with hardware.

## Sources

- Philips Semiconductors, *XA User Guide*, 1998 (`XA_USER_GUIDE_1.pdf`, archived at
  `web.archive.org/web/2007/http://www.nxp.com/acrobat_download/various/XA_USER_GUIDE_1.pdf`,
  SHA-256 `1ef28f942faac19f50eb98472284507948b74a12529c28026df7a45cfe6fc68a`): encodings,
  operations, flags, memory model, stack and interrupt frames, vector table.
- Philips Semiconductors, *16-bit 80C51XA Microcontrollers Data Handbook IC25*, 1997
  (bitsavers): the XA-G3 SFR table (pspec symbols).
- MAME `unidasm -arch xa`: black-box decode reference.
- asxa 1.12 (Marcos A. Stemmer and Fabio D'Agostini, GPL, https://asxa.sourceforge.net): run as
  an assembler to build the test programs; its example programs are the real-code test inputs.
  `test/real/fetch-and-build.sh` downloads the pinned tarball (SHA-256 checked) and builds them
  locally. Nothing from it is committed.

## Build and test

```sh
export GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC
python3 XA/tools/gen_xa.py > XA/data/languages/xa_gen.sinc
"$GHIDRA_INSTALL_DIR/support/sleigh" -a XA/data/languages
(cd XA && gradle buildExtension)      # or XA/test/build-jar.sh for a linked development install
XA/test/run-tests.sh --real "$HOME/.cache/ghidra-rare-scratch/xa-real" "$HOME/.cache/ghidra-rare-scratch/xa-tests"
```

`run-tests.sh` runs the following:
- generator check
- SLEIGH compile
- emulator cases
- every-entry test
- decode differential (`test/run-decode.sh`)
- with `--real`, the asxa build and the real-code checks (`test/real-check.sh`), comparing
  against MAME (`test/real/real_compare.py`) and the assembler source
  (`test/real/src_compare.py`)

This module is MIT-licensed; see [LICENSE](LICENSE).
