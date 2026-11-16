# SH4ALDSP

Renesas **SH4AL-DSP** processor module for Ghidra (SLEIGH): the SH-4A integer core without the
FPU, plus the SH-DSP unit. This is the CPU of the SH7305/SH73050 in the Casio fx-CG (Prizm,
fx-CG10/20/50) and ClassPad II calculators and of SH-Mobile parts such as the SH7723 and SH7724.
Ghidra's own `SuperH4` decodes the F000-FFFF opcode space as the FPU; on the SH4AL-DSP the same
space holds the DSP data transfers and the 32-bit DSP operations, so these chips need their own
language.

> **Status: verified** (decode differential, every-entry, emulator, real code; details below).

Written clean-room for Ghidra-Rare (MIT). The module was requested in
[issue #1](https://github.com/aleph-void/Ghidra-Rare/issues/1) by @TheRainbowPhoenix, whose
contribution was used only as a feature checklist: its README's feature list and its list of known
approximations were read; its SLEIGH and spec files (derived from Ghidra's Apache-2.0 SuperH4
module and from proprietary Casio/Renesas tools) were not. Ghidra's own SuperH4 SLEIGH was not
read either.

## Languages

| Language ID | Description |
|---|---|
| `SH4ALDSP:BE:32:default` | SH4AL-DSP, big endian (the Casio calculators) |
| `SH4ALDSP:LE:32:default` | SH4AL-DSP, little endian |

Both use the GCC SH ABI (arguments R4-R7 then the stack from offset 0, result in R0, R8-R14
callee-saved, R15 the stack pointer) and gcc's DWARF register numbers. ELF files with
`e_machine` 42 (EM_SH) and the e_flags machine value 6 (`EF_SH4AL_DSP`, what `gcc -m4al
-Wa,-isa=sh4al-dsp` or `as -isa=sh4al-dsp` produce) are detected by the opinion, which wins over
Ghidra's SuperH4 only for those files; SH-4A-nofpu and SH-4-nofpu flagged builds of the same code
still go to SuperH4 (tested).
The language IDs do not collide with Ghidra's or with another module here.

**Casio add-ins (.g3a):** there is no .g3a loader. Import the code part raw: the bytes from file
offset 0x7000 up to the 4-byte checksum at the end, with `SH4ALDSP:BE:32:default` at base address
0x00300000, and disassemble from 0x00300000 (`test/real-g3a.sh` does this). Add-in ELF files built
with `-m4a-nofpu` are flagged SH4A and are claimed by SuperH4; choose `SH4ALDSP:BE:32:default` by
hand for them.

## What the p-code models

- **Integer core:** the SH-1/2/3 instructions, SH-4A's MOVLI.L/MOVCO.L (the LDST link flag:
  MOVCO stores and sets T only after a MOVLI, and clears the link), MOVUA.L, MOVCA.L, SGR, DBR,
  SR with the DSP fields (RC, DSP, DMY, DMX, RF), register banks (switching RB exchanges R0-R7
  with the other bank), delay slots (BSR/JSR/BSRF save PC + 6 when the delay slot is a 32-bit DSP
  instruction), RTE, and TRAPA (TRA and EXPEVT at H'FF000020/24, SPC, SSR, SGR, VBR + H'100).
- **DSP registers:** X0 X1 Y0 Y1 M0 M1 and the 40-bit A0/A1 (A0G:A0 and A1G:A1 are also visible as
  `A0E`/`A1E`); DSR split into DC, CS, V, N, Z, GT, TC, TS, AV, AN, AZ, AGT; MOD, RS, RE.
- **Data transfers:** MOVX/MOVY (word, and the extended word/long forms with R0-R3 and any of
  X0-Y1 when the other side is NOPX/NOPY), MOVS (word/long, all four addressing modes, the guard
  registers), with post-increment, index (R8/R9) and pre-decrement updates, and **modulo
  addressing** (SR.DMX/DMY with MOD's ME/MS; DMY wins when both are set). Y pointers update their
  low word only (manual 6.4.2).
- **DSP operations:** every B-field operation, unconditional and DCT/DCF, with the 40-bit guard
  bits, carry/borrow, overflow and over-range, **saturation** when SR.S = 1 (fixed point, integer
  and PMULS -1.0 x -1.0), the DC bit by DSR.CS, N/Z/V/GT, the **T-bit link** (DSR.TC/TS) and the
  **flag accumulation** (AN/AZ/AV/AGT when DSR[11:8] != 0). Parallel instructions read their
  sources before the parallel loads write and stores see the registers before the operation
  writes (manual figures 6.9 and 6.12). PDMSB uses `lzcount`.
- **Repeat loops:** LDRS/LDRE/LDRC (extended repeat) and SETRC (conventional repeat: the loop
  length is found from RE - RS as in manual table 6.5) mark the loop end in disassembly context,
  and the end instruction decrements SR.RC and branches back to the start, so the decompiler sees
  a loop and the emulator runs it.

## Sources

- Renesas *SH4AL-DSP Software Manual*, Rev. 1.50, REJ09B0002-0150
  (`https://www.renesas.com/us/en/document/mah/sh4al-dsp-software-manual`, SHA-256
  b9fdab486b5e65c64d630df975403411b30d672771a1dd46d9256471f33de9de): the instruction tables of
  section 3, the DSP unit (section 6) and the operation descriptions of section 11 are the
  primary source for encodings and semantics.
- Renesas *SH-4A Software Manual*, Rev. 1.50, REJ09B0003-0150 (SHA-256
  14a2f803a09128cdaf3c5594db8a510adca7747a993e5729d8badc3e97008c18) and *SH-3/SH-3E/SH3-DSP
  Software Manual*, Rev. 4.00, REJ09B0317-0400 (SHA-256
  c9754788627d66cec70b8a292b02bfcea6ba8b57bc755c6d98ce1b48c9f11f7c), for cross-checking.
- The SH-3 integer SLEIGH, emulator harness, decode comparison, real-code and DWARF scripts of
  [aleph-void/ghidra-sh](https://github.com/aleph-void/ghidra-sh) (branch `ghidra-rare`, MIT;
  Copyright (c) 2019 William Hahne, rewritten and verified by Ghidra-Rare), reused and adapted with
  credit in the file headers.
- GNU binutils 2.45 and gcc 14.3 (sh-elf, with newlib 4.5) run only as black boxes:
  `objdump -m sh4al-dsp` as the decode reference, `as -isa=sh4al-dsp` to encode the emulator
  programs, `gcc -m4al` to build the real-code samples and to read off the ABI and the DWARF
  register numbers (R0-R15, PR 17, MACH 20, MACL 21). No binutils or gcc source was read.
- Real code: zlib 1.3.1 and Lua 5.4.7 (built here), and four third-party fx-CG add-ins from GitHub
  releases (below). Fetch scripts pin URL and SHA-256; nothing is committed.

## Results

Bar: [docs/VERIFICATION.md](../docs/VERIFICATION.md). Built and tested on Ghidra 12.1.4 (12.1.3
and 12.2 were not installed on the development machine; the release workflow builds them).

| Area | State |
|---|---|
| Builds | Both specs compile; `.sla` 55 KB each. The 32-bit operation table is generated by `tools/gen_pops.py` and the suite checks that it reproduces the checked-in file |
| Decode vs `objdump -m sh4al-dsp` (binutils 2.45), each byte order | **All 65,536 16-bit words**: 18,256 exact, 40,897 semantic, 5,632 invalid in both, 751 explained. **Every B field (65,536) under 8 A fields**: 111,168 exact, 8,192 semantic, 275,968 invalid in both, 128,960 explained. **Every A field (1,024) under 10 B fields**: 6,727 exact, 1,024 invalid in both, 2,489 explained. **50,000 random 32-bit words**: 14,005 exact, 29,713 semantic, 4,688 invalid in both, 1,594 explained. **0 unexplained.** "Semantic" = same instruction spelled differently (hex vs decimal, `@(addr,PC)` vs a bare address, `bt/s` vs `bt.s`) |
| Every-entry | **374/374** constructors reached (every word and every B field, in the normal and the four repeat-loop contexts) |
| Semantics | **53 hand-computed emulator cases per byte order** (54 in all, one per byte order for MOVUA): SH-4A integer ops (MOVLI/MOVCO, MOVUA, TRAPA, SR with DSP fields, PR = PC + 6 after a 32-bit delay slot), MOVX/MOVY/MOVS in every addressing form incl. index, extended long forms, modulo X and Y and the low-word Y update, the guard registers; PADD, PADDC, PSUBC, PSUB Sy,Sx, PCMP (carry and GE modes), PMULS fractional scaling and saturation, PADD PMULS, DCT/DCF with parallel moves (figure 6.9, true and false), PSHA/PSHL, PDMSB, PRND, PDEC/PINC, PNEG/PABS, PCOPY/PSWAP/PAND, PLDS/PSTS, saturation with AV and the T-bit overflow mode, guard-bit overflow, the DSR flag accumulation (figure 6.6) and T-bit link (figure 6.7), extended (LDRC) and conventional (SETRC, 4- and 1-instruction) repeat loops. Expectations come from the manual's worked examples or are computed by hand. **All pass; a deliberately broken expectation is reported in both byte orders** |
| Real code built here: zlib (example.c) and Lua 5.4.7, `gcc -m4al -O2`, newlib, plus hand-written DSP routines (FIR with an extended repeat loop, MOVS context save, MOVLI/MOVCO, modulo ring copy), big and little endian | 4 ELF files auto-detected as `SH4ALDSP:BE/LE`; 274,700 analysed instructions, **all identical to objdump** at the same addresses; 2,675 functions, **all decompile** (0 failures, 0 timeouts at 20 s). Bad-instruction bookmarks: zlib 1 each, Lua 92 (BE) / 82 (LE), all but 7 directly after a call to a function Ghidra had not yet proved non-returning (`luaD_throw`, `luaG_runerror`); the rest are further words of the same literal pools |
| Real third-party code: fx-CG add-ins [prizm_racing](https://github.com/duarteapcoelho/prizm_racing) v1.4 (MIT), [nesizm](https://github.com/tswilliamson/nesizm) v1.00 (MIT), [bad-apple-cg50](https://github.com/oxixes/bad-apple-cg50) 1.1.0 (Unlicense), [BadAppleCG50](https://github.com/Adamskye/BadAppleCG50) v1 (MIT) | Raw import from the add-in entry: 72,674 analysed instructions, **all identical to objdump**; 435 functions, **all decompile**; 1 bad-instruction bookmark (a literal pool after a call) |
| Spec files | cspec with `<global>` and the GCC prototype; pspec; DWARF map; ELF opinion. Checked with `gcc -m4al -g` in both byte orders: the opinion picks the language, prototypes and parameter storage come out right (R4-R7, stack arguments at Stack[0x0]/[0x4], soft-float `float` arguments in R4/R5), and SH4A-nofpu/SH4-nofpu flagged builds of the same code still go to SuperH4 |

### Explained decode differences (`test/decode-explained.txt`)

`test/compare.py` assigns every difference to a class from the instruction bits, and checks the
display classes value by value:

- **reserved-dz / reserved-ds**: Dz codes 0-4, 6, D, F of the DSP operations and Ds codes 0-4, 6
  of MOVS are reserved (manual tables 6.39, 6.15). objdump prints them as numbers, or for Dz = D/F
  as `a1g`/`a0g` (the MOVS codes); the module rejects them.
- **ignored-field**: objdump ignores operand fields that are fixed for an operation (PCMP's Dz,
  PCLR/PSTS/PLDS's Sx and Sy, the unused source field of the two-operand forms, the
  condition field of the forms that have no unconditional `00` code); the module follows table 6.39.
- **reserved-afield**: an A field with NOPX and NOPY but other bits set (NOPX needs bits 9, 7, 5
  clear, NOPY bits 8, 6, 4). objdump prints `pcmp x0,y0` / `pcmp x1,y1` or `.word` (bug below).
- **shift-imm-unsigned**, **ldrs-ldre-negative**: objdump bugs, below.
- **branch-in-delay-slot**: in random words, a delayed branch in the delay slot of another (a slot
  illegal instruction). Ghidra does not decode a delay-slot instruction that is itself delayed.

### Confirmed bugs in reference tools

- **objdump** prints the 7-bit PSHA/PSHL immediate unsigned: `psha #-5,a1` (assembled by gas to
  B field 17b5) disassembles as `psha #123,a1`. The manual's count is signed (-32..+32, -16..+16).
- **objdump/gas** treat the LDRS/LDRE displacement as unsigned: objdump shows a negative
  displacement 512 bytes too far forward, and gas rejects a backward target with "pcrel too far".
  The manual sign-extends it (range -256..+254 bytes).
- **objdump** prints `pcmp x0,y0` or `pcmp x1,y1` for the reserved A-field bits described above,
  as if they were a second DSP operation.

### Manual errata found (the module follows the reading noted)

- LDRS/LDRE: the operation code writes `PC + disp * 2`, the text says PC + 4 + disp * 2; gas,
  objdump and the module use PC + 4.
- PSHA example (11.4.18) gives FE22222222h for FF88888888h << 2, which cannot end in two 1 bits;
  the case expects FE22222220h.
- The DSR update code accumulates only the flag selected by TS and has unreachable `case 0x0`
  branches; the text and the worked example (figure 6.6: PADD with TS = 001 sets AGT and AV) say
  all four accumulate when DSR[11:8] != 0, which the module does.
- LDS Rm,DSR's code masks the value with 0x0000000F (an SH3-DSP leftover); table 2.4 makes bits
  15-0 writable and figure 6.6 loads TS with LDS. The module writes bits 15-0.
- PMULS's code lists X1 as Sf code 3; tables 3.16, 6.28 and 6.39 list A1. The module uses A1, as
  objdump does.
- Table 3.18 gives PDEC Sy as `10101001xx00zzzz`; section 11.4.10 gives `1010100100yyzzzz`, which
  objdump agrees with.

## Doesn't work (and why)

- SLEEP and LDTLB are pcodeops (power mode and TLB are hardware state). PREF, PREFI, ICBI, OCBI,
  OCBP, OCBWB and SYNCO have no effect: there is no cache in the model (OCBI's loss of dirty data
  cannot be shown with a flat memory).
- **PWAD and PWSB** are decoded (objdump decodes them at the condition-00 codes of POR and PXOR,
  and the manual's table 3.15 names them as unconditional three-operand operations) but their
  result is a pcodeop: no manual describes what they compute.
- Not modelled: privilege and exceptions (user-mode SR write masks, the DSP bit enabling the DSP
  instructions, slot/general illegal instruction exceptions, address errors), interrupts (which
  clear LDST), the MMU and memory-mapped registers other than TRA/EXPEVT.
- SR.RF is not changed by SETRC/LDRC: the manual leaves its values to "internal status".
- X/Y memory accesses use the full pointer value. The hardware puts only bits 15-1 on the X/Y
  bus (X/Y memory at H'A5000000/H'A5010000); with pointers that hold such addresses, as programs
  use them, the access is the same, and the full pointer keeps the CPU's and the DSP's view of the
  same memory at the same address.
- Repeat loops are found from the LDRS/LDRE/LDRC/SETRC instructions in the flow; a loop set up by
  restoring RS/RE with LDC (after an exception) is not followed. Branching into a conventional
  loop (forbidden by the manual) is not modelled.
- Parallel operations that write the same register twice (operand conflicts, undefined in manual
  6.5.15): the module's operation result wins.
- Decompiler: literal-pool bookmarks after calls to functions not yet known to be non-returning
  (as on Ghidra's other SH modules); add-in syscalls through the system-call table show as
  "Treating indirect jump as call".

## Unverified

- No SH4AL-DSP hardware or DSP simulator was available (QEMU has no SH-DSP). DSP semantics are
  checked against the manual's worked examples and hand computation only. Points where the
  manual's code and prose disagree and the module had to choose: the T-bit overflow mode after a
  shift (prose: overflow; code: 0), PABS of a negative 40-bit value whose low word is 0 (the code
  forces a borrow, the module negates exactly), the carry of a shift by 0, saturation of an
  over-range result (the code saturates by bit 39 of the wrapped result, the module too), DC for
  the reserved CS values 110/111 (module: 0), and the order of the two halves of MOVX.L/MOVY.L in
  little-endian memory (module: an ordinary 32-bit access).
- Encodings objdump accepts but the manual reserves are rejected; what the chip does with them is
  not known.
- 12.1.3 and 12.2 builds (not installed locally).

## Tests

```sh
export GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC     # with this module linked (tools/link-modules.sh)
SH4ALDSP/test/run-tests.sh [--real <workdir>]
```

Needs an sh-elf binutils/gcc 2.45/14.3 with newlib (`SH_TOOLS`, default
`~/.cache/ghidra-rare-scratch/tools/x-sh-elf/bin`). `--real` builds zlib and Lua
(`test/build-samples.sh`), fetches the four add-ins (`test/fetch-samples.sh`) and runs
`test/real-check.sh` / `test/real-g3a.sh` on them. The emulator cases are in `test/emu/cases.py`
(the generated `cases.txt` is checked in and the suite checks that it is reproduced).
