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
| Decode | DSP56000: 1,243,248 two-word slots vs MAME (every non-parallel word, every parallel-move field, every ALU opcode, 65,536 random), 0 unexplained: 394,967 agree, 336,125 both invalid, 344,626 encodings the manual leaves undefined (MAME accepts them), 165,450 confirmed MAME bugs, 2,080 DSP56002 instructions MAME lacks. An independent manual-derived validity table agrees on every slot. DSP56156: 261,285 slots, 0 unexplained. Constructors reached: 1,030/1,030 and 1,589/1,589 |
| Semantics | Data ALU with real flags, scaling, data-shifter limiting and convergent rounding (plus DSP56156 saturation and rounding modes); three-phase parallel moves; linear/modulo/bit-reverse AGU; system stack; REP/REPcc and DO/DO FOREVER loops. Emulator 81/81 (DSP56000; 77 hand encodings confirmed with asl) and 54/54 (DSP56156); broken expectation detected |
| Real code | DSP56000: Motorola BBS software, 10 shipped LODs plus 65 programs assembled with Motorola's ASM56000 (run as a black box): 5,179/5,179 listing statements identical to the assembler source; MAME at 5,446 listed addresses 0 unexplained; 135/135 functions decompile; 51 bad-instruction bookmarks (48 flow off the end of test programs, 3 data tables at P:0). DSP56156: the 34 DSP56100-manual benchmarks via ASM56100: 549/549 statements identical, 749/749 functions decompile |
| Doesn't work | Interrupts, peripherals, STOP/WAIT/RESET/SWI/DEBUG (user ops), stack-overflow flags, the DSP56002 double-precision mode; nested DO loops ending on the same LA; "unpredictable" modulo offsets wrap once; no .cld (COFF) loader (convert with cldlod); DSP56156 IMPY/IMAC special flags approximated, DO SP/SSL counts not modelled |
| Unverified | Hardware behaviour; DSP56002-only instructions (MAME and asl lack them); third-party DSP561xx binaries (none found) |

MAME bugs confirmed against the manuals and the assemblers: dsp56000: XY-move Y mode/register taken from the X fields; MOVEP pp address bits; Tcc S1,D1 table; accumulator source of ADD/SUB/TFR/CMP omitted; absolute-address extension word ignored in class I/II moves, bit ops and REP; reserved bits/codes accepted. dsp56156: no BF* instructions or (R2+xx) forms; dual-read multiply sources printed reversed; don't-care bits must be zero; SHFL/SHFR decoded at 15Dx/15Fx (in neither manual).

### Intel IA-64 (Itanium): done

| Area | State |
|---|---|
| Decode | Per slot vs objdump -m ia64-elf64, all 3 languages: 100k random bundles (299,352 slots) plus an opcode-space corpus (1,074,686 slots: every value of bits 27-40 per unit and slot, plus MLX), pseudo-ops (3,852) and branches (65): 0 unexplained. Explained: Itanium 9500 hint.m/mov dahr and lfetch.count (not in SDM rev 2.3), reserved mux1 values. Every entry 5,079/5,079 per language |
| Semantics | Full p-code for integer, compare/predication (all types), multimedia, FP (80-bit model with 17-bit exponent conversion), NaT propagation, spill/fill, speculation (chk.a always recovers), register stack (decompiler model with argsave plus an emulated RSE backing store), rotating registers (br.ctop/cexit/wtop/wexit), MLX movl/brl. Emulator 37/37 per language; broken expectation detected |
| Real code | Debian 7 ia64 (libz, busybox dynamic and static, gzip, bc, libsqlite3, libm, libc): 1,394,005 instructions, all identical to objdump; 0 bad instructions except 1 in busybox-static (a mis-ranged jump table); 11,205/11,228 functions decompile (22 hit a Ghidra decompiler bug, 1 libm timeout). GCC 14 objects/exe/so (Linux) and HP-UX ILP32/LP64 objects: 16/16 functions decompile, DWARF imported |
| Doesn't work | ALAT, deferred faults, interruptions, async RSE, FP status/rounding, IA-32 mode, TLS relocations; loop-switch jump tables are not recovered (149 sqlite warnings, 87 in libc); extra call arguments for unknown prototypes; "Illegal op in iblock" is Ghidra's conditional-execution bug, reproduced in 5 instructions |
| Unverified | Hardware or simulator behaviour; Windows, OpenVMS and HP-UX executables (only HP-UX objects built here) |

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
| Intel IA-64 (Itanium) | binutils `ia64` | done (see above) |

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

### s390x (IBM z/Architecture): done (community: @paulovitorjp)

| Area | State |
|---|---|
| Decode | All 2,748 opcode-table entries (g5 to z17) agree with objdump 2.45; 100% of the 42,020 fuzz words objdump decodes agree; llvm-objdump 21 agrees on 16,850 of 17,303 (the rest differ only in spelling) |
| Semantics | P-code for general, decimal, BFP, HFP, DFP, vector, vector packed decimal and z17 instructions, PLO, CUSE, CFC, UPT, TRTE, and (round 2) PFPO, the CPACF family (KM*, KIMD, KLMD, KMAC, KMA, PCC incl. scalar multiply, KDSA, PCKMO and the protected-key functions), PRNO DRNG, CMPSC, SORTL and DFLTCC query/expand. Emulator 784/784 hand-computed; qemu-s390x 10.2 differential 22,080/22,080 over 1,334 mnemonics; reference models: packed decimal 2,100, HFP 6,240, DFP 12,900, vector packed decimal 5,250, PFPO 1,500, all 100%; 0 uninitialised-temporary violations in 21,984 instructions |
| Real code | Debian libz/ls/sort/libc/busybox and Ubuntu libc: 1,007,254 instructions, all agree with objdump; 12,092 functions, 0 decompile failures or timeouts. Remaining bookmarks: trap halfwords after noreturn calls, two generic Ghidra .rodata issues. The .sla decodes to 13.65 MB (81% of Ghidra's 16 MiB limit) |
| Doesn't work | Still pcodeops: PRNO-TRNG bytes and the ECDSA-sign random mix (hardware entropy), DFLTCC-GDHT/CMPR (the PoO leaves them model-dependent), NNPA and the NNP-type conversions (model-dependent format), the firmware-identity query (function code 127); privileged/I-O/clock instructions, transactional execution, guarded storage, traps, EX/EXRL are inherent; PM3+ program objects, CTL+RLD, overlay and PDS images refused (no legal samples) |
| Unverified | ECDSA signing with the random mix (the emulator cannot run the pcodeop; error paths only); the protected-key wrap layout (from PoO figures 7-410 to 7-416, checked against library CBC, not hardware; Ed448 encrypted-key field offset assumed); CMPSC, SORTL, PRNO checked only against models and PoO examples; KDSA EdDSA verify uses the cofactorless equation; z/OS loaders on real z/OS modules; vector packed decimal and HFP scaling checked only against models of PoO behaviour; the 12.1.3 and 12.2 zips were built but not loaded |

Language ID `s390x:BE:64:default`; release `ghidra-rare-v1.1.0` adds the round-2 work.

### 6800 / 6801 / HD6301 / 68HC11: done (community: @sigurasg, @antoniovazquezblanco)

| Area | State |
|---|---|
| Decode | 0 unexplained differences in about 258,000 slots (full opcode pages × 4 patterns + 40,960 random per language) vs binutils libopcodes (HC11) and MAME `unidasm` (all four); every-entry 197/197, 220/220, 230/230, 308/308 and nothing outside the tables decodes |
| Semantics | 22,920 model-checked emulator cases (reference model from the manuals) + 183 hand-computed sequences, 0 failures, broken expectation detected; upstream's 432 JUnit tests pass. Fixed: BRN length, ROR sign, V after shifts, LSRD direction, TST/MUL/ABA flags, DAA, TAP, SWI vector, HC11 BRSET/BSET/BCLR, HC11 using the 6801 vectors, Y missing from the HC11 interrupt frame |
| Real code | 10 m68hc11-elf programs (B-Con crypto, tiny-AES-c, tiny-regex-c; GCC 3.4.6 built from source): 87,662 instructions identical to objdump, 0 bad-instruction bookmarks, 602/602 functions decompile; relocation handler byte-identical to ld on 4 objects |
| Doesn't work | WAI pushes and continues; STOP/SLP/TEST are no-ops; illegal-opcode/TRAP not simulated; HC11 INIT remap not followed; GCC soft frame pointer not mappable; banked relocations (R_M68HC11_24/3B/PAGE); 6800/6801/6301 calling convention heuristic; no HD6301 manual index |
| Unverified | Silicon behaviour; real 6800/6801/HD6301 firmware (no legal binaries or compiler); HD6301 AIM/OIM/EIM/TIM flags beyond the descriptions; X/Y-variant peripherals |

Reference-tool bugs: objdump `-m m68hc11` prints 0x00 as the HC12 `bgnd`; MAME misspells BRCLR (18 1F) as `brlcr`, decodes undefined store-immediate opcodes and HD6301 0x12/0x13, and decodes BRN/JSR-direct on the 6800.

### WE32100 (AT&T 3B2): done (community: @fletto2; instruction set regenerated here)

| Area | State |
|---|---|
| Decode | vs MAME `unidasm`: 496,416 structured slots (every opcode × descriptor at every position, every {type} prefix, prefix chains) + 100,000 random: 0 unexplained. vs asl (independent encoder): 3,416 forms agree (492 asl-rejected combinations). 2,202/2,202 constructors reached |
| Semantics | 350 hand-computed emulator sequences from the manual (modes, extension/truncation, infinite-precision flags, shifts/rotates, INSF/EXTF, 14 branch + 14 return conditions × flag sets, CALL/RET/SAVE/RESTORE, block/string moves, traps/GATE/CALLPS/RETPS); 2 deliberately wrong expectations detected |
| Real code | 30 KB of public-domain C (AES, DES, Blowfish, RC4, MD2/5, SHA-1/256, base64, rot13) built with GCC 2.95.3's we32k back end and assembled with asl: 6,348 instructions, 56 functions, 0 bad/error bookmarks, 56/56 decompile, all identical to MAME |
| Doesn't work | WE32200; no COFF loader (no legal samples) and no .dwarf; WAIT, INTACK, CFLUSH, ENBVJMP/DISVJMP, MOVTRW translation and SPOP* coprocessor ops are pcodeops; privilege/stack-bound/overflow/MMU/trace faults not modelled; decompiler sees arguments as in_ap[n] |
| Unverified | No hardware or AT&T-compiled code; manual-only rules (infinite-precision flags, CMP/TST on extended values, {type} persistence, ALSW3 sign bit where SIMH disagrees) |

MAME bugs: SPOPRT/SPOPT2/RVC misprinted, undefined 0xa2/0xa3 decoded as PUSHW. asl encodes RET as 0x18 (should be 0x08). SIMH CMP N width-truncated, V from unsigned 64-bit magnitude.

### SH-3 / SH-3E / SH-2E: done (community: @will07c5; instruction set rewritten here)

| Area | State |
|---|---|
| Decode | All 65,536 words × 5 languages vs objdump 2.45 (`-m sh2e/sh3/sh3e`): 0 unexplained, 0 explained differences. Every-entry 174/174 (2E), 162/162 (3), 193/193 (3E); upstream failed 18,658/65,536 |
| Semantics | Hand-computed emulator cases 128 (2E), 119 (3 BE/LE), 142 (3E BE/LE); broken expectation and 5 source mutants detected; upstream failed 46/119. QEMU 10.2.1 user-mode state diff: 677,080 vectors, 676,305 identical, 775 explained, 0 unexplained |
| Real code | NetBSD 10.1 sh3el/sh3eb userland: 2,445,755 instructions identical to objdump, 43,811 functions decompile, 0 fail, 2 time out; zlib and Lua built with sh-elf gcc 14.3 for all 5 languages: identical to objdump; DWARF, -fPIC .so relocations, PE opinion (synthetic), PLT stubs named after imports |
| Doesn't work | SLEEP, LDTLB pcodeops; FPSCR rounding/flags, FD/BL/MD effects, interrupts, MMU not modelled; SH-DSP, SH-4/4A, SH-2A not covered; literal-pool bookmarks after calls to unproven non-returning functions; Ghidra's own SuperH handler cannot import .o files with GOT32/PLT32/GOTPC |
| Unverified | No hardware or SH-3 simulator: exception model, SR reserved bits, FPSCR mask, FTRC of NaN, MAC.W/MAC.L with Rm==Rn (QEMU differs from the manual); no third-party SH-2E/SH-3E binary |

QEMU sh4: rotl/rotr never set T; div1 T differs for a zero divisor and Rm==Rn.

### H8 family (H8/300, 300L, 300H, H8S, H8SX): done (community: @shizmob; instruction set regenerated here)

| Area | State |
|---|---|
| Decode | 10 languages; vs objdump 2.45 on four corpora per language (table, fuzz, enum, gas asm): 0 unexplained, 100% agreement with an independent manual-table decoder; every constructor reached (H8SX 8,633/8,633) |
| Semantics | Hand-computed emulator tests 26/26/49/49/58/58/85×4 pass, broken expectations detected; GDB 17.2 simulator test programs run in Ghidra's emulator: 190/192 (the 2 failures depend on blocks dropped where the manual contradicts the simulator); that suite found 4 module bugs, all fixed |
| Real code | GCC 14.3 test program and zlib, 16 binaries: 351,877 instructions, 0 different from objdump, 3,343/3,359 functions decompile; ELF relocations byte-identical to GNU ld (9,768) |
| Doesn't work | 16 functions (newlib signal/_signal_r in 24-bit binaries); Ghidra's DWARF line reader misdecodes some H8 line numbers (GCC line_range 242); no chip peripheral maps; H8SX middle/maximum, H8/300L and the exrvalid/macsat context bits must be selected by hand |
| Unverified | Renesas/Hitachi compiler output and SYSROF; real firmware; H8SX middle/maximum and H8/300L in real code; saturating MAC and EXR frames only checked by hand against the manual |

objdump 2.45: ignores reserved bits, accepts invalid register lists, wrong @@vec:7 width in normal mode, decodes E registers in h8300 mode. gas/ld 2.45: out-of-range bsr d:8 truncated silently, a #xx:5 shift after a long-form shift mis-encoded, mova @(d,eN.w),erN encoded as rN.

### MN10300 / AM33 / AM33-2: done with listed gaps (community: @michaelbrandi; instruction set rewritten here)

| Area | State |
|---|---|
| Decode | 432,729 slots per machine: 0 unexplained vs objdump (`-m mn10300/am33/am33-2`) and MAME `unidasm`; every row of the MN1030 manual's instruction table (331 rows, 1,344 encodings) decodes to the manual's mnemonic and length except 3 manual errata; constructors reached 354/354, 804/804, 1,223/1,223 |
| Semantics | MN1030 base instructions per the manual (flags incl. addc/subc Z, div overflow V, movm/call/ret lists, setlb/Lcc loops, D10 pairs). AM33/AM33-2 semantics only where the manual or compiled C establishes them (76 C functions built with GCC 14 for all three machines, 148 calls run in Ghidra's emulator against results derived from C semantics; 132 AM33/AM33-2 constructors established this way). Emulator 44/44; broken expectations detected |
| Real code | Red Hat GNUPro am33-04r2-5 AM33-2 Linux (bash, ldconfig, libc, libz, libgcc_s) + newlib programs for all three machines + gcc objects: 586,412 instructions identical to objdump, language picked from e_flags, 0 bad/error bookmarks, 0 decompile failures (5,617 functions); relocations applied except bash's 7 COPY |
| Doesn't work | pcodeops where no non-GPL source establishes the behaviour: mac/macu/macb/macbu/mach/machu/dmach/dmachu, dmulh(u), sat16/24, mcste, swap/swaph/swhw, bsch (except from 0), EPSW moves, exreg0/exother save/restore, FPU conversions/sqrt/FPCR moves, dcpf; also udf/udfu, mcst9/mcst48/getchx/getclx, trap/syscall/rtm/break (trap goes to the fixed vector 0x40000010) |
| Unverified | AM33 forms the C runs don't execute; flags of 3/4-operand forms; D10 parallel read rules; double-precision ops by analogy; FMA double rounding; MN103S-only additions; AM34; real MN10300 firmware |

Provenance: an earlier revision, published briefly and since removed from the fork's history, wrote the AM33 semantics from the GPL GNU simulator's descriptions; it was replaced by a rework from non-GPL sources only. Details in the fork's CREDITS.md. Reference-tool bugs: binutils omits UDF20-35 imm forms and rejects bset/bclr/btst imm8,(abs16) unless am33-2; MAME has F4 movbu/movhu length, FC (d32,Am) load register swap, FA 9x d97 and bset (d8,An) unsigned d8 bugs.

### MN10200: done (community: @Pokechu22)

| Area | State |
|---|---|
| Decode | 295,296 slots: 0 unexplained vs objdump `-m mn10200` (54,338 objdump bug: sign-extended displacements printed unsigned; 14,074 MN102H extensions binutils lacks) and vs MAME `unidasm -arch mn10200`; 213/213 constructors reached |
| Semantics | All p-code except break/syscall/pxst. Fixed upstream: flags in a RAM hack space (now registers), immediate add/sub/cmp setting no flags, SUBC reversed with wrong flags, XOR imm16 flags, JSR/RTS not touching the stack, DIVU overflow, logic/shift flags. Emulator 30/30, broken expectation detected |
| Real code | No freely licensed MN10200 binaries and no maintained compiler: assembled routines via GNU as/ld (gcc convention, jump table): 54 instructions identical to objdump except its unsigned-displacement bug, 0 bad instructions, 5/5 functions decompile, switch recovered, .o relocations applied |
| Doesn't work | pxst (saturation mode of the next add/sub; undocumented), break and syscall are pcodeops |
| Unverified | MN102H extensions; mulq signedness; real compiled code; Panasonic compiler's calling convention; DWARF |

The language ID `MN102:BE:24:default` is kept although the chip is little-endian (documented in the ldefs).

### Cell SPU: done (community: @aerosoul94, @balika011, @elad335, @VelocityRa)

| Area | State |
|---|---|
| Decode | All 199 opcodes match the SPU ISA v1.2 document; 158,304 words (every 11-bit opcode × 48 fills + 60,000 random) vs objdump 2.45: 97,699 identical, 92 display-only differences, 60,513 rejected by both, 0 others; 262/262 constructors reached |
| Semantics | 128-bit registers with complete p-code; 37/37 emulator sequences (SIMD integer, shufb/selb, all load/store forms, branches, channels, iret, exact single-precision range rules, double-precision FMA rounded once), broken expectation detected |
| Real code | GCC 6.5 zlib linked with Ubuntu's SPU newlib/libgcc, Ubuntu libm/libc objects, Linux spufs images: 149,466 instructions, 100% agreement with objdump, 0 bad-instruction bookmarks, 1,120/1,120 functions decompile; 8,570/8,570 relocations agree with GNU ld; 32/32 switch statements recovered |
| Doesn't work | Double-precision rounding-mode fields not applied (flags are); frest/frsqest return an exact estimate; stop/halt and channel hardware are user ops; PPU relocations reported, not applied; 8-byte/vector DWARF register variables unmappable |
| Unverified | No SPU hardware or simulator; implementation-defined results (estimate-table bits, NaN payloads, DENORM) |

Language ID changed from `SPU:BE:128:default` (never selectable for ELF32) to `SPU:BE:32:default`; `.trans` files upgrade old programs.

### VAX: done (community: @kkaempf)

| Area | State |
|---|---|
| Decode | vs objdump 2.45: every opcode × operand position × addressing mode (36,604 instructions), 40,000 random, and every PC-relative/immediate specifier at every reachable offset (9,111): 0 unexplained (explained: reserved addressing modes objdump prints, the 780's immediate index base, BUGW/BUGL inline codes, 2 objdump bugs). Every-entry 1,490/1,490; upstream's own tests 14/14 |
| Semantics | All 306 opcodes are p-code (no pcodeops). Checked against SIMH VAX-11/780: 16,140 random-operand cases on 269 opcodes plus 27 programs × 30 register sets (calls/frames, traps, CHMx/REI, queues, CASE, SVPCTX/LDPCTX, MTPR/MFPR, probes): 0 mismatches, including 105 matching faults. Emulator 38/38 hand-computed, broken expectation detected |
| Real code | NetBSD 10.2/vax ls, ksh, csh, awk, ld.elf_so, libm, libc and the GENERIC kernel, auto-imported: 1,058,549 instructions in 16,320 functions, 1,057,430 identical to objdump, 1,119 explained, 0 unexplained; 3,887 relocations applied; relocatable objects match GNU ld byte for byte; 15,497 functions decompile, 14 fail, 3 time out |
| Fixed here | Spec did not compile with stock Ghidra; 37 instructions unimplemented; VAX floats used IEEE arithmetic; MUL/DIV did not set V; no ELF opinion, relocations, dwarf or usable cspec; entry masks (#1); register writes (#2); PC-relative relocation off by 4; PLT run-ins; bit-field decompile failures |
| Doesn't work | Memory management, interrupt delivery, first-part-done restart, machine checks (outside p-code's flat memory); compatibility-mode PDP-11 code; the vector extension (no oracle or binaries); RET skips the saved-PSW MBZ check; float code decompiles as integer arithmetic (decompiler knows only IEEE); 14 decompiler-internal failures and 3 timeouts reproducible with 12.2 |
| Unverified | BUGW/BUGL inline-code convention (VMS); R_VAX_PC8/PC16; the Debugger GUI; MicroVAX subset emulation traps |

objdump 2.45 bugs: cvtgf destination typed h-float; vax-dis.c MAXLEN 25 overruns on instructions longer than 25 bytes.

### SM83 (Game Boy): done (community: @Gekkio, @minorum)

| Area | State |
|---|---|
| Decode | 146,432 slots vs MAME `lr35902` (every opcode and operand pattern, every first/second byte pair, 17 three-byte forms × every high byte, 65,536 random): 122,985 exact, 17,706 spelling-only, 5,741 both invalid (the 11 undefined opcodes), 0 unexplained. RGBDS 1.0.1 reassembles Ghidra's own text to the original bytes for 73,182 instructions (386 differ only in STOP's ignored second byte). 121/121 constructors reached |
| Semantics | 114/114 hand-computed emulator cases (ALU, flags, DAA, rotates, BIT, 16-bit ops, all load modes, stack, call/ret/rst, EI/DI/HALT/STOP), broken expectation detected; upstream's JUnit suite passes (496 tests, 4 new) |
| Real code | 175 ROMs auto-detected as SM83 (115 Mooneye test ROMs built from pinned source, 60 GBDK-2020/SDCC programs incl. MBC5 autobanked): 149,843 instructions, 3,483 functions, 0 unexplained differences vs MAME; 3,480 decompile, 1 fails, 2 time out; 91 bad-instruction bookmarks, all explained |
| Doesn't work | IME, HALT, STOP and MBC writes are user ops (interrupt dispatch, EI delay, HALT bug, bank switching not modelled); bank-switched calls resolve only after constant bank writes or through configured dispatchers; one RAM routine that falls through past its copied bytes does not decompile; carry-chain idioms decompile byte-wise (decompiler); `__sdcccall1` cannot express every SDCC placement; no processor manual index |
| Unverified | Boot ROM loading; commercial games, CGB double speed, SGB, exotic MBCs; the Debugger factory and GUI import dialog; the full ROM run and JUnit suite were on 12.1.4 only |

Fixed here: echo RAM executable, RAM code copied by any helper, power-up bank 1, GBDK/SDCC conventions, symbol import (.sym/.noi), 12.2 build (hardware type is now a drop-down option).

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

### Synopsys ARCv2 (ARC EM/HS): done (community: Roman Korkikian, Sony)

| Area | State |
|---|---|
| Decode | Instruction set regenerated (tools/gen_arcv2.py) from black-box surveys of objdump 2.45's output (no binutils or GCC source read). vs objdump (cpu=hs/em, with and without DSP), both byte orders: every 16-bit halfword, 1,048,576 32-bit slots and 50,000 random, 0 unexplained (21,182 explained per order, mostly odd 64-bit register pairs objdump decodes with a warning). Every mnemonic objdump knows for HS and EM is decoded. 2,205/2,205 constructors reached per language. Upstream: 62% of the 32-bit space |
| Semantics | ALU flags, saturation, multiply/divide, bit fields, every load/store mode, ldd/std, delay slots (calls returned to 0 before), lp loops, enter_s/leave_s (frame layout confirmed from GCC 15.3 unwind tables), atomics, FPU arithmetic, FMA with the accumulator, compares and conversions, mpyd. 45 hand-computed emulator cases per byte order; broken expectation detected |
| Real code | Bootlin arcle-hs38 uClibc (LE: libuClibc 100,821 instructions, libgcc_s, ld-uClibc, libatomic, 3 programs) and Synopsys 2024.12 HS big-endian uClibc (libstdc++ 271,510 instructions, libuClibc, and more): 100% agreement with objdump, 0 bad instructions in libraries (upstream: 13,464 instructions and 1,433 bad on the same libuClibc), every function decompiles except 12 libstdc++ functions (DWARF register overlap for empty C++ class parameters). ELF opinion is now e_machine 195 (upstream claimed ARCompact's 93) |
| Doesn't work | About 280 DSP/SIMD/complex/accumulator/QuarkSE/FPX-assist operations are pcodeops (their arithmetic is in no public source); fcvt codes other than 0/2/4/9/11; FMA rounds twice; privileged and hardware instructions are pcodeops; TLS GOT relocations and R_ARC_COPY; register tail calls warn "could not recover jumptable" |
| Unverified | 64-bit register-pair order on big-endian; lp with lp_count 0; EM-only encodings on real code (no freely licensed EM firmware); QuarkSE, FPX-assist and SecureShield decode only |

Ghidra's SleighLanguage caches instruction prototypes by a 32-bit hash and returns the wrong prototype on a collision (1 corpus slot per byte order; the test harness parses uncached). objdump 2.45 prints u6 as a register in "0,limm,u6" forms of sub-opcodes 0x20-0x2e of majors 5-7.

### Sony PSP Allegrex: done (community: @kotcrab and contributors)

| Area | State |
|---|---|
| Decode | 1,327,168 enumerated + 100,000 random words vs psp-objdump (pspdev binutils, Allegrex branch) and rabbitizer 1.16.2: 0 unexplained; 2,203/2,203 constructors reached (VFPU prefix lanes under 32 context sets) |
| Semantics | Upstream had every VFPU op as a pcodeop (through a Kotlin injection library); now generated p-code (tools/gen_vfpu.py) for all VFPU instructions incl. VPFXS/T/D prefixes and the matrix, convert, pack and half-float ops. Fixed: VFPU decode accepting nonexistent sizes and fields, core instructions the Allegrex lacks (traps, SYNCI, RDPGPR/WRPGPR, WAIT, RDHWR, DI/EI), JALR rd=rs, CVT.W.S/ROUND.W.S rounding, 64-bit arguments and results. 47/47 hand-computed emulator cases; broken expectation detected. 4,230 random VFPU cases vs PPSSPP (built locally, black box): 0 different (VRCP/VNRCP within 5 ulp, transcendentals within tolerance) |
| Real code | 26 PSPSDK samples (pinned pspdev v20261001): 830,172 instructions, 10,989 functions, imported through the PSP loader, 0 unexpected bookmarks, 0 decompile failures, 0 unexplained vs psp-objdump |
| Doesn't work | VSIN/VCOS/VEXP2/VLOG2/VASIN and the VRND* generator and VWBN are pcodeops (no non-GPL description); VRCP/VNRCP divide exactly where hardware approximates; prefixes set through MTVC/VMTVC or separated from their instruction by non-VFPU code are not applied; vfim immediates shown in hex |
| Unverified | Real hardware (PPSSPP is the reference); prefixes on SFU ops, VDIV, VCRSP and VQMUL; swizzles outside the operand size; denormal half floats; commercial-game relocation and NID issues |

Built with upstream's Kotlin Gradle build (`build-module.sh --keep-build`, workflow input `keep_build: true`); two changes make it build for Ghidra 12.1.x. psp-objdump decodes JALX and generic coprocessor fallbacks and accepts VMFVC/VMTVC below 128; rabbitizer falls back to R4000 tables for the Allegrex.

### Padauk PDK13/14/15/16: done (community: @CUB3D)

| Area | State |
|---|---|
| Decode | Every opcode word of PDK13/14/15/16 (8,192/16,384/32,768/65,536) vs the MIT fppa-pdk-tools dispdk and SDCC's ucsim_pdk: 0 unexplained against either; Ghidra's text re-assembled with sdaspdk13/14/15: 0 differ (PDK15 NMOV not accepted by sdas). Every constructor reached in all five languages (87/87 to 112/112). Upstream's five specs did not compile |
| Semantics | Fixed: word-addressed code space and return addresses, the program counter colliding with the I/O port `pc`, borrow-based CF/AC on subtraction, PCADD base, RETI, device register tables (the PMS150C table was PMS134's), stack pointer in data memory. 68 hand-computed emulator sequences plus a broken expectation per ISA; 13,774 random single-instruction states vs ucsim agree (deviations are confirmed ucsim bugs) |
| Real code | 13 SDCC-built free-pdk showcase images (GPL-3.0, pinned URL + SHA-256, not committed) for PMS150C, PFS154, PFS172 and PFS173: 4,003 instructions, 129 functions, 0 bad or error bookmarks, 0 decompile failures, every instruction agrees with ucsim (243 in ucsim gaps); Intel Hex and flat binaries import |
| Doesn't work | Peripherals, timers, watchdog, interrupt dispatch and clock (WDRESET/STOPSYS/STOPEXE/PMODE/PUSHWPC/POPWPC are pcodeops); no .pdk loader; register tables for five devices only; no ELF/DWARF (SDCC emits neither) |
| Unverified | LDSPTL/LDSPTH pointer source (data memory at SP vs ROM); NADD flags; PDK16 behaviour ucsim cannot run (hand cases only, no PDK16 compiler or free firmware); the PMC884 register table; TRAP |

ucsim_pdk does not update ZF on MOV A,M/IO, returns the low byte from LDSPTH, swaps LDTABL/LDTABH and mis-executes several PDK16 instructions; dispdk swaps PDK16 GOTO/CALL and the A,M/M,A forms of NMOV/NADD/CEQSN/COMP; the Free PDK PDK16 table has a shifted hex column.

### Sunplus u'nSP: done (community: @SamuelWAnderson45, @GMMan)

| Area | State |
|---|---|
| Decode | Every first word × 2 second words (131,072 records) vs MAME `unidasm unsp20`: 97,420 agree, 33,646 invalid in both, 6 explained, 0 unexplained; 2.0 extended group (0xff80 prefix × every second word × 2 third words): 76,288 agree, 0 differences; vs unsp12 and unsp10 0 differences beyond newer-version and reassigned encodings. naken_asm round trip of 219 forms: 0 differ. 914/914 constructors reached in both SECBANK states |
| Semantics | Regenerated from tools/gen_unsp.py: extended registers, SECBANK (sr1-sr4) as context, push/pop/retf/reti/break/call/goto/mul/ds/fr/int implemented; fixed FIR-move on/off inverted, sub/cmp carry with a zero subtrahend, PC-destination ops not branching. 133 hand-computed emulator cases (expectations from veesem, ISC, and the V.Smile hardware notes); broken expectation detected |
| Real code | No freely licensed compiled u'nSP binary exists (V.Smile ROMs are commercial; homebrew repos are unlicensed). Programs assembled with naken_asm (memcpy, checksum, strlen, jump-table dispatch, dot product): 84 instructions, 7/7 functions decompile, switch recovered, identical to MAME |
| Doesn't work | divs, divq, exp and the register-count shifts are pcodeops (semantics documented only inside the vendor IDE); interrupt entry; SB is one register (banked per mode in hardware); fraction mode; CS writes to SR do not redirect later jumps; call/push stores show as byte-stack arithmetic (16-bit word-addressed SP); the cspec is upstream's |
| Unverified | TSTB polarity and bit-index masking; v1.3 SS/MDS registers; encodings the oracles call invalid; compiled code |

### Microchip PIC16F153xx: done (community: @mh-, Ghidra PR #667)

| Area | State |
|---|---|
| Decode | All 16,384 14-bit words vs gpdasm (gputils 1.5.2): 0 unexplained (4 explained: CLRW don't-care bits, gpdasm's 0x0061 halt); vs MAME `unidasm pic16c62x` on the 14,080 shared encodings: 0 unexplained (90 enhanced-only); 8 assembler pseudo-ops 8/8 vs gpasm. 118/118 constructors reached |
| Semantics | Fixed: RETLW matching LSLF/LSRF/ASRF, digit carry of subtractions, RLF/RRF/MOVIW flags, CALL/GOTO/BRA/BRW/return targets and return addresses, the skip model, CALL/GOTO decompiled as jump tables (now direct through a PCLATH context set by MOVLP), 32 of 272 SFR symbols, INTCON bit names, SKPC family swapped, PCLATH ranges. 112 emulator cases hand-computed from DS40001865D (gpasm-assembled); broken expectation detected; a self-built program (CRC-16, multiply, XTEA, bubble sort, computed goto) matches Python on 6 vectors |
| Real code | react66/bootloader-pic16 (MIT) stubs through the Intel Hex loader: 430 instructions identical to gpdasm, 19 functions, 0 bad or error bookmarks, 0 decompile failures |
| Doesn't work | The FSR linear data (0x2000-0x2FEF) and flash (0x8000+) windows are plain data addresses (a data space cannot alias); TOSL/TOSH/STKPTR, stack depth, interrupt context save, CLRWDT/SLEEP/RESET/OPTION; PCLATH written other than by MOVLP is not tracked; SFR names are the 15325/45 map. Kept as a separate language, not a variant of Ghidra's PIC-16 module |
| Unverified | XC8/MPLAB output (none freely licensed) and its calling convention; ELF/DWARF; other family members' SFR maps; silicon |

gpdasm prints addfsr with the FSRnL address instead of n and decodes 0x0061 as halt; the data sheet's MOVLB encoding line is garbled (00 0001 01kk kkkk).

### TI TMS9900: done (community: @gnulnulf, @cvpeck)

| Area | State |
|---|---|
| Decode | 231,072 slots (every first word × 2 extension-word sets + 100,000 random) vs MAME `unidasm tms9900`: 225,125 agree, 5,947 both invalid, 0 unexplained; xas99 re-assembles every decodable slot (11 wrapping jumps skipped). 101/101 constructors reached |
| Semantics | Semantics and addressing rewritten (tools/gen_operands.py). Fixed: byte operations on the low byte, auto-increment never incrementing, B/BL/BLWP/XOP/X using operand contents instead of the address, C/CB operand order, JHE/JLE logic, DIV overflow, XOP vector, R11 and ST6, ABS flags, NEG/INC/DEC carry, shift counts 0 and 16, empty CRU instructions, compile errors. 171 hand-computed emulator sequences pass and 2 wrong ones are detected |
| Real code | Stevie editor ROM banks (GPL-3, pinned commit + SHA-256, not committed): 11,429 listed instructions agree with the author's xas99 listing, MAME and xas99; 428 functions, 368 decompile with 0 failures |
| Doesn't work | X is a pcodeop; IDLE/CKON/CKOF/LREX/RSET pulses, interrupts and CRU devices; BLWP/XOP vector targets are not followed statically; inline data after BL is decoded as code (355 instructions in Stevie); no TMS9995 instructions; no loader |
| Unverified | Flag corner cases (NEG and ABS carry, LDCR/STCR parity, RTWP clearing unused ST bits) are from the 1976 data manual only; no CPU-simulator oracle; no ELF/DWARF |

xas99 3.6.5 assembles `LDCR Rn,16` with the STCR encoding.

### Motorola DSP56300: done (community: @roblg)

| Area | State |
|---|---|
| Decode | All 2^24 words vs MAME `dsp563xx`: 5,036,139 agree, 983,726 both invalid, 10,757,351 explained, 0 unexplained; 200,000 random words 0 unexplained; 0 decoded words outside the manual's formats. asl round trip on every 10th decoded word (1,579,314): 0 unexplained. 1,023/1,023 constructors reached |
| Semantics | Fixed: reserved bits, shift-count and S,#n ranges, BRCLR-class absolute ea, NN/NR condition codes swapped, system stack pushing byte addresses (RTS returned to three times the address) and part of SR, DO not setting LF, MAC/MPY changing C, CMP saturating. Added: limiter, rounding, scaling and SM saturation, DIV/NORM/NORMF/CLB, 48-bit CMPU, AGU modifiers in the modulo variant, cspec reset SR mode bits. 40 hand-computed emulator cases (33 default, 7 modulo); broken expectation detected in both; loop-end analyzer checked |
| Real code | 23 DSP56300 modules from sambanks/octabam (MIT, pinned commit + SHA-256, assembled with asl): 13,548 instructions, 68/68 functions decompile, 0 bad or error bookmarks; every instruction re-assembles to the listing's words |
| Doesn't work | SA/SC (16-bit) and DM (double-precision multiply) modes are not modelled: such code decodes but computes as 24-bit; BRKcc jumps through a computed LA+1; STOP/WAIT/RESET/cache/DEBUG/TRAP/ILLEGAL are pcodeops |
| Unverified | Hardware; Motorola-toolchain COFF binaries (none freely licensed); the 16-bit modes |

MAME's dsp563xx disassembler shifts X:Y move address modes by one, decodes R:Y class I moves with the X:R layout, has a wrong QQQQ table, decodes MPYI qq with the QQ table, mishandles INSERT/EXTRACT destinations, rejects LSR #17-23, decodes CLB at the wrong encoding and accepts two forms the manual does not define. asl 1.42 stores DOR's absolute LA instead of a displacement, encodes CMP A,B as MAX and ASL S1,S2,D as NORMF.

### GameCube/Wii DSP: done (community: @Pokechu22, @Tilka)

| Area | State |
|---|---|
| Decode | All 65,536 first words × 3 second words (196,608 cases) vs Dolphin's DSPTool (built and run as a black box): 130,212 exact, 2,109 both invalid, 68,584 explained (display rules and four manual-vs-DSPTool operand-field disagreements), 0 unexplained; 64,976/65,536 equal to the manual's opcode table, the other 560 documented. 481/481 constructors reached in both languages (MAME has no GC DSP) |
| Semantics | Fixed: product register unrelated to $prod, AM ignored, ADDR/SUBR unshifted, CLRL not rounding, SBCLR/SBSET swapped, extension ops not parallel, CALLcc clobbering st0, RTI/IF/CALLR TODOs, flag macros on the wrong bytes, saturation never compiled, SUB/CMP/NEG overflow, nested loops hanging. New `exact` language reads $cr at run time and saturates at 40 bits. 58 (default) / 61 (exact) hand-computed emulator cases; 12,000 random instructions per language agree with a model written from Duddie's manual; mutated model detected |
| Real code | 24 DSPSpy test programs (GPL-2.0-or-later, assembled with DSPTool, not committed) with Dolphin's free ROM, through the new loader: 8,780 instructions, 640 functions, 0 bad or error bookmarks, 0 decompile failures, 0 unexplained vs DSPTool |
| Doesn't work | Wrap registers $wr, $sr.SU and the $st0-3 hardware-stack behaviour (manual silent); two loops ending on one instruction; interrupts, DMA and the accelerator |
| Unverified | ADDPAXZ/CLRL/MADDC/MSUBC operand fields where the manual and DSPTool disagree (the module follows the manual); MOVP-family C flag; IFcc before a two-word instruction; hardware |

DSPTool's assembler encodes `clrl $ac0.l` and `$ac1.l` identically and rejects `maddc $ac0.m,$ax1.h`, which its disassembler prints.

### Nintendo 64 RSP: done (community: @Random06457)

| Area | State |
|---|---|
| Decode | 5,494/5,494 armips forms round-trip; 200,000 random and 11,700 structured words vs MAME `unidasm rsp`: 0 unexplained; armips re-assembles Ghidra's text with 0 differences. 477/477 constructors reached |
| Semantics | Upstream copied a MIPS32 spec (FPU, multiply and pattern conflicts) and left most vector ops as pcodeops; replaced by a standalone RSP spec with a generated vector unit (accumulators, flags, reciprocal unit). Fixed: vmudh/vxor wrote vt, vnxor spelled vvxor, element order, jr/jal/branch targets with the 12-bit link, r29 as SP. 58 hand-computed emulator cases; broken expectation detected; 12,688 random single instructions (every vector function × 16 elements, all LWC2/SWC2, COP2 moves) identical to ares' vector unit (ISC, black-box harness) |
| Real code | 10 Peter Lemon RSP demos (Unlicense, built with bass) through the fixed loader with DMEM: 2,185 instructions, 0 bad or error bookmarks, 10/10 functions decompile, identical to bass output |
| Doesn't work | Multi-byte accesses crossing the end of DMEM do not wrap; COP0/DMA side effects; break falls through; branches in delay slots; no ELF/DWARF |
| Unverified | Real hardware (ares is the oracle); reserved function codes as VZERO, VEQ/VNE/VGE clearing VCC high, cfc2 register 3, vrcp-family lane selection for e < 8 |

Upstream's loader did not compile on Ghidra 12, opened a GUI file chooser (breaking headless use) and claimed every file; it now offers DMEM as an option and is not preferred. MAME's RSP disassembler takes the mfc2/mtc2 element from the wrong bits, prints a bogus lui rs and extra vmacq operands, shows vsar as vsaw, lacks lwu and decodes a nonexistent lwv.

### Sega Dreamcast VMU (Sanyo LC8670): done (community: @RossMeikleham)

| Area | State |
|---|---|
| Decode | vs MAME `unidasm lc8670`: 986,432 records per language (every first × second byte × 12 third bytes + 200,000 random), 806,432 more with other bank contexts and 2,085 address-dependent records at page crossings: 0 differences. waterbear assembler: 2,536 statements covering every form identical in both languages. 82/82 constructors reached |
| Semantics | Rewritten: SFRs as RAM-space variables, ADD/ADDC/SUB/SUBC/ROLC/BE/BNE flags, PSW parity, RAM bank and IRBK as context (`vmu:2:default`) or read from PSW at run time (new `vmu:2:dynamic`), stack in bank 0, LDF/STF on a 128 KB flash space, DIV by zero, vectors as entry points. 107 hand-computed emulator cases per language; broken expectation detected |
| Real code | 4 DreamPotato test programs (MIT, pinned URL + SHA-256, not committed): 1,115 instructions, 85/85 functions decompile, 0 bookmarks, every instruction identical to waterbear's disassembly; the new loader imports .vms games without options |
| Doesn't work | Interrupts, timers, serial, Maple, HALT, LCD/VRAM auto-increment and the flash unlock sequence are hardware state; the default language follows bank bits only through SET1/CLR1 PSW; instructions straddling the end of the 64K space; no loader for .vmu flash images (extract the .vms); PSW and the stack show as RAM variables in the decompiler |
| Unverified | Hardware and the Sanyo manual (semantics from Comstedt, Grinberg and DreamPotato): ADDC/SUBC overflow, parity polarity, R0-R3 pointer cells following RAMBK0, DIV by zero; no BIOS or commercial images used |

### TI TMS320C28x: done (community: @outlandnish, @abedegno)

| Area | State |
|---|---|
| Decode | vs TI C2000 CGT 20.2.6 dis2000 (free download, run as a black box): AMODE=0 1,245,377 instructions (every first word × 4 second words, parallel halves compared), 1,226,842 agree, 0 unexplained; AMODE=1 626,527 instructions, 0 unexplained; CLA language 84,191 instructions, 0 unexplained (the rest is dis2000 accepting reserved modes and bits). 729/729 constructors reached (directed corpus for the rarest forms) |
| Semantics | Fixed: AMODE=1 and the ARP-implicit C2xLP modes, ARP=n side effect, MOV/MOVH loc16,ACC<<n shift off by one, NORM shadowing SXTB and shifts, missing PUSH/POP pairs, LRETE, RESET, IACK, MOV PM,AX, CLRC CNF/M0M1MAP and several shift forms, reserved bits in about 40 two-word forms, a stub swallowing TMU opcodes, MOVB and MAC flags, real INTR/TRAP/IRET with correct NMI/EMUINT vectors, PM shift, F32TOI16R rounding; ELF opinion (EM 141). 57 hand-computed emulator cases; broken expectation detected |
| Real code | Public-domain crypto-algorithms plus own code built with cl2000 EABI, auto-detected: 1,530 instructions identical to dis2000, 46 functions, 0 bad or error bookmarks. Nothing from TI is committed |
| Doesn't work | F2838x FPU64, TMU type-2 conditional forms, FINTDIV and about a dozen VCU-II instructions decode as undefined (6,607 of 1.25M corpus words; outside the F2837xD target); PIE, pipeline and EALLOW enforcement; RESET/IACK are pcodeops |
| Unverified | SXTB flags; *BR0-- (only *BR0++ has a case); the F2812 pspec (dis2000 has no device option); COFF and relocatable input; no DWARF mapping |

Chosen over mwdmwd/ghidra-c28x, which was close in decode agreement; everything it decoded that this module did not was added, and it is credited. dis2000 accepts reserved addressing modes (empty operand) and ignores several reserved bits.

### TI TMS320C24x: done (community: @banksy-git; instruction set regenerated here)

| Area | State |
|---|---|
| Decode | All 65,536 first words vs the SPRU160C tables: 51,266 agree, 14,270 undefined in both, 0 differences. vs MAME `unidasm tms320c5x` on 98,304 records: 76,958 in the C24x set, 64,080 identical, 12,878 explained (MAME lacks MPY #k13 and mis-sizes MACD and NORM), 0 unexplained; identical to Ghidra-Rare's TMS320C2x/C5x module on the shared subset; c5xasm round trip 0 unexplained. 1,469/1,469 constructors reached under 64 context combinations |
| Semantics | Generated by tools/gen_c24x.py, derived from Ghidra-Rare's own TMS320C2x/C5x generator restricted to SPRU160C. Upstream's constructors were decode-only and broken (ARU field used as the AR number, CALL push, 1,152 BCND/CC/RETC encodings rejected, reserved ARU decoded), so they were replaced. 125 hand-computed emulator cases per byte order; broken expectation detected |
| Real code | c5xtools TI-assembled images (MIT), shared subset: 674 lines identical to MAME; a demo program built with c5xasm: 4/4 functions decompile in both byte orders, 0 bookmarks |
| Doesn't work | IDLE is a pcodeop; BACC/CALA table dispatch is not resolved; no COFF/ELF opinion (TI C2xx and C5x COFF share one target ID); DMOV/LTD/MACD always move data (hardware skips external memory); memory map and CNF not modelled |
| Unverified | Real F24x/C20x firmware (none freely licensed); reverse-carry modes beyond hand cases; I/O timing, interrupt masks and device peripheral maps (symbols only) |

### SuperFX (GSU): done (community: @ChekeEdd)

| Area | State |
|---|---|
| Decode | 1,043 statements assembled by bass (which writes the ALT/TO/FROM/WITH prefixes itself): all agree; wla-superfx assembles the 966 non-branch forms to identical bytes. vs MAME `unidasm superfx` on 40,000 random strings: 274,091 prefix-free instructions agree, 1,961 explained (BGE/BLT names), 0 unexplained (MAME ignores prefixes, so 60,094 post-prefix instructions are not comparable). All 1,536 ALT1/2/3 × opcode slots agree with bass or the hardware fall-back rule. 132/132 constructors reached |
| Semantics | Rewritten: prefix state through context, Sreg/Dreg, flags, RAM/ROM banks, delay slots, LOOP/LJMP, PLOT/RPIX and COLOR/GETC options in p-code. 106 hand-computed emulator cases (all 11 branches taken and not taken with delay slot, PLOT/RPIX in every colour mode, dither, transparency); broken expectation detected. Upstream's decompiler never started, its p-code always used R0 and branch conditions 06/07 were inverted |
| Real code | DiscoC v0.2.0 SNES demo payloads (GPL-3.0 compiler output, pinned URL + SHA-256, not committed), 9 images: 61,742 listing lines identical to the compiler's own listing, 64/64 functions decompile |
| Doesn't work | A prefix in the delay slot of a taken branch does not reach the target (decode-time context); multi-byte instructions in a delay slot; pipeline, cache and bus timing; jump tables through JMP Rn; calls recognised only as LINK + jump; the exact odd-address word swap prints as `*(a ^ 1)` |
| Unverified | Hardware: PLOT/RPIX bit-plane layout and dither orientation, FMULT/LMULT carry, LJMP/CACHE and CBR, GSU-1 vs GSU-2 differences; commercial ROMs not used |

MAME names opcode 06 BLT and 07 BGE; on hardware 06 branches when S = V (BGE), and bass and WLA assemble bge as 06. bass does not range-check `link #n`.

### AMD Am29000/Am29050: done (community: @mumbel)

| Area | State |
|---|---|
| Decode | 307,464 words (exhaustive field corpus + 250,000 random) vs GNU objdump 2.14 (a29k, built from source) and MAME `unidasm am29000`: 0 unexplained against either (vs objdump: 120,721 identical, 118,608 equivalent, 67,351 both invalid, 784 explained: binutils lacks mtacc/mfacc). The LE language decodes the byte-swapped corpora exactly as BE. 257/257 constructors reached. Upstream agreed with objdump on 50.7% |
| Semantics | Reworked from AMD's manuals: local registers lr0-lr127 are the stack-cache words at gr1+4*N, so calls decompile with parameters and frames; 14 TODO-empty and 4 disabled instructions implemented. 58 hand-computed emulator cases (flags, traps in delay slots, register-stack calls, loadm/storem, byte/half ops, multiply/divide steps, special registers, TLB, FP single/double in all rounding modes, accumulators, FPS flags); broken expectation detected |
| Real code | GCC 2.95.3 + binutils 2.14 (pinned sources) builds of public-domain crypto code: COFF auto-detected, 72/72 functions found (uncalled ones by the trace-back-tag pattern) and decompile, 8,444 instructions agree with objdump, 0 bad or error bookmarks; Am29050 FP program 26/26, 337 instructions agree |
| Doesn't work | Indirect gr0 access to local registers reaches a separate register bank, not the stack words (only spill/fill/context-switch code does this); the memory stack (gr125) shows as pointer arithmetic (one stack pointer per function); unmasked FP exception and multiply/divide overflow traps are not raised (FPS bits are set; they made decompiled arithmetic unreadable), XS/US never set; some double-returning functions get a 4-byte or void return until the signature is set; iret/halt/inv/coprocessor/trap vectoring are approximations or pcodeops |
| Unverified | Silicon or a simulator trace; LE emulator behaviour (decode only); CR after loadm/storem; real 29K firmware (none freely licensed) |

Upstream's a29k.sinc carried the GPL binutils opcode-table legend and 201 table lines as comments; they are removed in their own commit. MAME am29000 shows the emulate RB as an immediate, prints clz and div0 operands as bare or unprefixed numbers, and has no Am29050 instructions.

### Sunplus SCORE7: done (community: @ArthurKoba, Ghidra PR #9671)

| Area | State |
|---|---|
| Decode | vs GNU objdump 2.45 `-m score7`, both byte orders, slots at 0 and 2 mod 4: all 65,536 halfwords, 1,048,576 32-bit words (every major × bits 14-0) and 50,000 random, 0 unexplained; MAME `unidasm score7` agrees on all 12,410 undefined-parity words. 545/545 constructors reached per language |
| Semantics | 36/36 hand-computed emulator cases per byte order (PCE pairs with T set and clear, bcnz loops, cr1 flags); broken expectation detected. Fixed here: immediate bit and shift counts read as registers, PCE pairs decoded as both instructions with T-selected p-code (were raw halves and a pcodeop), separate flag registers, shift carries, about 100 missing encodings, objdump syntax; cspec from GCC 4.5.4 output (stack offset 16, was 4; r4:r5 64-bit order was swapped) |
| Real code | zlib and crypto-algorithms built with GCC 4.5.4 score-elf, LE and BE: 146 functions and about 18,000 instructions per byte order, 0 bad instructions, 0 error bookmarks, every function decompiles, 100% semantically equal to objdump, DWARF imported, opinion picks the byte order |
| Doesn't work | Custom-engine DSP ops (min/max/bitrev/saturating/MAC forms, ceinst, lcb..sce) and system/coprocessor ops are pcodeops (no non-GPL description; MAME does not emulate them); Ghidra 12.1.4's SLEIGH assembler throws an NPE on this language (the PR's fix is in Ghidra core, which an extension cannot ship); no ELF relocation handler |
| Unverified | Rotate flags (MAME does not emulate rotates; the shift carry rule is used); real S+core7 firmware (none freely licensed) |

objdump 2.45 prints the LE PCE marker order reversed and leaves the ldc3 offset unscaled; the score linker in binutils 2.28 and 2.45 mis-relocates backward j/jl (the samples use binutils 2.20.1); GCC 4.5.4's score libgcc floating-point helpers ICE. sronco/ghidra-score7 has no license and was not used.

### Motorola 68HC16 (CPU16): done (community: @HausRummel)

| Area | State |
|---|---|
| Decode | vs MAME `cpu16`: 102,400 structured slots and 50,000 random, 0 unexplained (structured: 84,473 exact, 1,050 semantic, 6,657 explained: odd branch offsets, JMP/JSR with a non-zero top nibble, PSHM/PULM bit 7). asl round trip 0 mismatches; Motorola MASM 4.6 encodings 856/856. 1,372/1,372 constructors reached |
| Semantics | Full p-code with 20-bit bank arithmetic and live EK/ZK, signed offsets, stack/call/RTI/SWI frames, PSHM/PULM, all flags and the 36-bit MAC unit. 37/37 hand-computed emulator cases pass and a broken expectation is detected; 30,240 random-state cases match a model written from the CPU16 Reference Manual |
| Real code | zlib 1.3.1 built with the GNU hc16 GCC 2.8.1 (steve-m/hc16-toolchain, pinned; runtime library stubbed, its sources are all rights reserved): 21,173 instructions, 89/89 functions decompile, 0 bad-instruction or error bookmarks, every instruction matches MAME. New HC16GccInlineArgs.java script for GCC's inline arguments after library calls |
| Doesn't work | SK:SP does not wrap at 1 MB (masking breaks the decompiler's stack tracking); WAI, BGND and LPSTOP are opaque (wait for hardware); interrupts other than SWI and divide by zero; JMP/JSR with a non-zero top nibble are rejected |
| Unverified | Hardware and real HC16 firmware (none freely licensed); Z2/Z3 peripheral maps, the JTEC preset and the calling conventions |

asl requires an operand for LDHI, encodes it in 4 bytes (manual, MAME and MASM: 2) and does not wrap branch distances at 1 MB. MAME prints page-2 ORAA as `ora`, ignores the JMP/JSR top nibble, prints odd branch targets and shows MOVB/MOVW post-increment offsets unsigned. chirpy8/ghidra_68HC16 and rimwall/Ghidra-HC16-Processor were compared only (chirpy8's RTS restores all flags; rimwall has no license and a 16-bit address space).

### ADI SHARC (ADSP-214xx): done (community: @roblg)

| Area | State |
|---|---|
| Decode | 298,048 words (structured + 40,000 random) vs MAME `unidasm sharc` (ADSP-2106x): 0 unexplained (17,429 exact, 108,452 semantic, 81,693 invalid in both, 90,474 in 21 explained classes). Multiplier opcodes vs the PGR tables: 2,048 words, 0 mismatches. VISA consistency with the ISA decode: 151,552 words and 6,529 16-bit parcels, 0 mismatches. 3,862/3,862 constructors reached (loop-end, delay-slot, bit-reverse and SIMD contexts swept) |
| Semantics | Rewritten from the Programming Reference rev 2.4: all flags and sticky bits, ALU saturation, float NaN and denormal flush, FIX/TRUNC modes, 80-bit MR, bit FIFO, circular buffers, bit-reverse, LW, PC/loop/status stacks, and SIMD (PEy half of every instruction). 51 hand-computed emulator programs pass (10 SIMD); broken expectation detected |
| Real code | image_segmentation.dxe (MIT, CCES for ADSP-21489, pinned SHA-256, not committed) through the new DXE loader: 9,060 instructions, 210 functions, 0 bad-instruction or error bookmarks, 209/209 decompile; vs selache seldump (black box) at the same addresses 0 unexplained |
| Doesn't work | SIMD and bit-reverse modes are context assumptions (the SIMD Mode analyzer sets them between MODE1 PEYEN set/clear), not dynamic MODE1; broadcast loads; 40-bit extended float (no p-code type); IDLE/EMUIDLE/FLUSH CACHE are pcodeops; RTI does not pop the status stack (pushed on interrupt entry); RECIPS/RSQRTS return the exact value (seed table unpublished); VISA delay slots need the Delay Slot analyzer; a DO whose loop end precedes it cannot be marked; 48-bit code pointers in data are not followed; two run-time stub tables entered by computed jumps; MULTI_PROC LDR, .doj objects and DWARF |
| Unverified | Hardware or simulator; VISA only for consistency with the ISA decode; memory map and IVT only for the 5-Mbit parts; only one real executable |

MAME's 2106x disassembler misreads type 5 COND and register fields and the type 7a DAG, swaps FLOAT/FIX/RND R/F letters, prints (LR) on RTI, accepts reserved multiplier opcodes and shift-immediate bit 22, and has MR B-register moves off by one. selache seldump on 214xx code gets type 3/4/15/16 DAG fields, VISA lengths of types 7a/16a, shift-immediate opcodes, short compute OP 7, the system register table, type 5/6a/19a and CJUMP targets wrong; the real code agrees with the module in each case examined.

### Motorola MC146805E2: done (community: @gareth8118, Ghidra PR #856)

| Area | State |
|---|---|
| Decode | 251,936 slots vs MAME `unidasm m146805`: 230,120 agree, 20,841 both invalid, 975 MAME quirks (undefined 6E/7E printed as JMP), 0 unexplained; asl (`-cpu 68HC08`) re-assembles all 230,120 to the original bytes. 98/98 constructors reached |
| Semantics | 152 hand-computed emulator cases pass and 2 wrong expectations are detected; 5,998 random single-instruction states vs MAME's MC146805E2 core (run as a black box) identical in A, X, SP, flags, a 496-byte data window and PC. The PR as imported failed 16/152 hand cases and 740/5,998 states: BSET had BCLR's body, BRSET/BRCLR left C alone, NEG on memory took Z/N from the operand, ROR shifted arithmetically, CPX compared A, SWI pushed no CC and jumped to the vector address, MUL (a 68HC05 instruction) was decoded, RSP loaded 0xFF |
| Real code | Five Apache-2.0 programs from tgtakaoka/retro-bionic (pinned commit + SHA-256): 1,391 instructions identical to the author's listings, 55/55 functions decompile, 0 bad-instruction bookmarks |
| Doesn't work | Stack-pointer wrap within 0x60-0x7F (masking SP would break the decompiler's stack analysis; 201/210 wrap-only cases fail by design); 13-bit address wrap; BIL/BIH (IRQ pin pcodeop); timer, ports and interrupt dispatch. The PR's second language, `6805:BE:16:default`, was dropped because Ghidra ships it |
| Unverified | Real hardware; the Motorola data sheet (MUL's absence rests on MAME and asl agreeing); stack extent (the PR's pspec says 0x40-0x7F, MAME 0x60-0x7F); the pspec memory map and vectors come from the PR |

### Fairchild F8: done (community: @polartape, Ghidra PR #9087)

| Area | State |
|---|---|
| Decode | 115,472 slots vs MAME `unidasm f8`: 108,593 agree, 1,177 both invalid, 5,702 explained MAME gaps, 0 unexplained; asl (`-cpu F3850`) re-assembles all 114,295 decoded slots to the original bytes (13 branch-wrap cases asl cannot encode). 228/228 constructors reached |
| Semantics | 129 hand-computed emulator cases pass and 2 wrong expectations are detected; 6,570 random single-instruction states vs MAME's F8 core (run as a black box) identical in all registers, the whole scratchpad and PC. The PR as imported differed only in PI/JMP, which leave the target's high byte in A (5/131 hand cases, 59/6,570 states) |
| Real code | Jim Loos's MK38P70 monitor, MK3850 monitor and Tiny BASIC (MIT, pinned commits + SHA-256, assembled with asl): disassembly identical to the asl listings (747, 763 and 2,481 instructions), 46/46 functions decompile, 0 bad-instruction bookmarks |
| Doesn't work | 12-bit address wrap of the single-chip parts (16-bit as in MAME); interrupt dispatch and timer (vectors are entry symbols only); the single-level PC1 stack loses nested return addresses, as on the chip; the calling convention is a guess; undefined opcodes 2D-2F; raw binaries only |
| Unverified | Real hardware; scratchpad register 15 and INS/OUTS 2/3 (asl accepts them, MAME's core executes them, its disassembler prints data); port I/O data (hand cases only); the F8 manuals the PR cites were not available |

MAME `unidasm f8` prints BT 5 / BF 5 as BP / BM and does not know register 15 or ports 2/3.

### ARC32 (ARCtangent-A4/A5): done (community: @cyrozap, Ghidra PR #3233)

| Area | State |
|---|---|
| Decode | vs libopcodes 2.25.1 (built here; 2.45 dropped the A4/A5 disassembler), both byte orders: 276,480 field-enumerated, 258,240 low-word and 50,000 random slots, 0 unexplained (explained: extension majors, optional instructions, extension conditions, reserved encodings). 600/600 constructors reached per language |
| Semantics | 42/42 hand-computed emulator sequences per byte order; broken expectation detected. Fixed here: MAX/MIN/NORM, `.jd` delay slots, `lp` loops and the other upstream TODO/FIXMEs; cspec, pspec and DWARF map from GCC 4.5.4 output |
| Real code | zlib 1.3.1 and crypto-algorithms built with GCC 4.5.4 (pinned URLs + SHA-256), LE and BE: 157 functions, 52,712 instructions, 0 bad instructions, 0 error bookmarks, every function decompiles, disassembly 100% semantically equal to objdump, switch tables recovered. Analyzers for `sr`-initialised loops and GCC's `j.d [r]` / `add blink,blink,2` indirect calls |
| Doesn't work | Extension instructions/conditions and brk/sleep/swi are pcodeops (customer or system hardware); libgcc routines returning through a copy of blink decompile with "treating indirect jump as call" (C is correct); `lp` loops need EmulatorHelper, because PcodeEmulator ignores globalset (Ghidra #9337) |
| Unverified | Real A4 firmware (none freely licensed); optional instructions checked only against the manual |

PR #6344 (@dgenin), listed as ARCv2, is the same ARCtangent-A4 ISA; it is credited for the `sr [lp_end]` loop set-up idea, and no code was copied. binutils 2.25.1's ARC disassembler reads uninitialised locals (the oracle was built with `-ftrivial-auto-var-init=zero`) and drops the delay suffix of `j`/`jl limm` when the condition has no name; GCC 4.5.4 built as a 64-bit host program ICEs in extract_insn.

### PS2 Emotion Engine (R5900): done (community: @chaoticgd, @beardypig)

| Area | State |
|---|---|
| Decode | 153,280 enumerated + 100,000 random words vs GNU objdump 2.45 `-m mips:5900` and rabbitizer 1.16.2: 0 unexplained; 275/275 wasaylor/r5900-opcodes (MIT) entries decode as listed; 667/667 constructors reached |
| Semantics | Real p-code for the base ISA, all 107 MMI instructions, COP0 Status/EPC, COP1 with FCR31 flags and VU0 macro mode (lane registers, dest masks, vf0/vi0, ACC, Q/I/R, clipping, MAC/Status flags, VU0 memory at 0x11004000); upstream had MMI/VU as pcodeop stubs. 122/122 hand-computed emulator cases; broken expectation detected |
| Real code | 11 PS2SDK samples built with pinned ps2dev v2.0.0: 380,075 instructions and 4,824 functions, auto-imported as r5900, 0 error bookmarks, 0 decompile failures, 100% agreement with objdump; hardware-register references created |
| Fixed here | About 30 base-MIPS/COP0/COP1 bugs (DIVU signed, TGE unsigned, shift masks, reserved fields, JALR rd=rs, BGEZAL ra, overflow traps, LQ/SQ alignment, $zero reads, COP0 Count folding, FPU register order and more); opinion by EF_MIPS_MACH; ELF extension claims only PS2 ELFs (it broke Allegrex); hardware registers as default symbols |
| Doesn't work | EE FPU/VU non-IEEE arithmetic (clamping, denormal flush, round toward zero): p-code float ops are IEEE round-to-nearest (flags are set as hardware does); VRNEXT is a pcodeop (LFSR polynomial in no non-GPL source); VCALLMS/BC2x/Count/Random/TLB/cache/performance counters are hardware state; VU micro mode is a separate processor; overlays, FID, DWARF 1 and IOP modules are outside the processor module |
| Unverified | Issues reported against commercial games or the BIOS (not reproducible on legal samples); flag behaviour exactly at the clamp boundary |

GNU objdump `mips:5900` decodes JALX, WAIT, CFC0/CTC0 and MIPS III FPU conversions the R5900 lacks, has no VSQRT, decodes SQRT.S with the wrong operand field and rejects VU macro words with non-zero reserved fields that compilers emit. rabbitizer 1.16.2 falls back to generic MIPS III tables for R5900 and rejects SYSCALL with a code.

### Intel i960: done (community: @mumbel, Ghidra PR #1452)

| Area | State |
|---|---|
| Decode | 357,008 slots (exhaustive mode corpus + 250,000 random) vs GNU objdump 2.28 (built with the i960 target) and MAME `unidasm i960`: 0 unexplained against either (vs objdump: 34,781 identical, 23,073 equivalent, 283,000 both invalid, 16,191 explained). 289/289 constructors reached |
| Semantics | 52 hand-computed emulator cases pass in both languages; broken expectation detected. Reworked here from Intel's manuals: operand encodings (M/S bits, literals, COBR src1), semantics, cspec for the i960 calling convention; the LEBE language now has its own .sla (it pointed at the LE one and could not load) |
| Real code | GCC 2.95.3 (-mka/-mkb, built from pinned sources) builds of B-Con crypto, FP math and Intel's newlib i960 string routines: crypto.elf 6,623 instructions agree with objdump (66 are binutils display bugs), 108/108 functions decompile, 0 bad bookmarks; fpmath 28/28; 80960Cx routines 7/7; COFF build auto-detected, 40/40 decompile. 28 relocatable objects: 0 bytes differ from GNU ld. Boot Record analyzer marks IBR/PRCB on a test ROM |
| Doesn't work | Transcendental FP ops (sinr, cosr, tanr, atanr, logr, logepr, expr) and privileged hardware ops (caches, interrupts, DMA, process management, calls, halt) are pcodeops; the decompiler shows the frame-save stores `call` makes (unaff_r4 in 12/108 functions); COFF symbols carry no function type, so only labels |
| Unverified | Silicon or a cycle-accurate simulator; Cx/Jx/Hx SFR names and the IBR/PRCB layout (manuals only; no freely licensed firmware with a boot record); MC process/debug instructions are decode-only |

Upstream's `scripts/scrape.py` transcribed the GPL binutils 2.30 opcode table and is removed from the fork. Reference-tool bugs: binutils puts the T bit in CTRL targets, has dcinva at 0xAC (manual 0xAD) and movre at 6E1 (manual 6E9), decodes the integer src1 of cvtir/cvtilr/scaler/scalerl as FP, and accepts literal destinations; MAME rejects M=1 S=1 in unused fields and M3=1 SFR operands, lacks ldtime/condrec, and accepts FP literal destinations.

### STMicroelectronics ST7: done (community: @agatti, Ghidra PR #3631)

| Area | State |
|---|---|
| Decode | vs asl (AS 1.42) `-cpu ST7`: 530 forms enumerated from the PM0002 manual give 513 exact, 17 documented aliases, 0 different; 60,000 random strings per language, 0 mismatches. 164/164 constructors reached. The PR had 13 SLEIGH pattern conflicts and accepted chained pre-bytes |
| Semantics | 142 (ST7) and 143 (ST72) hand-computed emulator cases pass and a broken expectation is detected (the PR head failed 30 of the 142); 19,941/19,941 runnable random single instructions agree with an independent model written from PM0002. Rewritten here: flags, stack, every addressing mode, jumps, TRAP |
| Real code | Five Digi RabbitNet ST72264 firmware images (MPL-2.0, pinned URL + SHA-256, not committed): 917-2,150 instructions and 58-71 functions each, 0 decompile failures; all 6,783 instructions round-trip through asl |
| Doesn't work | HALT/WFI are userops; interrupt entry, peripherals, SP wrap and the device-dependent SP high byte not modelled; vector-table size guessed; no DWARF register map, and the calling convention is a guess (no ST7 C compiler exists) |
| Unverified | ST72 I1/I0 priority semantics (PM0002 is silent; upstream's definition kept); whether LD S,r sets N/Z; CC bits 7-5 reading as 1; the ELF opinion (e_machine 68, no sample); devices other than the ST72264 |

SDCC has no ST7 port and MAME no ST7 disassembler, so the oracles were asl and the uCsim ST7 simulator (black boxes) plus the manual model. uCsim defects found: LD (X),X printed with Y, SWAP X printed as swapw, CP X,#imm treated as 16-bit, JP jumping to the byte stored at the target, LD leaving N/Z unchanged, BTJx not setting C, TRAP missing, 92-prefixed BSET/BRES/BTJx ignoring the pointer, PUSH CC omitting bits 7-5, 16-bit X/Y.

### NEC uPD78xx (78C10): done (community: @ajxs, @depili; Ghidra PR #7930)

| Area | State |
|---|---|
| Decode | vs MAME `unidasm upd7810`: 196,608 slots + 200,000 random words, 0 unexplained (153,951/160,022 exact, 36,777/33,832 equal after number normalisation, 5,868/6,139 invalid on both, 12/7 explained). vs asl `-cpu 78C10`: all 2,607 operand combinations of the manual's 213 forms decode to the assembler source and nothing outside them decodes. 317/317 constructors reached |
| Semantics | 2,616 emulator cases: 132 hand-computed (incl. the manual's DAA, RLD/RRD, SOFTI/RETI examples), 2,404 randomised against an independent model of the manual, 80 whole programs against Python references (sum, bubble sort, multiply, BCD add, strcmp, CRC-8, popcount, table lookup + BLOCK); broken expectation detected. Fixed in the PR: ANAX opcode, LDEAX/STEAX, unreadable/unwritable register operands, ZCM,A, OFFI, SKIT flag, SBBW/DSBB spelling; ORI r operated on A, MUL multiplied EA, DIV remainder register, INR/DCR changed CY, GT compare flags, DADC/DSBB carries, DAA was a pcodeop, TABLE address, SKIT/SKNIT flag reset, SOFTI could be skipped |
| Real code | DiKon (MIT, hand-written 78C10, 1,833 bytes, pinned commit + SHA-256): 682 instructions identical to MAME, 14 functions, 0 decompile failures, 0 bad-instruction bookmarks; 3 error bookmarks are jumps into a ROM not in the image. CALT table calls 3/3 resolved |
| Doesn't work | EI/DI/HLT/STOP and interrupt-enable state are user ops; peripherals and port pin vs latch; manual stack manipulation returning with RETS; division by zero (undefined in the manual); other cores (7800/7801/7802, 78C05/06, 7807/8/9, NMOS 7810) deliberately not implemented; no ELF/DWARF/loader |
| Unverified | Real silicon; 16-bit half-carry (uses bit 3 of the low byte) and NEGA flags (manual silent); only one freely licensed real program (1.8 KB) |

MAME decodes SK/SKN flag code 001 as NV (a 7807-series flag) and EADD/ESUB EA,V, which the 78C1x manual and asl reject (the 12/7 explained slots).

### Intel 8008: done (community: @spirosekulovski, Ghidra PR #8007)

| Area | State |
|---|---|
| Decode | 170,464 slots vs MAME `unidasm i8008`: 0 differences (168,039 agree, 2,425 both invalid); asl (`-cpu 8008new`) re-assembles all 168,039 to the original bytes; 52/52 constructors reached |
| Semantics | 95 hand-computed emulator cases and 2 wrong expectations detected; 7,410 random single-instruction states vs MAME's i8008 CPU core (run as a black box) identical. The PR as imported failed 30/95 hand cases and 2,344/7,410 states (parity never computed, ADC/SBB used an overwritten carry, 16-bit M and addresses, HALT spelling) |
| Real code | Jim Loos's monitor and Paul Robson's Tiny BASIC (both MIT, pinned URL + SHA-256): every instruction identical to the assembler listings and MAME, 58/58 functions decompile, 0 bad-instruction bookmarks (error bookmarks only for jumps into RAM stubs) |
| Doesn't work | Return-stack overflow (more than 7 nested calls; modelled as a normal stack at 0xFFF0-0xFFFF to keep the decompiler working); interrupts and READY; the six undefined opcodes are not decoded; no wrap at 0x4000; raw binaries only |
| Unverified | Real hardware; IN port data (MAME's mod8 has none) |

### MELPS-740: done (community: @philpem, Ghidra PR #5012)

| Area | State |
|---|---|
| Decode | 506,365 records per language (all opcode × operand bytes, 3-byte forms × 22 high bytes, 120k random) vs MAME `unidasm m740`: 0 unexplained (451,998 exact; about 53k reserved opcodes where MAME decodes 6502 leftovers; 1,200 FST/SLW forms MAME lacks). Vs asl `-cpu MELPS740`: 275/273/276 accepted forms agree and 148k records re-assemble to the original bytes. Every constructor reached (115/114/116) |
| Semantics | Emulator 64/64/66 hand-computed from the 1989 Series 740 manual (binary and decimal ADC/SBC, T flag, addressing incl. zero-page wrap, bit ops, branches, JSR/BRK/RTI stack bytes, MUL/DIV, both stack pages); broken expectation detected. Fixed: T flag ignored, MUL/DIV missing, special-page JSR, ADC V flag, STA #imm at 0x89, stack in page 1 (the 740 stack is zero page), JSR pushing the next address, BRK vector, zero-page pointer wrap |
| Real code | SBC740 OSI/MS BASIC assembled with ca65: 3,667/3,667 instructions identical to the assembler and MAME in all 3 languages; 109 functions, 108/108 decompile; L-chika 18/18; 21 bad-instruction bookmarks, all explained |
| Doesn't work | FST/SLW/WIT/STP are pcodeops (clock state); peripherals and interrupts; BRK vector fixed at FFF4; vector targets disassembled but not made functions; 16-bit SP (deliberate); no ELF/DWARF (no toolchain) |
| Unverified | Decimal-mode N/V/Z; DIV by zero (no-op); zero-page pointer wrap at FF; SFR names (from the PR); hardware |

MAME m740 lacks FST/SLW/MUL/DIV. asl 1.42 b315 encodes `LDA ($zz)` as the 65C02 form (JMP ($zz) on the 740), accepts all of FST/SLW/WIT/MUL/DIV for any device, and aborts after about 40 errors in one run.

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

### NS32016 / NS32532: done (community: @raybellis; instruction set regenerated here)

| Area | State |
|---|---|
| Decode | 402,804 slots per variant (binutils opcode table × 32×32 mode fields, all option/register values, 200,000 random) vs libopcodes and MAME `unidasm`: 0 unexplained (default: 297,844 agree, 31,480 both invalid, 73,480 explained; NS32532: 313,164 / 31,480 / 58,160). Constructors reached 1,624/1,624 and 1,670/1,670 |
| Semantics | Full p-code for the NS32016, NS32081 FPU and NS32082 MMU instructions, plus the NS32532 variant. Emulator 1,251 (default) and 1,258 (NS32532) tests, 0 failed, 3 deliberately wrong expectations detected each; hand-computed groups plus random vectors × 22 ALU/shift/mul/div ops × 3 sizes against an independent Python model |
| Real code | 31 NetBSD 1.5 pc532 programs and libraries (cc1, cc1plus, f771, gdb, libc, libm, …) auto-imported by the new a.out loader: 1,175,301 instructions, 1,175,292 identical to libopcodes (the other 9 are a binutils `cxp` bug); 2,794 functions decompiled, 2 failures (libm) |
| Doesn't work | Hardware operations (SVC/BPT/FLAG traps, WAIT, EOI, RDVAL/WRVAL, CINV, TLB purge) are pcodeops; NS32381 POLY/DOT/SCALB/LOGB pcodeops (no documentation); FSR flags and rounding mode, interrupts and the 24-bit bus not modelled; no ELF/DWARF (no such toolchain exists) |
| Unverified | No hardware or ns32k emulator oracle for semantics (MAME source only): ROUND ties-even, CMPf N rule, DIV floor (MAME differs), CHECK/INDEX/BCD details, NS32381 register aliasing, NS32332 and CG16 |

Reference-tool bugs: binutils: `@disp` printed as decimal digits read as hex, `cxp` operand shown as an address, 19-bit ids compared on 16 bits, `sfsr` index byte misdecoded; gas `$` immediate parsed as a symbol. MAME: 64-bit immediate low dword FFFFFFFF, MOVM/CMPM negative length unsigned, SFSR decodes an unused field.

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
