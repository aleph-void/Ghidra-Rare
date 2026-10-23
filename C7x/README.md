# TI C7000 (C7x) processor module for Ghidra

A SLEIGH processor module for the Texas Instruments C7000 DSP family: a 64-bit VLIW DSP with
execute packets, constant- and condition-extension slots, 64-bit scalar register files and
512-bit (C7100/C7120) or 256-bit (C7504/C7524) vector register files. Targets **Ghidra 12.1.4**.

The module was written clean-room. The register model, addressing modes, extension slots and
ABI come from TI's public documentation (SPRUIP0 *C71x DSP CPU, Instruction Set, and Matrix
Multiply Accelerator*, SPRUIG4 *C7000 EABI*). The public documents do not specify instruction
encodings, so the encodings were derived **black-box** from TI's own disassembler: random and
targeted 32-bit words were fed through `asm7x` (`.word`) and `dis7x` from C7000 Code Generation
Tools 5.0.2.LTS, and bit fields were inferred from how the output text changes. No TI binary was
decompiled or disassembled to obtain this, and no IDA module was used.

## Languages

| Language ID        | Core  | Vector registers | Notes |
|--------------------|-------|------------------|-------|
| `C7x:LE:64:C7100`  | C7100 | 512-bit          | ELF default |
| `C7x:LE:64:C7120`  | C7120 | 512-bit          | C7100 + extra stores (`VST*INT*`), `NLCINITW`, ... |
| `C7x:LE:64:C7504`  | C7504 | 256-bit          | bfloat16 ops, `VLDDUP4*`, `VLD*UNPK*`, HWA (MMA) ops |
| `C7x:LE:64:C7524`  | C7524 | 256-bit          | C7504 + `ILUT*`/`IHIST*` lookup-table ops |

Each variant has its own generated instruction set, because `dis7x -v=<silicon>` accepts a
different set of opcodes for each core (for example C7504 drops several C7100 dot-product and
`VLDDUP16W`-style forms and adds bfloat16 arithmetic).

**ELF loading.** `lnk7x` writes `e_machine = 145` (0x91), ELFCLASS64, little endian. The opinion
maps that to `C7x:LE:64:C7100`. The ELF header does not identify the core: `e_flags` is 0. The
core is recorded only in the `.c7xabi.attributes` section (vendor `c7xabi`, tag 4 = ISA:
1 = C7100, 2 = C7120, 4 = C7504, 7 = C7524), and Ghidra's opinion files cannot match on build
attributes. For C7120/C7504/C7524 images, choose the language when importing (in the GUI, or
with `-processor C7x:LE:64:C7504` in headless mode). You can check the tag with
`readelf -x .c7xabi.attributes file.out`; the byte after `04` near the end of the dump is the ISA.

## Files

- `data/languages/c7x.sinc`: the hand-written core. It holds:
  - The address spaces and the execute-packet context (p-bit chaining, `||` display).
  - The `CSTX0`/`CSTX1` constant-extension slots and the `CCEXT0`/`CCEXT1` condition-extension
    slots.
  - The `.B` branches (`B`, `BE`, `CALL`, `CALLE`, `BNL`, `RET`, `RETS`), plus `BA`/`CALLA`.
  - The unit-less group (`NOP n`, `IDLE`, `TICK`, `PROT`/`UNPROT`, `MARK`, `MFENCE`, ...).
  - The `@if SIL` selection of the generated files.
- `data/languages/c7x_{gen,fields,regs,ops}_<SIL>.sinc`: generated for each silicon by
  `gen/gen.py`. They contain the token fields, register files, operand subtables, about 7,300
  instruction constructors and their p-code. **Do not edit them; regenerate them instead.**
- `data/languages/c7{100,120,504,524}.slaspec`: thin variant wrappers (`SIL`, `VLEN`).
- `c7x.ldefs`, `c7x.pspec`, `c7x.cspec` (EABI), `c7x.opinion` (ELF e_machine 145).
- `gen/`: the black-box encoding pipeline. See "Regenerating" below.
- `test/`: `run-tests.sh`, `compare.py` (Ghidra vs dis7x), `ghidra_dis.sh` + `DumpC7x.java`
  (packet-aware linear disassembly), `DecompC7x.java` (import/analysis/decompile check), and
  `elf/demo.c` + `elf/build.sh`. `demo.c` is a ~250-line C program with loops, a switch, structs,
  a linked list, function-pointer dispatch, CRC, sorting, 64-bit multiply/divide, float clamping,
  and C7x vector types (`__int8`, `__short8`).

## What is decoded

There are about 1,000 distinct mnemonics per core: 1,019 for C7100, 1,046 for C7120, 987 for
C7504 and 1,005 for C7524. They cover every dis7x operand form found by sampling:

- Scalar ALU, compare, logical, shift, bit-field (`EXT`/`EXTU`/`SET`/`CLR`), multiply,
  divide/modulo and float (SP/DP).
- Loads and stores in every addressing mode: `*R(ucst5/scst32)`, `*R++(...)`, `*R(R)`,
  `*R++(R)`, `*R(SAn)`/`*R(SAn++)`, and `*PC(...)`/`*ECSP(...)`. This includes speculative
  loads, swap loads/stores, and store-a-constant (`STKW`/`STKD`/`VSTK*`).
- The vector ALU, multiply, dot-product, permute, pack/unpack, sort, compare-to-predicate,
  predicated store (`VSTP*`) and streaming-engine/streaming-address (`SE*`, `SA*`) instructions.
- MMA/HWA instructions (`HWAOPEN`, `HWALD*`, `HWAOP*`, `HWAXFER*`...), lookup table and
  histogram, `MVC` to and from control registers (including `ECR0`-`ECR3839`), and `MVCI`.
- Predication, both the embedded `[A0]`-`[!A5]` field and the condition-extension (`CCEXT`)
  form. The cross-path unit suffix (`.L1X` etc.) is decoded as well.

**Execute packets.** A word with the p-bit set forwards the packet state to the next word
through `globalset`. The following words are displayed with `||`, and they receive the packet's
`CSTX` constants and `CCEXT` predicates. The constant extension is applied the way dis7x shows
it, for both CSTX0 and CSTX1. This covers 32-bit extended immediates; `MVK64`
(CSTX1:CSTX0:10 bits); `EXT`/`EXTU`/`REPLACE` whose second field lives only in the extension;
store-a-constant (data from one slot, offset from the other); and `BE`/`CALLE`.

**Parallel semantics are sequential.** Instructions in an execute packet are executed in
address order. Branches are always the last word of a packet (a `.B` word cannot carry a set
p-bit), so control flow is correct. A packet in which one instruction reads a register that an
earlier instruction of the same packet writes is modelled incorrectly; compiler output rarely
does this.

## Semantics

The following have real p-code:

- Scalar integer ALU ops, both the 64-bit `…D` and the 32-bit `…W` forms. 32-bit results are
  zero-extended, as SPRUIP0 describes.
- `SUBR*` reverse subtract, logical `LAND`/`LOR`, all integer and SP/DP float compares,
  `MPY*`, `DIV*`/`MOD*`, `EXT`/`EXTU`, `ADDA*`/`SUBA*`, `ADDKPC`, `MV`/`MVC`/`MVK32`/
  `MVKU32`/`MVK64`, and predicate-register logic.
- All scalar loads and stores (sign/zero extension, base update in post-increment modes,
  scaled register offsets) and the plain vector loads and stores `VLD<n><T>`/`VST<n><T>`.
- The element-wise vector ops (`VADD*`, `VSUB*`, `VSHL*`/`VSHR*`, `VAND*`/`VOR*`/`VXOR*`,
  `VMAX*`/`VMIN*`, `VMPYWW`...) when they run on 64-bit scalar registers. The compiler emits
  these for ordinary scalar code, for example `VSHRW A4,A5,A4` for `int >> int`.
- Branches, calls (`RP` = return address), `RET`, `BA`/`CALLA` (computed), and `BNL`
  (conditional on the `bnl_taken()` pcodeop).
- Predication: an instruction whose predicate is false skips to the next instruction.

5-bit scalar immediates are sign-extended in p-code (SPRUIP0 Table 3-12), even though dis7x
displays them unsigned. For example, `ADDW A0,0x1f,A0` adds −1.

Everything else uses a named pcodeop, about 880 per core: vector ops on vector registers,
dup/unpack/swap loads, packing/predicated stores, streaming engine, HWA/MMA, LUT/histogram,
`MVCI`, cache/fence/protection ops, `SYSCALL`, and so on. These pcodeops still read their
source operands and write their destination registers. For loads and stores, the effective
address and the base-register update are real p-code even when the data transfer is a
pcodeop.

**Calling convention** (SPRUIG4):

- Arguments are in `A4`-`A12`, then on the stack.
- The result is in `A4`.
- `D15` is the stack pointer and `RP` holds the return address.
- `A8`-`A15`, `VB14`, `VB15`, `D15` and `RP` are callee-saved.

Vector arguments in `VB0`-`VB15` are not modelled in the prototype.

## Test results (`test/run-tests.sh`)

The reference is TI `dis7x` 5.0.2.LTS with `-v=<silicon>`. Matching is exact text after
normalising whitespace and number formatting (hex/decimal, sign extension) and resolving
dis7x's `$+0x..` fetch-packet-relative branch targets.

| Corpus (seed 7) | C7100 | C7120 | C7504 | C7524 |
|---|---|---|---|---|
| 50,000 random words: dis7x-decodable words that Ghidra matches | 99.93 % of 9,365 | 99.93 % of 9,377 | 99.91 % of 9,137 | 99.90 % of 9,162 |
| same: dis7x-invalid words that Ghidra still decodes | 2 of 40,635 | 2 of 40,623 | 8 of 40,863 | 24 of 40,838 |
| `demo.c` compiled with `cl7x -O2`: `.text` words (real packets, CSTX/CCEXT) | 99.82 % of 1,113 (2 × `MV .S2X`) | 100 % of 1,113 | 100 % of 1,113 | 100 % of 1,113 |
| linked `demo<SIL>.out`: functions decompiled / failed | 200 / 0 | 200 / 0 | 200 / 0 | 200 / 0 |

The fuzz words have the p-bit clear, so each one is a single-instruction packet. The demo
corpus exercises multi-word packets and both extension slots. Larger runs while developing
(200,000 words per core, other seeds) gave 99.7–99.9 %.

The headless run imports the linked ELF (with the RTS library linked in) and auto-analyses it.
`DecompC7x.java` then reports instruction, function and error-bookmark counts, decompiles every
function, and prints a few of them. The opinion check imports without `-processor` and expects
`C7x:LE:64:C7100`. The two error bookmarks in each demo are `switch` jump-table data that sits
in `.text` after a `BA`.

Run it with:

```
export GHIDRA_INSTALL_DIR=/path/to/ghidra_12.1.4_PUBLIC   # with this module installed or linked
export C7X_CGT=/path/to/ti-cgt-c7000_5.0.2.LTS            # asm7x, dis7x, cl7x, RTS libs
C7x/test/run-tests.sh /tmp/c7x-tests 50000
```

## Known gaps

- **Remaining disassembly mismatches** (≈0.1 % of decodable words):
  - `MVCI`: its three register fields share bits (12-bit overlapping atoms), and the generator
    skips it.
  - Some `VPERM` operand combinations (`SE1++` sources).
  - A few `MV` forms where a move-to-predicate key overlaps a predicated move. Ghidra then drops
    `[Ax]`, or on C7100 prints `BMn` where dis7x prints `Bn` (`MV .S2X A6,B0`).
  - `VPUT*` to `CUCR` on C7504/C7524.
  - `EXTV`/`EXTUV` fields that come from a constant extension.
  - A predicated vector store whose addressing mode makes the displayed offset `(0)`.
- **Context after an undecodable word.** If a word inside a packet is BAD, the following words
  lose the packet context (`||`, CSTX and CCEXT), the same way they would in any disassembler
  that cannot decode the word.
- **Black-box coverage.** Instruction forms that random sampling and the targeted probes never
  hit are missing. Rare encodings that are only valid next to a CSTX slot are the most likely
  gaps. The `gen/refine_loop.sh` loop feeds fuzz mismatches back into the pipeline.
- **Semantics.** Vector-register operations, streaming engine, MMA/HWA and LUT are pcodeops.
  Execute packets are sequential. `B0`-`B15` writes do not clear the upper vector bits.
  `CALL` return addresses and `BNL` loop control are approximations.
- **Core selection.** ELF imports default to C7100 (see "ELF loading" above).
- The decompiler occasionally fails with "memory range beyond end of address space" in
  functions that use all-ones 64-bit constants (`MVK64 -1`) next to vector ops; this is not
  yet understood.
- Branches to compiler-generated local labels (`$C$L..`) that the ELF symbol table exports can
  show up in the decompiler as calls to tiny "functions".

## Building the extension

Run `gradle buildExtension` with `GHIDRA_INSTALL_DIR` set. With Gradle 8.10, the Gradle JVM must
be JDK 17 or 21 (with `javac`). The module has no Java sources, and `copyDependencies` is disabled.

## Regenerating the instruction tables

`gen/pipeline.sh WORKDIR SIL` rebuilds `c7x_*_SIL.sinc` from scratch with TI's tools. It runs
about 2 minutes per core on 12 threads and uses ~150 MB in WORKDIR. The stages are:

1. `sample.py` decodes 10 M random words with dis7x and groups them by
   (mnemonic, unit, operand skeleton, predicated).
2. `infer.py` flips single bits of sample words to find each group's fixed opcode bits and
   operand fields. It then enumerates each operand field to get a value→text table.
3. `refine.py` splits groups whose operand fields share bits into sub-groups.
4. `probe_ext.py` and `anaext.py` place each form after `CSTX0`/`CSTX1` and derive how the
   constant extension combines with each immediate.
5. `gen.py` emits SLEIGH: decision-tree constant subtables, attached-register subtables,
   cross-path and predicate tables, and the constructors with p-code from `semantics.py`.

`gen/refine_loop.sh WORKDIR SIL N` runs fuzz comparisons and adds the mismatching words as
extra seeds (`WORKDIR/extraSIL.json`). Compiling a slaspec needs about 1–2 GB of Java heap,
so compile the four variants one at a time.
