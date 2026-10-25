# Credits: Renesas RL78 module

This module is a community SLEIGH module that Ghidra-Rare imported, tested and fixed. Testing
showed that most of the instruction decoding was wrong, so the instruction set was rebuilt;
the module's layout, language ID, register-bank context design and spec files come from the
original author.

## Upstream

| | |
|---|---|
| Selected source | [CUB3D/ghidra-rl78](https://github.com/CUB3D/ghidra-rl78), commit `906636abc3563e183ba9d3351e7a679506f82f61` (2026-07-26) |
| Ghidra-Rare fork | [aleph-void/ghidra-rl78](https://github.com/aleph-void/ghidra-rl78/tree/ghidra-rare), branch `ghidra-rare`, commit `9f4b7b90704a997dd856fb5045ae23aae88d84d5` |
| License | Apache License 2.0 (`LICENSE`, unchanged) |
| Original author | Callum Thomson ([@CUB3D](https://github.com/CUB3D), commits as "CUB3D") |
| Compared, not borrowed | [hedgeberg/RL78_sleigh](https://github.com/hedgeberg/RL78_sleigh) (MIT, Hedge Berg; marked non-functional by its author and does not load in Ghidra 12.1.4); [zecoxao/yarl78s](https://github.com/zecoxao/yarl78s) (no license; its current spec does not compile on 12.1.4, its old spec is hedgeberg's); [xyzz/ghidra-rl78](https://github.com/xyzz/ghidra-rl78) (MIT, Ilya Zhuravlev; not in the candidate list; 97.6% semantic agreement with objdump on the random corpus) |

No code was copied from the alternatives. Encodings were taken from the RL78 Family User's
Manual: Software (R01US0015, Rev. 2.20) and checked against GNU binutils 2.45; flag semantics
follow the manual.

Ghidra-Rare's changes are separate commits on branch `ghidra-rare` of a fork of the upstream
repository, on top of the upstream history, so the original license and authorship are
preserved.

## Ghidra-Rare changes

Each item names the problem and how it was found.

1. **Instruction set rebuilt and generated** (`tools/gen_rl78.py` writes `rl78.sinc`). Found by
   differential testing against objdump: the upstream spec agreed on 52.9% of random slots and
   49.9% of the opcode corpus. Problems included:
   - `saddr` and `sfr` offsets sign-extended (`0xffe20 + signed byte`); `saddr` 00-1F must map to
     FFF00-FFF1F;
   - `[HL]`/`[DE]`/`[HL+byte]` dereferenced memory twice; `word[B]`/`word[C]` scaled the index by 2;
   - data accesses ignored the F0000 near-area base; the stack was at `zext(SP)`;
   - most `ES:`-prefixed forms missing (144,531 corpus slots objdump decoded);
   - several register operands printed empty (`mov ,A`, `inc `), `#` missing from immediates,
     `[HL+byte]` decoded with the wrong length;
   - `RET` popped 5 bytes; skips used `delayslot` and then jumped into the skipped instruction;
     `CMPS` set CY like `CMP` (the manual also sets it when the values differ or A or X is 0).
2. **Register model.** Registers stay memory-mapped as upstream intended (banks at FFEE0-FFEFF,
   CPU registers at FFFF8-FFFFF) and the bank remains a context field set by `SEL RBn`; PSW
   flags became bit ranges so PSW reads and writes stay consistent. Found by code review;
   checked by the emulator tests.
3. **`segment()` userop and pspec `segmentop`** for near and `ES:` addressing, so the decompiler
   handles 16-bit pointers and stack frames. Found by decompiling the real binaries.
4. **RL78-S1/S2 language** (`RL78:LE:16:S2`): `CE FB xx` is a store on those cores and the
   multiply/divide group on S3. Found comparing against objdump's G13 and G14 ISAs.
5. **ELF opinion** used `e_machine` 40 (ARM) with `e_flags` 197 and a processor name that did
   not match the ldefs, so no RL78 ELF was recognised. Now `EM_RL78` (197), core from `e_flags`.
   Found by real binaries.
6. **pspec**: program counter declared; volatile SFR areas (a UART transmit loop decompiled
   without its data writes); the reset vector is a code pointer, not an entry point. Found by
   real binaries.
7. **cspec**: GCC RL78 calling convention (stack arguments, r8-r15 return in register bank 1,
   callee-saved r16-r21); SFRs are global memory. Found by real binaries.
8. **DWARF register mapping** (`rl78.dwarf`) and GNU external name in the ldefs.
9. **`BRK`** is a returning userop: as a call through the 0007E vector it made the vector's
   value (0 in GCC images) a call target. Found by real binaries.
10. **`ghidra_scripts/RL78Vectors.java`** marks up the vector and CALLT tables of raw images.

Ghidra-Rare-only files (not in the fork): `README.md`, `CREDITS.md`, `build.gradle`,
`extension.properties`, `.gitignore`, `LICENSE` (copied from the upstream repository root) and
`test/`.
