# Renesas RL78

Ghidra processor module for the Renesas RL78 family (RL78-S1, S2 and S3 CPU cores: RL78/G10,
G12, G13, G14, G23, F1x, L1x, I1x and others). It is a community module,
[CUB3D/ghidra-rl78](https://github.com/CUB3D/ghidra-rl78) (Apache-2.0), imported by Ghidra-Rare,
tested against GNU binutils and largely rebuilt. See [CREDITS.md](CREDITS.md) for provenance and
the list of changes.

| Language ID | Cores | Notes |
|---|---|---|
| `RL78:LE:16:default` | RL78-S3 (G14, G23, ...) | includes MULHU, MULH, DIVHU, DIVWU, MACHU, MACH (`CE FB xx`) |
| `RL78:LE:16:S2` | RL78-S1/S2 (G10, G12, G13, ...) | `CE FB xx` is a plain `mov 0xffffb, #xx` |

The ELF opinion matches `EM_RL78` (197) and picks the language from `e_flags` (G14 or
unspecified: S3; G13 and G10: S2).

## What it models

- Every instruction of the RL78 Software manual (R01US0015) in both languages, including the
  `ES:` prefix on any instruction, `SKcc` (the next instruction gets a conditional skip through
  a context field) and `SEL RBn` (the register bank is a flow-following context field).
- Registers are memory-mapped as on the chip: banks 3..0 at FFEE0-FFEFF, SP/PSW/CS/ES/PMC/MEM at
  FFFF8-FFFFF, MACR at FFFF0. A `saddr` or `sfr` operand that hits a register is shown and
  tracked as that register (GCC keeps its virtual registers r8-r31 in banks 1-3).
- Near (16-bit) addresses resolve into F0000-FFFFF and `ES:` addresses into `(ES & 0xF) << 16`
  through a `segment()` userop with a pspec `segmentop`, so the decompiler types 16-bit pointers
  and finds stack variables through `SP`.
- Z, AC and CY for all ALU, shift, rotate, compare and bit instructions; `CALL`/`CALLT`/`RET`/
  `RETI`/`RETB` with the 4-byte stack frame; `HALT`, `STOP`, `BRK` fall through.
- cspec: the GCC RL78 ABI (all arguments on the stack, return value in r8-r15 = bank 1 at
  FFEF0). DWARF register mapping for GCC. SFR areas (F0000-F07FF, FFF00-FFFEF) are volatile.
- `ghidra_scripts/RL78Vectors.java` marks up the vector and CALLT tables of a raw image and
  creates functions at their targets.

## Results

Reference: GNU binutils 2.45 RL78 disassembler (libopcodes, through `test/slotdis.c`; G14 ISA for
the S3 language, G13 for S2). "Semantic" allows the spellings listed in `test/compare.py`
(decimal vs hex, register names for memory-mapped registers, `[hl+0]`, addresses mod 2^20).

| Test | Result |
|---|---|
| All 2-byte opcode prefixes and 3 bytes after `ES:`, 3 operand tails (393,728 slots) | both decode 393,146; 99.80% semantic, 95.16% exact (both languages). Every difference is a confirmed objdump quirk, see below |
| 60,000 random 8-byte slots | 100.00% semantic, 97.56% exact; 0 Ghidra-only, 0 objdump-only |
| Every-entry decode test (`CoverageCheck.java`) | 466/466 constructors reached (S3), 452/452 (S2) |
| p-code emulator (`EmuCheck.java`) | 56/56 hand-computed sequences pass (ALU and flags, every addressing mode, ES:, shifts/rotates, bit ops and bit branches, skips, call/ret/callt, push/pop, banks, S3 multiply/divide/MAC); a deliberately wrong expectation fails |
| Real binaries: 11 GCC-built ELFs from public sources (below), imported without forcing the language | language picked by the opinion (3 S2, 8 S3); 357 functions, 26,600 instructions; 0 bad-instruction or error bookmarks; 357/357 functions decompile; disassembly 100% semantic (70-75% exact) vs `rl78-elf-objdump -d` at the same addresses |
| Builds | `.sla` 27.7 KB (S3) / 26.8 KB (S2); compiles and builds with Ghidra 12.1.3, 12.1.4 and 12.2 |

Before Ghidra-Rare's changes the upstream module agreed with objdump on 52.9% of the random slots
(objdump decoded 2,850 that it rejected) and on 49.9% of the opcode corpus (144,531 rejected,
mostly `ES:` forms); its ELF opinion matched no RL78 file.

Real-binary samples (`test/fetch-real-samples.sh`, pinned commits and SHA-256, built with
`test/build-toolchain.sh`: binutils 2.45, GCC 14.3.0, newlib 4.5.0; never committed):
the six RL78/G14 and three RL78/G13 demos of
[msalau/rl78-samples-R5F104FEAFP](https://github.com/msalau/rl78-samples-R5F104FEAFP) and
[-R5F100SLAFB](https://github.com/msalau/rl78-samples-R5F100SLAFB) (Unlicense), FreeRTOS-Kernel
V11.1.0 (MIT) with its GCC RL78 port, and a program linking newlib/libm/libgcc
(`test/real-src`).

## Confirmed reference-tool bugs

- objdump decodes `61 81` and `61 A1` as `add`/`sub a, [hl+b]`. In `rl78-decode.opc` those two
  patterns have 15 bits (`0110 0001 1000 000`) so the last bit is a don't-care; the manual's
  second instruction map leaves both cells empty and only `61 80`/`61 A0` are defined
  (12 slots in the opcode corpus).
- objdump prints `es:` on `[SP+byte]` operands after an `ES:` prefix. The manual has no
  `ES:[SP+byte]` form and `rl78-elf-as` rejects `mov a, es:[sp+5]` ("ES: prefix not allowed
  here"); Ghidra ignores the prefix there (774 slots).
- Cosmetic: objdump prints relative branch targets below 0 as 64-bit values and keeps the
  unused top nibble of `!!addr20`.

## Known gaps

- GCC's crt0 defines the absolute symbol `__rl78_abs__ = 0`; Ghidra's ELF loader turns it into
  an entry-point function on the reset vector, which decompiles to `halt_baddata` (one per
  image, harmless).
- Only the GCC calling convention is described; CC-RL and IAR register-argument conventions are
  not.
- The flash mirror (MAA) is not modelled: data reads in F0000-FFFFF that mirror flash do not
  resolve to the code bytes.
- `BRK` is a returning userop rather than a call through the 0007E vector; `BRK1` (`FF`,
  objdump's name for erased flash) is a userop.
- AC is left unchanged by ADDW/SUBW/CMPW (the manual calls it undefined).
- The register bank follows `SEL RBn` along the flow only; an interrupt handler reached without
  a `SEL` uses bank 0 unless its context is set.
- Ghidra's emulator does not run segmentop injections; `EmuCheck.java` supplies `segment()` as a
  callback.

Unverified: CC-RL or IAR output and RL78-S1 (G10) images (no freely licensed samples were
found); third-party prebuilt firmware (the samples are built here from public source).

## Testing

```
test/build-toolchain.sh <workdir> <prefix>      # rl78-elf binutils/gcc/newlib (once)
export PATH=<prefix>/bin:$PATH GHIDRA_INSTALL_DIR=/path/to/ghidra_12.1.4_PUBLIC
test/fetch-real-samples.sh <samples>            # optional: build the real-binary samples
BU_SRC=<binutils-2.45 source> BU_BUILD=<binutils build --enable-targets=all> \
  REAL_SAMPLES=<samples> test/run-tests.sh <workdir>
```

`run-tests.sh` compiles both specs, links the module into the Ghidra install, runs the decode
comparison, the every-entry test, the emulator tests and (with `REAL_SAMPLES`) the real-binary
check. `tools/gen_rl78.py` regenerates `data/languages/rl78.sinc`.
