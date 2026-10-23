# TI PRU / PRU-ICSS processor module for Ghidra

SLEIGH processor module for the Texas Instruments Programmable Real-time Unit
(PRU, PRU-ICSS, PRUSS, ICSSG). It covers PRU core revisions V0 to V4, matching
the TI toolchain's `--silicon_version` / `-v0`..`-v4`. Target: **Ghidra 12.1.4**.

It was written clean-room from TI documentation (SPRUIJ2 *PRU Assembly
Instruction User's Guide*, AM335x TRM SPRUH73 chapter 4) and validated against
two reference disassemblers: GNU binutils 2.45 `objdump -m pru` and TI PRU CGT
2.3.3 `dispru`. The closed-source IDA module that inspired it was not used.

## Languages

| Language ID     | Core revision | Instruction set |
|-----------------|---------------|-----------------|
| `PRU:LE:32:v0`  | V0            | base ISA (ALU, LDI, JMP/JAL, QBxx, LBBO/SBBO/LBCO/SBCO, HALT, SLP) |
| `PRU:LE:32:v1`  | V1 (AM18xx / OMAP-L138 PRUSS) | + LMBD |
| `PRU:LE:32:v2`  | V2            | + MVIB/MVIW/MVID, XIN/XOUT/XCHG (and ZERO/FILL = XIN 255/254) |
| `PRU:LE:32:v3`  | V3 (AM335x, AM437x, AM57xx PRU-ICSS) | + LOOP/ILOOP, SXIN/SXOUT/SXCHG |
| `PRU:LE:32:v4`  | V4 (ICSSG: AM64x, AM65x, ...) **ELF default** | + TSEN 0/1 (task manager enable). That is the only addition TI CGT 2.3.3 knows: `clpru -v4` accepts it and `dispru -v4` decodes exactly the two words `0x32000000`/`0x32800000`. |

The per-revision differences come from probing TI `clpru -vN` (which
instructions it accepts) and `dispru` (which words it decodes for objects built
with `-vN`). A sweep of 196,096 patterned words (every top byte combined with
every value of one other byte) found TSEN as the only V3/V4 difference.

ELF: `EM_TI_PRU` (144), little-endian ELF32. Both TI and GNU executables import
automatically (`data/languages/pru.opinion`). Neither ELF flavour records the
core revision in `e_flags` (TI keeps it in `__TI_build_attributes`), so the
opinion cannot tell V3 from V4. ELF imports default to **V4**: its decoder is
V3 plus the two TSEN words, which are reserved on V3, so it disassembles
firmware for either revision (V3 firmware simply never contains TSEN). Pick
another variant by hand for V0-V2 firmware.

`PRU_ElfExtension` (Java, `src/main/java`, built into `lib/PRU.jar`) adjusts
PRU ELF imports:
* **Entry point 0.** TI firmware is normally linked with `e_entry = 0`, which
  Ghidra's ELF loader ignores. Stripped firmware then got no function and no
  disassembly at all. The extension creates `entry` at code:0.
* **TI local labels.** clpru/asmpru emit compiler and assembler local labels
  (`$C$L12`, `$run$exit`, macro labels `$M$45$`, ...) as zero-size `STT_FUNC`
  symbols. Names starting with `$` cannot be C functions, so these become
  plain labels instead of one-instruction pseudo-functions.
* **Constant table.** TI links record each constant-table base they use as an
  absolute symbol `__PRU_CREG_BASE_C<n>`. These values are applied to `c<n>`
  over the code, so LBCO/SBCO resolve without running
  `PRUSetConstantTable.java`.

## Model

* **Harvard memory.** `code` holds instruction memory and `data` holds data
  memory (32-bit, byte addressed). LBBO/SBBO/LBCO/SBCO, the stack and data
  pointers use `data`. Code and data both start at 0, so their addresses overlap
  as on the hardware.
* **Word-addressed PC.** The hardware PC is a 16-bit count of 32-bit words.
  Ghidra's `code` space is byte addressed (24-bit), the same as TI and GNU ELF
  files, `objdump` and `dispru`, so the listing shows the same addresses as both
  reference tools. Code address = 4 × hardware PC.
  * JMP/JAL immediates, QBxx and LOOP offsets are scaled by 4 when decoded.
  * Values that the program keeps in registers stay hardware word addresses:
    the JAL/CALL link in `ra.w2`, `jmp rX` / `jal rY, rX` targets, `ret`, and
    LOOP_TOP/LOOP_END. The p-code converts them with `<<2` / `>>2`, which the
    emulator test checks.
  * GNU ld links `.text` at 0x20000000. The 24-bit code space truncates that to
    0, so GNU ELFs load at the correct addresses too.
* **Registers.** `r0`..`r31` have subregisters `.b0`-`.b3` and `.w0`-`.w2`;
  `.w1` is the unaligned bytes 1-2. Each register sits at register-space offset
  4·n, so a PRU "register address" (`&r2.b1` = 9) is its register-space offset.
  MVIx and the burst/XFR instructions use that offset to address the register
  file.
  * Names follow binutils: `sp` = r2, `ra` = r3, `fp` = r4, with pspec aliases
    r2/r3/r4.
  * R30 (GPO) and R31 (GPI/event status) are cspec globals and also a
    `volatile` register range in the pspec. Every read and write is kept: a
    sampling loop `mov r21.w0, r31.w0` is not folded into the last value
    written to R31, and back-to-back `r30` writes (bit-banging) or an R31 event
    write before HALT are not dropped as dead stores.
* **Constant table.** `c0`..`c31` are registers that LBCO/SBCO read as their
  base address. Set their values with *Set Register Value*, or run
  `ghidra_scripts/PRUSetConstantTable.java`. That script loads the AM335x table
  from SPRUH73 Table 4-9 (C24-C31 at their reset values) and accepts overrides
  such as `c28=0x10000`. Once set, LBCO/SBCO produce data references and the
  decompiler resolves them: `sbco &r14, c0, 0x24, 4` becomes
  `Data00020024 = param_1`.
* **Hardware loops.** `LOOP`/`ILOOP` mark the last instruction of the body with
  a context bit through `globalset`. That instruction then gets
  `LOOP_CNT--; if (LOOP_CNT != 0) goto top`, so the control-flow graph, the
  decompiler (`do { ... } while (--cnt)`) and the emulator all see a real loop.
* **Pseudo-ops.** Display follows binutils: `nop`, `mov` (= `or d, s, 0`), `ret`,
  `call`, `wbs`, `wbc`, `zero`, `fill`. TI's `mov` encoding (`and d, s, s`) is
  shown as `and`, as both reference tools show it. `ldi32` pairs are not fused;
  they stay as two `ldi`.

## Semantics

* **Full p-code:**
  * ALU instructions with the PRU's zero-extension rules. Arithmetic sets
    `CARRY` from bit *width(dst)* of the result, and borrow for
    SUB/SUC/RSB/RSC.
  * LSL/LSR/CLR/SET take the shift or bit operand mod 32. MIN, MAX and NOT are
    also implemented.
  * LMBD uses `lzcount` at the source field width and returns 32 when no bit is
    found.
  * LDI, JMP, JAL/CALL (link = word address of the next instruction) and RET
    (`return`).
  * QBxx compares `OP(255) <cond> REG1`. QBA, QBBS/QBBC, WBS/WBC.
  * HALT calls the `halt` pcodeop and **falls through**. The core stops, and
    the host restarts it. Firmware using the pru_rproc syscall/downcall
    convention, or assembly that waits for the host, relies on the host
    resuming at the next instruction (BeagleLogic does both). With HALT as a
    terminator, that code was never disassembled. SLP calls the `sleep`
    pcodeop. TSEN (V4) calls `tsen(enable)`.
  * MVIB/MVIW/MVID read and write the register file through a pointer, with
    post-increment and pre-decrement.
  * LBBO/SBBO/LBCO/SBCO with an immediate length 1..124 are unrolled into direct
    register varnodes, so the decompiler sees exactly which registers are
    loaded or stored. The pieces are naturally aligned (a whole register, `w0`,
    `w2` or a byte) and never straddle two registers. A straddling varnode,
    such as `sbbo &r13.b1, ..., 4`, made the decompiler fail with "Cannot
    properly adjust input varnodes". There is one constructor per start byte up
    to 44 bytes, which covers the TI prologue/epilogue `sbbo &r3.b2, sp, 0, 2+4n`.
    An unaligned burst longer than 44 bytes, or a length in `r0.bN`, becomes a
    byte loop. Unrolling those too would push the `.sla` past the 16 MB the
    Java decoder accepts.
  * ZERO/FILL (XIN 255/254) write the register range.
* **Named pcodeops that still read/write the right registers:**
  * XIN/XOUT/XCHG/SXIN/SXOUT/SXCHG: `xin(dev, byte)`, `xout(dev, byte, val)`
    and so on, applied per register chunk.
  * XIN from device 0 (the MPY/MAC unit) is `mpy_xin(byte, r25, r28, r29)`, so
    multiply operands stay live (`seed * 1103515245` survives decompilation).
* **cspec (TI PRU C ABI, SPRUHV7; GCC follows it):**
  * Arguments in r14..r29, then the stack. Return value in r14 (r15:r14 for
    64-bit).
  * `sp` = r2 in `data`, growing down. Return address `ra.w2`.
  * Callee-saved: r3..r13. Caller-saved: r0, r1, r14..r29.
  * Data pointers are 4 bytes. Alignment is 1.

## Coverage, measured by `test/run-tests.sh`

The corpus has 25,892 words. The structured part covers:
* every opcode and sub-opcode, every register selector, IO on/off;
* all 128 burst and XFR length encodings;
* every MVI size and mode;
* every QB condition with edge offsets.

It also includes 4,000 class-biased random words and 20,000 fully random words.
Text is normalized before comparison: register aliases, decimal immediates,
absolute byte branch targets, `cN`. The "semantic" figures also expand
pseudo-ops.

| comparison                      | words decoded by the reference | exact  | semantic |
|---------------------------------|------------------|--------|----------|
| V3/V4 vs GNU objdump 2.45       | 18,443 | **100.00 %** | 100.00 % |
| V3 vs TI dispru `-v3`           | 17,555 | 99.90 % | **100.00 %** |
| V4 vs TI dispru `-v4`           | 17,557 | 99.90 % | **100.00 %** |
| V2 vs TI dispru `-v2`           | 17,429 | 99.90 % | 100.00 % |
| V1 vs TI dispru `-v1`           | 17,125 | 99.91 % | 100.00 % |
| V0 vs TI dispru `-v0`           | 16,915 | 99.91 % | 100.00 % |

* The "exact" misses against TI are all pseudo-op spellings, for example
  `mov`/`nop`/`ret`/`call`/`wbs`/`zero`, which dispru prints as base
  instructions.
* Ghidra never fails on a word that a reference decodes.
* Words Ghidra decodes but a reference rejects:
  * **vs objdump: 187 (V3), 189 (V4).** 97 are `not` with IO=0, which is how
    TI `clpru` encodes NOT and which binutils cannot decode. 90 are MVIx, which
    binutils lacks; those match TI. The V4 extra 2 are TSEN.
  * **vs dispru: 850 to 1,075.** These are JMP/JAL/LDI/HALT/SLP/LOOP words
    whose reserved fields are non-zero. dispru rejects them; binutils, the
    primary reference, decodes them, and so does this module.
* No version gating error: a Vn language never decodes an instruction that
  dispru `-vN` rejects for lack of that feature (for example LMBD on V0, XFR or
  MVI on V1, LOOP on V2).

Other checks:
* **Emulation (`test/emu-test.sh`):** 30/30 register and memory checks pass for
  a TI-assembled program. It covers carry/borrow, sub-register writes, LMBD,
  NOT, CLR/SET/MIN/MAX, SBBO/LBBO into an unaligned register start, MVIB with
  post-increment, LOOP (5 iterations), FILL, QBGT, JAL link value, CALL/RET and
  a register-indirect JMP.
* **ELF import (`test/elf-check.sh`):**
  * `test/elf/demo_v3.elf` is built with TI clpru 2.3.3 `-O2`: C plus an
    assembly file using LBCO/SBCO, LOOP, MVI and XOUT.
  * `test/elf/gnu_demo.elf` is built with GNU as/ld 2.45.
  * Both import as `PRU:LE:32:v4` (the ELF default), auto-analyze, and decompile every function
    without errors. Calls, arguments, returns, loops, the switch chain, the
    constant-table addresses and the R30/R31 I/O all come out readable.

## Real-world binaries (`test/real-binaries.sh`)

`test/fetch-real-samples.sh` downloads the samples from pinned release URLs and
checks their SHA-256. The binaries are not committed.
`test/real-binaries.sh` then runs `test/real-check.sh` on each sample:
* headless import **without** `-processor`;
* auto-analysis;
* decompile every function (`PruRealCheck.java`);
* diff the analysed listing of the executable sections against
  `objdump -D -z -m pru` and `dispru -v3` over the same bytes
  (`elf_code.py`, `real_compare.py`, same normalization as `compare.py`).

Samples: **BeagleLogic release-v1.1** (GPL-3.0, Kumar Abhishek),
`beaglelogic-pru0` and `beaglelogic-pru1`. They are TI clpru ELFs for AM335x
with debug info, built from `beaglelogic-firmware/` at tag `release-v1.1`
(commit aa771f4c). pru0 is C plus an assembly capture loop and the pru_rproc
syscall stubs. pru1 is hand-written assembly: the sampling loops and
`HALT`-and-wait.

| | beaglelogic-pru0 | beaglelogic-pru1 |
|---|---|---|
| language picked by the ELF opinion | `PRU:LE:32:v4` | `PRU:LE:32:v4` |
| functions after analysis | 12 | 8 |
| code words disassembled by analysis | 205 / 205 | 481 / 482 (the remaining word is a dead `halt` after `jmp`) |
| bad-instruction / error bookmarks | 0 | 0 |
| functions decompiled (no failures, no timeouts) | 12 / 12 | 8 / 8 |
| vs objdump (exact) | 205 / 205 | 481 / 481 |
| vs dispru (exact / semantic) | 180 / 205 (pseudo-op spelling), 205 / 205 | 477 / 481, 481 / 481 |

The decompiled output was checked against the source:
* `configure_capture`, `main` (event polling, the `run()` call, the PRU1
  reset) and the `run()` assembly loop (`xin 10, &r21, 36` into the
  scatter/gather buffers) read like the source.
* `handle_downcall` comes out as the right `if` chain over the downcall ids.
  Its returns, however, are `jmp ra.w0` (the downcall ABI), so they show up as
  "Treating indirect jump as call".

Bugs this check found and fixed, with the numbers before each fix:
* **HALT was a terminator.** The code after `HALT` in the syscall stubs and
  in pru1's `main` was never disassembled (pru0 had 196/205 words, pru1 had
  471/482).
* **TI local labels became functions.** pru0 had 39 functions and pru1 had
  116 (`$C$L*`, `$run$*`, `$M$*`/`$E$*` macro labels). The new
  `PRU_ElfExtension` fixes this.
* **R31 reads were constant-folded.** In pru1's sampling loops, every
  `mov r21.w0, r31.w0` decompiled to the last value written to R31 (`0x2b`)
  instead of a pin sample. R30 and R31 are now volatile.

Other fixes made during the same review, found by probing the reference
tools and stress-testing analysis:
* **`e_entry = 0` imports.** A stripped ELF linked at entry 0 (the TI
  default) got no function and no disassembly at all. Fixed in
  `PRU_ElfExtension`.
* **TSEN (V4).** It was undecodable. It is now added for V4, and ELF imports
  default to V4.
* **Unaligned bursts.** Bursts such as `lbco &r21.b3, ...` and
  `sbbo &r3.b2, sp, 0, 34` were unrolled into register varnodes that
  straddled two registers, so a function could fail to decompile with
  "Cannot properly adjust input varnodes". The pieces are now aligned.

## Known gaps

* **SCAN (V0 only, deprecated)** is not decoded. Its encoding is not
  documented, and neither clpru 2.3.3 nor binutils supports it.
* **V4 / ICSSG extensions** beyond TSEN are not modelled, because the TI CGT
  used here knows no others. TSEN is an opaque pcodeop. The task manager's
  effect on control flow (hardware task switches) is not modelled.
* **XFR devices other than MPY/MAC** (scratchpad banks 10-12, the other PRU's
  registers, broadside accelerators) are opaque pcodeops. SXIN/SXOUT/SXCHG
  have the same data flow as XIN/XOUT/XCHG.
* **LOOP edge cases.** Loop modelling needs flow disassembly to reach the LOOP
  before the body. Linear-sweep disassembly is fine; only the semantics need
  the context. Loops whose last body instruction is itself a taken branch, and
  LOOP offsets of 0 or 1, are approximated. Nested hardware loops are not
  modelled (the hardware has a single loop unit).
* **Immediates are shown in hex**, Ghidra's default; objdump prints decimal.
  The comparison normalizes this.
* **Decode strictness follows binutils.** Words with non-zero reserved fields
  decode where dispru prints `.word`. MVIx follows TI: pointers must be
  `r1.b0`..`r1.b3` and the reserved bits must be zero.
* **TI assembly labels.** `PRU_ElfExtension` turns `$`-prefixed local labels
  into plain labels. Assembly labels with ordinary names (BeagleLogic's
  `sample100m8`, `samplexm`, ...) are still zero-size `STT_FUNC` symbols and
  still become functions, so a jump to one looks like a tail call.
  `ghidra_scripts/PRUFixupTiLabels.java` removes these after analysis and
  re-derives the function bodies. Use it as a `-postScript`, or run it from
  the Script Manager. It is not run automatically.
* **Hand-written assembly calling conventions.** `jal rX.w2, f` with a link
  register other than `r3.w2`, and returns such as `jmp r24.w2` or `jmp ra.w0`,
  are modelled as a call and an indirect jump. The decompiler shows such a
  return as "Treating indirect jump as call". It is still correct, but noisy.
  Ghidra does not infer that a routine reached by `jal` never returns. A
  `jal` as the last word of `.text` then shows up as flow into non-existent
  memory and `halt_baddata()` in its callers.
* **HALT falls through** (see Semantics). After the last HALT of a routine
  that the host never resumes, analysis continues into whatever follows. For
  example, BeagleLogic's `sc_downcall` runs into `_c_int00`.
* **Register-offset LBCO/SBCO** (`sbco &r8, c0, r0.w0, 4`) do not get a data
  reference even when `cN` is known. The decompiler shows the base as a
  constant plus the offset.
* **The constant-table helper only knows AM335x.** Use overrides, or set the
  registers by hand, for other devices: AM437x/AM57xx/K3 entries differ for
  some indexes.
* **Untested:** big-endian PRU ELFs, which the TI tools can produce but which
  are not declared; relocatable `.obj` imports; V0/V1/V2 ELFs on real
  firmware; GNU-toolchain (pru-gcc) firmware beyond `test/elf/gnu_demo.elf`.

## Files

```
data/languages/pru.sinc            generated SLEIGH (tools/gen_pru_sinc.py; regenerate, don't edit)
data/languages/pru_v{0..4}.slaspec feature switches per core revision
data/languages/pru.ldefs .pspec .cspec .opinion
ghidra_scripts/PRUSetConstantTable.java   set c0..c31 (AM335x table + overrides)
ghidra_scripts/PRUFixupTiLabels.java      drop TI label pseudo-functions
tools/gen_pru_sinc.py              generator for pru.sinc
test/run-tests.sh                  full test: corpus, objdump, dispru, Ghidra, compare, emu, ELF
test/gen_corpus.py, compare.py, ti_dis.py, ghidra-dis.sh, PruDumpDisasm.java
test/emu-test.sh, PruEmuTest.java, emu/   p-code emulation test (TI-assembled emu_test.bin)
test/elf-check.sh, PruElfCheck.java, elf/ ELF import/decompile check (demo_v3.elf, gnu_demo.elf)
test/build-jar.sh                  compile src/main/java into lib/PRU.jar (quick path for tests)
test/fetch-real-samples.sh         download the public real-world samples (pinned, sha256-checked)
test/real-binaries.sh              real-world check: fetch + real-check.sh per sample -> real-report.txt
test/real-check.sh, PruRealCheck.java, elf_code.py, real_compare.py   import/analyze/decompile/diff one ELF
src/main/java/.../PRU_ElfExtension.java  ELF import tweaks (entry 0, TI labels, constant table)
```

## Running the tests

```sh
export GHIDRA_INSTALL_DIR=/path/to/ghidra_12.1.4_PUBLIC
export OBJDUMP=/path/to/binutils-2.45/build/binutils/objdump   # built with --enable-targets=pru-elf
export TI_CGT=/path/to/ti-cgt-pru_2.3.3                          # optional: per-version TI comparison
test/run-tests.sh /tmp/pru-test        # report in /tmp/pru-test/report.txt
test/real-binaries.sh /tmp/pru-real    # real-world firmware; report in /tmp/pru-real/real-report.txt
```

Both scripts build `lib/PRU.jar` with `test/build-jar.sh`, which needs `javac`
21 or newer. Ghidra loads a module's Java code only from `<module>/lib/*.jar`.
Without the jar, the language still works, but the ELF import tweaks
(`PRU_ElfExtension`) are inactive. Delete `lib/` before running
`gradle buildExtension`, which builds and packages its own `lib/PRU.jar`.

The TI CGT Linux installer (`ti_cgt_pru_2.3.3_linux_installer_x86.bin`) is a
32-bit BitRock installer. On current distributions, run it with
`GLIBC_TUNABLES=glibc.rtld.execstack=2` and a writable `HOME`:
`--mode unattended --prefix <dir>`.

Building the installable extension:
`GHIDRA_INSTALL_DIR=... gradle buildExtension` creates the zip in `dist/`.
`.sla` files are compiled on first use.
