# MicroBlaze processor module for Ghidra

A SLEIGH processor module for the AMD/Xilinx MicroBlaze soft processor. It was written
clean-room from AMD UG984, *MicroBlaze Processor Reference Guide* (v2022.1), and checked
against GNU binutils `objdump`. It targets Ghidra 12.1.4.

## Languages

| Language ID               | Description                                    | ELF auto-select              |
|---------------------------|------------------------------------------------|------------------------------|
| `MicroBlaze:BE:32:default` | 32-bit MicroBlaze (C_DATA_SIZE=32), big endian    | e_machine 189 / 0xBAAB, ELF32 MSB |
| `MicroBlaze:LE:32:default` | 32-bit MicroBlaze, little endian                  | e_machine 189 / 0xBAAB, ELF32 LSB |
| `MicroBlaze:BE:64:default` | 64-bit MicroBlaze (C_DATA_SIZE=64), big endian    | e_machine 189, ELF64 MSB     |
| `MicroBlaze:LE:64:default` | 64-bit MicroBlaze, little endian                  | e_machine 189, ELF64 LSB     |

The 64-bit languages use 8-byte registers and 64-bit addresses. They contain the full
32-bit instruction set plus the 64-bit extensions. AMD tools only produce little-endian
64-bit code; the big-endian 64-bit language is provided for completeness.

## Files

- `data/languages/microblaze.sinc`: registers, the imm/imml context, operand tables, and the
  whole 32-bit ISA.
- `data/languages/microblaze64.sinc`: the 64-bit extensions. These are long arithmetic, logic
  and compare (`addl`, `cmpl`, `andl`, `pcmpleq`...); `imml` prefixes (one or two of them);
  the `addli`/`addlik` style two-operand opcode 0x1a; long barrel shifts and bit fields
  (`bslll`, `bslrai`, `bslefi`...); `ll`/`sl`/`lli`/`sli`/`llr`/`slr`; `sextl8/16/32`; and the
  extended-address branches `bea*`/`beal*`/`brea*`.
- `data/languages/microblaze_fsl.sinc`: the stream instructions `get`/`put`/`getd`/`putd`
  with every n/c/t/a/e flag combination (there are 128 forms). `scripts/gen_fsl.py`
  generates this file.
- `microblaze_{be,le}{32,64}.slaspec`: thin variant wrappers.
- `microblaze.ldefs`, `microblaze.opinion` (ELF), `microblaze32.pspec`, `microblaze64.pspec`
  (the PC and the reset/interrupt/exception vectors), `microblaze32_{be,le}.cspec` and
  `microblaze64.cspec`.
- `microblaze.dwarf`: DWARF register mapping (r0-r31, r1 = stack pointer, CFA = r1 at entry),
  so Ghidra's DWARF analyzer can import gcc debug info (function prototypes, types, locals).
- `src/main/java/.../MicroBlaze_ElfRelocationHandler.java` (+ `MicroBlaze_ElfRelocationType`):
  ELF relocation handler for the `R_MICROBLAZE_*` types (coverage under "Known gaps").
- `src/main/java/.../MicroBlaze_ElfExtension.java`: ELF loader extension that makes PIC
  PLT stubs resolvable (r20 = GOT over `.plt`, PLT entries named after their JUMP_SLOT
  symbols so they become thunks).

## What is decoded

The full UG984 instruction set, including all the optional units:

- The integer ALU, including the carry and keep variants.
- `mul`/`mulh`/`mulhu`/`mulhsu`/`muli` and `idiv`/`idivu`.
- The barrel shifter, both register and immediate forms, plus `bsefi`/`bsifi`.
- The single-precision FPU (`fadd` through `fsqrt`, every `fcmp.*`, `flt`/`fint`).
- The 64-bit double-precision FPU (`dadd` and the rest, `dbl`/`dlong`).
- Pattern compare (`pcmpbf`/`pcmpeq`/`pcmpne`).
- `clz`, `swapb`/`swaph`, `sext8`/`sext16`, `src`/`srl`/`sra`.
- `msrset`/`msrclr`, `mfs`/`mts` and `mfse`/`mtse` with objdump's special register names,
  and `mfs rD, rpvrN`.
- Loads and stores: byte-reversed (`lbur`, `lhur`, `lwr`...), exclusive (`lwx`/`swx`), and
  extended-address (`lbuea` through `swea`).
- The cache operations `wic`, `wdc`, `wdc.flush`, `wdc.clear`, `wdc.clear.ea`,
  `wdc.ext.flush` and `wdc.ext.clear`.
- `mbar`, `sleep`, `hibernate`, `suspend`, and the TLB operations.
- Every branch, return and break form.

**imm / imml prefixes.** A prefix stores its value in context registers with `globalset`,
and the next Type B instruction picks it up. The displayed operand is the instruction's own
16-bit field, which is what objdump prints. The value used in p-code and in references is
the combined 32-bit value (`imm`), 40-bit value (one `imml`) or 64-bit value (two `imml`).
Branch targets are shown as resolved addresses.

**Flow.** All the `…d` branch forms and `rtsd`/`rtid`/`rtbd`/`rted` use `delayslot(1)`.
`rtsd r15, 8` is a return. `brlid r15, …` and `brald` are calls. `bra`/`brad` through a
register are computed jumps. `brki rD, imm` is a call to the vector, with two exceptions
found in real code: `brki r14, 0x8` (the Linux system call) is
`r3 = syscall(r12, r5, …, r10)` and falls through, and `brki r0, -1` (gcc's
`__builtin_trap()`) is `trap()` and does not return.

## Semantics

There is real p-code for the following:

- Integer ALU ops. The carry flag `C` is its own register and is merged into `rmsr` by
  `mfs`, `mts`, `msrset` and `msrclr`.
- Compares, multiply and divide, shifts and barrel shifts, bit-field extract and insert,
  sign extension, `swap*` and `pcmp*`.
- All loads and stores. Byte-reversed accesses really do swap the bytes. `lwx`/`swx` keep
  a reservation bit.
- Branches and calls, with conditions evaluated before the delay slot.
- FPU and DFPU arithmetic, compares and conversions, using float p-code.
- All of the 64-bit long operations.

Named pcodeops (each still reads and writes the correct registers) model the stream I/O
(`fslGet`/`fslPut`), cache and TLB maintenance, barriers, sleep, extended-address
loads/stores, PVR reads, `clz`, the `pcmpbf` byte count, the Linux `syscall` and `trap`.

**Calling convention** (UG984 chapter 4):

- Arguments are in r5 to r10, then on the stack at `r1+28` (or `r1+56` on 64-bit). On
  32-bit cores a 64-bit argument takes the next two registers with no alignment
  (`f(p, u64 x)` is p = r5, x = r6:r7), most significant word first on big endian and
  least significant first on little endian; this is a `<join/>` rule in the cspec.
- The result is in r3, with r3:r4 holding 64-bit values on 32-bit cores.
- The return address is in r15, and r19 to r31 are callee-saved.
- r2 and r13 are the small-data anchors, and r14/r16/r17 hold the interrupt, break and
  exception return addresses.

## Test results (`test/run-tests.sh`)

The reference disassemblers are:

- **32-bit:** upstream GNU binutils 2.45 `objdump -m microblaze`.
- **64-bit:** AMD/Xilinx-patched binutils 2.42, built by `test/build-xlnx-binutils.sh`
  from the meta-xilinx rel-v2025.1 patch series. Upstream binutils has no 64-bit
  MicroBlaze.

Three kinds of corpora are used:

- **fuzz:** words taken from the opcode tables with their operand fields randomised, plus
  uniformly random words, plus words with imm/imml prefixes. There are about 41k words for
  32-bit and 50k for 64-bit.
- **asm:** gas output for every table mnemonic.
- **vec:** hand-built vectors covering every Type B instruction with and without
  `imm`/`imml` prefixes, and the branch/return forms.

In the results below, a match also counts words that both tools reject. BE and LE give
identical results.

| Corpus                         | Words  | Agreement |
|--------------------------------|--------|-----------|
| fuzz32 vs binutils 2.45        | 41,329 | 99.56 % (180 mismatches; all are objdump bugs, see below) |
| asm32 vs binutils 2.45         | 860    | 98.95 % (9 mismatches; objdump bugs) |
| vec32 vs binutils 2.45         | 523    | 100 %     |
| fuzz64 vs Xilinx objdump       | 50,315 | 99.89 % (57 mismatches; all `wdc.ext.clear`) |
| asm64 vs Xilinx objdump        | 1,325  | 99.77 % (3 mismatches; `wdc.ext.clear`) |
| vec64 vs Xilinx objdump        | 1,618  | 100 %     |
| fuzz32 vs Xilinx objdump       | 41,329 | 95.1 % (the Xilinx objdump also decodes 64-bit-only opcodes in 32-bit mode) |

Coverage of the mnemonics in the opcode tables:

- **32-bit:** 279 of the 290 names in binutils 2.45 appear in the corpora and match. The
  other 11 are assembler pseudo-ops (`la`, `lmi`, `smi`, `nop`, `not`, `sub`, `tuqula`,
  `rtb`), or are instructions objdump never prints because of the bugs below.
- **64-bit:** 389 of the 411 Xilinx table names appear and match. objdump prints the
  `bealXXi` forms as `imml` + `beaXXi`, and so does Ghidra.

The remaining mismatches are all objdump bugs, confirmed in `opcodes/microblaze-opc.h`:

- `bslli`/`bsrai`/`bsrli` use `OPCODE_MASK_H3B` (0xFC00F9E0), which leaves out the S/T bits
  (bits 9 and 10). objdump therefore prints all three as `bsrli`, and also accepts the
  undefined S=T=1 form. Ghidra decodes them as UG984 specifies.
- `wdc.clear` uses mask 0xFC0000FF and comes before `wdc.ext.clear` in the table, so
  `wdc.ext.clear` (low 11 bits 0x466) is printed as `wdc.clear`.

**Emulator tests** (`test/emu_tests.py` and `test/EmuCheck.java`) run instruction sequences
in Ghidra's p-code emulator and check the resulting register values. They cover:

- Arithmetic and carry, compares, multiply and divide.
- Barrel shifts and bit fields, logic, `pcmp`, `sext`, shifts, `clz`, `swap`.
- Loads and stores, calls and returns with delay slots, conditional branches, MSR carry,
  and the FPU.
- `imm` prefixes, plus `imml`, long ALU, `ll`/`sl`, `bslll`, `sextl32` and the DFPU on
  64-bit.

Results: 32/32 pass on BE32 and LE32, and 44/44 pass on BE64 and LE64.

**ELF import and decompile** (`test/elf`, `test/DecompileCheck.java`):

- **32-bit (`mbtest_be.elf`, `mbtest_le.elf`):** these are linked executables built from
  hand-compiled, gcc-style assembly (`mbtest.s`, with the C equivalent in `mbtest.c`).
  Ghidra auto-selects the language, finds all 10 functions with no error bookmarks, and
  decompiles them to clean C. That includes the r1+28/+32 stack arguments, the 64-bit
  r3:r4 return, a loop, a lookup-table switch and the MMIO store.
- **64-bit (`mbtest64_le.o`):** a relocatable ELF64 object built with Xilinx `gas -m64`.
  All 5 functions decompile, with `imml` constants folded (for example
  `param_1 + 0x123456789abc`).
- These ELFs are hand-written assembly. Real gcc output is covered by the real-world
  binaries below.

## Real-world binaries (`test/real-binaries.sh`)

`test/fetch-real-samples.sh [dir]` downloads four public, gcc-built binaries, pinned by URL
and SHA-256 (nothing is committed). `test/real-binaries.sh [dir] [workdir]` then imports each
one headless with no `-processor` flag, runs auto-analysis, decompiles every function
(`RealCheck.java`, 60 s timeout each) and diffs every instruction Ghidra found against
objdump at the same address (`compare.py`).

| Sample | Source | Format |
|--------|--------|--------|
| `zcu102-zynqmp_pmufw.elf` | AMD/Xilinx [soc-prebuilt-firmware](https://github.com/Xilinx/soc-prebuilt-firmware) `xlnx_rel_v2025.2` (commit 7319a74d), ZynqMP PMU firmware | ELF32 LE executable, DWARF 5 |
| `vck190-versal_psmfw.elf` | same, Versal PSM firmware | ELF32 LE executable, DWARF 5 |
| `vck190-versal_plmfw.elf` | same, Versal PLM firmware | ELF32 LE executable, DWARF 5 |
| `libc.so.6` | Bootlin toolchain `microblazebe--glibc--stable-2025.08-1` | ELF32 BE shared object (PIC, GOT/PLT, 6,400 dynamic relocations) |

Results (the sources are in Xilinx/embeddedsw `lib/sw_apps/{zynqmp_pmufw,versal_psmfw,versal_plm}`):

| Sample | Language picked | Functions | Bad instr. | Decompiled | Disassembly vs Xilinx objdump |
|--------|-----------------|-----------|------------|------------|-------------------------------|
| pmufw  | LE:32 | 390 | 0 | 390 / 390 | 18,139 / 18,139 words (100 %) |
| psmfw  | LE:32 | 275 | 0 | 275 / 275 | 11,089 / 11,089 (100 %) |
| plmfw  | LE:32 | 695 | 0 | 695 / 695 | 69,211 / 69,211 (100 %) |
| libc.so.6 | BE:32 | 3,735 | 0 | 3,715 / 3,722 (7 timeouts) | 445,575 / 445,575 (100 %) |

- **Disassembly.** Every instruction Ghidra found matches the Xilinx objdump. Against
  upstream binutils 2.45 the only differences are its `bsrli`/`bslli`/`bsrai` mask bug
  (254, 126 and 703 words in the three firmware images). The words Ghidra does not reach
  (10, 6, 24 and 5,486) are alignment `nop`s, two unreferenced gcc code fragments with no
  symbol, and, in libc, the unwind cleanup landing pads (glibc is built with `-fexceptions`) plus the computed-goto labels of
  `vfprintf`. None of them is reachable by normal flow.
- **Decompilation.** gcc's prototypes, types and locals come in from DWARF, and the
  decompiled code reads like the C source: switch tables, 64-bit arguments and returns,
  struct accesses and MMIO. In libc, GOT-relative globals resolve
  (`*PTR_stdout_0022ac98`), PLT stubs are thunks (`malloc`, `free`, `__tls_get_addr`...)
  and system calls show up as `syscall(0x8c, fd, ...)`. The 7 libc timeouts are the
  very large `__gconv_transform_*` and `strtod`/`strtof` internals.
- **Relocations.** libc: 6,372 applied, 15 skipped (NONE, TLS module IDs), 17
  thread-local relocations reported as warnings, 0 errors. The relocatable-object check
  imports `test/elf/mbtest.s` assembled by Xilinx gas (15 relocations, `R_MICROBLAZE_64`
  and `R_MICROBLAZE_32_PCREL_LO`) and compares it with the same object linked by Xilinx
  `ld` at Ghidra's addresses. All 118 words are identical, BE and LE.

Problems the real binaries found, all fixed:

| Problem | Before | After |
|---------|--------|-------|
| No DWARF register mapping. Ghidra's DWARF import threw an NPE for every function, so no prototypes, types or locals were imported. | every function `undefined f(void)` | prototypes from DWARF (`microblaze.dwarf`) |
| No ELF relocation handler. GOT entries in libc stayed 0. | 6,404 relocation errors, 363 bad-instruction bookmarks, 121,752 undefined code bytes | 0 errors, 0 bad instructions, 21,960 bytes |
| `brki r14, 0x8` (the Linux syscall) was a call to address 8, and `brki r0, -1` (`__builtin_trap`) a call to 0xffffffff. | flow errors and bad data in libc | `syscall(...)` (falls through) and `trap()` (no return) |
| 64-bit arguments (`u64`, `long long`) were not passed in register pairs. | `in_r6`/`in_r7` artefacts | `<join/>` rule: `f(p, u64 x)` gives x = r6:r7 |
| PIC PLT stubs use r20 (GOT pointer) set by the caller, so they could not be resolved. | `(**(code **)(unaff_r20 + 0x14))()` | thunks: `free`, `malloc`, ... |

Before these fixes libc had 4,155 functions, many of them spurious ones created from unrelocated data. 66 of them decompiled with `halt_baddata` and 72 had unrecovered jump tables; after the fixes the counts are 0 and 7 (the 7 are genuine `bra` register jumps). 13 libc functions in the plain list are external-linkage stubs that Ghidra places in its fake `EXTERNAL` block; these are not decompiled.

## Known gaps

- **DWARF line tables.** Ghidra rejects a few hundred source-map (line number) entries in
  each firmware image with "IllegalArgumentException for source map entry ... -55". Its
  line-program reader computes negative line numbers for these gcc DWARF 5 line tables
  (`line_range` 242), while readelf decodes them correctly. This is a generic Ghidra DWARF
  issue: it only creates the `Error/DWARF` bookmarks (121, 200 and 94 in the firmware) and
  does not affect code, functions or types. The "un-recoverable expressions" in the DWARF
  summary are optimised-out locals, which are normal.
- **Calls through the GOT.** These decompile as `(*(code *)PTR_strlen_0022ae00)()`, which is
  the usual Ghidra rendering for PIC code. The callee is named, but its arguments are not
  shown unless the callee has a prototype.
- **Relocation handler coverage.** Applied and checked against ld: `32`, `REL`, `GLOB_DAT`,
  `JUMP_SLOT`, `64`, `32_PCREL_LO`. Implemented from bfd but untested: `32_PCREL`,
  `64_PCREL`, `32_LO`, `SRO32`/`SRW32`, `GOTPC_64`, `GOTOFF_*`, `PLT_64`, and the 64-bit
  `imml` and `IMML_64` forms. Not applied (they need a linker-built GOT or the TLS runtime,
  and are reported instead): `GOT_64`, `TLSGD`, `TLSLD`, the TLS offset types,
  `TEXTREL*` and `COPY`.
- **MMU and privileged effects are only modelled as pcodeops.** This applies to TLB
  writes, cache maintenance, `sleep`/`hibernate`/`suspend` and stream I/O. Exceptions such
  as divide-by-zero, FPU exceptions and unaligned access are not modelled.
- **Extended-address loads and stores** (`*ea`) use pcodeops with the full 64-bit address
  (`rA:rB`). The decompiler does not see them as ordinary memory accesses.
- **Big-endian 64-bit is untested against real tools.** The Xilinx `gas -m64` emits only
  little-endian ELF64. The BE64 language passes the same disassembly and emulator tests
  on raw binaries. No real 64-bit MicroBlaze binary was available.
- **Small-data anchors are not tracked.** r2/r13 are not set from `_SDA_BASE_`/`_SDA2_BASE_`,
  so `lwi rX, r13, off` references are not resolved automatically. None of the real
  samples uses small-data addressing: the Xilinx firmware sets r2/r13 but never
  dereferences them.

## Building and testing

```sh
export GHIDRA_INSTALL_DIR=/path/to/ghidra_12.1.4_PUBLIC
$GHIDRA_INSTALL_DIR/support/sleigh -a data/languages      # compile .sla
gradle buildExtension                                     # extension zip in dist/ (.sla + lib/MicroBlaze.jar)

# full test (rebuilds corpora, runs Ghidra headless + reference objdumps, emulator, ELF checks)
MB_GHIDRA=/path/to/ghidra_12.1.4 OBJDUMP=/path/to/binutils-2.45/objdump \
  XBU=/path/to/xlnx-binutils/build test/run-tests.sh [workdir]

# real-world binaries (downloads ~60 MB once; compiles the Java part with javac)
test/fetch-real-samples.sh samples
MB_GHIDRA=/path/to/ghidra_12.1.4 XOBJDUMP=/path/to/xlnx-binutils/build/binutils/objdump \
  XBU=/path/to/xlnx-binutils/build XLD=/path/to/xlnx-binutils/build-ld \
  test/real-binaries.sh samples [workdir]
```

The Java part (the relocation handler and the ELF extension, in `src/main/java`) is built by
`gradle buildExtension` into the extension's `lib/MicroBlaze.jar`. When the module directory
is symlinked straight into `Ghidra/Processors` for development, `real-binaries.sh` compiles the
jar and copies it to `lib/`, which is git-ignored.

Other scripts in `test/`:

- `build-xlnx-binutils.sh` builds the Xilinx reference binutils.
- `elf/build.sh` rebuilds the committed test ELFs.
- `ghidra-dis-ctx.sh` runs the linear-sweep disassembler with imm/imml context, using
  `DumpDisasmCtx.java`.
- `ghidra-script.sh` runs headless import plus a postScript.
- `gen_corpus.py`, `vectors.py` and `compare.py` generate the corpora and compare the
  results. `compare.py` takes an optional address delta for shared objects that Ghidra
  rebases.
- `RealCheck.java` is the analysis, decompile and listing postScript used by
  `real-binaries.sh`. `rawcmp.py` compares raw words with an ld-linked object.

`run-tests.sh` symlinks the module into `$MB_GHIDRA/Ghidra/Processors/MicroBlaze`. It
ignores any inherited `GHIDRA_INSTALL_DIR`, so a real install is not modified by accident.
