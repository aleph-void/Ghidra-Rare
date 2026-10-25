# Status: what works and what doesn't

Last updated 2026-10-23. This is the running ledger for the project. Each module's README has the
details and the exact test commands; this page tracks the state across modules and the lessons learned.

The upstream IDA repositories contain no source code in the repository itself (README, license and
screenshots only). Each module ships as a release zip that this project has deliberately not
downloaded or opened, because its license forbids derivative works. Every module here was written
from vendor documentation or learned from a reference disassembler, so nothing below is inherited
from the IDA work.

Terms used below:

- **Decoded**: Ghidra produces the same instruction as the reference disassembler.
- **Semantics**: the p-code does the right thing (checked by the emulator or the decompiler).
- **Real binaries**: third-party binaries we did not build, imported and analysed headless.
- **TI local**: TI firmware whose license forbids disassembly. The user approved local testing
  only; it is never committed, fetched by repo scripts, or described beyond summary numbers here.

## Modules

### PRU: done

| Area | State |
|---|---|
| Decode, V0–V4 | 100% exact vs GNU objdump (18,443 words); 100% semantic vs TI `dispru` (17,555 words; differences are pseudo-op spellings) |
| Semantics | Full p-code incl. hardware loops; emulator 30/30 |
| Real binaries | BeagleLogic pru0/pru1: disassembly identical to objdump, 0 decompile failures. TI local (6 images): 0 decompile failures, 1 bad-instruction bookmark |
| Doesn't work | V0 `SCAN` (undocumented, no reference tool decodes it). `jmp rX` returns decompile with "treating indirect jump as call". Plainly named asm labels become functions (`PRUFixupTiLabels.java` cleans up). No data refs for LBCO/SBCO with a register offset. A trailing non-returning `jal` makes analysis run off the end of `.text` |
| Unverified | Real V0–V2 firmware |

### MicroBlaze: done

| Area | State |
|---|---|
| Decode | 99.56% (32-bit) / 99.89% (64-bit) of fuzz words vs objdump; every remaining difference traced to objdump bugs |
| Semantics | Emulator 32/32 (32-bit), 44/44 (64-bit) |
| Real binaries | Xilinx pmufw/psmfw/plmfw: 0 bad instructions, disassembly identical to Xilinx objdump, all functions decompile. Bootlin BE `libc.so.6`: identical disassembly, 0 relocation errors, 3,715/3,722 decompile (7 timeouts) |
| Doesn't work | Exceptions/MMU not modelled. Small-data bases r2/r13 not tracked. GOT_64/TLS/COPY relocations reported, not applied |
| Unverified | Any real 64-bit MicroBlaze binary (none public); big-endian 64-bit beyond raw words |

### xCORE: done

| Area | State |
|---|---|
| Decode | XS1 vs LLVM: 99.92% (16-bit), 100% (32-bit). XS2/XS3: ~95% / ~99.5%; all differences are XS2/XS3-only or re-encoded opcodes LLVM lacks |
| Semantics | ALU, memory, flow, XS3 FPU in p-code; resource/channel/port/VPU ops are pcodeops |
| Real binaries | 20 tile images from XMOS releases: 0 bad instructions, 22,471/22,471 branch targets valid, 4,341 functions decompiled with 4 failures (decompiler rejects a −1 sentinel load). XMOS `lib_xud` asm source: 1,025/1,025 instruction groups |
| Doesn't work | Stripped images: dual-issue mode can't be recovered reliably (22 of 25 wrong-mode branches remain). XS2 vs XS3 is not auto-selected (not in the ELF header) |
| Unverified | Some XS2/XS3-only instructions are checked only against the manual tables |

### C7x: done

| Area | State |
|---|---|
| Decode | 100% (C7100/C7120/C7504) and 99.99% (C7524) of decodable fuzz words vs TI `dis7x`, with 0 invalid words accepted; 100% of `cl7x -O2` output on all four cores. Generator is deterministic |
| Semantics | Scalar integer/FP, loads/stores, predicates, branches in p-code; ~880 vector/streaming-engine/MMA ops per core are pcodeops |
| Real binaries | Demo program: 200/200 functions decompile on all four cores. TI local: 99.98–99.99% disassembly agreement, 0 bad instructions, 1 decompile failure in ~2,100 functions |
| Doesn't work | Predicated `VST4D`/`VST16H` offsets print `(0x40)` where `dis7x` prints `(0)`. One C7524 `VAPYSB` form with an `SE0` source. Packet context is lost after an undecodable word (rare now). B0–B15 writes don't clear upper vector bits. The core isn't auto-selected; run `ghidra_scripts/C7xCoreCheck.java`, which reads `.c7xabi.attributes` and names the right language |

### SASS: done (11 variants, Kepler to Blackwell)

| Area | State |
|---|---|
| Decode | Held-out bitsandbytes cubins vs `nvdisasm`: 100.00% (sm_60, sm_70, sm_100), 99.98% (sm_75), 99.99% (sm_86), all but 2 instructions (sm_90, sm_120). Random-word fuzz 98.9–99.9% (128-bit), 94.9–96.6% (64-bit). Own kernels 100% on SM70–SM120, 99.9% on SM35/52/60. cuRAND corpus 100% (local-only check, never committed) |
| Semantics | Integer, memory and control flow in p-code; tensor, texture, conversion and most special-function ops are `sass_*` pcodeops |
| Real binaries | Every bitsandbytes cubin imports with the language the opinion picks (CUDA ≤12 and CUDA 13 `e_flags` layouts) and decompiles with 0 failures |
| Doesn't work | 64-bit variants decode many random words `nvdisasm` rejects. Kepler was learned only from our kernels plus random probes, and prints `ATOM.CAS`'s implicit register pair as a number. Turing prints `RED [UR]` with an `RZ.64` base; one `ULEA.HI.X.SX32` encoding undecoded; float immediates print as hex. Raw 64-bit images need the `ctl` context set per bundle (the cubin loader does it) |
| Unverified | Real third-party Kepler and Maxwell code: no held-out cubins for SM35 or SM52 were tested |

## Planned: clean-room modules for CPUs IDA Pro supports and Ghidra doesn't

From a comparison with IDA Pro 9.1's supported-processor list (2026-10-25). Written here from vendor
manuals, verified against a free reference disassembler run as a black box:

| CPU | Reference disassembler | Status |
|---|---|---|
| Zilog Z8 | MAME `z8` | in progress |
| Philips XA (51XA) | MAME `xa` | in progress |
| ST9 / ST9+ | MAME `st9`, `st9p` | in progress |
| TI TMS320C2x (C25) and TMS320C5x | MAME `tms320c2x`, `tms320c5x` | in progress |
| Intel i860 | MAME `i860` | planned |
| Analog Devices ADSP-218x | MAME `adsp21xx` | planned |
| Motorola DSP56000 and DSP561xx | MAME `dsp56000`, `dsp56156` | planned |
| Renesas RX (v1, v2, v3) | binutils `rx`, `rx:v2`, `rx:v3` | planned |
| Intel IA-64 (Itanium) | binutils `ia64` | planned |

Extensions of community modules: V850E1/E1F/ES into RH850 (binutils `v850e1`), H8SX into the H8
module (binutils `h8300sx`), SH-2E alongside SH-3 (binutils `sh2e`). No reference tool found, so
not started: ST20, Z380, SAM8, KR1878, M7900, 78K0S, F2MC-8L/LC, DSP566xx, TMS320C55x, TX19/TX19A,
Rockwell C39, .NET CIL.

## Community modules

Imported from other authors and verified to the same bar. Each lives in an `aleph-void` fork
(git submodule under `community/`); see its `GHIDRA-RARE.md` and `CREDITS.md`.

### Alpha: done (community: @kkaempf, @mattst88; 15 languages)

| Area | State |
|---|---|
| Decode | vs objdump 2.45 on every opcode-table entry and 50k random words: 21264+ 100% (99.2% exact); 21064 99.87% and 21164 98.23%, the rest traced to 2 confirmed objdump bugs. Every entry decodes (EV4 716/716, EV5 880/880, EV6 670/670). CALL_PAL names vs MAME 128/128 per OS |
| Semantics | Emulator 37/37 (upstream as imported failed 9); 40,000/40,000 random operate instructions agree with qemu-alpha |
| Real binaries | Debian alpha libz, ls, sort, libc, static busybox and QEMU's palcode-clipper: 826,708 instructions identical to objdump, 0 bad instructions, 1,703 relocations applied, 13,649 functions decompile with 0 failures |
| Fixed here | PALcode encodings for all 3 PAL formats, `bis ra,lit,rc` as MOV, ZAP/ZAPNOT, EXTxH, NEGT, RPCC/RC/RS, STS size, FP compares, CALLSYS/RDUNIQ results, reserved opcodes, ELF opinion (signed e_machine), relocation handler, DWARF maps, LP64 cspec, gp seeding, PALcode entry-point script |
| Doesn't work | MVI min/max/PERR, FPCR and IPR accesses are pcodeops. Rounding/trap qualifiers not modelled. VAX FP uses IEEE p-code. LDS/STS convert by value. ~2% of functions lose a switch table. ldgp's double entry gives 2 overlapping functions. gp-relative `.o` relocations not applied |
| Unverified | Real NT/VMS binaries and EV4/EV5 PALcode images (checked against objdump/MAME only) |

### 65816: done (community: @achan1989, @kaayzouee; 65802 added here)

| Area | State |
|---|---|
| Decode | 100% semantic vs MAME's g65816 disassembler (driven with M/X options) in all 5 M/X/E modes; 100% ca65 round trip; every opcode decodes in every mode |
| Semantics | SingleStepTests/65816 25,600/25,600; emulator 45/45; 65802 emulator 8/8; M/X context tracking 23/23; upstream issue regressions 44/44; upstream JUnit 37/37 |
| Real binaries | 13 homebrew ROMs (PVSnesLib examples, snes-test-roms): 45,803 instructions match MAME, widths correct at every traced PC, 892/892 executed references use the DBR/DP MAME saw, 0 decompiler timeouts (was 8) |
| Fixed here | Ghidra 12 cspec, direct calls, XCE (also after REP/SEP #$01), p-code errors, PHP..PLP/PEA width tracking, callee REP/SEP widths reaching callers, WAI/STP as flow, immediates as constants (upstream #10), DBR tracking, vector entry points, the 65802 language, SNES loader with LoROM/HiROM/ExHiROM/SA-1/SuperFX/SRAM; all upstream README limitations and issues addressed |
| Doesn't work (inherent) | Widths decided by run-time data (PLP with no PHP/PEA, XCE after a computed carry); code executed at two widths (one instruction per address); instruction-stream wrap past $xx:FFFF; function pointers passed as data; DP is not carried into callees; SA-1/GSU coprocessor code and mapper switching |
| Unverified | ExHiROM/SA-1/SuperFX maps on real cartridges (only synthetic images are freely available); large commercial-style ROMs |

### ARCompact: done (community: @niooss-ledger, Ghidra PR #3006)

| Area | State |
|---|---|
| Decode | 100% semantic vs objdump (ARC700, ARC600, both byte orders) on every opcode-table entry, every 16-bit halfword and 50k random slots, 0 unexplained; 884/884 constructors. The PR scored 26.8% on the table |
| Semantics | Base ISA with flags, delay slots, zero-overhead loops, `j.f`/`rtie`, extended arithmetic, XMAC 32x16, FPX single, saturating ops; emulator 56/56 per byte order |
| Real binaries | Synopsys arc-2024.12 uClibc (LE/BE) and Bootlin glibc: 8,701 functions, 368,266 instructions identical to objdump, 0 bad, all decompile; libstdc++ 302,490 instructions, 5,712/5,724 decompile (GCC DWARF quirk); relocations match GNU ld |
| Fixed here | Instruction set reworked from differential testing, GCC calling convention, DWARF map, ELF relocation handler and PLT markup, big-endian language (token layout from Jackson Donaldson's fork), stand-alone extension build |
| Doesn't work (inherent) | Undocumented extension ops (XMAC dual-16, CRC, Viterbi, FPX double assist, SIMD byte) are pcodeops: no public definition of what they compute. Customer-defined condition codes 16-31 and EXTnn. TLS relocations reported, not applied (Ghidra has no TLS model) |
| Unverified | Real ARC600 binaries (none freely available) |

### LM32: done (community: @jevinskie, @cyrozap)

| Area | State |
|---|---|
| Decode | 100% of non-explained words vs objdump 2.45 on the opcode table (3,360) and fuzz (50,000), BE and LE; differences are display classes (gp-relative form, unnamed CSRs) and manual-only div/mod. Upstream was at 60% on the table |
| Semantics | Full p-code for ALU, memory, flow, CSRs; emulator 26/26 BE and LE |
| Real binaries | 3 HDMI2USB/LiteX images: disassembly identical to objdump (31,353 instructions), 656 functions, 0 decompile failures, DWARF prototypes import (upstream: DWARF import failed on every function) |
| Fixed here | Operand display, reserved bits, user/gp forms, CSRs as registers, ELF opinion, DWARF map, cspec per GCC ABI, relocation handler |
| Doesn't work | Exceptions, interrupts and cache ops not modelled; `user`/`raise` are pcodeops; FDPIC not handled; ~200 DWARF line-table bookmarks per image (a generic Ghidra issue) |
| Unverified | Stack-argument offsets on real code; relocation types 8/16/GOTOFF/dynamic; the LE language on real binaries (no LE hardware exists) |

### SPC700: done (community: @qwertymodo; spec regenerated here)

| Area | State |
|---|---|
| Decode | 100% semantic vs MAME's spc700 disassembler (Sony syntax) on 3 corpora of 16,384 records; bass re-assembles 100% of the 65816-style variant's output; every opcode decodes in both variants |
| Semantics | SingleStepTests/spc700 255,995/256,000 on both variants (the 5 failures are instructions whose bytes wrap past $FFFF, which Ghidra can't decode); emulator 47/47; PSW.P context 13/13; loader 4/4 |
| Real binaries | SNESMOD driver (PVSnesLib, MIT), 1 build and 3 MAME dumps: all 6,169 instructions match MAME, 1 decompiler timeout each (the command dispatcher) |
| Fixed here | Both variants generated from one opcode table; p-code rewritten (dp operands, stack page, CALL/TCALL/BRK, flags, MUL/DIV/DAA/DAS); PSW.P tracked through PUSH/POP PSW; SLEEP/STOP halt; 16-bit return addresses; loader entry points, DSP register block and option checks. Upstream issues #1 (`JMP [!a+X]`) and #2 (INC/DEC flags) proven fixed by emulator cases |
| Doesn't work (inherent) | The engine entry point can't be found automatically (the IPL's entry word is overwritten and no prologue pattern is reliable; see the README). DSP/timer behaviour and Sony's IPL ROM overlay aren't modelled. Bounded jump tables time out the decompiler (switch recovery, outside the module) |
| Unverified | Commercial sound drivers (deliberately not used); any second open-source driver |

### Micronova (Data General microNOVA): done (community: @pkooiman)

| Area | State |
|---|---|
| Decode | All 65,536 words vs MAME's Nova disassembler: 0 unexplained (2,110 microNOVA-specific encodings checked against the DG manual and novadis); 108/108 constructors; dga assembler corpus 1,180/1,240 (60 dga bugs) |
| Semantics | ALC/carry/skips, every addressing mode incl. indirect chains and auto-increment, hardware stack/SAV/RET, MUL/DIV, TRAP, CPU device; emulator 45/45 (upstream 18/45) |
| Real binaries | Nova SOC mini monitor (GPL-3 source listing): 194 instructions identical to MAME and the source, 0 bad, 10/10 decompile |
| Fixed here | PC-relative indirect depth, JSR's AC3, TRAP decoding (2,048 words decoded as ALC), 1,530 valid words rejected, MUL/DIV/SAV/RET/CPU I/O semantics, carry and interrupt registers, operand syntax, pspec/cspec, stale README |
| Doesn't work (inherent) | Device I/O, interrupts, RTC and HALT are pcodeops (external hardware); the stack-overflow interrupt isn't raised; returns through a memory cell (`JMP @cell`) decompile as computed jumps |
| Unverified | Real DG microNOVA software (MP/OS, DTOS and diagnostics aren't freely licensed); mN602 differences |

### OpenRISC 1000: done (community: @smaeul, @Spritetm)

| Area | State |
|---|---|
| Decode | 100% of non-explained words vs objdump 2.45 on the opcode table (6,090) and fuzz (50,000), BE and LE; differences are 3 documented classes (manual-only `l.lf`/`lf.stod.d`/`lf.dtos.d`, `l.muldu` 0xc vs binutils 0xd, register pairs past r31) |
| Semantics | Full p-code incl. ORFPX32/ORFPX64A32 on register pairs; emulator 33/33 BE and LE |
| Real binaries | Bootlin glibc (libc, libm, ld.so, static ldconfig) and a Linux kernel: disassembly identical to objdump (1.31M instructions), 14,303 functions, 0 decompile failures, relocations 0 errors |
| Fixed here | Delay slots on BE, `l.jal`/`l.jalr` link address, PC-read `l.jal 8`, reserved bits, shift fields, the whole FPU, `l.sys`, `l.cmov`, ELF opinion, DWARF map, relocations, PLT thunks |
| Doesn't work | glibc `vfprintf` computed-goto tables (49 `.rodata` words disassembled). Kernel exception vectors not auto-disassembled. SR flag bits are separate registers, so `mfspr`/`mtspr SR` doesn't see them. TLS/GOT relocations reported, not applied. `l.muldu` as GNU as encodes it (0xd) doesn't decode |
| Unverified | LE/no-delay-slot language on real binaries (hx330x images have no public license); `R_OR1K_16`/`8` relocations vs ld |

### RH850 (V850E2/E3): done (community: @esaulenka and contributors)

| Area | State |
|---|---|
| Decode | 100% semantic vs GNU objdump on the full binutils opcode table, all first halfwords and 100k random words, RH850 and V850E2M; every objdump-only encoding is an objdump bug. 556/556 and 374/374 constructors reached. Ghidra's built-in V850 `v850e3v5` language scores 73% on the same opcode table; upstream as imported 92% |
| Semantics | Integer, flags, saturation, loads/stores incl. 23-bit, LD.DW and post-increment, PREPARE/DISPOSE, PUSHSP/POPSP, LOOP, SWITCH, LDL/STC, FPU single/double; emulator 51/51. System, debug, hypervisor, TLB, cache and DSP-extension ops are pcodeops |
| Real binaries | 6 GCC-built ELFs (Lua, zlib; V850E2V3 and RH850): 301,610 instructions, 0 bad instructions, 3,290/3,290 functions decompile, disassembly identical to objdump. On the Lua build Ghidra's built-in module leaves 117 KB undisassembled; this one 138 bytes |
| Fixed here | Renamed to RH850 (IDs collided with Ghidra's V850 by case), FPU generated from a table, condition operands, SLD sign extension, SST order, shifts, system registers and G4MH instructions, GCC's E2 indirect-call sequence, cspec/DWARF/opinion, CALLT resolution script (upstream issue #20); upstream issues #40, #42 and README TODOs |
| Doesn't work | Shares EM_V800/EM_V850 with Ghidra's V850 module. libgcc `__save_*` helpers return via `jmp [r10]` (10 unrecovered jumps per E2 image). FPU conversions ignore the rounding mode. CALLT needs `RH850CallT.java` |
| Unverified | G4MH post-increment/decrement loads/stores (no reference tool decodes them); CC-RH/GHS output; third-party firmware |

### RL78: done (community: @CUB3D; instruction set rebuilt here)

| Area | State |
|---|---|
| Decode | 100% semantic on 60,000 random slots and 99.80% on the full opcode corpus vs GNU objdump (G13 and G14 ISAs); every difference is a confirmed objdump quirk. Every constructor reached (466/466, 452/452). Upstream was at 52.9% |
| Semantics | Full p-code incl. flags, ES:, skips, register banks, S3 multiply/divide/MAC; emulator 56/56 |
| Real binaries | 11 GCC-built ELFs from public source (msalau samples, FreeRTOS, newlib): 0 bad instructions, 357/357 functions decompile, disassembly identical to objdump |
| Fixed here | Instruction set regenerated from the RL78 manual; S1/S2 language; ELF opinion (EM_RL78, core from `e_flags`); PC, segment op and volatile SFRs; GCC calling convention; DWARF map; vector/CALLT markup script |
| Doesn't work | GCC's absolute `__rl78_abs__` symbol becomes a bogus function at the reset vector. Only the GCC calling convention. Flash mirror (MAA) not modelled. BRK is a returning userop. Register bank only follows SEL along the flow |
| Unverified | CC-RL/IAR output, RL78-S1 (G10) images, third-party prebuilt firmware (none freely licensed found) |

### TMS34010: done (community: @ZPaul2Fresh8; instruction set rewritten here)

| Area | State |
|---|---|
| Decode | 0 unexplained differences vs MAME on all 65,536 opcodes and 50,000 random slots; 330/330 constructors reached; NetBSD gspa assembler corpus 1,644/1,644 vs source. Upstream: 86.4%, and its pspec didn't load in Ghidra 12 |
| Semantics | Full p-code incl. bit-addressed fields and all graphics ops (PIXT, DRAV, LINE, FILL, PIXBLT with PPOP, transparency, plane mask, window modes); emulator 98/98 (20 from the User's Guide); 137 MAME graphics vectors match (18 differ only in B10-B14 scratch) |
| Real binaries | NetBSD A2410 grf_ultms program (BSD): 259/259 instructions identical to MAME and to source, 0 bad, decompiles |
| Fixed here | Module layout, instruction set rewrite, memory model, pspec/cspec, symbol scripts for bit addresses, vector script; all README/TODO limitations from upstream |
| Doesn't work | Interrupts and PBX resume not modelled (block ops run atomically). Bit-addressed pointers decompile as `*(p>>3)`, so no stack frames or stack parameters. Field sizes unknown at function entry until a SETF. No TI COFF loader. TMS34020 not covered (gap pass queued) |
| Unverified | Commercial arcade/TIGA code (not freely licensed), TI C compiler output, PIXBLT/FILL W=1/W=2 and PBV with L,L (MAME doesn't implement them) |

## Lessons

### What worked

1. **Differential testing against a reference disassembler on two corpora**: every encoding a
   toolchain can emit (assembler-enumerated or table-enumerated) plus tens of thousands of random
   words. Score exact text and semantic equivalence separately, and bucket differences by class.
2. **Generating SLEIGH from tables instead of hand-writing it** (PRU, xCORE, C7x, SASS, MicroBlaze
   stream ops). Fixes go into the generator and every variant picks them up.
3. **Learning encodings from an oracle when there is no documentation.** SASS flips each bit of a
   seed word and diffs `nvdisasm` output to find fields; C7x probes `dis7x` to infer fields and
   extension rules.
4. **Real third-party binaries.** Every module had bugs that only real binaries exposed: halt
   semantics, volatile I/O registers, entry point 0, toolchain label symbols, DWARF register maps,
   relocations, 64-bit argument pairs, syscalls, dual-issue mode markers, shadowed opcodes, and
   operand order.
5. **An encoding-coverage test that enumerates every table entry.** Differential fuzzing misses an
   opcode that neither side decodes, because "both undefined" counts as agreement (xCORE `VFTFF`).
6. **Vendor assembly source as an oracle** for operand order and branch-offset rules when no tool
   decodes an instruction (xCORE `crcn`, dual-issue branches).
7. **Emulator checks of p-code** with hand-computed expected register and memory values.

### What didn't, or cost time

- **Reference tools have bugs.** objdump prints `bslli`/`bsrai` as `bsrli`; LLVM prints xCORE
  `CHKCTI` immediates differently from the manual. Confirm in the tool's source or the manual
  before "fixing" the module to match.
- **Ghidra limits.** `.sla` files over 16 MB don't load (PRU unaligned bursts). `sleigh -a` on
  several large specs was OOM-killed; compile one at a time. 128-bit tokens can't have a field
  crossing bit 64. Ghidra ignores an ELF entry point of 0.
- **Spec-file traps.** A cspec without `<global>` makes every decompile fail (C7x). A missing
  `.dwarf` register mapping makes DWARF import fail on every function (MicroBlaze, xCORE).
  Unaligned subregister pieces cause "Cannot properly adjust input varnodes" (PRU). Halt/stop
  instructions modelled as terminators hide code a host resumes into (PRU).
- **Opinion files only see `e_machine` and `e_flags`.** Variants recorded in sections, notes or
  build attributes (xCORE, C7x, TI PRU) need a script or loader extension; `e_flags` layout also
  changed between CUDA 12 and 13.
- **SLEIGH doesn't backtrack.** A root constructor whose subtable has no matching alternative makes
  the decode fail instead of trying another root constructor (microNOVA TRAP vs ALC). Put such
  exclusions in the root pattern.
- **Size blow-ups in generated SLEIGH.** SASS's first Maxwell spec produced an 11.9 MB `.sinc`, and
  SM35/SM75 hit SLEIGH's constructor limit (Kepler had 80k constructors before modifier groups that
  were really immediates were collapsed into one computed constructor; now ~6.5k). Above ~45k constructors Ghidra's `.sla` decoder
  failed; the generator now splits into smaller segments. Check constructor count and `.sla` size
  per variant before wiring it up.
- **Register-file width can change between generations.** Blackwell widened uniform-register
  fields from 6 to 8 bits (URZ 63 to 255); a fixed register table made Ghidra reject every
  instruction using UR63 or above and capped Blackwell fuzz at 83–87% until it was keyed on field
  width.
- **Non-deterministic generators** make reruns regress silently (C7x). Fix seeds and sort.
- **Generated constructors can shadow hand-written ones.** C7x's generator learned its own
  `RET`/`RETS` as plain pcodeops; SLEIGH preferred them, every function ran into the next and
  analysis of one firmware image timed out. Keep flow instructions hand-written and make the
  test suite fail when no call or return flow is recognised.
- **Build plumbing.** Ghidra's `buildExtension.gradle` copies every jar under
  `Ghidra/Processors` into `lib/`, shadowing other modules' classes; set
  `copyDependencies.enabled = false`. Ghidra 12 has no Jython (Java GhidraScripts only). The
  distro JDK 21 package here is a JRE without `javac`.
- **Environment.** `/tmp` is a tmpfs with a per-user quota; a gcc cross-build failed there. Large
  scratch data now lives in `~/.cache/ghidra-rare-scratch`.
- **Sample licensing.** TI's firmware license forbids disassembly; XMOS and NVIDIA binaries have
  their own terms. Record each sample's license and fetch freely licensed ones by pinned URL and
  SHA-256 instead of committing them.
