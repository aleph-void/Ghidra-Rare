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

### SASS: Ampere/Ada committed, other generations in progress

| Area | State |
|---|---|
| Done | SM80, SM86, SM89 committed. vs `nvdisasm`: 96.9–97.6% of random words, 99.94% of a held-out bitsandbytes sm_86 cubin, 100% of our own ptxas kernels; 99.99% on the cuRAND corpus (local-only check, never committed). Auto language selection from `e_flags` (CUDA ≤12 and CUDA 13 layouts) |
| In progress | SM75, SM90, SM100, SM120 (128-bit); SM52 (64-bit) learning; 64-bit control-word support written, untested |
| Not started | Volta (SM70/72), Kepler (SM35/37), remaining Pascal/Maxwell variants |

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
