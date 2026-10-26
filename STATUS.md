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

### Z8: done

| Area | State |
|---|---|
| Decode | 0 unexplained differences vs MAME on the opcode corpus and 50,000 random slots, across six RP contexts; 410/410 constructors reached. MAME's D7 operand order and four CMOS opcodes differ from the Zilog manual |
| Semantics | Arithmetic, flags, control flow, register-pointer selection, separate code/data/register-file spaces and both stack modes; emulator 102/102 internal-stack and 96/96 external-stack |
| Real code | Seven freely licensed assembler sources: 698/698 listed instruction forms decode without boundary conflicts; five analysed programs have 1,622 instructions identical to MAME, 38/38 functions decompile, 0 bad-instruction bookmarks |
| Doesn't work | Peripheral behavior, interrupt timing, HALT/STOP and watchdog side effects are not modeled in p-code |
| Unverified | Behavior on physical Z8 hardware; choose the external-stack language explicitly for devices configured that way |

### ST9 / ST9+: initial support complete

| Area | State |
|---|---|
| Decode | 158,752 records per variant vs MAME, 0 unexplained differences; every constructor reached (961/961 ST9, 983/983 ST9+) |
| Semantics | Byte/word arithmetic, flags, working registers, calls, stacks and ST9+ segmented code have p-code; 17/17 emulator cases per variant |
| Analysis | Fixed-vector analyzer; original smoke program: 11/11 instructions, 3/3 functions decompile on both variants, 0 error bookmarks |
| Doesn't work | ST9+ DPR physical data-memory mapping, peripheral behavior, interrupt timing, HALT/WFI side effects |
| Unverified | No freely licensed third-party ST9 firmware found; most p-code forms have not been checked against hardware |

### XA (Philips 51XA): done

| Area | State |
|---|---|
| Decode | 262,144 slot records per configuration (every first/second byte pair × 3 operand tails, plus 65,536 random) vs MAME in native/DS tracked, native/DS dynamic and page 0: 0 unexplained. 224,711 agree (68,090 both invalid), 9,433 confirmed MAME bugs, 27,220 encodings MAME accepts that the user guide forbids, 780 odd FCALL/FJMP targets. 3,658/3,658 constructors reached |
| Semantics | ALU/flags (PSW write precedence), all addressing modes with DS/ES/SSEL segments and DS tracking, bits, shifts/rotates/NORM/DA, mul/div, CJNE/DJNZ, PUSH/POP lists, USP, call/trap/RETI frames; emulator 160/160 per language (80 cases × 2 DS modes), broken expectation detected |
| Real code | asxa 1.12 example programs (assembled with asxa as a black box, fetched by pinned URL + SHA-256): listing-guided disassembly identical to the assembler source on every statement compared (e.g. 1,271/1,272, 1,259/1,260, 263/271; the rest skipped, 0 different); 0 MAME differences beyond its bugs; 146/146 functions decompile |
| Doesn't work | Register banks (one R0–R3), user-mode stacks (R7 = system SP), 80C51 compatibility mode, odd-address word alignment, interrupts/peripherals. Emulation needs a `segment` user-op callback. Inline-argument calls decode the string as code; table-dispatched monitor commands are not reached by auto-analysis |
| Unverified | No freely licensed third-party XA firmware or compiled C (SDCC xa51 not built); hardware behavior |

MAME `xa` bugs confirmed against the manual: RR/RRC count field, ASR #imm and RLC field decoding, MOV [Rd],dir / dir,[Rs] pointer bits, XCH Rd,dir register bits, 16/8 divide operand sizes, byte register name in CJNE.w Rd,#imm, #data8 read from the wrong byte after a 16-bit offset, data-memory bit addresses offset 20h twice. asxa bug: XCH Rd,[Rs] assembles with the pointer in the wrong bits.

### TI TMS320C2x / C5x: initial support complete

| Area | State |
|---|---|
| Decode | 98,304 records per family vs MAME, 0 unexplained (C2x 5,636 and C5x 18,364 explained: reserved ARU 011, MAME's MPYU-as-MPYS, no `MPY #k`, bit-7 and length quirks); every constructor reached (448/448 C2x, 1,655/1,655 C5x); round trip through c5xasm (91,684 records) and AS (84,298): 0 unexplained |
| Semantics | Arithmetic with carry, overflow and saturation, product shifter, indirect and bit-reversed addressing, RPT/RPTB/XC, delayed branches (C5x), block moves, status registers, optional C5x circular buffers; 41 emulator cases per language, a deliberately broken expectation per family is detected; run-time ARP/DP/SXM/OVM/PM fallback |
| Real code | MIT C25 program and dump routine plus 9 TI-assembled C5x examples: 0 error bookmarks, all functions decompile, listing identical to MAME apart from the explained classes; c5xlnk COFF .out loads as C5x; relocatable .obj relocates correctly |
| Doesn't work | Peripherals, interrupts, pipeline effects, CNF/OVLY RAM remap; C2x COFF must be picked manually (opinion offers C5x); COFF data sections are not moved to the data space |
| Unverified | No hardware or TI firmware check; C26 CONF and C2xx-only encodings are tested only against MAME and AS |

### Renesas RX (RXv1/RXv2/RXv3): done

| Area | State |
|---|---|
| Decode | 1,048,576 slot records per language (16 corpora) vs objdump -m rx/rx:v2/rx:v3: 0 unexplained. RXv3: 485,991 agree, 516,298 both invalid, 46,287 explained (about 45,800 reserved encodings objdump accepts, 413 BFMOV and 60 MVTDC objdump bugs). 1,246 / 1,346 / 1,681 constructors reached (all) |
| Semantics | Full p-code incl. flags, all addressing modes, string ops/RMPA as loops, 72-bit accumulators with RACW/RACL/RDAC* saturation, FPU with ROUND modes, MOVLI/MOVCO, BFMOV, DFPU. INT/BRK/WAIT/SAVE/RSTR are user ops. Emulator 59/59 (v1), 68/68 (v2), 72/72 (v3); broken expectation detected |
| Real code | Own builds of public source (GCC 14 rx-elf + newlib: tour.c ×4 configs, zlib 1.3.1 example/minigzip) and assembled RXv2/RXv3 routines: 199,166 instructions identical to objdump, 1,760/1,760 functions decompile, 0 bad-instruction/relocation bookmarks; relocatable objects import with 0 relocation errors |
| Doesn't work | USP/ISP switch by PSW.U, user-mode write protection, FPSW/DPSW exception flags, register banks, big-endian data mode. ELF without an RXv2/RXv3 flag loads as RXv3 (GNU ld drops the bit). Ghidra's DWARF reader gives ~100-130 error bookmarks per -g image (gas line_range 242) |
| Unverified | No freely licensed third-party RX firmware; GCC 14 can't target RXv2/RXv3, so those are checked only with assembled code and the corpora; no hardware comparison |

objdump bugs confirmed against the manual: BFMOV slsb/width, MVTDC field order (gas encodes it the same wrong way). Encodings the manual doesn't list decode as invalid even where objdump accepts them.

### Intel i860 (XR/XP): done

| Area | State |
|---|---|
| Decode | 589,824 corpus words vs MAME per language: 0 unexplained (XR: 487,387 agree, 63,571 both invalid, 38,866 explained: MAME accepts misaligned pairs, undefined control registers, reserved core-escape and FP precision/P encodings, plus confirmed MAME bugs). 1,154/1,154 GNU as forms identical to source; 709/709 (XP) and 683/683 (XR) constructors reached |
| Semantics | Full p-code for core, FP, graphics and all 62 dual-operation data paths. Delay slots incl. annulled bc.t/bnc.t; dual-instruction mode tracked in the disassembler context with the 8.6.1 CC rules; adder/multiplier/graphics/load pipelines as registers. Emulator 68/68 (XP), 67/67 (XR); 19/19 kernel runs (pipelined dot products in dual mode, z-buffer) |
| Real code | No freely licensed third-party i860 binaries exist. 36 GCC 4.0.4 builds of zlib 1.3.1 and Embench-IoT 1.0 (old port patched just enough to build, test/real/patch-gcc.py): 132,259 instructions identical to objdump, 0 bad, 2,675/2,675 functions decompile; relocations 24/24 identical to GNU ld |
| Doesn't work | Traps/bri trap return, KNF/DS, paging, caches, FP exceptions and rounding modes, big-endian mode; frcp/frsqr are exact (hardware ~8 bits); mixed single/double multiplier pipelines; dual-mode switches across branches assume steady state; GOT relocations not applied; ~30 DWARF line bookmarks per program (Ghidra line_range bug) |
| Unverified | Third-party i860 code (NeXTdimension, Paragon, iPSC/860 software is not free); XP-only instructions vs a second disassembler (MAME lacks them; checked with GNU as/objdump); hardware behaviour |

MAME i860 bugs confirmed against the manual: control-register codes shown as code & 7; core-escape opcodes decoded by bits 1-0 (stio→lock, ldint→calli); intovr and unlock not decoded; pfeq.dd printed as pfeq.ds; reserved PFMAM data-path code 1111 printed as mm12tpm; spellings ppfld, pstd.d, pfmul3.ddss. GNU as sets flush bit 2, which the manual says must be zero, so the module ignores those bits.

### ADSP-218x: done

| Area | State |
|---|---|
| Decode | All 16,777,216 instruction words vs MAME `adsp21xx`: 0 unexplained. 14,726,146 agree, 793,587 invalid on both sides. 1,257,483 differ: 996,863 manual-reserved encodings MAME decodes, 261,120 from 2 confirmed MAME bugs, 244 MAME omissions (TOPPCSTACK, IDLE, ENA/DIS INTS, empty mode control). 800/800 constructors reached |
| Semantics | ALU/MAC/shifter with flags and MSTAT modes, unbiased MR rounding, SAT MR, DIVS/DIVQ, read-before-write multifunction instructions, circular-buffer and bit-reverse addressing, DO UNTIL zero-overhead loops, PC/loop/count/status stacks as register files. Emulator 78/78, broken expectation detected |
| Real code | Two MIT-licensed VisualDSP++ ADSP-2181 executables (pinned URL + SHA-256) through the DXE loader: 620/620 analysed instructions identical to the assembler source, 612 identical to MAME plus 8 MAME omissions, 58/58 functions decompile, 0 error bookmarks |
| Doesn't work | Secondary register bank (one register set); interrupts, timers, SPORT/DMA and flag pins are plain registers or user ops; PMOVLAY/DMOVLAY overlays and BIASRND not modelled; decompiler assumes L = 0 and reset MSTAT modes at function entry; DWARF in DXE files not imported; DXE layout comes from reading linked files |
| Unverified | Hardware or simulator behaviour; MR rounding at the exact midpoint (the manual's two descriptions disagree); whether `IF NOT CE CALL` decrements CNTR; 218x variants other than the 2181 |

MAME `adsp21xx` bugs confirmed against the manual: AMF 01101 (`MR − xop·yop (SU)`) printed as `(SS)`; type 9 constants with YY = 11 decoded as Y = 0.

### DSP56000 / DSP56156: done

| Area | State |
|---|---|
| Decode | DSP56000: 1,243,248 two-word slots vs MAME (every non-parallel word, every parallel-move field, every ALU opcode, 65,536 random), 0 unexplained: 394,967 agree, 336,125 both invalid, 344,626 encodings the manual leaves undefined (MAME accepts them), 164,850 confirmed MAME bugs, 2,080 DSP56002 instructions MAME lacks. An independent manual-derived validity table agrees on every slot. DSP56156: 261,285 slots, 0 unexplained. Constructors reached: 1,030/1,030 and 1,589/1,589 |
| Semantics | Data ALU with real flags, scaling, data-shifter limiting and convergent rounding (plus DSP56156 saturation and rounding modes); three-phase parallel moves; linear/modulo/bit-reverse AGU; system stack; REP/REPcc and DO/DO FOREVER loops. Emulator 79/79 (DSP56000; 77 hand encodings confirmed with asl) and 54/54 (DSP56156); broken expectation detected |
| Real code | DSP56000: Motorola BBS software, 10 shipped LODs plus 65 programs assembled with Motorola's ASM56000 (run as a black box): 5,179/5,179 listing statements identical to the assembler source; MAME at 5,446 listed addresses 0 unexplained; 135/135 functions decompile; 51 bad-instruction bookmarks (48 flow off the end of test programs, 3 data tables at P:0). DSP56156: the 34 DSP56100-manual benchmarks via ASM56100: 549/549 statements identical, 749/749 functions decompile |
| Doesn't work | Interrupts, peripherals, STOP/WAIT/RESET/SWI/DEBUG (user ops), stack-overflow flags, the DSP56002 double-precision mode; nested DO loops ending on the same LA; "unpredictable" modulo offsets wrap once; no .cld (COFF) loader (convert with cldlod); DSP56156 IMPY/IMAC special flags approximated, DO SP/SSL counts not modelled |
| Unverified | Hardware behaviour; DSP56002-only instructions (MAME and asl lack them); third-party DSP561xx binaries (none found) |

MAME bugs confirmed against the manuals and the assemblers: dsp56000: XY-move Y mode/register taken from the X fields; MOVEP pp address bits; Tcc S1,D1 table; accumulator source of ADD/SUB/TFR/CMP omitted; absolute-address extension word ignored in class I/II moves, bit ops and REP; reserved bits/codes accepted. dsp56156: no BF* instructions or (R2+xx) forms; dual-read multiply sources printed reversed; don't-care bits must be zero; SHFL/SHFR decoded at 15Dx/15Fx (in neither manual).

## Planned: clean-room modules for CPUs IDA Pro supports and Ghidra doesn't

From a comparison with IDA Pro 9.1's supported-processor list (2026-10-25). Written here from vendor
manuals, verified against a free reference disassembler run as a black box:

| CPU | Reference disassembler | Status |
|---|---|---|
| Zilog Z8 | MAME `z8` | done (see above) |
| Philips XA (51XA) | MAME `xa` | done (see above) |
| ST9 / ST9+ | MAME `st9`, `st9p` | initial support complete (see above) |
| TI TMS320C2x (C25) and TMS320C5x | MAME `tms320c2x`, `tms320c5x` | initial support complete (see above) |
| Intel i860 | MAME `i860` | done (see above) |
| Analog Devices ADSP-218x | MAME `adsp21xx` | done (see above) |
| Motorola DSP56000 and DSP561xx | MAME `dsp56000`, `dsp56156` | done (see above) |
| Renesas RX (v1, v2, v3) | binutils `rx`, `rx:v2`, `rx:v3` | done (see above) |
| Intel IA-64 (Itanium) | binutils `ia64` | planned |

Extensions of community modules: V850E1/E1F/ES into RH850 (binutils `v850e1`), H8SX into the H8
module (binutils `h8300sx`), SH-2E alongside SH-3 (binutils `sh2e`). No reference tool found, so
not started: ST20, Z380, SAM8, KR1878, M7900, 78K0S, F2MC-8L/LC, DSP566xx, TMS320C55x, TX19/TX19A,
Rockwell C39, .NET CIL.

## Community modules

Imported from other authors and verified to the same bar. Each lives in an `aleph-void` fork
(git submodule under `community/`); see its `GHIDRA-RARE.md` and `CREDITS.md`.

### C6000: verified with documented packet limitations (community: @geepot)

| Area | State |
|---|---|
| Decode | All 415 32-bit opcode rows and 173/174 compact rows reached; random and per-opcode corpora checked against GNU objdump and TI `dis6x` in both byte orders. The remaining compact `SPKERNEL` row has reference formatting/context disagreement |
| Semantics | 40/40 hand-computed emulator cases in each byte order; branch delay windows, compact packets, arithmetic and addressing exercised |
| Real binaries | Eight Linux BusyBox/uClibc files and two TI-built zlib files: 10 files, 6,396 functions, 480,153 analysed instructions. BusyBox and smaller libraries decompile fully; uClibc and zlib have documented conditional-packet decompiler errors and zlib timeouts. Shared decoded instructions agree with GNU except documented relocation sites, compact register rendering and `SPKERNEL` text |
| Fixed here | ELF import and relocations, packet context, branch delay slots, compact and C64x+ decode, calling convention and DWARF map |
| Doesn't work | Big-endian compact execution order in a 32-bit word, nested branch delay windows, packet atomicity and software-pipelined loop replay in p-code; C66x instructions not decoded |

### s390x (IBM z/Architecture): done with listed gaps (community: @paulovitorjp)

| Area | State |
|---|---|
| Decode | All 2,748 opcode-table entries (g5 to z17) agree with objdump 2.45; 100% of the 42,020 fuzz words objdump decodes agree; llvm-objdump 21 agrees on 16,850 of 17,303 (the rest differ only in spelling) |
| Semantics | P-code for general, decimal, BFP, HFP, DFP, vector, vector packed decimal and z17 instructions, PLO, CUSE, CFC, UPT, TRTE. Emulator 97/97 hand-computed; qemu-s390x 10.2 differential 22,080/22,080 over 1,334 mnemonics; reference models: packed decimal 2,100/2,100, HFP 6,240/6,240, DFP 12,900/12,900, vector packed decimal 5,250/5,250 |
| Real code | Debian libz/ls/sort/libc/busybox and Ubuntu libc: 1,007,254 instructions, all agree with objdump; 12,092 functions, 0 decompile failures or timeouts. Remaining bookmarks: trap halfwords after noreturn calls, two generic Ghidra .rodata issues |
| Doesn't work | CPACF crypto (KM*, KIMD, KLMD, KDSA, PCC, PCKMO), CMPSC, SORTL and PFPO are still pcodeops (the .sla is 12.5 MB of the 16 MB limit); privileged/I-O/clock instructions, transactional execution, guarded storage, traps, EX/EXRL, NNPA, DFLTCC, PRNO TRNG are inherent; PM3+ program objects, CTL+RLD, overlay and PDS images refused (no legal samples) |
| Unverified | z/OS loaders on real z/OS modules; vector packed decimal and HFP scaling instructions are checked only against models of PoO behaviour; PLO, CUSE, CFC, UPT, TRTE and z17 additions have hand-computed tests only; the 12.1.3 and 12.2 zips were built but not loaded |

### Cell SPU: done (community: @aerosoul94, @balika011, @elad335, @VelocityRa)

| Area | State |
|---|---|
| Decode | All 199 opcodes match the SPU ISA v1.2 document; 158,304 words (every 11-bit opcode × 48 fills + 60,000 random) vs objdump 2.45: 97,699 identical, 92 display-only differences, 60,513 rejected by both, 0 others; 262/262 constructors reached |
| Semantics | 128-bit registers with complete p-code; 37/37 emulator sequences (SIMD integer, shufb/selb, all load/store forms, branches, channels, iret, exact single-precision range rules, double-precision FMA rounded once), broken expectation detected |
| Real code | GCC 6.5 zlib linked with Ubuntu's SPU newlib/libgcc, Ubuntu libm/libc objects, Linux spufs images: 149,466 instructions, 100% agreement with objdump, 0 bad-instruction bookmarks, 1,120/1,120 functions decompile; 8,570/8,570 relocations agree with GNU ld; 32/32 switch statements recovered |
| Doesn't work | Double-precision rounding-mode fields not applied (flags are); frest/frsqest return an exact estimate; stop/halt and channel hardware are user ops; PPU relocations reported, not applied; 8-byte/vector DWARF register variables unmappable |
| Unverified | No SPU hardware or simulator; implementation-defined results (estimate-table bits, NaN payloads, DENORM) |

Language ID changed from `SPU:BE:128:default` (never selectable for ELF32) to `SPU:BE:32:default`; `.trans` files upgrade old programs.

### TILE-Gx: initial support complete (community: @speidy)

| Area | State |
|---|---|
| Decode | 318,760 bundles vs GNU libopcodes: 100% semantic agreement, 0 unexplained; 1,521/1,521 constructors reached |
| Semantics | 29/29 emulator cases in each of four languages, including parallel bundle behavior, memory, branches, atomics and SIMD |
| Real binaries | Four linked zlib 1.3.1 ELFs (LE/BE, 32/64 ABI): 35,413 analysed bundles match GNU exactly; 324/324 functions decompile, 0 bad-instruction and error bookmarks |
| Fixed here | Manual-derived language generator, big-endian data and 32-bit ABI, ELF opinions, signed `char`, DWARF map and test harness |
| Doesn't work | ELF relocations in relocatable objects; cache/TLB/network and floating-point helper instructions use unverified named user operations; some 32-bit C output has saved-register and switch warnings |

### Blackfin: done (community: @geepot)

| Area | State |
|---|---|
| Decode | All 65,536 16-bit words and 387,072 sampled longer encodings vs GNU objdump: 0 unexplained differences; 304 LSETUP offset differences are an objdump bug |
| Semantics | GNU simulator differential: 59,914 scalar, 18,649 DSP packet, 456 video and 3,013 circular-DAG cases agree; emulator 28/28 hand-computed cases |
| Real binaries | Seven FDPIC libraries/objects: 3,610 functions decompile with 0 failures; 232,390 analysed instructions, one explained LSETUP text difference, and 2 error bookmarks for a deliberate illegal opcode |
| Fixed here | ELF relocations, FDPIC GOT tracking, DWARF map, calling convention, video instructions and circular-DAG addressing |
| Doesn't work | Blackfin+ extensions; dynamic R_BFIN_FUNCDESC values; 72 large-function switch tables with a spilled GOT pointer; exception, cache and simulator-console operations are opaque |
| Unverified | Hardware behavior beyond the GNU simulator |

### MeP: done (community: @CreepNT)

| Area | State |
|---|---|
| Decode | Core and IVC2 opcode table, first-halfword, fuzz and VLIW corpora match GNU objdump semantically in both byte orders, with zero unexplained differences; all 881 IVC2 slot forms reached |
| Semantics | Core emulator: 49/49 cases in each byte order; IVC2 emulator: 6/6 in each byte order. UCI, DSP and most IVC2 arithmetic remain user operations because their chip-specific or vector behavior lacks a public specification |
| Real binaries | 17 GCC-built files: 9,117 functions and 790,111 instructions; zero bad-instruction bookmarks; every function decompiles with zero failures or timeouts |
| Fixed here | Standalone extension, complete core decode, IVC2/VLIW mode, big-endian support, ELF relocation handling, GCC return and switch recognition, DWARF map |
| Unverified | Sony CMeP toolchain output and Toshiba IVC2 toolchain output |

### FR60 / FR81: done for the FR30 core (community: @desrdev)

| Area | State |
|---|---|
| Decode | FR60 vs GNU binutils 2.45: all 192,882 shared first-halfword slots exact and all 98,100 shared random slots semantically equal; zero Ghidra-only decodes. Reference-only slots print `???` for reserved registers. FR81's extra forms lack a GNU oracle |
| Semantics | Nine hand-computed emulator cases pass in each language, including negative immediates, flags, shifts, loads and stores; 251/258 FR60 and 401/408 FR81 constructors reached (seven shadowed aliases) |
| Real binaries | Six GCC-built Lua/zlib ELFs: 257,785 instructions exact against objdump, 3,523/3,523 functions decompile, zero bad-instruction bookmarks. DWARF negative line numbers cause 671 importer error bookmarks |
| Fixed here | Negative immediate semantics, ASR2, coprocessor field and COPSV length, ELF opinion, malformed DWARF register map, extension metadata |
| Unverified | FR81-only instructions and actual FR60/FR81 firmware; coprocessor hardware effects are opaque |

### Alpha: done (community: @kkaempf, @mattst88; 15 languages)

| Area | State |
|---|---|
| Decode | vs objdump 2.45 on every opcode-table entry and 50k random words: 0 unexplained (21064/21164 remainders are 2 confirmed objdump bugs); every entry decodes (EV4 716/716, EV5 880/880, EV6 670/670); CALL_PAL names vs MAME 128/128 per OS |
| Semantics | Emulator 53/53; 2 x 20,000 random instructions on 206 mnemonics agree with qemu-alpha or, for VAX floating point, an exact-rational model (QEMU's VAX helpers are broken). MVI min/max/PERR, bit-exact LDS/STS/LDF/LDG, /C /M /D rounding with FPCR, real VAX F/G/D arithmetic |
| Real binaries | Debian alpha libz, ls, sort, libc, static busybox and QEMU palcode: 100% vs objdump, 0 bad, 0 decompile failures, 0 overlapping ldgp entries (was 1,448 in libc). Windows NT/AXP (MiKTeX 1.07, Info-ZIP unzip; GPL/free): 125,022 instructions, 829 functions, 0 failures. OpenVMS AXP (Info-ZIP UnZip): 13,899 instructions, 141 functions decompile |
| Fixed here | PALcode formats, many semantics bugs, ELF opinion, relocations incl. gp-relative ones in `.o` files, DWARF maps, cspecs (shared int/FP argument slots, 32-bit NT/VMS pointers), ldgp entry thunks, PE support (opinion, `.pdata`, IAT), VMS procedure descriptors, switch tables (102 to 47 lost) |
| Doesn't work (inherent) | 47 switch tables reached through merged values the decompiler doesn't separate. Trap qualifiers and FPCR exception bits (hardware exception state). RPCC, AMASK, cache hints, barriers, IPRs are pcodeops. TLS relocations: Ghidra rejects them before the handler runs. VMS images have no Ghidra loader (imported raw) |
| Note | Bit-exact single-precision loads decompile as a bit-mapping expression rather than `(double)f` (30 sites in ls/sort, 23 in libc) |

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

### M-CORE: done (community: @CUB3D, Ghidra PR #9270)

| Area | State |
|---|---|
| Decode | All 65,536 halfwords vs objdump 2.45, BE and LE: 100% semantic, 0 unexplained (differences are manual-only accelerator ops, 3 objdump bugs and GDB simulator calls); 138/138 constructors. The PR scored 41% |
| Semantics | Full ISA in p-code; trap/bkpt/divide-by-zero take the manual's exception entry; emulator 30/30 per byte order |
| Real binaries | No freely licensed M-CORE firmware exists; the 19 Embench-IoT programs (GPL-3) built with GCC 14/newlib, BE and LE: 38 ELFs, 159,369 instructions, 100% semantic vs objdump, 3,330/3,330 functions decompile. Relocations vs GNU ld: 62/62 bytes identical |
| Fixed here | Instruction set reworked from differential testing, GCC cspec and DWARF map, ELF relocation handler, exceptions, newlib's simulator service calls (bad instructions in every program before), LE language, stand-alone extension build |
| Doesn't work (inherent) | 33 bad instructions in GCC crtstuff stubs (inline asm switches section mid-function; objdump shows the same bytes as data). DWARF line-table bookmarks from a Ghidra bug (signed-byte line advance vs M-CORE gas's line_range 242). h_* accelerator and low-power ops are pcodeops (attached hardware). PSR AF register bank, memory-raised exceptions and interrupts not modelled |
| Unverified | Real M-CORE firmware (none freely licensed); R_MCORE_PCRELIMM4BY2/PCREL32 (no assembler or linker produces them) |

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
| Decode | 0 unexplained differences vs objdump 2.45 on the opcode table (95.85%; the rest are manual-only instructions and register pairs past r31) and 50,000 random words (98.45%), BE and LE; 145/145 entries decode. `l.muldu` decodes in both the manual's (0xc) and GNU as's (0xd) encodings |
| Semantics | Full p-code incl. ORFPX32/ORFPX64A32, exact IEEE `lf.rem`, SR flag bits consistent through `l.mtspr`/`l.mfspr`/`l.rfe`; emulator 38/38 BE and LE |
| Real binaries | Bootlin glibc (libc, libm, ld.so, static ldconfig) and a Linux kernel: 100% identical to objdump, 0 decompile failures; relocations incl. the GOT model match GNU ld; kernel exception vectors and `__ex_table` fixups found automatically (vmlinux: 9,047 functions) |
| Fixed here | Delay slots on BE, link address, PC-read `l.jal 8`, reserved bits, shift fields, the FPU, `l.sys`, `l.cmov`, ELF opinion, DWARF map, relocation handler (incl. GOT model), PLT thunks, SR flags, vector analyzer |
| Doesn't work (inherent) | TLS relocations: Ghidra rejects every STT_TLS relocation before the processor's handler runs. `l.cust*`/`lf.cust1` are implementation-defined. Barriers and hardware exceptions (overflow, range, alignment traps). glibc `vfprintf` computed-goto tables (decompiler) |
| Unverified | LE/no-delay-slot language on real binaries (hx330x firmware has no license); ORBIS64 (no 64-bit core exists) |

### RH850 (V850E1/E2/E3): done (community: @esaulenka and contributors)

| Area | State |
|---|---|
| Decode | 100% semantic where both decode vs GNU objdump on the full binutils opcode table, all first halfwords and 100k random words, in RH850, V850E2M and V850E1; E1 has zero one-sided decodes. 556/556, 374/374 and 243/243 constructors reached. Ghidra's built-in V850 `v850e3v5` language scores 73% on the same opcode table; upstream as imported 92% |
| Semantics | Integer, flags, saturation, loads/stores, branches, calls, atomic ops, and FPU single/double with FPSR rounding modes and unsigned 64-bit conversions; emulator 63/63 RH850 and 34/34 V850E1. System, debug, hypervisor, TLB, cache and DSP-extension ops remain pcodeops |
| Real binaries | Nine GCC-built ELFs (Lua, zlib; V850E1, V850E2V3 and RH850): 472,196 instructions, 5,005/5,005 functions decompile, all decoded instructions agree semantically with objdump. E1 has 0 bad-instruction bookmarks; E2V3 has 17 at words objdump also rejects; RH850 has 0 |
| Fixed here | Added V850E1 core language, RH850 ELF loader, automatic CALLT and GCC prologue-helper analyzers, 46 call fixups verified against 128 linked helpers; improved FPU conversions. Earlier fixes include instruction decode, cspec/DWARF/opinion, system registers and G4MH instructions |
| Doesn't work | GCC gives E1 and E2V3 identical RH850 ABI flags, so E1 needs explicit language selection. FPU exception flags and traps are not modelled |
| Unverified | V850E1F FPU and V850ES-specific extensions; G4MH post-increment/decrement loads/stores (no reference tool decodes them); CC-RH/GHS output; third-party firmware |

### RL78: done (community: @CUB3D; instruction set rebuilt here)

| Area | State |
|---|---|
| Decode | 100% semantic on 60,000 random slots and 99.80% on the full opcode corpus vs GNU objdump (G13 and G14 ISAs); every difference is a confirmed objdump quirk. Every constructor reached (466/466, 452/452). Upstream was at 52.9% |
| Semantics | Full p-code incl. flags, ES:, skips, register banks, S3 multiply/divide/MAC, BRK/RETB through the 0007E vector; emulator 57/57 |
| Real binaries | 11 GCC-built ELFs from public source (msalau samples, FreeRTOS, newlib): 0 bad instructions, 346/346 functions decompile, disassembly identical to objdump |
| Fixed here | Instruction set regenerated from the RL78 manual; S1/S2 language; ELF opinion; PC, segment op and volatile SFRs; GCC calling convention; DWARF map; vector analyzer (vector and CALLT tables, no bogus function at 00000, flash mirror block for MAA = 0); BRK as a real call |
| Doesn't work (inherent) | Register bank of an interrupt handler without SEL depends on PSW.RBS at run time (settable per handler). MAA = 1 mirror is selected at run time; the S1 mirror window differs per chip. BRK1 (erased flash) resets the chip. Ghidra's emulator ignores segmentop |
| Unverified | CC-RL/IAR output (no freely licensed samples), RL78-S1 (G10) images |

### TMS34010/TMS34020: done (community: @ZPaul2Fresh8; instruction set rewritten here)

| Area | State |
|---|---|
| Decode | 0 unexplained differences vs MAME on all 65,536 opcodes and 50,000 random slots; 330/330 constructors reached; NetBSD gspa assembler corpus 1,644/1,644 vs source. Upstream: 86.4%, and its pspec didn't load in Ghidra 12 |
| Semantics | Full p-code incl. bit-addressed fields and all graphics ops (PIXT, DRAV, LINE, FILL, PIXBLT with PPOP, transparency, plane mask, window modes); emulator 98/98 (20 from the User's Guide); 137 MAME graphics vectors match (18 differ only in B10-B14 scratch) |
| Real binaries | NetBSD A2410 grf_ultms program (BSD): 259/259 instructions identical to MAME and to source, 0 bad, decompiles |
| Fixed here | Module layout, instruction set rewrite, memory model, pspec/cspec, symbol scripts for bit addresses, vector script; all README/TODO limitations from upstream |
| TMS34020 | All 65,536 opcode slots, 50,000 fuzz records and 64 special cases compared with MAME with zero unexplained differences; 376/376 constructors reached across both languages; 80/80 hand-computed emulator cases pass. TI COFF object and executable corpora checked against source and MAME. |
| Doesn't work | Interrupts and PBX resume not modelled (block ops run atomically). Bit-addressed pointers decompile as `*(p>>3)`, so no stack frames or stack parameters. Field sizes unknown at function entry until a SETF. TMS34020 coprocessor execution needs external p-code callbacks. |
| Unverified | Commercial arcade/TIGA and real TMS34020 code (no freely licensed samples found), TI C compiler output, PIXBLT/FILL W=1/W=2 and PBV with L,L (MAME doesn't implement them) |

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
