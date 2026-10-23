# NVIDIA SASS processor module for Ghidra

Disassembly, p-code and CUDA cubin loading for NVIDIA GPU machine code (SASS),
for Ghidra 12.1.4.

SASS encodings are undocumented.  This module was produced **clean-room** by
black-box learning from NVIDIA's own disassembler (`nvdisasm`): a learner flips
bits of instruction words, watches how nvdisasm's text changes and derives an
encoding model per instruction *form*; a generator turns those models into
SLEIGH.  No NVIDIA documentation, no third-party disassembler code and nothing
from the closed-source IDA module was used.

> **Milestone 1 (checkpoint):** 128-bit Ampere / Ada variants SM80, SM86, SM89
> complete and tested.  Turing, Hopper, Blackwell, Volta and the 64-bit
> Maxwell/Pascal/Kepler encodings are being added in the same module (the
> learner and generator already support them; see "Status").

## Languages

| Language ID          | GPUs (ELF `sm_NN`)                    | Encoding | Status |
|----------------------|---------------------------------------|----------|--------|
| `SASS:LE:64:SM80`    | Ampere GA100 (sm_80)                  | 128-bit  | done   |
| `SASS:LE:64:SM86`    | Ampere GA10x, Orin (sm_86, sm_87, sm_88) | 128-bit | done |
| `SASS:LE:64:SM89`    | Ada Lovelace (sm_89)                  | 128-bit  | done   |
| `SASS:LE:64:SM75`    | Turing (sm_75)                        | 128-bit  | in progress |
| `SASS:LE:64:SM90`    | Hopper (sm_90, sm_90a)                | 128-bit  | in progress |
| `SASS:LE:64:SM100`   | Blackwell (sm_100/101/103/110)        | 128-bit  | planned |
| `SASS:LE:64:SM120`   | Blackwell (sm_120/121)                | 128-bit  | planned |
| `SASS:LE:64:SM70`    | Volta (sm_70, sm_72)                  | 128-bit  | planned |
| `SASS:LE:64:SM52` / `SM60` / `SM35` | Maxwell / Pascal / Kepler | 64-bit + control words | in progress |

Only the variants listed in `data/languages/sass.ldefs` are built.

## Using it

Import a `.cubin` (or a cubin extracted from a fat binary with `cuobjdump -xelf`)
with the default ELF loader: `sass.opinion` selects the variant from `e_machine`
190 (EM_CUDA) and the SM number in `e_flags` (bits 0-7 for CUDA <= 12 /
ELF ABI 7, bits 8-15 for CUDA 13 / ABI 8).

cubins put every section at address 0 and use section-relative symbol values.
`SASS_CubinElfExtension` (Java, `src/main/java`) lays the sections out one after
another from 0x10000, re-creates the symbols at section start + value, and makes
every function symbol a function (`STO_CUDA_ENTRY` kernels become entry points).
Kernel parameters live in constant bank 0 (`c[0x0][0x160+]` on Ampere/Ada), which
the decompiler shows as `cbank` globals.

Raw instruction images can be loaded with the Raw Binary loader and a
`SASS:LE:64:SMxx` language.

## What the disassembly looks like

Text follows nvdisasm (`cuobjdump -sass`) as closely as SLEIGH allows:

* mnemonics, modifiers, operand order, register names (`R0..R254, RZ`,
  `UR0..UR62, URZ`, `P0..P6, PT`, `UP0..UP6, UPT`, `B0..B15`), `SR_*` special
  registers, `c[bank][offset]`, `[R2.64+UR4+0x10]`, `desc[UR4][...]`, `.reuse`;
* differences: Ghidra prints operands separated by `,` without a space, branch
  targets as absolute addresses, and **float immediates as raw hex bits**
  (SLEIGH cannot print floating point; `1.0` in an `FFMA` shows as `0x3f800000`,
  a double immediate as its 64-bit pattern, a half as 16 bits);
* scheduling control bits (stall, yield, barriers) are not shown, like nvdisasm.
  Operand-reuse flags are shown as `.reuse`.

## Semantics

Real p-code for the integer / memory / control-flow core, generated from operand
roles (`tools/semantics.py`):

* `MOV`, `IADD3` (incl. carry in/out predicates), `IMAD` (`.WIDE`, `.HI`,
  `.X`, `.U32`; also the `IMAD.MOV` / `IMAD.SHL` / `IMAD.IADD` aliases),
  `LOP3.LUT` (any LUT, folded by the decompiler), `SHF` (funnel shifts),
  `LEA`/`LEA.HI`, `ISETP` (all comparisons, `.U32`, `.AND/.OR/.XOR`),
  `SEL`, `IABS`, `IMNMX`, `POPC`, their uniform-datapath twins (`UIADD3`, ...);
* `FADD/FMUL/FFMA`, `DADD/DMUL/DFMA`, `FSETP/DSETP`, `FSEL`;
  `HFMA2.MMA RZ,RZ,imm` (the compiler's constant-load idiom);
* loads/stores `LDG/STG/LD/ST` (generic space `ram`), `LDS/STS` (`shared`),
  `LDL/STL` (`local`), `LDC/ULDC` and constant-bank operands (`cbank`,
  address = bank * 0x10000 + offset), with `.U8/.S8/.U16/.S16/.64/.128` sizes;
* `S2R/CS2R/S2UR` read `SR_*` registers;
* flow: `BRA` (also predicated via the guard), `BRX/JMX` (indirect), `CALL`,
  `RET`, `EXIT`; every instruction's `@Px` / `@!Px` guard is a conditional skip.

Everything else (tensor `HMMA/IMMA/HGMMA`, textures, surfaces, atomics,
`SHFL`, `MUFU`, conversions, barriers, ...) calls a named pcodeop
`sass_<MNEMONIC>(sources...)` that writes the first destination register, so
data flow stays visible.

Calling convention (`sass.cspec`): `R1` = stack pointer into `local`, arguments
in `R4...`, result in `R4`(`/R5`), return address in `RETPC`.

## How it was built

```
tools/learn.py        black-box learner (bit flips -> slots, modifier groups, special values)
tools/build_spec.py   learns all forms of one architecture until every seed word is reproduced
tools/evidence.py     scores every form on the corpus (decides which wins when patterns overlap)
tools/fix_reuse.py    re-learns operand-reuse flags (nvdisasm only shows them for some control words)
tools/gen_sleigh.py   learned spec -> data/languages/sass_<V>.sinc
tools/semantics.py    p-code templates
tools/gen_ldefs.py    sass.ldefs, sass.opinion, slaspecs
tools/pack_spec.py    prunes a spec to the forms used and gzips it (spec/<V>.json.gz)
```

Seeds: every instruction word of NVIDIA's libcurand cubins from the CUDA 13.4
(and, for older SMs, 12.x) PyPI wheels (79k-102k unique words per architecture)
plus 48 random words for each of the 4096 opcode values.  libcurand is under
NVIDIA's proprietary EULA, so **none of its words are committed**:
`test/fetch-libcurand-corpus.py` re-downloads the pinned wheels (SHA-256
checked) and rebuilds the corpus locally (`test/corpus/`, git-ignored) when you
want to re-learn or run the local check.

A *form* is the set of words sharing some fixed bits; its model has *slots*
(register / immediate / float / pc-relative fields, linear in the bits),
*groups* (small sets of modifier bits enumerated exhaustively against nvdisasm)
and *specials* (text changes when a slot is RZ / PT / zero / negative).  Each
form is validated on 240 random words; failures split it.

`spec/<V>.json.gz` holds the forms the generator uses (~0.3 MB each).  The
learner's seed words are replaced by synthesized canonical words (fixed bits,
modifier values printing the form's skeleton, every operand field = 1),
re-verified against nvdisasm by `tools/pack_spec.py`, so the .sinc files can be
regenerated without nvdisasm and without any third-party binary:

```
python3 tools/gen_sleigh.py spec/SM80.json.gz data/languages/sass_SM80.sinc
```

Re-learning an architecture from scratch:

```
test/fetch-libcurand-corpus.py                       # local only, never commit
tools/build_arch.sh SM80 test/corpus/sm80.txt         # learn + evidence + generate
tools/fix_reuse.py SM80 spec/SM80.json && tools/pack_spec.py spec/SM80.json
```

## Test results

`test/run-tests.sh` (needs Java 21+, Python 3, nvdisasm 13.x; ptxas optional):

| Variant | committed vectors (`test/vectors/`) | random fuzz, 20k words (FUZZ_SEED=7) | held-out real code | LOCAL check: libcurand corpus (training set, not committed) |
|---------|------------------|------------------------------|--------------------|--------------------|
| SM80    | 99.38 % of 3,848 | 97.6 % of 1,395 valid        | ptxas kernels 100 % | 99.99 % of 88,924 |
| SM86    | 99.33 % of 3,872 | 96.9 % of 1,439 valid        | bitsandbytes sm_86: 99.94 % of 112,216; ptxas kernels 100 % | 99.99 % of 78,770 |
| SM89    | 99.33 % of 3,862 | 96.9 % of 1,428 valid        | ptxas kernels 100 % | 99.99 % of 78,770 |

The committed vectors are 3,000 words from the MIT-licensed bitsandbytes 0.50.2
sm_86 cubin (https://github.com/bitsandbytes-foundation/bitsandbytes) and the
ptxas-built test kernels, plus ~850 random words nvdisasm accepts.  None of these
were used for learning.

Fuzz words are uniform over the 4096 opcode values with random operand bits, so
they over-represent rare instructions; "ghidra-only" (words Ghidra decodes but
nvdisasm rejects, mostly scheduling-control constraints) was 36-37 per 20k.

"Exact" means Ghidra's text equals nvdisasm's after normalising whitespace,
hex padding and float-vs-hex immediates (`test/compare.py`).

### Real-world binaries

`test/fetch-real-samples.sh` downloads the bitsandbytes 0.50.2 wheel (MIT) from
PyPI by HTTP range requests and extracts one cubin per SM (sm_60, 75, 86, 90,
100, 120) into `test/samples/` (not committed).  run-tests.sh imports each one
headless (language chosen by the opinion), runs auto-analysis, decompiles
functions and diffs all `.text` sections against nvdisasm.

* sm_86 (`libbitsandbytes_cuda124_sm86_1.cubin`, CUDA 12.4): opinion selects
  `SASS:LE:64:SM86`; 112,216 instructions, **99.94 %** identical to nvdisasm
  (14 undecoded `ULEA.HI.X.SX32` encodings never seen in training; 50
  `IMAD.SHL.U32` printed as `IMAD.U32` - nvdisasm's alias for power-of-two
  multipliers).

ptxas-built test kernels (`test/ptx/kernels.ptx`: vector add, a loop calling a
non-inlined device function, shared memory, `bar.sync`, `shfl`, atomics) import,
analyse and decompile; e.g. the SM80 `vadd` kernel decompiles to

```c
iVar1 = in_SR_CTAID_X * iCbank00000000 + in_SR_TID_X;
if (iVar1 < _DAT_cbank_00000178) {
  *(float *)((long)iVar1 * 4 + _DAT_cbank_00000170) =
       *(float *)((long)iVar1 * 4 + _DAT_cbank_00000160) * 2.0 +
       *(float *)((long)iVar1 * 4 + _DAT_cbank_00000168);
```

## Known gaps

* Float immediates are shown as hex bit patterns.
* nvdisasm aliases that depend on operand *values* other than RZ/PT/zero
  (e.g. `IMAD.SHL.U32` for power-of-two multipliers) are printed in the
  generic form.
* Encodings seen neither in the corpus nor among the random probes may be
  undecoded (`??`) or, rarely, decoded where nvdisasm rejects them (Ghidra does
  not check scheduling-control constraints, e.g. `.reuse` validity).
* Exotic instructions (`BMOV` special registers, `OUT`, `DEPBAR` sets, very
  rare modifier combinations) account for most of the remaining fuzz
  mismatches.
* Semantics of tensor, texture, surface, warp-collective, conversion and
  most floating-point special functions are pcodeops.
* Branches inside a cubin are section relative; calls between sections are
  resolved through symbols only.

## Building as an extension

```
GHIDRA_INSTALL_DIR=<ghidra_12.1.4> gradle buildExtension
```
(`copyDependencies` is disabled in build.gradle).  For a quick test setup link
the module into `Ghidra/Processors/SASS` and run `test/build-jar.sh`.
