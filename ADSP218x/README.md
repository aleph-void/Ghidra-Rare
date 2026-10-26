# Analog Devices ADSP-218x for Ghidra

An independent SLEIGH module for the Analog Devices ADSP-218x fixed-point DSPs (ADSP-2181 and the
rest of the 218x family). Every instruction uses one 24-bit word, and data is 16 bits wide. The
module targets Ghidra 12.1.4, and its language also compiles with 12.1.3 and 12.2.

It was written from the *ADSP-2100 Family User's Manual*, 3rd edition (Analog Devices, September
1995; bitsavers mirror `components/analogDevices/dsp/ADSP-2100_Users_Manual_3ed_Sep95.pdf`,
SHA-256 `44caea99…41fed`). The parts used were:

- Appendix A: instruction coding, register, condition and constant tables
- Chapter 15: instruction set reference, the semantics of every instruction
- Chapters 2–4: ALU, MAC and shifter detail, sequencer and loop stacks, address generators
- Chapter 10: ADSP-2181 memory map

MAME `unidasm -arch adsp21xx` was used only as a black-box decode reference. No source of MAME or
of any other tool was read. One thing was learned from the oracle and not the manual: the
register codes PMOVLAY and DMOVLAY (REG group 01, codes 1110 and 1111). The 1995 manual describes
both registers but leaves them out of its Appendix A table.

## Language and memory model

| Language | Spaces |
|---|---|
| `ADSP218x:BE:16:default` | `pm`: program memory, 24-bit words (Ghidra word size 3, word-addressed, one instruction per word).<br>`dm`: data memory, 16-bit words.<br>`io`: the 218x I/O space, 2048 16-bit words. |

Images use 3 big-endian bytes per program word. This matches the VisualDSP++ DXE files and the
boot format. For a raw image, import it with the BinaryLoader at `pm:0000`.

**Registers.**
- The data registers, MR (MR2:MR1:MR0, 40 bits held sign-extended), SR (SR1:SR0) and the DAG
  registers I0–I7, M0–M7 and L0–L7 are registers.
- So are the system registers ASTAT, MSTAT, SSTAT, IMASK, ICNTL, CNTR, SB, PX, RX/TX, IFC,
  OWRCNTR, PMOVLAY and DMOVLAY.
- Each register holds its value the way the DMD bus reads it:
  - I, L and CNTR are zero-extended from 14 bits, and M is sign-extended from 14 bits.
  - MR2 and SE are sign-extended from 8 bits, and SB from 5 bits.
  - Writing MR1 sign-extends into MR2.
- The ASTAT bits (AZ AN AV AC AS AQ MV SS) and the MSTAT modes (SEC_REG, BIT_REV, AV_LATCH,
  AR_SAT, M_MODE, TIMER, G_MODE) are separate 1-byte registers. Reading ASTAT or MSTAT rebuilds the
  value from them, and writing either register reloads them.

**Instructions.** All 31 instruction types of Appendix A are decoded, including the 218x I/O
space instructions, `IDLE (n)`, `ENA/DIS INTS`, TOPPCSTACK and the type 9 constants.

**Semantics.** Everything has p-code: ALU, MAC and shifter operations with their flags, the
divide primitives, data moves, and the program sequencer.
- The AR saturation, AV latch and MAC integer/fractional modes follow MSTAT.
- MAC rounding is unbiased and saturates MR.
- **Multifunction instructions** read every operand before writing any result, so
  `AR = AX0 + AY0, AX0 = DM(I0,M0)` uses the old AX0 (manual 15.4).
- **Address generators.** DM/PM indirect accesses post-modify through the modulus logic. Circular
  buffers work the manual's way: base = I with the low ceil(log2 L) bits cleared,
  `I = (I + M − B) mod L + B`. With L = 0 the access is linear. DAG1 addresses go through the
  bit-reverse logic when MSTAT BIT_REV is set.
- **Zero-overhead loops.** `DO addr UNTIL term` marks the loop's last instruction through the
  disassembler context, using `globalset` to set the end flag, the termination code and the loop
  top. The root constructor adds the loop logic after that instruction:
  - The termination condition is tested on the status the previous instruction produced.
  - If the condition is false, control returns to the top of the loop. A `CE` loop decrements
    CNTR at this point.
  - If it is true, the loop and PC stacks are popped, and the count stack too for `CE`.
  - An instruction that branches itself takes precedence over the loop logic (manual 3.2.4, case 2).
- **Hardware stacks.** The PC stack (16 entries), count stack (4), loop stack (4) and status stack
  (12) are register files, so CALL/RTS/RTI, DO, PUSH/POP and TOPPCSTACK leave nothing behind in
  decompiled C. `IF NOT CE JUMP` decrements the counter and pops the count stack when it
  expires.

**Compiler spec.** The compiler spec tells the decompiler that L0–L7 = 0 and that BIT_REV,
AR_SAT, AV_LATCH and M_MODE are off at function entry, which is their reset state. The
circular-buffer, bit-reverse and saturation logic therefore folds away unless the code sets those
registers. ALU add and subtract flags use `carry`/`scarry`/`sborrow`, so the decompiler recovers
comparisons.

**Loader and symbols.**
- `ADSP218xDxeLoader` loads VisualDSP++ 3.x DXE executables: 32-bit little-endian ELF, e_machine
  30, with 44-byte section headers.
  - Allocated PROGBITS sections with flag bit 0x2000 go to `pm`, the others to `dm`. These
    meanings come from reading linked files; the format has no public specification.
  - The loader applies the symbol table (functions and data objects) and the processor labels.
  - It makes the twelve interrupt vectors entry points.
- The pspec names the twelve ADSP-2181 interrupt vectors (pm:0000–002C, four words each, from
  User's Manual Table 3.6) and the memory-mapped control registers at dm:3FE0–3FFF. The vectors
  are entry points, so raw images are analysed from every vector.

## Verification

`test/run-tests.sh [--real <dir>] [<workdir>]` runs everything below. It needs MAME `unidasm` on
PATH and Ghidra with the module linked.

| Check | Result |
|---|---|
| Decode vs MAME, **all 16,777,216 instruction words** | 14,726,146 agree, 793,587 invalid on both sides, 1,257,483 differ. **0 unexplained** (buckets below) |
| Every entry | 800/800 SLEIGH constructors reached (all words in the default context, plus the loop-end contexts) |
| Emulator | 78/78 hand-computed cases pass, and a deliberately broken expectation is reported as a failure |
| Real code | Two VisualDSP++ executables, MIT licensed (below): 620 analysed instructions. **620/620 identical to the assembler source**; 612 identical to MAME and 8 where MAME prints nothing. 58/58 functions decompile, with 0 error bookmarks |

### Decode differences, all explained

Encodings MAME decodes that the manual leaves reserved. Ghidra rejects them, as real code never
contains them.

| Words | Reason |
|---:|---|
| 425,043 | Reserved register codes and shifter X operand 001, which MAME itself prints as `??` |
| 215,040 | Type 9 MAC with bits 7–4 other than 0000 (xop·yop) or 0001 (xop·xop) |
| 114,688 | Type 9 ALU with bits 7–4 ≠ 0 but BO = 00/10 (not a constant) |
| 65,702 | Writes to SSTAT (read-only) and reads of IFC/OWRCNTR (write-only) |
| 65,535 | NOP (type 30) with nonzero low bits |
| 48,768 | Mode control (type 18) with bits 1–0 ≠ 00 |
| 32,768 | Type 9 constants with NOT, negate or ABS (the manual defines constants only for add, subtract, AND/OR/XOR and PASS) |
| 15,360 | Type 9 with AMF = 00000 |
| 13,056 | xop·xop with formats other than SS/UU/RND, or with yop ≠ 00 |
| 128 | Type 19 with bit 5 set |
| 16 | DIVS with AY0 or 0 as yop (the manual allows AY1 and AF) |
| 15 | Modify flag out with no flag operation |

Confirmed MAME bugs, checked against Appendix A and Chapter 15:

| Words | Bug |
|---:|---|
| 246,784 | AMF 01101 (`MR − xop·yop (SU)`) is printed as `(SS)` |
| 14,336 | Type 9 constants with YY = 11 (bits 12–15: 0x1000…0x8000 and their inverses) are decoded as Y = 0 |

MAME omissions: Ghidra decodes these valid instructions, and MAME prints nothing for them or marks
them invalid.

| Words | Instruction |
|---:|---|
| 128 | Mode control with no mode change. MAME prints nothing; Ghidra prints `ENA/DIS NONE` |
| 109 | `reg = TOPPCSTACK` / `TOPPCSTACK = reg` (MAME prints `??`) |
| 5 | `IDLE` and `IDLE (n)` (MAME prints nothing) |
| 2 | `ENA INTS` / `DIS INTS` |

Ghidra's syntax follows the manual where MAME's is ambiguous or loses information:
- `AR = PASS AY0` instead of `AR = AY0`, since the plain form looks like a register move.
- `MR = MR (RND)` instead of `MR = MR + MX0 * 0 (RND)`.
- `PASS 3` for a constant passed through Y + 1.

`test/compare.py` maps these spellings to each other before it compares.

### Real code

Real code was tested on github.com/AlexLefte/Electricity-Consumption-Meter (MIT), pinned to commit
`81db8b4`. It is an electricity meter for the ADSP-2181 EZ-KIT Lite that talks to an AVR
through the flag and I/O ports.
- Two executables were built with VisualDSP++ (ADI linker 3.1.5.2). `test/real/fetch.sh` fetches
  them by pinned URL and SHA-256, along with their assembler sources and include file. Nothing is
  committed here.
- Each program is imported with the DXE loader and auto-analysis.
- `real_compare.py` checks every analysed instruction against MAME at the same address.
- `src_compare.py` places every statement of the source's program-memory sections at its
  address, resolves symbols, `#define`s, `LENGTH()` and 1.15 fractional constants with the
  linker's values, and compares the statement with the instruction Ghidra decoded there.

| Program | Functions | Instructions | Source statements | MAME | Decompile |
|---|---|---|---|---|---|
| `meter.dxe` (main program) | 37 | 493 | 493 identical, 32 not reached | 489 identical, 4 omissions (IDLE, ENA INTS) | 37/37 |
| `pftest.dxe` (flag/port test) | 21 | 127 | 127 identical, 32 not reached | 123 identical, 4 omissions | 21/21 |

The 32 unreached statements in each program are the `RTI` padding behind each vector's first
instruction, which no path reaches.

## Known gaps

- **Not modelled:**
  - The secondary register bank. `ENA SEC_REG` sets SEC_REG, but the module has one set of
    data registers. Modelling the bank would make every data-register access conditional and
    the decompiled code unreadable.
  - Interrupts and their automatic PC/status pushes, IDLE (a user op), timers, SPORTs, BDMA/IDMA
    and the flag pins (FI, FO and FL0–FL2 are plain registers).
  - PMOVLAY/DMOVLAY overlay mapping.
  - Biased rounding, which is selected by the BIASRND bit of the SPORT0 autobuffer register in
    data memory. MAC rounding is always unbiased.
  - The sticky SSTAT stack-overflow bits. A push beyond the stack depth loses the bottom entry.
  - The rule that a CNTR load does not push an invalid counter value.
  - The one-cycle delay of `reg = TOPPCSTACK`.
- **Loop context:** Two DO loops that end on the same instruction keep only the last loop's
  context. The manual forbids that case.
- **Decompiler assumptions:** The decompiler assumes L = 0 and the reset MSTAT modes at every
  function entry. Interrupt handlers that rely on circular buffers set up elsewhere, like the
  meter's `next_cmd`, decompile with linear addressing. The emulator always uses the actual
  register values.
- **Not imported:** DWARF in DXE files, which VisualDSP++ emits as `.debug_*` sections. The DXE
  loader is not Ghidra's ELF loader. Relocatable `.doj` objects are not loaded either.
- **Unverified:**
  - Behaviour against hardware or ADI's simulator.
  - The DXE section-flag meanings beyond the two linked files tested.
  - MR rounding at the exact midpoint. The manual's two descriptions disagree (2.3.2.6): the
    worked examples change MR0 and the biased/unbiased table does not. The module follows the
    examples.
  - DIVS/DIVQ and EXP (LO)/EXPADJ beyond the hand-computed cases.
  - Whether `IF NOT CE CALL` decrements the counter, which the manual states only for JUMP.
    The module decrements only for JUMP.
  - Real third-party code for 218x variants other than the 2181.

## Files

- `data/languages/`:
  - `adsp218x.slaspec` (hand-written core)
  - `adsp218x_gen.sinc` (generated by `tools/gen_adsp218x.py` from the Appendix A tables)
  - `.ldefs`, `.pspec`, `.cspec`
- `src/main/java/adsp218x/ADSP218xDxeLoader.java`: the VisualDSP++ DXE loader.
- `test/`:
  - `run-tests.sh`, `run-decode.sh`, `compare.py`, `gen_corpus.py`, `ghidra-corpus.sh` and
    `ADSPDumpDisasm.java`: exhaustive decode differential.
  - `every-entry.sh` and `EveryEntry.java`.
  - `emu-test.sh`, `ADSPEmuTest.java`, `emu/cases.py` (the hand-computed cases) and
    `emu/asm.py` (a field packer for them).
  - `real-check.sh`, `ADSPRealCheck.java` and `real/`: fetch, MAME comparison, source comparison.
  - `build-jar.sh`: builds `lib/ADSP218x.jar` for a linked development install.
