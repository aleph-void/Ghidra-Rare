# Intel i860 (80860 XR / XP) for Ghidra

An independent SLEIGH module for the Intel i860 64-bit RISC processor: the 80860XR and the
80860XP, little-endian. It targets Ghidra 12.1.4 (the specs also compile on 12.1.3 and 12.2).
Encodings and behavior were implemented from Intel's *i860 64-Bit Microprocessor Family
Programmer's Reference Manual* (1991). MAME `unidasm -arch i860` is the black-box decode
reference. GNU binutils 2.30 (as, ld and objdump) and GCC 4.0.4 build the test programs and
serve as a second reference; they are also run as black boxes. Nothing was taken from the
source of MAME, binutils or GCC.

## Languages

| Language | CPU |
|---|---|
| `i860:LE:32:XR` | 80860XR |
| `i860:LE:32:XP` | 80860XP: XR plus `ldio`, `stio`, `ldint`, `scyc`, `pfld.q` and the control registers `bear`, `ccr`, `p0`-`p3` |

The ELF opinion (EM_860 = 7) selects the XP language, a superset that also runs XR code. The ELF
header does not record which CPU a program was built for.

## Model

- **Registers.** r0-r31 (r0 reads as zero; r2 = `sp`, r3 = `fp`, r1 = return address) and
  f0-f31 (f0/f1 read as zero). 64-bit operands use even pairs `fd0`-`fd30` and 128-bit operands
  use aligned groups `fq0`-`fq28`. Misaligned pairs and groups are undefined (manual 3.2), so
  they are not decoded.
- **Control registers** are `fir`, `psr`, `dirbase`, `db`, `fsr` and `epsr` (XR), plus `bear`,
  `ccr` and `p0`-`p3` (XP). `psr.CC`, `LCC`, `SC`, `PS`, `PM` and `epsr.OF` are separate
  registers. `ld.c`/`st.c` of `psr` and `epsr` assemble and split them.
- **I/O.** The XP `ldio`/`stio` access a separate `io` space.
- **Delayed branches.** `br`, `call`, `calli`, `bri`, `bla`, `bc.t` and `bnc.t` have a delay
  slot. A `bc.t`/`bnc.t` that is not taken skips its slot. `call`/`calli` link the address after
  the slot. `bri r1` is a return. `bla` updates LCC after its slot and branches on the old LCC.
- **Dual-instruction mode** (manual 8.6) is tracked by the disassembler context and follows
  figure 8-12:
  - An instruction with the D bit set (a floating-point instruction, or `shrd`, whose bit 9 is
    interpreted as D) decides the mode one step later.
  - In dual mode, each 8-byte pair is the floating-point word followed by the core word.
  - A delayed branch in the core word has the next pair as its delay slot, and `call` links past
    that pair.
  - The p-code of a pair runs the floating-point word first. That gives the 8.6.1 rules for
    loads and stores in the companion word (the floating-point operation reads the old
    register).
  - When the companion is `pfgt`/`pfle`/`pfeq`, a `bc`/`bnc` tests the old CC (rule 1) and a
    CC-setting core instruction does not override the compare (rule 4).
- **Floating-point pipelines** (manual 8.1) are registers:
  - adder A1-A3 (three stages)
  - multiplier M1-M3 (three stages for single-precision sources, two for double)
  - graphics G1 (one stage)
  - load L1-L3 (three stages, used by `pfld`)
  - KR, KI, T and MERGE

  A pipelined instruction stores the last stage into fdest, then reads its sources, so a source
  that is also fdest gets the stored value (8.1.3). It then advances the pipe and enters the new
  result. Scalar instructions leave their result in the last stage. The decompiler follows
  values through the stages, so software-pipelined loops decompile to their arithmetic.
- **Dual operations** (`pfam`/`pfsm`/`pfmam`/`pfmsm`): all 62 data-path codes of table 8-1
  have p-code, including K and T loading.
- **Graphics.**
  - `faddp` (MERGE update by pixel size, table 8-2), `faddz`, `form`
  - `fzchks`/`fzchkl` (PM accumulation)
  - `pst.d` (pixel-mask stores by `psr.PS`)
  - `fiadd`/`fisub`
- **Other instructions.** `fmlow` (low bits of the mantissa product, also used for integer
  multiply), `fix`/`ftrunc` and the precision conversions have p-code.
- **User ops.** `trap`, `intovr`'s trap, `lock`, `unlock`, `flush`, `ldint` and `scyc` are user
  ops.
- **Calling convention** (GCC 4.0 i860 port, learned from its output):
  - integer arguments in r16-r27 and floating-point arguments in f8-f15
  - results in r16 (r16:r17 for 64-bit integers) or f8/fd8
  - r4-r15 and f2-f7 callee-saved
- **DWARF registers.** r0-r31 = 0-31 and f0-f31 = 32-63.
- **Function starts.** The function-start patterns recognize the word 0xc80000NN that GCC puts
  before every function, followed by `addu -N,sp,sp`.
- **ELF relocations.** `I860_ElfRelocationHandler` applies these relocations, including those
  in relocatable objects:
  - 32, PC26, PLT26, PC16
  - HIGH, HIGHADJ, HAPC, LOPC
  - LOW0-LOW3, SPLIT0-SPLIT2
  - RELATIVE, GLOB_DAT, JUMP_SLOT

## Verification

`test/run-tests.sh` runs all of these. Except where noted, the numbers are for both languages.

### Decode vs MAME

Three word corpora have 589,824 test words:

- every op6 × every value of bits 10-0
- every op6 × 4,096 register-field combinations
- 65,536 random words

On the XR, 487,387 words agree, 63,571 are invalid on both sides, and the 38,866 differences
are all explained. On the XP, 39,464 differences are explained, and 0 are unexplained on either
language. `test/compare.py` checks each difference against rules taken from the manual. It also
checks that no word both sides decode breaks a manual rule, and that no word that follows the
rules is rejected by both.

XR differences, all words that MAME accepts:

| Count | Reason |
|---:|---|
| 23,196 | misaligned register pairs or groups |
| 11,607 | undefined control-register codes |
| 2,645 | decoded by core-escape bits 1-0 only |
| 762 | nonzero reserved core-escape fields |
| 465 | precision suffixes the instruction does not have (.ds for .p, etc.) |
| 141 | a P bit on a scalar-only or pipelined-only instruction |
| 46 | the reserved PFMAM/PFMSM data-path code 1111 |
| 4 | pfeq precision naming |

The XP also has 3,283 XP encodings that MAME does not know.

### Assembler corpus

`test/gen_asm.py` lists 1,154 instruction forms, assembled by GNU as `-mxp`. All 1,154 decode
identically to their source on the XP. On the XR, exactly the 54 XP-only forms are rejected.

### Every entry

709/709 (XP) and 683/683 (XR) SLEIGH constructors are reached, in all disassembly contexts
(single mode, low and high word of a dual pair, and a high word paired with a compare).

### Emulator

68 hand-computed cases pass on the XP and 67 on the XR, the I/O case being XP-only. They cover:

- add/subtract CC and OF, logic, shifts, SC/`shrd`, loads and stores (split offsets,
  autoincrement, `.q`)
- `psr`/`epsr`/`fsr` access, every branch kind with delay and annulled slots, `bla` loops, call
  links
- scalar FP and conversions, compares, `fmlow`, `fiadd`/`fisub`
- the adder, multiplier, graphics and load pipelines
- three dual operations, `faddp`/`faddz`/`form`/`fzchks`/`pst.d`
- dual-mode compare/branch and CC rules, and the dual-mode call link

A deliberately broken expectation is reported as a failure.

### Hand-written kernels

`test/real/kernels.s` uses pipelined dot products (scalar and dual-instruction mode with `bla`
loops), a 16-bit z-buffer with `fzchks`/`pst.d`, and a polynomial. It is assembled, analysed and
called in the emulator. 19/19 runs give the mathematical results. Its 108 instructions are
identical to objdump and MAME.

### Real code

zlib 1.3.1 and the Embench-IoT 1.0 programs were compiled with GCC 4.0.4 at -O2 and -O1. They
are linked bare-metal with `test/real/rt`: start-up code, a small libc/libm and the `.div`/`.rem`
helpers that the port calls.

- 36 ELFs give 2,675 functions and 132,259 analysed instructions. All are identical to GNU
  objdump at the same addresses. They agree with MAME except for 38 GCC `pfeq.dd` instructions,
  which MAME prints as `pfeq.ds`.
- There are 0 bad-instruction bookmarks, and 2,675/2,675 functions decompile with 0 timeouts.
- DWARF prototypes import.
- Stripped (checked once, not part of `run-tests.sh`), the function-start patterns recover 132
  of zlib-O2's 134 functions and 58 of nbody-O2's 62. The missing ones are the hand-written
  `.div`/`.rem` stubs, which have no GCC prologue and are not called in those programs.

Four builds were skipped because the obsolete GCC port aborts on them: picojpeg at both levels,
qrduino at -O2 and wikisort at -O1.

### ELF relocations

The 24 relocations in `test/reloc.s` cover every type GNU as emits. The words Ghidra produces are
identical to GNU ld's link at the same addresses.

## Reference tool differences

These MAME `i860` disassembler bugs were checked against the manual:

- Control-register codes are shown as code & 7, so code 9 (`p1`) prints as `psr`. Codes 6 and 7
  print `!`.
- Core-escape opcodes are decoded by bits 1-0 only. `stio` and reserved codes print as `lock`;
  `ldint` and reserved codes print as `calli`.
- `intovr` and `unlock` are not decoded at all.
- `pfeq`'s precision is printed from the S and R bits. R is not a precision bit for compares
  (8.3.2), and GNU as encodes `pfeq.dd` with R = 0, which MAME prints as `pfeq.ds`.
- The reserved PFMAM/PFMSM data-path code 1111 is printed as `mm12tpm`/`mm12tsm`.
- Spellings: `ppfld`, `pstd.d`, `pfmul3.ddss`/`ppfmul3.ddss`, and S/R suffixes glued to
  `faddp`, `faddz`, `form` and `fzchk*`. `test/compare.py` normalizes these.
- MAME accepts the reserved encodings listed above, and has no XP instructions or registers.

GNU as and the manual differ in a few places:

- GNU as sets bit 2 of `flush`, which the manual says must be zero, so the module ignores bits
  2-1 of `flush`.
- GNU as has no `pfeq.sd` and no `scyc.s`/`scyc.l`. The manual's size field allows them, and the
  module decodes them.

MAME and objdump both show immediate offsets aligned to the operand size (for example bit 1 of an
`ld.l` offset, bit 3 of a `.q` offset). The manual forces only the low bits it lists to zero,
because the remaining bits must already be zero in valid code. The module shows and uses the
aligned offset, as the tools do.

## Known gaps

- **Not modeled** (hardware state):
  - Traps and their return. `bri` with trap bits set restores U/IM and the delayed mode switch
    (DS/DIM). KNF, `fir` contents, user-mode write protection and big-endian mode (`epsr.BE`) are
    not modeled.
  - Paging, caches and the lock protocol (`lock`/`unlock`/`flush` are user ops).
  - Floating-point exceptions, the result-status bits and FSR rounding modes. `fix` rounds
    half-way cases away from zero; the default mode rounds to even.
- **Approximations:**
  - `frcp`/`frsqr` are exact here; the hardware gives about 8 bits and software refines them.
  - Pipelined results are stored with the current instruction's result precision. The manual's
    rules for mixing single- and double-precision multiplies in one pipeline are not modeled;
    the manual itself advises against mixing.
  - The first adder stage after a compare is set to zero (undefined in the manual).
- **Dual-mode context across branches.** A branch target inherits the mode at the branch, which
  assumes the steady state (dual-mode loops). Mode switches that straddle a branch, or start in
  a trap handler (`psr.DS`), are not followed. Indirect-branch targets start in single mode.
- **DWARF line-table bookmarks.** GNU as for the i860 writes a line_range of 245. Ghidra's line
  program reader turns those line advances negative and bookmarks the source-map entries (about
  30 per program). This is the same Ghidra issue as M-CORE's line_range 242.
- **ELF relocations.** GOT/PLT-relative relocations (LOGOT*, SPGOT*, HAGOT*, HIGOT* and the
  GOTOFF forms) are reported, not applied. No position-independent i860 toolchain output was
  available to test them.
- **Unverified:**
  - No freely licensed third-party i860 binaries were found: NeXTdimension, Paragon, iPSC/860
    and Stardent software is not freely licensed. Real-code testing uses programs built from
    public source with the last GCC and binutils that support the i860.
  - XP-only instructions are checked only against the manual and GNU as/objdump, because MAME
    does not decode them.
  - Behavior has not been compared with hardware.

## Sources

- Intel, *i860 64-Bit Microprocessor Family Programmer's Reference Manual*, order 240875-001,
  May 1991. This was the source for encodings (appendix B), core instructions (chapter 7),
  floating-point, graphics, pipelines and dual-instruction mode (chapter 8), registers
  (chapter 3) and examples (chapter 12). Archived at
  `bitsavers.org/components/intel/i860/240875-001_i860_64-Bit_Microprocessor_Programmers_Reference_May91.pdf`,
  SHA-256 `d28f004c2a2a568c77bb4b22daeed3454cee1e226fb9cd859b1d46edc77aa120`.
- Intel, *i860 XP Microprocessor Data Book*, order 240874-001, May 1991 (bitsavers): XP
  additions.
- MAME `unidasm -arch i860`: black-box decode reference.
- GNU binutils 2.30 (`as`, `ld`, `objdump`, `readelf` for the i860-stardent-sysv4 target) and
  GCC 4.0.4. They are run as black boxes to build test programs, to cross-check decoding and
  relocations, and to learn the relocation numbers and the GCC calling convention. GCC's
  obsolete i860 port needs the build fixes in `test/real/patch-gcc.py`.
  `test/real/build-toolchain.sh` fetches both by pinned URL + SHA-256 and builds GCC in an i386
  Debian 5 container.
- Test program sources (`test/real/fetch-sources.sh`, pinned URL + SHA-256):
  - zlib 1.3.1 (zlib license)
  - Embench-IoT 1.0 (GPL-3.0-or-later)

  They are built and analysed locally. Nothing from them is committed.

## Build and test

```sh
export GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC
i860/tools/build-sla.sh                 # regenerate i860_gen.sinc, compile both .sla files
i860/test/build-jar.sh                  # or: (cd i860 && gradle buildExtension)
i860/test/real/build-toolchain.sh ~/i860-work    # binutils 2.30 + GCC 4.0.4 (needs docker)
i860/test/run-tests.sh --real ~/i860-work ~/i860-tests
```

Without `--real`, `run-tests.sh` runs these checks:
- the generator check
- the SLEIGH compile
- the emulator cases
- the decode differential vs MAME
- the every-entry test

With `--real` it adds:
- the assembler corpus
- the relocation check
- the kernel emulation
- the real-code checks, fetching and building the programs if needed (`test/real-check.sh` for
  one ELF)

This module is MIT-licensed; see [LICENSE](LICENSE).
