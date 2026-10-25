# Credits: WDC 65816

## Upstream

- Repository: https://github.com/kaayzouee/ghidra-65816
- Commit: `dbe194026a4b810e9224cc9a4092de2798c67866` (2026-10-21, "Merge pull request #15")
- Ghidra-Rare fork: [aleph-void/ghidra-65816](https://github.com/aleph-void/ghidra-65816/tree/ghidra-rare), branch `ghidra-rare`, commit `77b4520e4cbb6d55c5b5ffba7ddd64ff82ce84b2`
- License: MIT (`LICENSE`, copyright 2019 achan1989, 2026 kaayzouee)

## Original authors

The SLEIGH specification was written by **achan1989** (Adrian Chan, GitHub
[@achan1989](https://github.com/achan1989)) in
[achan1989/ghidra-65816](https://github.com/achan1989/ghidra-65816) (MIT, 2019; archived in
2024 at commit `b70cb21d5297ebae8dee54e5d140bacd612d670c`). **Greg Kennedy**
([@greg-kennedy](https://github.com/greg-kennedy)) contributed a fix to `658xx.sinc` there
(commit `6df2b00`, 2021).

kaayzouee/ghidra-65816 is a continuation of that repository with its full history: the 75
achan1989/Greg Kennedy commits followed by 20 commits by **Kay**
([@kaayzouee](https://github.com/kaayzouee), 2026) that fix instruction semantics (CMP/CPX/CPY
carry, CPY width selection, XBA, transfer flags, BRK/COP bank and B flag, STP flow, XCE in native
mode, emulation-mode status images, PLP/RTI index cleanup), make jumps and calls computed, and
add regression tests and CI. Its SLEIGH is therefore *not* identical to achan1989's: 145 lines
of `658xx*.sinc` differ, all from Kay's commits.
[saffronisa/ghidra-saffron](https://github.com/saffronisa/ghidra-saffron) is an unmodified copy
of achan1989's repository (same HEAD `b70cb21`).

Commit authors (from `git log`): achan1989 `<achan1989@gmail.com>` (74 commits), Kay
`<kaayzouee@gmail.com>` (20), Greg Kennedy `<kennedy.greg@gmail.com>` (1).

## What Ghidra-Rare changed

Each change is a commit on branch `ghidra-rare` of a fork of kaayzouee/ghidra-65816; the module
here is a copy of that branch's processor files.

1. **cspec** (`2d2f11f`): Ghidra 12 refused to load `65816.cspec` (`unexpected attribute
   "type"`), so the language could not be used at all. New `__near` (JSR/RTS, default) and
   `__far` (JSL/RTL) prototypes passing C/X/Y and returning C.
2. **Direct jumps and calls** (`7985af3`): absolute `JMP`/`JML`/`JSR`/`JSL` were computed
   (`goto [x]`/`call [x]`), so the disassembler never followed them and called code was not
   found. They are direct again; only the indirect forms stay computed. The absolute operand
   shows the full 24-bit target.
3. **XCE decode mode** (`fb8f462`): the disassembly action `ctx_EF=CF` cannot read the run-time
   carry and always produced 0, so code after `sec; xce` was decoded in native mode with 16-bit
   widths. A one-instruction (`noflow`) carry context set by `CLC`/`SEC` now selects emulation
   (M=X=1) or native mode after `XCE`.
4. **PER/WDM display** (`5bc71ec`): `PER` shows the pushed address, `WDM` its signature byte.
5. **P-code errors found by emulation** (`dc81958`): 16/24-bit pushes (`PHA` in 16-bit mode,
   `JSR`, `JSL`, `PEA`, `PEI`, `PER`, `BRK`, `COP`) failed in the emulator because a nested
   macro local captured the caller's local of the same name; 16-bit pulls (`RTS`, `RTL`, `RTI`,
   `PLA` in 16-bit mode) wrote bytes into a 2-byte temporary that the emulator rejects; `PHP`,
   `BRK` and `COP` pushed an uninitialised status byte with M/X read from the wrong bits of
   `contextreg`, and the emulation-mode direct-page wrap read E the same way and never applied.
   The decode-time `ctx_MF`/`ctx_XF`/`ctx_EF` are now passed to those macros.
6. **PHP/PLP and PEA/PLP context tracking** (`5759dd9`): `PLP` left the decode widths unchanged,
   so code after a `PLP` that restores 8-bit widths was mis-decoded; in snes-test-roms the reset
   routine decoded a data byte as `BRA` after `pea $xx30; plp` and Ghidra's flow repair removed
   the whole routine. `PHP` now saves M/X in flow context and `PLP` restores them; a `PEA` just
   before `PLP` supplies the pulled byte.
7. **SNES ROM loader** (`ec93195`, `src/main/java/ghidra65816/SnesRomLoader.java`): the opinion
   file named a "SNES ROM" loader that did not exist. LoROM/HiROM detection from the internal
   header, ROM, mirrors, WRAM and I/O mapping, and the vectors as entry points with the right
   decode context.

Ghidra-Rare-only files (not in the fork): `build.gradle`, `extension.properties`, `README.md`,
`CREDITS.md`, `test/`.

## Test inputs and tools (not redistributed)

- MAME `g65816` disassembler (`src/devices/cpu/g65816/g65816ds.cpp`, BSD-3-Clause, Karl
  Stenerud), fetched at tag `mame0285` by `test/build-mame-dis.sh`.
- cc65 `ca65`/`ld65` (zlib) for the assembler round trip and the test programs.
- [SingleStepTests/65816](https://github.com/SingleStepTests/65816) (MIT), commit `307c63f`.
- PVSnesLib 4.6.0 example ROMs ([alekmaul/pvsneslib](https://github.com/alekmaul/pvsneslib), MIT;
  library zlib) and [undisbeliever/snes-test-roms](https://github.com/undisbeliever/snes-test-roms)
  20210217 (MIT), fetched by `test/fetch-real-samples.sh`.
