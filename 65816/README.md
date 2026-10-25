# WDC 65816 (SNES main CPU)

Ghidra processor module for the WDC W65C816S (65816) as used in the Super Nintendo: SLEIGH
disassembly with M/X/E width tracking, p-code semantics, and a SNES ROM loader (LoROM/HiROM).
Language ID `65816:LE:16:default`.

This is a community module: achan1989's
[ghidra-65816](https://github.com/achan1989/ghidra-65816) as continued by kaayzouee
([ghidra-65816](https://github.com/kaayzouee/ghidra-65816)), MIT. See [CREDITS.md](CREDITS.md)
for the authors and every change Ghidra-Rare made (a fork commit per change).

## What it covers

- All 256 opcodes in emulation and native mode, with the accumulator (M) and index (X) widths
  as decode context. The context follows `REP`/`SEP`, `XCE` after `CLC`/`SEC`, `PHP`...`PLP`
  (one level, along branches and calls) and `PEA`; `PLP`. Callees inherit the caller's context;
  after a call the caller keeps its own.
- The program counter is the 24-bit `PBR:PC`. Absolute `JMP`/`JSR` target the instruction's bank.
- SNES ROM loader (`SNES ROM`): finds the internal header, maps ROM where the CPU sees it (LoROM
  banks `$00-$7D:8000`, FastROM mirrors at `$80+`; HiROM `$C0+` with `$40+` and `$00/$80:8000`
  mirrors), WRAM `$7E0000-$7FFFFF`, the low-RAM mirror and the I/O pages (volatile), and turns
  the vectors into entry points: RESET and the emulation vectors in emulation mode, the native
  vectors with M=X=1.
- cspec: `__near` (JSR/RTS, default) and `__far` (JSL/RTL) prototypes.

## Results (Ghidra 12.1.4)

| Check | Result |
|---|---|
| Decode vs MAME `g65816` (every opcode x 16 operand patterns + 30,000 random words), each of M/X/E = 000, 010, 100, 110, 111 | 100% semantic, 96.8% exact text (34,096 records per mode); every difference is a spelling alias |
| ca65 re-assembles Ghidra's text to the same bytes | 100% (34,096 records x 5 modes) |
| Every opcode decodes in every mode | 1,280/1,280 |
| Context tracking test (`test/ctx/ctx.s`: REP/SEP, CLC/SEC+XCE, calls, PHP/PLP, PEA/PLP) | 20/20 |
| Emulator, hand-computed cases (`test/emu`) | 45/45 |
| SingleStepTests/65816, 50 tests per opcode and mode | 25,400/25,600; the 200 failures are `WAI` and `STP` (halt pcodeops) |
| Real ROMs: 13 homebrew ROMs (10 PVSnesLib C/WLA-DX incl. HiROM, 3 ca65), loader picked automatically | 0 decode differences vs MAME in 45,803 disassembled instructions; 5 bad-instruction bookmarks in all (0 or 1 per ROM; 4 are code run under two widths, 1 a branch into unmapped memory); 8 of 530 functions time out in the decompiler (30 s), no other decompile failures |
| Real ROMs vs MAME execution traces (10 s of emulation each) | every executed instruction Ghidra disassembled has the right width (100.00% in all 13 ROMs); Ghidra reaches 82–100% of executed PCs (40% for `mapandobjects`, whose main loop is only reached through a function pointer) |

The decode oracle is MAME's g65816 disassembler built with M and X as options
(`test/build-mame-dis.sh`; `unidasm` hard-codes M=X=0, and the driver reproduces its output
exactly in that mode). Execution traces come from MAME's `snes` driver with an independent
SPC700 boot ROM (`test/trace/make_ipl.py`), so the copyrighted IPL is never needed.

## How to test

```sh
export GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC
CC65_BIN=/path/to/cc65/bin SINGLESTEP=1 REAL_SAMPLES=/path/to/samples \
  test/run-tests.sh /path/to/workdir
```

`CC65_BIN` (ca65/ld65) enables the assembler round trip and rebuilds the test programs;
`SINGLESTEP=1` fetches SingleStepTests once (about 3 GB downloaded, 13 MB kept);
`REAL_SAMPLES` fetches the homebrew ROMs by pinned URL and SHA-256
(`test/fetch-real-samples.sh`) and, if `mame` is installed, traces each one. Nothing fetched is
committed.

## Known gaps

- Width changes the static context cannot see: `PLP`/`RTI` without a matching `PHP` or `PEA`,
  `XCE` without `CLC`/`SEC` just before it (native mode is assumed), `REP`/`SEP` in a callee
  (the caller continues with its own widths). Code reached under two different widths gets a
  "Multiple flows produced inconsistent instruction prototype" bookmark (PVSnesLib's sound
  upload loop runs the same `LDA [dp],Y` with M=0 and M=1).
- The p-code reads M/X/E from the decode context, not from a run-time flag: emulating across a
  width change only works when the context at the next instruction is right.
- `WAI` and `STP` are pcodeops (the emulator stops on them). Instructions or operands that wrap
  at the end of a program bank are not modelled (upstream limitation).
- Indirect jumps and calls (`JMP (abs,X)`, `JML [abs]`, function pointers) are not followed;
  PVSnesLib's `main` is reached that way.
- Loader: no ExHiROM, SA-1, SuperFX or other coprocessor maps; SRAM is not mapped. The DBR is not
  tracked, so absolute data references assume bank 0 or the loader's mirrors.
- 65802 is not supported (upstream).

## Reference-tool bugs found

- MAME `g65816` prints stack-relative offsets as signed (`lda -$1,s` for `$ff,s`) and prints
  `$80` as `-$0`; branch/`BRL`/`PER` displacements of `$80`/`$8000` also print as `-$0`.
- MAME prints `JML [abs]` (`$DC`) as `jml ($1234)` and `JML long` (`$5C`) as `jmp`.
