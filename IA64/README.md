# Intel IA-64 (Itanium) for Ghidra

An independent SLEIGH module for the Intel Itanium architecture (IA-64), as used by Linux,
HP-UX, OpenVMS and Windows on Itanium. It targets Ghidra 12.1.4. Instruction encodings and
behavior were implemented from the *Intel Itanium Architecture Software Developer's Manual*,
volume 3, revision 2.3. GNU objdump (`-m ia64-elf64`) is a black-box decode reference, and the
GNU assembler, readelf and GCC are run as black boxes to build test programs and to learn
relocation numbers. Nothing was taken from any tool's source.

## Languages

| Language | Data | Addresses | Use |
|---|---|---|---|
| `IA64:LE:64:default` | little-endian | 64-bit | Linux, Windows, OpenVMS (LP64) |
| `IA64:BE:64:default` | big-endian | 64-bit | HP-UX `+DD64` (LP64) |
| `IA64:BE:32:default` | big-endian | 32-bit | HP-UX ILP32 (default HP-UX model), registers stay 64-bit |

Bundles are always little-endian (`instructionEndian="little"`), and only data accesses follow
the language's byte order. The ELF opinion picks the language from `EM_IA_64` (50), `EI_DATA` and
`EI_CLASS`. In the ILP32 language, effective addresses are the low 32 bits of the 64-bit
register, and arguments and results are sign-extended (`ia64_ilp32.cspec`).

## Model

**Bundles and slots.** Each 128-bit bundle (5-bit template, three 41-bit slots) is
disassembled as three Ghidra instructions, one per slot, at bundle+0, +6 and +11. objdump prints
slot 2 at +12. A Ghidra address cannot point inside a byte, so slot 1 starts at the byte that
holds its high bits and the low bits it shares with slot 0 reach it through context (`s1lo`,
`s2lo`, set by the previous slot with `globalset`). The template is carried the same way.
A long-immediate MLX bundle has two Ghidra instructions: slot 0 and the 10-byte L+X pair at +6
(`movl`, `brl`, `brl.call`, `break.x`, `nop.x`, `hint.x`). Stops (`;;`) are shown after the
slot they follow. Branch targets and `ip` are bundle addresses. Branches to slot 1 or 2 are
not possible on Itanium, so flow and references always land on slot 0.

**Predication.** Every instruction tests its qualifying predicate first. `(p0)` instructions
have no test. Compares write predicate pairs, including the `.unc`, `.and`, `.or` and
`.or.andcm` forms and their parallel variants. `pr`, `pr.rot` and the rotating predicates
p16-p63 are registers.

**Register stack.** `alloc` records the frame (size of locals, outputs, rotating region) in
context, which flows through the function. At `br.call`, the caller's locals r32.. are copied
to `argsave0-95` and its outputs (up to 8) move down to r32-r39, the callee's inputs, which the
cspec lists as parameters. The rest depends on `DECOMPILE_MODE`, a 1-byte register the pspec
sets to 1 for analysis and that is 0 in the emulator:
- *Decompiler model*: after the call op, the outputs and the caller's locals are restored from
  `argsave`. Return values come from r8-r11 and f8-f15, and stacked registers above the frame are
  killed by the call. This gives normal-looking parameters and calls with arguments. Doing the
  save before the mode test keeps values held in local registers (typically the saved gp)
  constant across calls even in the partial functions Ghidra's switch recovery works on.
- *Emulator model*: `br.call` also spills the saved locals to the backing store at `ar.bsp`
  (the p-code after a call op does not run in the emulator), and `br.ret` restores the frame
  from `ar.pfs` and the backing store. Calls and returns, nested calls and recursion therefore
  emulate correctly (the emulator cases check this). NaT bits of spilled registers and
  `ar.rnat` are not part of this model.

A call in slot 0 or 1 skips the rest of its bundle on return (the return link is the next
bundle).

**Rotating registers.** `br.ctop`, `br.cexit`, `br.wtop` and `br.wexit` rotate the general
registers (by the rotating region size from `alloc`), f32-f127 and p16-p63, and handle `ar.lc`
and `ar.ec` as the manual describes. `clrrrb` is a user op. Rotation is modeled as physical
register copies, so loops built by modulo scheduling emulate correctly; the decompiler shows the
copies.

**NaT bits and speculation.** Each general register has a NaT bit (`r0.nat`...`r127.nat`).
Arithmetic propagates it, `ld.s`/`ld.sa` set it from the address's NaT (deferred faults are not
modeled), `ld8.fill`/`st8.spill` move it through `ar.unat`, and `tnat` and `chk.s` test it.
`chk.a` always branches to recovery code (the ALAT is not modeled, so the recovery is always
taken, which is correct but pessimistic). The pspec tracks all NaT bits as 0 at function entry,
so they fold away in the decompiler.

**Floating point.** The 82-bit floating-point registers are modeled as 80-bit extended values
(10-byte registers, with the significand and the sign/exponent available as sub-registers).
`getf.exp`/`setf.exp` convert between the 15-bit model exponent and the 17-bit register format,
so values outside the double-extended exponent range are not exact. f0 and f1 are the
constants 0.0 and 1.0. `fma`, `fms`, `fnma`, `frcpa`, `frsqrta`, conversions, compares and classes are p-code;
parallel single-precision operations work on the two halves of the significand. Rounding
precision and status-field selection (`.s0`-`.s3`) are shown but not modeled (the host rounding
of Ghidra's float operations is used).

**Multimedia, system and other instructions.** Parallel arithmetic, shifts, `mux`, `mix`,
`pack`, `unpack`, `psad`, `pmpy` and `popcnt` are p-code. Cache and TLB maintenance, `probe`,
`thash`/`ttag`, `tak`, `itc`/`itr`/`ptc`/`ptr`, indirect register files (`rr`, `pkr`, `dbr`,
`ibr`, `pmc`, `pmd`, `cpuid`, `msr`), `cover`, `loadrs`, `flushrs`, `bsw`, `epc`, `br.ia` and
`break` are user ops; `break` falls through, which keeps Ghidra's non-returning-function
discovery working after GCC's `break 0` behind calls that do not return. `rfi` returns to
`cr.iip`. The Itanium 9500 additions (`hint.m` operands, `mov dahr`, `lfetch`
counts) are not in revision 2.3 and are decoded as revision 2.3 defines them.

## Loader support

- `IA64_ElfRelocationHandler`: data relocations (DIR, GPREL, LTOFF, PLTOFF, FPTR, PCREL,
  SEGREL, SECREL, LTV, IPLT, REL) in both byte orders and instruction relocations in slots
  (IMM14, IMM22, IMM64, PCREL21B/M/F, PCREL60B, LTOFF22X, LDXMOV). Official function descriptors
  and linkage-table entries that a relocatable object needs are created in an artificial
  `%ia64.linkage` block. TLS relocations (TPREL, DTPMOD, DTPREL) are reported as unsupported,
  and COPY is skipped.
- `IA64_ElfExtension`: sets `r1` (gp) over the executable blocks from `DT_PLTGOT`, `__gp`, or the
  `_start` sequence that computes gp; makes functions from the `.IA_64.unwind` table; names PLT
  stubs after their IPLT relocation.
- `ia64.dwarf`: DWARF register numbers (r0-r127, f0-f127 at 128, p0-p63 at 256, b0-b7 at 320).

## Verification

- **Decode vs GNU objdump** (binutils 2.45 `-m ia64-elf64`, per slot, all three languages):
  - random corpus (100,000 bundles, 299,352 slots): 84,893 identical, 214,443 invalid in both,
    16 explained differences, 0 unexplained;
  - opcode-space corpus (every value of slot bits 27-40, the major opcode and the extension
    fields, for each unit in each slot position, with two random samples of the low bits, plus
    the X-unit space of MLX bundles; 1,074,686 slots): 781,166 identical, 293,503 invalid in
    both, 17 explained, 0 unexplained;
  - pseudo-op corpus (3,852 slots: `mov`, `shl`, `fmpy`, `fabs`, ... aliases) and branch corpus
    (65 slots, including MLX `brl`): all identical.
  - Explained differences: the Itanium 9500 extensions (`hint.m` read as `mov dahr`, `lfetch`
    with bit 19 read as `lfetch.count`), which revision 2.3 does not define; and reserved `mux1`
    permutations (Table 4-74), which objdump prints as a raw number while the manual marks them
    reserved.
- **Every entry:** 5,079/5,079 SLEIGH constructors are reached in each language.
- **Emulator:** 37 hand-computed cases pass in each language (111/111), and a deliberately
  broken expectation is reported. They cover arithmetic, logic, shifts, `extr`/`dep`, compares
  of every type and predication, `tbit`/`tnat`, loads and stores with post-increment,
  `cmpxchg`/`fetchadd`, speculation and NaT propagation, spill/fill, `br.cloop`, counted and
  rotating loops (`br.ctop`, `br.wtop`), calls and returns through the register stack
  (direct, indirect, nested, long branch), `pr` moves, `xma`, floating-point arithmetic,
  conversions, merges, classes, `frcpa` and parallel FP, and multimedia instructions.
- **Real binaries** (Debian 7 "wheezy" ia64 packages, freely licensed, fetched by
  `test/real/fetch.sh` with pinned SHA-256; nothing committed):

| Binary | Functions | Instructions | Identical to objdump | Bad instr. | Decompiled | Unrecovered jump tables |
|---|---|---|---|---|---|---|
| libz.so.1.2.7 | 177 | 24,260 | 24,257/24,257 | 0 | 113/113 | 0 |
| busybox 1.20.0 (dynamic) | 2,414 | 242,101 | 242,101/242,101 | 0 | 1,752/1,752 | 18 |
| busybox 1.20.0 (static) | 3,575 | 550,615 | 550,615/550,615 | 1 | 3,569/3,575 | 23 |
| gzip 1.5 | 340 | 29,146 | 29,143/29,143 | 0 | 167/167 | 2 |
| bc 1.06.95 | 223 | 20,939 | 20,936/20,936 | 0 | 134/134 | 0 |
| libsqlite3.so 3.7.13 | 1,802 | 156,972 | 156,972/156,972 | 0 | 1,588/1,591 | 149 |
| libm-2.13.so | 386 | 70,471 | 70,471/70,471 | 0 | 357/361 (1 timeout) | 0 |
| libc-2.13.so | 3,556 | 299,522 | 299,510/299,510 | 0 | 3,525/3,535 | 87 |

  There are no error bookmarks apart from the one bad instruction (see known gaps). libc has 16
  warnings: 11 TLS relocations that are not applied and 5 functions whose calling convention
  the decompiler's parameter analysis could not recover. 22 of the 23 decompiler failures are
  the Ghidra decompiler bug described under known gaps, and the other is a libm timeout; 4 libm
  functions end in `halt_baddata`. 144 of
  the 149 sqlite warnings are the same dispatch (`sqlite3VdbeExec`), reported once per
  function Ghidra split it into.

  "Identical" counts the instructions Ghidra disassembled that match objdump after operand
  normalization (a few instructions in non-text sections are not compared). Slots objdump
  decodes but Ghidra did not reach are nop-only padding bundles, code reached only through
  unrecovered jump tables, and data objdump decodes as code.
- **GCC output:** a freestanding C test program (`test/real/src/prog.c`) built with GCC 14
  cross compilers for `ia64-linux-gnu` (object, static executable, shared object) and
  `ia64-hp-hpux11.23` (ILP32 and LP64 objects, big-endian): 0 bad instructions, 16/16 functions
  decompile in every build, the disassembly matches objdump except at relocation sites, and the
  DWARF information is imported.
- All three `.slaspec` files compile with Ghidra 12.1.3, 12.1.4 and 12.2 (the `.sla` files are
  0.63-0.65 MB), and `tools/build-module.sh` builds the extension zip.

No objdump decode bugs were confirmed: every difference found is one of the explained classes
above.

## Known gaps

- **Not modeled:** the ALAT (advanced-load checks always take the recovery path), deferred
  speculation faults, interruptions, the RSE's asynchronous behavior (`cover`, `loadrs` and
  `flushrs` are user ops), privilege levels and protection keys, FP status flags and rounding
  controls, the IA-32 instruction set (`br.ia` is a user op plus a branch).
- **Decompiler:**
  - Calls to functions with unknown prototypes can show extra arguments, because output
    registers that hold stale values are passed as r32-r39.
  - Switches dispatched from a shared block reached by several paths (loop switches such as
    `sqlite3VdbeExec`, or a dispatch that a non-returning call falls into) have no guard
    Ghidra can see, so the jump table is not recovered ("Too many branches") and the code
    behind it is not disassembled automatically. In one busybox-static function a table is
    recovered with a wrong range and flow reaches `.rodata` (the one bad-instruction bookmark).
  - "Conditional execution: Illegal op in iblock" (22 functions above) is a Ghidra decompiler
    bug, reproduced with a 5-instruction function: `mov r8=0`, a compare, `(p7) mov r8=1`,
    then another `(p7)` instruction. The conditional-move rule turns the 0/1 merge into a
    COPY of the predicate, and `ConditionalExecution::resolveIblockRead` throws for a COPY
    whose input is defined outside the block. The p-code is correct.
  - Rotating loops decompile as explicit register copies.
- **TLS** relocations are not applied (reported in the import log).
- **Unverified:** behavior has not been compared with hardware or a full simulator; the
  register stack's emulator model has been checked only with the emulator cases; Windows,
  OpenVMS and HP-UX executables (as opposed to objects built here) were not tested.

## Sources

- Intel, *Intel Itanium Architecture Software Developer's Manual*, volume 3: *Instruction Set
  Reference*, revision 2.3, May 2010 (`itanium-architecture-vol-3-manual.pdf`, from
  `https://www.intel.com/content/dam/www/public/us/en/documents/manuals/itanium-architecture-vol-3-manual.pdf`
  via the Internet Archive, SHA-256
  `67cdd91b3d3781fc432fc1c2c1b31053d1f611ddc5064209431fc32029ffe6f2`): formats, encodings,
  operations, register files, register stack, rotation, predication, NaT handling.
- GNU binutils (objdump `-m ia64-elf64`, gas, readelf, ld) and GCC 14 for `ia64-linux-gnu` and
  `ia64-hp-hpux11.23`, built locally, used only as black boxes: decode reference, assembling the
  emulator cases and test programs, and listing relocation numbers.
- Debian 7 ia64 packages (zlib, busybox, gzip, bc, sqlite3, eglibc) from
  `archive.debian.org`, real-code test inputs only.

## Build and test

```sh
export GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC
python3 IA64/tools/gen_ia64.py IA64/data/languages     # regenerates ia64_gen*.sinc, ia64_regs.sinc
IA64/test/build-sla.sh                                  # compile the three languages
(cd IA64 && gradle buildExtension)                     # or IA64/test/build-jar.sh for a linked install
IA64/test/run-tests.sh --real "$HOME/.cache/ghidra-rare-scratch/ia64-real" "$HOME/.cache/ghidra-rare-scratch/ia64-tests"
```

`run-tests.sh` runs the following:
- generator check
- SLEIGH compile and size check
- emulator cases in all three languages, plus a broken expectation that must fail
- every-entry test in all three languages
- decode differential vs objdump (`test/run-decode.sh`; needs `IA64_OBJDUMP` or the default
  binutils path)
- with `--real`: the Debian binaries (`test/real/run-real.sh`; set `IA64_PROJ` to a project
  directory without dot-directories in its path)

`test/emu/cases.py` regenerates `test/emu/cases.txt` with the ia64-linux-gnu assembler, and
`test/real/build-own.sh` builds the GCC test program.
