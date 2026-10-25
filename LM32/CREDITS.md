# Credits: Lattice LM32 module

This module is a community SLEIGH module that Ghidra-Rare imported, tested and fixed. The
original processor specification was written by its authors below; Ghidra-Rare's changes are
listed after them.

## Upstream

| | |
|---|---|
| Source | [jevinskie/ghidra-lm32](https://github.com/jevinskie/ghidra-lm32), commit `6c7d0025af4a42fd246b9ba78ac956d3eee8d682` (2025-10-23) |
| Ghidra-Rare fork | [aleph-void/ghidra-lm32](https://github.com/aleph-void/ghidra-lm32/tree/ghidra-rare), branch `ghidra-rare`, commit `48b47f58fc4715bb8ace9b75cf97a618a151a917` |
| License | MIT (`LICENSE`, "Copyright (c) 2022 Jevin Sweval", unchanged) |
| Original authors | Jevin Sweval ([@jevinskie](https://github.com/jevinskie)): the LM32 SLEIGH specification, cspec, opinion (2019–2022). cyrozap ([@cyrozap](https://github.com/cyrozap)): extension build support, manual index (2025) |

Ghidra-Rare's changes are kept as separate commits on branch `ghidra-rare` of a fork of the
upstream repository, on top of its full history, so the original license and authorship are
preserved.

The upstream repository also contains Lattice's *LatticeMico32 Processor Reference Manual*
(`data/manuals/LatticeMico32ProcessorReferenceManual39.pdf`). Ghidra-Rare does not
redistribute that PDF, because it is Lattice's document. Only the manual index
(`lm32.idx`) is kept; see the README for where to get the manual.

## Ghidra-Rare changes

1. **`lm32.sinc` reworked after differential testing against GNU objdump 2.45.**
   Agreement on the binutils opcode table was 60 %; it is now 100 % apart from two display
   differences documented in the README. The fixes:
   - Register r0 is a real register and prints as `r0` (it was shown as `0`).
   - Operand order and separators follow binutils (branches lacked the comma before the
     target).
   - Reserved bits that binutils requires to be zero must be zero.
   - `raise` decodes only `break` and `scall`, and both fall through.
   - The aliases objdump prints are decoded as such: `mv`, `mvi`, `mvu`, `mvhi`, `mva`, `not`,
     `nop`, `ret`, `eret`, `bret`.
   - The `user` instruction and gp-relative loads and stores are decoded.
   - `rcsr`/`wcsr` read and write named CSR registers instead of opaque pcodeops.
   - Shift amounts are taken mod 32.
   - `eret`/`bret` restore `IE`.
   - `call` sets `ra` from the next instruction.
   - Found by differential testing and the every-entry test.
2. **cspec rewritten from gcc's `config/lm32/lm32.h`.**
   - Stack arguments at sp+4. There was no stack entry before, so arguments after the eighth
     were lost.
   - 64-bit arguments use register pairs (join rule).
   - 64-bit results in r1:r2.
   - Callee-saved and killed registers, unsigned `char`, data organization, return address.
3. **DWARF register map (`lm32.dwarf`).** Without it every function's DWARF import failed with
   a NullPointerException (about 1,900 log lines per firmware), so functions had no
   prototypes (237 of 272 in `opsis-net-firmware.elf` were `undefined f(void)`). With it, 4
   of 272 are. Found by real
   binaries.
4. **pspec and opinion.**
   - r0 is tracked as 0.
   - `IP`, `CC` and `JRX` are volatile.
   - The opinion picks BE or LE by ELF endianness (both languages matched e_machine 138
     before).
   - gnu external names in the ldefs.
5. **ELF relocation handler** (`R_LM32_*`) for relocatable objects.

Ghidra-Rare-only files (not in the fork): `README.md`, `CREDITS.md`, `build.gradle` (replaces
upstream's in the release build), `extension.properties`, `.gitignore` and `test/`.
