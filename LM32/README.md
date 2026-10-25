# Lattice LM32 (LatticeMico32) processor module for Ghidra

A SLEIGH processor module for the LatticeMico32 32-bit soft CPU. It is used in LiteX/MiSoC
and Milkymist SoCs and is reported in AMD SMU firmware. It is a community module that
Ghidra-Rare imported, tested against GNU binutils, and fixed:

- [jevinskie/ghidra-lm32](https://github.com/jevinskie/ghidra-lm32) by Jevin Sweval, with
  build changes by cyrozap.
- MIT.
- See [CREDITS.md](CREDITS.md) for the upstream commit and every Ghidra-Rare change.
- It targets Ghidra 12.1.4, and also builds on 12.1.3 and 12.2.

## Languages

| Language ID | Description | ELF auto-select |
|---|---|---|
| `lm32:BE:32:default` | LatticeMico32, big endian (the real CPU and the gcc/binutils target) | e_machine 138 (EM_LATTICEMICO32), ELF32 MSB |
| `lm32:LE:32:default` | Same ISA, little endian (kept from upstream; no known hardware) | e_machine 138, ELF32 LSB |

## Files

- `data/languages/lm32.sinc` holds the whole ISA. Field names follow binutils: rs0 is bits
  25–21, rs1 is bits 20–16, rs2 is bits 15–11. `lm32_be.slaspec` and `lm32_le.slaspec` are
  the endian wrappers.
- `lm32.cspec` follows gcc `config/lm32/lm32.h`:
  - Arguments in r1–r8, then the stack at sp+4.
  - 64-bit values take two consecutive registers, most significant word first.
  - Results in r1 or r1:r2.
  - r11–r25 and fp are callee-saved.
  - `char` is unsigned.
- `lm32.pspec` declares PC, tracks r0 as 0, and marks IP, CC and JRX volatile.
- `lm32.dwarf` is the gcc DWARF register map. `lm32.opinion` and `lm32.ldefs` are the other
  spec files.
- `src/main/java/.../LM32_ElfRelocationHandler.java` handles the `R_LM32_*` relocations.
- `data/manuals/lm32.idx` is the index for Lattice's *LatticeMico32 Processor Reference
  Manual*, which is not included. To use Ghidra's manual lookup, put
  `LatticeMico32ProcessorReferenceManual39.pdf` in `data/manuals/`. It is available from
  Lattice, and the upstream repository also has a copy.

## What is decoded

Every instruction in the binutils 2.45 opcode table (`opcodes/lm32-opc.c`). Ghidra prints the
same assembler aliases objdump does: `mv`, `mvi`, `mvu`, `mvhi`, `mva`, `not`, `nop`, `ret`,
`eret`, `bret`, `break` and `scall`.

Two decodings go beyond binutils:

- `div` and `mod` (opcodes 0x27/0x35) are in the processor manual's opcode table but have no
  binutils entry.
- `user` (opcode 0x33) is decoded with its 11-bit function field.

## Semantics

There is real p-code for the following:

- All ALU, compare, shift, multiply and divide instructions. Shift amounts are mod 32.
- Loads and stores.
- Branches, `bi`, `calli`, `call`, `b`, `ret`.
- `eret`/`bret`, which return through `ea`/`ba` and restore `IE.IE` from `EIE`/`BIE`.
- `rcsr`/`wcsr`, which read and write the named CSR registers.

`break` and `scall` set `ba`/`ea` and call the pcodeops `breakpoint()`/`syscall()`. Both fall
through, because their handlers return to the next instruction. `user` is a pcodeop that
reads its two source registers.

## Test results

Run `test/run-tests.sh` for the synthetic tests, and `test/fetch-real-samples.sh` then
`test/real-binaries.sh` for real binaries (see "Testing" below).

### Decoding vs GNU objdump 2.45

`objdump -b binary -m lm32` with `-EB` or `-EL`. The `table` corpus holds every binutils
opcode-table entry (80) with its operand bits all 0, all 1, and with 40 random fills. The
`fuzz` corpus is 50,000 random words. A word that both tools reject counts as agreement.

| Corpus | Words | Agreement | Exact + semantic among decoded words | Unexplained differences |
|---|---|---|---|---|
| table, BE | 3,360 | 89.29 % | 3,000 / 3,360 | 0 |
| fuzz, BE | 50,000 | 99.60 % | 27,324 / 27,526 | 0 |
| table, LE | 3,360 | 89.29 % | 3,000 / 3,360 | 0 |
| fuzz, LE | 50,000 | 99.60 % | 27,324 / 27,526 | 0 |

"Semantic" means the same instruction with numbers in another base: Ghidra prints hex where
objdump prints decimal.

Every difference falls into one of three classes, and `compare.py` reports each one:

1. **gp-relative loads and stores.** When the base register is gp (r26), objdump prints only
   the offset (`lw r5,8483`). Ghidra prints `lw r5,(gp+0x2123)`, which keeps the base
   register visible. Same operation and operands (343 table words, 201 fuzz words).
2. **CSR numbers with no name** (11–13, 20–23, 28). objdump prints `???`, Ghidra `csrN`
   (17 table words).
3. **`div`/`mod`**, as above (1 fuzz word).

The upstream module agreed on 60 % of the table corpus before these fixes.

**Every-entry test** (`test/entry_check.py`): all 80 table entries decode in Ghidra, with
operand bits 0 and 1, with the same mnemonic objdump prints for that word, on BE and LE.

### Emulator

`test/emu_tests.py` and `test/EmuCheck.java` run 26 sequences per language. They cover:

- Add and subtract with wrap-around.
- Register and immediate logic, where the immediates are zero-extended.
- `andhi`/`orhi`.
- Register shifts (amount 33 behaves as 1) and immediate shifts.
- `mul`/`muli` with negative operands, `divu`/`modu`, `div`/`mod`.
- Every register and immediate compare, signed and unsigned.
- `sextb`/`sexth`.
- Word, half and byte loads and stores with negative offsets, checked for big- and
  little-endian byte order.
- gp-relative access and `mva`, `mv`/`not`, `wcsr`/`rcsr`.
- Taken and not-taken branches, signed versus unsigned branches, a loop, `calli`/`ret`,
  `call` through a register, `b`, and `eret` (target and `IE` restore).

Results: 26/26 on BE and 26/26 on LE. With `--break N` the generator makes one expectation
wrong, and the check then reports exactly that test as failed.

### Relocations

There is no LM32 gcc build here, so the relocation handler is checked with hand-written
assembly in `test/elf/`, assembled by binutils 2.45 configured `--target=lm32-elf`:

- **`relocs.o`.** Ghidra imports it, applying 13 relocations at addresses it chooses. GNU ld
  then links the same object at those addresses. 68 of 68 bytes are identical. The types
  checked are `HI16`, `LO16`, `CALL`, `BRANCH` and `32`, against local, section and
  undefined symbols.
- **`relocs_gprel.o`** covers `R_LM32_GPREL16`. GNU ld cannot be the reference for this type
  (see "Confirmed reference-tool bugs"), so `test/gprel_check.py` checks Ghidra's values
  against the bfd formula S + A − `_gp` instead. All 4 match.

### Real binaries

`test/fetch-real-samples.sh` downloads three gcc-built LM32 ELF executables with DWARF from
[timvideos/HDMI2USB-firmware-prebuilt](https://github.com/timvideos/HDMI2USB-firmware-prebuilt).
They are pinned to commit `bf8ee7bf`, build `v0.0.4-130-g155c7db`, by URL and SHA-256, and are
never committed:

- The LiteX BIOS (BSD-2-Clause).
- Two HDMI2USB-litex-firmware images (BSD-2-Clause), one of them with the uIP network stack.

`test/real-binaries.sh` imports each one headless with no `-processor` flag (the opinion
picks `lm32:BE:32:default`), analyses it, decompiles every function and compares every
instruction with objdump at the same address.

| Sample | Functions | Bad instr. | Decompiled | Disassembly vs objdump | Undisassembled `.text` words |
|---|---|---|---|---|---|
| `opsis-net-bios.elf` | 91 | 0 | 91 / 91 | 4,718 / 4,718 (100 %) | 48 (vector padding `nop`s) |
| `opsis-net-firmware.elf` | 272 | 0 | 272 / 272 | 12,480 / 12,480 (100 %) | 49 |
| `nexys_video-video-firmware.elf` | 293 | 0 | 293 / 293 | 14,155 / 14,155 (100 %) | 49 |

With upstream's module the same three images were 80–86 % identical to objdump, and DWARF
import failed for every function (no register map). In `opsis-net-firmware.elf`, 237 of 272
functions were `undefined f(void)`. With this module, 4 of 272 are: DWARF prototypes, types and locals
import. The decompiled C matches the sources:

- `isr()` reads `IP & IM`.
- `hb_service()` shows its static counters.
- libgcc `__muldi3` has 64-bit arguments in register pairs.

There are no decompile failures or timeouts. Ghidra adds about 200 `Error/DWARF` bookmarks
per image for gcc line-table entries ("IllegalArgumentException for source map entry …
-22"). This is the generic Ghidra DWARF line-number issue also seen with MicroBlaze. It only
affects source-line mapping.

## Known gaps

- **No compiled test program.** No LM32 gcc build was available here. Compiled-code coverage
  comes from the three real images, which have no function with more than eight arguments,
  so the stack-argument offset (sp+4, from gcc's `STACK_POINTER_OFFSET`) is unverified on
  real code.
- **Relocation handler coverage.**
  - Checked against ld: `HI16`, `LO16`, `CALL`, `BRANCH`, `32`.
  - Checked against the bfd formula: `GPREL16`.
  - Implemented from bfd but untested: `8`, `16`, `GOTOFF_HI16`/`GOTOFF_LO16` and the
    dynamic types (`RELATIVE`, `GLOB_DAT`, `JMP_SLOT`).
  - Reported, not applied: `16_GOT` and `COPY`.
  - FDPIC (`elf32-lm32fdpic`) is not handled.
- **Not modelled.** Exceptions, interrupts and cache effects (`wcsr ICC/DCC`) are not
  modelled. `user` and the `raise` instructions are pcodeops.
- **Little endian.** The LE language is decode- and emulator-tested only. LatticeMico32
  hardware and gcc are big endian.
- **Exception vectors.** In the LiteX images the vectors are `bi .` loops padded with
  `nop`s. The padding is never reached by flow, so it stays undisassembled.

## Confirmed reference-tool bugs

- **GNU ld `R_LM32_GPREL16` (binutils 2.45, `bfd/elf32-lm32.c` `lm32_elf_assign_gp`).** ld
  looks for `_gp` in the output symbol table, which does not exist yet during an ELF final
  link. The first GPREL16 relocation is reported as "internal error: dangerous error", and
  every later one is computed with gp = 4. `test/elf/relocs_gprel.s` reproduces it.
- **objdump display.** objdump prints undefined CSR numbers as `???`, and gp-relative
  loads and stores without their base register. These are display choices, listed so that
  diffs stay explainable.

## Testing

```sh
export GHIDRA_INSTALL_DIR=/path/to/ghidra_12.1.4_PUBLIC   # with Ghidra/Processors/LM32 -> this module
export OBJDUMP=/path/to/binutils-2.45/objdump               # built with --enable-targets=all
export LM32_OPC=/path/to/binutils-2.45/opcodes/lm32-opc.c
export LM32_BINUTILS=/path/to/lm32-elf/bin                  # optional: binutils --target=lm32-elf (ld check)
test/run-tests.sh work                                      # decode, every-entry, emulator, relocations
test/fetch-real-samples.sh samples
test/real-binaries.sh samples work-real                     # real binaries (~2 min)
```

Other files in `test/`:

- `gen_corpus.py`, `compare.py` and `entry_check.py`: corpus generation and comparison.
- `DumpWords.java`: decodes each word on its own.
- `EmuCheck.java`: the emulator check.
- `RealCheck.java`: analysis, listing and decompile statistics.
- `DumpMem.java`, `rawcmp.py`, `reloc-check.sh` and `gprel_check.py`: the relocation checks.
- `build-jar.sh`: compiles `lib/LM32.jar` for a development install.
- `elf/build.sh`: reassembles the test objects.
