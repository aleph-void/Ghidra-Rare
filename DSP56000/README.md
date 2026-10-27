# Motorola DSP56000 / DSP56156 for Ghidra

An independent SLEIGH module for Motorola's DSP56000 family: the 24-bit DSP56000/DSP56001
core (with the DSP56002 additions) and the 16-bit DSP56156 (DSP561xx, DSP56100 family core).
It targets Ghidra 12.1.4. Instruction encodings and behavior were implemented from the
Motorola family manuals; MAME `unidasm -arch dsp56000` and `-arch dsp56156` are black-box
decode references, and Motorola's own DSP56000 and DSP56100 assemblers (freely distributed
DOS tools, run under dosbox) and the asl assembler are run as black boxes to build test
programs. Nothing was taken from any tool's source. The DSP56300 family is not covered here
(see the community module roblg/ghidra-dsp56300).

## Languages and memory model

| Language | Core | Words | Memory spaces |
|---|---|---|---|
| `DSP56000:BE:16:default` | DSP56000/DSP56001, plus DSP56002 INC, DEC, DEBUG, DEBUGcc, MPY/MAC (±)S,#n,D | 24 bits, held in 4-byte units | P, X, Y (64K words each) |
| `DSP56000:BE:16:DSP56156` | DSP56156 (DSP56100 family) | 16 bits | P, X (64K words each) |

DSP56000 words are stored in 4-byte big-endian units (high byte zero), the layout MAME and
Motorola's COFF tools use: Ghidra's decompiler does not finish on pointer arithmetic in a
space whose word size is not a power of two (a load through an incremented pointer in a loop),
so 3-byte words are not used. Raw 24-bit images with 3 bytes per word must be widened first.
DSP56156 words are 2-byte big-endian units.

Both languages model:
- 56-bit (DSP56000) or 40-bit (DSP56156) accumulators A and B with their A2/A1/A0 parts,
  X/Y input registers, R/N/M address registers, SR (MR plus CCR flags kept as separate flag
  registers), OMR, SP, LA, LC.
- The hardware system stack (SSH:SSL, 15 levels) as the `ss` space indexed by SP. JSR/BSR
  push PC and SR there, RTS/RTI pop them, MOVEC to/from SSH pushes/pops, DO pushes LA/LC and
  PC/SR. The cspec uses SP in `ss` as the stack pointer.
- Parallel moves in the order the hardware uses: move sources and effective addresses
  first, then the data ALU operation, then move destinations. A move therefore reads the old
  value of a register the ALU operation writes, and the ALU operation reads the old value of a
  register the move loads.
- The data shifter/limiter: accumulators moved onto a data bus are scaled and saturated
  (L latches limiting, S follows the scaling-bit equations). Rounding is convergent, at the
  position the scaling mode selects (DSP56156 also has OMR two's-complement rounding and
  saturation modes). E and U follow the scaling mode.
- Address modifiers in p-code: linear, modulo M+1 (wrapping in the 2^k block that holds Rn;
  an offset that is a multiple of the block size jumps to another block), bit-reversed
  (reverse carry) and, on DSP56000, the DSP56002 multiple-wrap-around modulo. The cspec
  assumes Mn = FFFFh (linear) and MR = 0 at function entry, so the decompiler folds the
  modifier and scaling logic away until code changes them.
- REP: the repeated instruction is executed as the REP's delay slot in a loop (Ghidra shows
  it with a leading `_`). The same instruction reached by a jump runs once. DSP56156 REPcc
  repeats until the condition is true.
- DO loops: DO sets disassembly context on the loop's last instruction (LA and LA-1, for a
  two-word last instruction). That instruction's p-code decrements LC and branches to the
  loop start, or pops the loop state. DSP56156 DO FOREVER and BRKcc are included.
- Bit operations, Tcc, NORM, DIV, MOVEC/MOVEM/MOVEP, LUA, and on DSP56156 the bit-field
  (BF*), CHKAAU, DMAC, IMPY/IMAC, EXT, SWAP, ASL4/ASR4/ASR16 and (R2+xx) forms.

STOP, WAIT, RESET, SWI, ILLEGAL and DEBUG are user ops. The pspecs mark the interrupt vectors
(two words each) as entry points and name the on-chip peripheral registers in X:FFC0–FFFF:
DSP56001 from Motorola's IOEQU.ASM equates, DSP56156 from its User's Manual.

`DspLodLoader` imports Motorola LOD files, the ASCII absolute load format of Motorola's
assemblers and linkers (`_START`, `_DATA P/X/Y/L`, `_BLOCKDATA`, `_SYMBOL`, `_END`). Six-digit
words select the DSP56000 language and four-digit words the DSP56156 one. Contiguous words
become initialized blocks, the rest of X and Y stays uninitialized, symbols become labels and
`_END` becomes the entry point.

Ghidra prints Motorola syntax with numbers in `0x` form. It keeps the assembler's force
operators: `<` for short immediates, absolute short and 12-bit jump addresses, `>` for long
absolute addresses, and `<<` for I/O short (`pp`) addresses. DO shows the assembler's `expr`
operand (LA+1), not the LA stored in the instruction.

## Verification

### Decode vs MAME

**DSP56000**, 1,243,248 two-word slots, 0 unexplained differences:
- every word with bits 23–16 = 00h–0Fh (all non-parallel instructions, MOVEP, class II moves)
- every parallel-move field with two data ALU opcodes
- every data ALU opcode with 32 move fields
- 65,536 random words

| Bucket | Records |
|---|---|
| Agree | 394,967 |
| Both invalid | 336,125 |
| MAME decodes an encoding the manual leaves undefined | 344,626 |
| MAME XY move: Y mode/register taken from the X fields | 84,439 |
| MAME MOVEP: peripheral address taken from bits 13..8 | 39,839 |
| MAME omits the accumulator source of ADD/SUB/TFR/CMP/CMPM/ADDL/ADDR/SUBL/SUBR (some also have the XY bug) | 17,150 |
| MAME MOVEP P:ea: peripheral space and address wrong | 14,538 |
| MAME Tcc: S1,D1 register table differs from the manual | 8,359 |
| DSP56002 instruction MAME lacks | 2,080 |
| MAME ignores the absolute-address extension word | 1,125 |

An independent table in `test/explain_dsp56000.py`, written from the manual's encoding
summary, decides whether each word is a defined instruction. It agrees with Ghidra on all
1,245,184 slots (Ghidra decodes ⇔ the table says the word is defined). That table is what
justifies every "MAME decodes an encoding the manual leaves undefined" record.

**DSP56156**, 261,285 slots (every 16-bit first word with three extension-word tails, plus
random words), 0 unexplained differences:

| Bucket | Records |
|---|---|
| Agree | 214,141 |
| Both invalid | 16,530 |
| MAME rejects a parallel move into the data ALU accumulator (assembler restriction) | 16,270 |
| MAME prints the dual-read multiply sources in S2,S1 order | 12,279 |
| MAME decodes an encoding the manual leaves undefined | 1,102 |
| X:(R2+xx) / P:(R2+xx) forms MAME lacks | 403 |
| MAME rejects TFR(3) with D1 = D2 (assembler restriction) | 256 |
| MAME rejects Tcc R0,R0 without a data ALU transfer | 123 |
| MAME requires DIV / DMACss / TST(2) don't-care bits to be 0 | 151 |
| BFCHG/BFCLR/BFSET/BFTSTH/BFTSTL (MAME lacks them) | 16 |
| MAME prints a MOVE with no move fields as NOP; rejects SSH as DO/REP count or MOVE(C) SSH,SSH | 14 |

Its own manual-derived validity table (`test/explain_dsp56156.py`) agrees with Ghidra on every
slot.

### Every entry

1,030/1,030 SLEIGH constructors (DSP56000) and 1,589/1,589 (DSP56156) are reached, with and
without the DO loop-end context.

### Emulator

Hand-computed expectations from the manuals. A deliberately broken expectation is reported
as a failure.

- **DSP56000: 81/81.** Covers ALU flags (E/U/N/Z/V/C/L), MPY/MAC/MACR with convergent
  rounding, shifts and rotates, logic on A1, ADC/ADDL/ADDR/CMPM/CLR/TST, a 24-step DIV,
  NORM, parallel-move read/write ordering, limiting in both directions, immediate-short
  justification, L: moves (also with scaling up and down), XY moves in both banks, class I/II moves, all addressing modes,
  modulo wrap up/down/+N, block jump, multiple wrap-around, bit-reverse FFT order, REP, DO
  loops (one- and two-word last instructions), JSR/RTS, Jcc, JCLR/JSET, bit operations,
  MOVEC/ANDI/ORI on SR/CCR/MR, Tcc with an R move, MOVEP, MOVEM, scaling mode, SSH push/pop,
  and the DSP56002 INC and MPY #n. All hand encodings except the two DSP56002 ones were
  confirmed by assembling the same text with asl (`test/check-encodings.sh`: 77 agree).
- **DSP56156: 54/54.** Code assembled with ASM56100. Covers ALU flags, 40-bit
  overflow/carry, convergent vs two's-complement rounding, OMR saturation, move limiting,
  modulo + CHKAAU, bit reverse, (R2±xx), dual reads, TFR3, REP, REPcc, DO, DO FOREVER +
  BRKcc, JSR/RTS, Tcc, LEA, BF ops, MOVE(M), MOVEP, ANDI, EXT, SWAP, ASR16, NORM, DMACss.

### Real code

**DSP56000.** The real code is Motorola's freely distributed DSP56000 software from the
Motorola DSP bulletin board archive, mirrored on bitsavers. Motorola released it "without any
license fee or royalty". The set has two parts:
- 10 LOD files Motorola built and shipped, 5 of them with the assembler's listings (ADC16
  demo programs, DGE audio, the bootstrap)
- the archive's sources (FFT, filters, floating-point library, functions, matrix, lattice,
  speech, telecom, benchmarks), assembled with Motorola's DSP56000 Assembler 3.1 into LOD
  files and listings: 65 distinct programs

`test/real/fetch-and-build.sh` downloads everything by pinned URL + SHA-256 and builds
locally; nothing is committed. Results:

- Listing-guided disassembly vs the assembler's source statements: 5,179/5,179 code
  statements in 70 listings identical. Another 108 were skipped because their operands use
  macro-local symbols or assembler functions the comparison script does not evaluate.
  Comparison handles symbols, expressions, fractional constants, local labels, overlays,
  macro expansions and Motorola's syntax alternatives (MOVE for MOVEC/MOVEM/MOVEP, AND/OR for
  ANDI/ORI, either order of the two move fields).
- MAME at the same 5,446 listed addresses: 4,628 agree and 33 are data words both reject;
  8 follow a data word MAME read as a two-word instruction. The other 777 are explained by
  the MAME bugs below, plus MAME's 16-bit display of MOVEC long immediates. 0 are
  unexplained.
- Auto-analysis of the 75 LOD files: 135 functions, all decompile (0 failures, 0 timeouts),
  and 4,135 of the 5,179 listed statements reached (the rest are interrupt handlers and
  routines only reached through tables or the host). 51 bad-instruction bookmarks: 48 are
  code running off the end of the loaded words (test programs that stop at their last
  instruction). The other 3 are data-only table files placed at P:0, which the reset vector
  makes code.

**DSP56156.** No freely licensed DSP561xx binaries were found. The 34 benchmark programs in
Appendix B of the DSP56100 Family Manual were assembled with Motorola's ASM56100 (from the
freely distributed DSP56100 simulator kit) by `test/real/bench156.sh`:
- 549/549 listing statements identical, 0 boundary errors
- the same images vs MAME: 69,411 words agree, and 55 are dual-read multiply sources MAME
  prints in S2,S1 order
- auto-analysis: 749 functions (including the vector entries in the zero fill around the
  code), all decompile. The 103 bookmarks are "maximum run of repeated byte instructions" in
  that fill.

MAME `dsp56000` bugs confirmed against the manual and asl/ASM56000:
- In XY moves it takes the Y address mode and register from the X fields.
- MOVEP takes the peripheral address from the ea/register field. For P:ea it also prints
  Y:FFC0+.
- The Tcc S1,D1 register table is wrong.
- The accumulator source of two-operand ALU forms is omitted (`add a` for `add b,a`).
- The absolute-address extension word of class I/II moves, bit operations and REP is
  ignored.
- Reserved bits, register codes and modes are accepted.

MAME `dsp56156`:
- No BF* instructions and no (R2+xx) forms.
- Dual-read multiply sources are printed reversed.
- Don't-care bits are required to be zero.
- Some legal encodings are rejected as assembler restrictions.
- SHFL/SHFR are decoded at 15Dx/15Fx (in neither manual).

One manual-vs-assembler conflict: the DSP56100 Family Manual says Z = 0 selects X:(A1) in
MOVE(C), but ASM56100 and MAME encode it with Z = 1. The module follows the assembler.

## Known gaps

- **Not modeled (hardware state):** interrupts and exception processing, peripherals,
  STOP/WAIT/RESET/SWI/ILLEGAL/DEBUG (user ops), cycle timing, system-stack overflow and
  underflow flags (SP SE/UF bits), the DSP56002 double-precision multiply mode (SR.DM).
- **DO loops:**
  - Nested loops that end on the same LA are not modeled.
  - The loop-end context depends on the DO having been disassembled first. A loop body
    disassembled before its DO (reached by a jump) gets no loop-end p-code.
  - DSP56156 DO SP / DO SSL special counts are not modeled.
- **Modulo addressing:** an offset larger than the modulus that is not a block-size multiple
  ("unpredictable" in the manual) wraps once.
- **Decode policy:** encodings the manuals call assembler restrictions (duplicate
  destinations, parallel moves into the ALU destination) are decoded rather than rejected.
- **DSP56156 approximations:** IMPY/IMAC E, U and Z ("special definition") are approximated.
  CHKAAU after a dual read reflects the R3 update. The TFR(3) register path goes through the
  scaling shifter.
- **Loaders:** Motorola's COFF object/absolute format (`.cld`) is not loaded. Convert it with
  Motorola's `cldlod` to a LOD file.
- **Unverified:** behavior on hardware. No third-party DSP561xx binaries were tested.
  DSP56002-only instructions are checked only against the manual (MAME and asl lack them).

## Sources

- Motorola, *DSP56000 Family Manual* (DSP56KFAMUM/AD), 1992 and 1995 editions (bitsavers
  `components/motorola/56000/56000/`), SHA-256 of the 1995 PDF
  `d1afbd2fc9aa4731dfb88b9c239f590ab24a78df73b23fb7f4d01b14468b3799`: instruction pages,
  encoding summary A.10, condition codes, address generation, data ALU.
- Motorola, *DSP56000/DSP56001 User's Manual*, 1990 (bitsavers): interrupt vectors.
- Motorola, *DSP56100 Family Manual* (DSP56100FM/AD), 1994 (bitsavers
  `components/motorola/56000/56100/`), SHA-256
  `d801b6c0f8dd5ed3ba0f4a99486a4ae5a4595a4fee6ab99d26f16a456038ba1a`, and *DSP56156 User's
  Manual*: DSP56156 encodings, operation, memory map, vectors, peripherals.
- Motorola DSP bulletin-board software (bitsavers `components/motorola/56000/56K_BBS/`):
  IOEQU.ASM peripheral equates, and the real-code test programs.
- Motorola DSP56000 Assembler 3.1 (`DSPBIN_3.1/dspbin.zip`) and DSP56100 assembler
  (`dsp56100Simulator.zip`), both from bitsavers, run under dosbox as black boxes to build
  test programs.
- asl (Alfred Arnold's macro assembler, GPL), run as a black box to confirm the emulator
  cases' hand encodings.
- MAME `unidasm -arch dsp56000` / `-arch dsp56156`: black-box decode references.

## Build and test

```sh
export GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC
python3 DSP56000/tools/gen_dsp56000.py > DSP56000/data/languages/dsp56000_gen.sinc
python3 DSP56000/tools/gen_dsp56156.py > DSP56000/data/languages/dsp56156_gen.sinc
"$GHIDRA_INSTALL_DIR/support/sleigh" -a DSP56000/data/languages
(cd DSP56000 && gradle buildExtension)    # or DSP56000/test/build-jar.sh for a linked install
ASL=/path/to/asl DSP56000/test/run-tests.sh --real "$HOME/.cache/ghidra-rare-scratch/dsp56k-real" \
	"$HOME/.cache/ghidra-rare-scratch/dsp56k-tests"
```

`run-tests.sh` runs:
- the generator checks and the SLEIGH compile
- emulator cases for both languages, including the broken-expectation check (and, with
  `ASL`, the asl encoding check)
- the decode differential (`test/run-decode.sh`, `compare.py` with `explain_*.py`)
- the every-entry test (`test/every-entry.sh`)
- with `--real`, the real-code checks (`test/real/run-real.sh` for DSP56000,
  `test/real/bench156.sh` for DSP56156). These need curl, unzip, pdftotext and dosbox.

This module is MIT-licensed; see [LICENSE](LICENSE).
