# NVIDIA SASS processor module for Ghidra

Disassembly, p-code and CUDA cubin loading for NVIDIA GPU machine code (SASS),
for Ghidra 12.1.4.

SASS encodings are undocumented.  This module was produced **clean-room** by
black-box learning from NVIDIA's own disassembler (`nvdisasm`): a learner flips
bits of instruction words, watches how nvdisasm's text changes and derives an
encoding model per instruction *form*; a generator turns those models into
SLEIGH.  No NVIDIA documentation, no third-party disassembler code and nothing
from the closed-source IDA module was used.

> **Milestone 4 (final):** every generation from Kepler to Blackwell has a
> language (11 variants, sm_35 .. sm_121), each learned, generated and tested
> the same way.  The 128-bit variants (Volta .. Blackwell) reproduce nvdisasm on
> 99.98-100 % of real code; the 64-bit ones (Kepler, Maxwell, Pascal) are less
> polished (see the tables and Known gaps).

## Languages

| Language ID          | GPUs (ELF `sm_NN`)                    | Encoding | Status |
|----------------------|---------------------------------------|----------|--------|
| `SASS:LE:64:SM35`    | Kepler (sm_35, sm_37)                 | 64-bit + control word per 7 | done (small training set, see gaps) |
| `SASS:LE:64:SM52`    | Maxwell (sm_50, sm_52, sm_53)         | 64-bit + control word per 3 | done |
| `SASS:LE:64:SM60`    | Pascal (sm_60, sm_61, sm_62)          | 64-bit + control word per 3 | done |
| `SASS:LE:64:SM70`    | Volta (sm_70, sm_72)                  | 128-bit  | done   |
| `SASS:LE:64:SM75`    | Turing (sm_75)                        | 128-bit  | done   |
| `SASS:LE:64:SM80`    | Ampere GA100 (sm_80)                  | 128-bit  | done   |
| `SASS:LE:64:SM86`    | Ampere GA10x, Orin (sm_86, sm_87, sm_88) | 128-bit | done |
| `SASS:LE:64:SM89`    | Ada Lovelace (sm_89)                  | 128-bit  | done   |
| `SASS:LE:64:SM90`    | Hopper (sm_90, sm_90a)                | 128-bit  | done   |
| `SASS:LE:64:SM100`   | Blackwell datacenter (sm_100, sm_101, sm_103, sm_110) | 128-bit | done |
| `SASS:LE:64:SM120`   | Blackwell consumer (sm_120, sm_121)   | 128-bit  | done   |

A variant serves the SM numbers nvdisasm decodes identically (sm_50 code uses
the SM52 language, sm_61/62 SM60, sm_72 SM70, sm_87/88 SM86, sm_101/103/110
SM100, sm_121 SM120); the opinion maps each `e_flags` SM number to its variant.
Each variant was learned from the nvdisasm build that supports it: CUDA 13.4 for
SM75+, 12.4 for SM50-SM72 and 11.8 for SM35.

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

### 64-bit encodings (Kepler, Maxwell, Pascal)

These architectures put one 64-bit scheduling *control word* in front of every
3 instructions (Kepler: 7), i.e. at every 32-byte (64-byte) aligned address.
The languages have a context bit `ctl`; constructors decode control words as a
`SCHED <raw value>` pseudo-instruction that falls through.  The cubin loader
extension sets `ctl` at every bundle start of the executable sections.  For a
raw image run `test/SassDumpDisasm.java` (it marks the bundles first) or set
the `ctl` context register yourself at each 32-byte boundary.

## What the disassembly looks like

Text follows nvdisasm (`cuobjdump -sass`) as closely as SLEIGH allows:

* mnemonics, modifiers, operand order, register names (`R0..R254, RZ`,
  `UR0..UR62, URZ`; Blackwell `UR0..UR254, URZ`, `P0..P6, PT`, `UP0..UP6, UPT`, `B0..B15`), `SR_*` special
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
                      (--alias-probes: powers of two in immediates, for IMAD.SHL-style aliases;
                       --relearn: re-learn forms that validate below 90 %)
tools/evidence.py     scores every form on the corpus (decides which wins when patterns overlap)
tools/fix_reuse.py    re-learns operand-reuse flags (nvdisasm only shows them for some control words)
tools/gen_sleigh.py   learned spec -> data/languages/sass_<V>.sinc
tools/semantics.py    p-code templates
tools/gen_ldefs.py    sass.ldefs, sass.opinion, slaspecs
tools/pack_spec.py    prunes a spec to the forms used and gzips it (spec/<V>.json.gz)
```

Seeds: every instruction word of NVIDIA's libcurand cubins from the CUDA 13.4
(and, for SM50-SM72, 12.x) PyPI wheels (79k-102k unique words per architecture),
the words of our own test kernels (`test/cuda/kernels.cu`, compiled with clang
and ptxas by `test/build-cu-cubins.sh`; 2.8k-3.9k words per architecture,
covering half/bf16 conversions, atomics, shuffles, calls ...), plus 48 random
words for each of the 4096 opcode values.  libcurand has no Kepler code, so
SM35 was learned from the test kernels and random words only.  libcurand is under
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
test/build-cu-cubins.sh /tmp/cu 80                    # kernels.cu -> cubins (needs clang, ptxas)
test/cubin_words.py 16 /tmp/cu/k80_*.cubin > /tmp/cu/words_SM80.txt
cd tools
python3 build_spec.py SM80 --corpus ../test/corpus/sm80.txt /tmp/cu/words_SM80.txt --alias-probes
python3 fix_reuse.py SM80 ../spec/SM80.json           # 128-bit only
python3 evidence.py SM80 ../spec/SM80.json ../test/corpus/sm80.txt /tmp/cu/words_SM80.txt
python3 pack_spec.py ../spec/SM80.json                # -> spec/SM80.json.gz
python3 gen_sleigh.py ../spec/SM80.json.gz ../data/languages/sass_SM80.sinc
```

The generator resolves overlapping forms into disjoint root patterns (forms are
ranked by their accuracy on the corpus; a value-specific exception such as an
alias with a fixed immediate keeps its overlap with a more general form, so
SLEIGH prefers it there) and collapses modifier groups that are really
immediates into one computed constructor.  Generated `.sla` files are 0.8-1.3 MB.

## Test results

`test/run-tests.sh` (needs Java 21+, Python 3, nvdisasm; ptxas and clang
optional) - numbers of the run with `FUZZ_SEED=7`:

| Variant | committed vectors (`test/vectors/`) | random fuzz, 20k words | LOCAL check: libcurand corpus (training set, not committed) |
|---------|------------------|------------------------|--------------------|
| SM35    | 99.29 % of 3,780 | 96.58 % of 1,610 valid | (no Kepler code in libcurand) |
| SM52    | 98.93 % of 4,002 | 94.85 % of 7,749 valid | 100.00 % of 84,678 (sm_50 build) |
| SM60    | 98.98 % of 4,002 | 94.94 % of 8,148 valid | 100.00 % of 85,185 |
| SM70    | 99.92 % of 3,754 | 99.75 % of 1,218 valid | 100.00 % of 82,382 |
| SM75    | 99.92 % of 3,759 | 99.76 % of 1,258 valid | 100.00 % of 78,639 |
| SM80    | 99.95 % of 3,848 | 99.93 % of 1,395 valid | 100.00 % of 88,924 |
| SM86    | 99.95 % of 3,872 | 99.93 % of 1,439 valid | 100.00 % of 78,770 |
| SM89    | 99.95 % of 3,862 | 99.93 % of 1,428 valid | 100.00 % of 78,770 |
| SM90    | 99.92 % of 3,956 | 99.30 % of 1,567 valid | 100.00 % of 90,894 |
| SM100   | 99.84 % of 3,691 | 98.88 % of 1,158 valid | 100.00 % of 102,143 |
| SM120   | 99.84 % of 3,662 | 99.28 % of 1,118 valid | 100.00 % of 89,255 |

The committed vectors are ~3,000 instruction words of real code - the
MIT-licensed bitsandbytes 0.50.2 cubins
(https://github.com/bitsandbytes-foundation/bitsandbytes; sm_60, 70, 75, 86, 90,
100, 120 builds, the sm_86 build for SM80/SM89 and the sm_60 build for SM52) and
our ptxas-built test kernels - plus ~700-1,000 random words nvdisasm accepts.
For SM35 the real-code words are the test kernels only.  The bitsandbytes
words were never used for learning; the test-kernel words were (from milestone
3 on).  Split by origin, the real-code words are 100 % exact for every variant except
SM35 (99.89 %); the random words 99.1-99.8 % for SM70-SM120 and 95.7-97.6 % for
the 64-bit variants.

Fuzz words are uniform over the 4096 opcode values with random operand bits, so
they over-represent rare instructions.  "ghidra-only" (words Ghidra decodes but
nvdisasm rejects, mostly scheduling-control constraints) was 32-101 per 20k for
the 128-bit variants; random 64-bit words are dense in valid opcodes and Ghidra
decodes many that nvdisasm rejects (6.5k of 20k for SM52/SM60, 12k for SM35).

"Exact" means Ghidra's text equals nvdisasm's after normalising whitespace,
hex padding and float-vs-hex immediates (`test/compare.py`).

### Real-world binaries

`test/fetch-real-samples.sh` downloads the bitsandbytes 0.50.2 wheel (MIT) from
PyPI by HTTP range requests and extracts one cubin per SM (sm_60, 70, 75, 86,
90, 100, 120) into `test/samples/` (not committed).  run-tests.sh imports each
one headless (language chosen by the opinion), runs auto-analysis, decompiles
functions and diffs all `.text` sections against nvdisasm.  None of these words
were used for learning.

| cubin (CUDA)    | language picked by opinion | instructions | identical to nvdisasm | functions / decompiled |
|-----------------|----------------------------|--------------|----------------------|-------------------------|
| sm_60 (11.8)    | `SASS:LE:64:SM60`  | 101,697 | **100.00 %** | 203 functions, 30/30 sampled decompile |
| sm_70 (12.4)    | `SASS:LE:64:SM70`  | 113,472 | **100.00 %** | 207 functions, 30/30 |
| sm_75 (12.4)    | `SASS:LE:64:SM75`  | 114,080 | **99.98 %**  | 207 functions, 30/30 |
| sm_86 (12.4)    | `SASS:LE:64:SM86`  | 112,216 | **99.99 %**  | 1,403 functions, 30/30 |
| sm_90 (12.4)    | `SASS:LE:64:SM90`  | 96,488  | **99.998 %** (2 differ) | 203 functions, 30/30 |
| sm_100 (13.0)   | `SASS:LE:64:SM100` | 108,704 | **100.00 %** | 203 functions, 30/30 |
| sm_120 (13.0)   | `SASS:LE:64:SM120` | 110,144 | **99.998 %** (2 differ) | 203 functions, 30/30 |

On sm_75 the remaining differences are `RED [UR]` printed with an explicit
`RZ.64` base and `ULEA.HI.X.SX32`.

Test kernels: `test/ptx/kernels.ptx` (vector add, a loop calling a non-inlined
device function, shared memory, `bar.sync`, `shfl`, atomics) and
`test/cuda/kernels.cu` (25-28 kernels: 32/64-bit integer and float/double
arithmetic, conversions with all rounding modes, half/bf16, every memory width,
shared-memory reductions, warp shuffles and votes, atomics and fences, switch
tables, recursion, local arrays, indirect calls) are compiled for every built
SM; all import, analyse and decompile (every function), and their disassembly is
100 % identical to nvdisasm for SM70-SM120, 99.5-99.9 % for SM35/SM52/SM60.
E.g. the SM80 `vadd` kernel decompiles to

```c
iVar1 = in_SR_CTAID_X * iCbank00000000 + in_SR_TID_X;
if (iVar1 < _DAT_cbank_00000178) {
  *(float *)((long)iVar1 * 4 + _DAT_cbank_00000170) =
       *(float *)((long)iVar1 * 4 + _DAT_cbank_00000160) * 2.0 +
       *(float *)((long)iVar1 * 4 + _DAT_cbank_00000168);
```

## Known gaps

* Float immediates are shown as hex bit patterns.
* nvdisasm aliases that depend on operand *values* (e.g. `IMAD.SHL.U32` for
  power-of-two multipliers) are learned per value from probes; a value never
  probed prints in the generic form.
* 64-bit encodings: Ghidra does not know nvdisasm's validity rules beyond the
  learned forms, so it decodes many random words nvdisasm rejects.  Kepler was
  learned from ~2.8k words of our own kernels plus random probes only.
  Kepler/Maxwell `ATOM.CAS` print the implicit second compare register
  (`R(n+1)`) as a number.
* `RED [URx]` (Turing) prints an explicit `RZ.64+` base.
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
