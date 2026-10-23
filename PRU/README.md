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
| `PRU:LE:32:v3`  | V3 (AM335x, AM437x, AM57xx PRU-ICSS) **default** | + LOOP/ILOOP, SXIN/SXOUT/SXCHG |
| `PRU:LE:32:v4`  | V4 (ICSSG)    | same decode as V3. TI CGT 2.3.3 assembles and disassembles nothing extra for `-v4`. |

The per-revision differences come from probing TI `clpru -vN` (which
instructions it accepts) and `dispru` (which words it decodes for objects built
with `-vN`). On a 25,886-word corpus, `dispru` gives identical output for V3 and
V4.

ELF: `EM_TI_PRU` (144), little-endian ELF32. Both TI and GNU executables import
automatically (`data/languages/pru.opinion`). Neither ELF flavour records the
core revision in `e_flags` (TI keeps it in `__TI_build_attributes`), so ELF
imports default to **V3**. Pick another variant by hand if needed.

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
  * R30 (GPO) and R31 (GPI/event status) are declared as cspec globals so their
    reads and writes survive decompilation.
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
  * HALT is a self-loop terminator. SLP calls the `sleep` pcodeop.
  * MVIB/MVIW/MVID read and write the register file through a pointer, with
    post-increment and pre-decrement.
  * LBBO/SBBO/LBCO/SBCO with an immediate length 1..124 are unrolled into direct
    register varnodes, so the decompiler sees exactly which registers are
    loaded or stored. A length in `r0.bN` becomes a byte loop.
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

The corpus has 25,886 words. The structured part covers:
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
| V3/V4 vs TI dispru (`-v3`/`-v4`) | 17,555 | 99.90 % | **100.00 %** |
| V2 vs TI dispru `-v2`           | 17,429 | 99.90 % | 100.00 % |
| V1 vs TI dispru `-v1`           | 17,125 | 99.91 % | 100.00 % |
| V0 vs TI dispru `-v0`           | 16,915 | 99.91 % | 100.00 % |

* The "exact" misses against TI are all pseudo-op spellings, for example
  `mov`/`nop`/`ret`/`call`/`wbs`/`zero`, which dispru prints as base
  instructions.
* Ghidra never fails on a word that a reference decodes.
* Words Ghidra decodes but a reference rejects:
  * **vs objdump: 187.** 97 are `not` with IO=0, which is how TI `clpru`
    encodes NOT and which binutils cannot decode. The other 90 are MVIx, which
    binutils lacks; those match TI.
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
  * Both import as `PRU:LE:32:v3`, auto-analyze, and decompile every function
    without errors. Calls, arguments, returns, loops, the switch chain, the
    constant-table addresses and the R30/R31 I/O all come out readable.

## Known gaps

* **SCAN (V0 only, deprecated)** is not decoded. Its encoding is not
  documented, and neither clpru 2.3.3 nor binutils supports it.
* **V4 / ICSSG extensions** beyond the V3 instruction set are not modelled,
  because the TI CGT used here has none. Additions such as task manager or
  broadside device semantics would need newer TI tools or docs.
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
* **TI local labels.** TI emits `$C$Ln` and assembly labels as zero-size
  `STT_FUNC` symbols, so Ghidra creates functions at them.
  `ghidra_scripts/PRUFixupTiLabels.java` removes these and re-derives the
  function bodies. Use it as a `-preScript` and/or `-postScript`, or run it
  from the Script Manager. It is not run automatically.
* **The constant-table helper only knows AM335x.** Use overrides, or set the
  registers by hand, for other devices: AM437x/AM57xx/K3 entries differ for
  some indexes.
* **Untested:** big-endian PRU ELFs, which the TI tools can produce but which
  are not declared; relocatable `.obj` imports; V0/V1/V2 ELFs on real
  firmware.

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
```

## Running the tests

```sh
export GHIDRA_INSTALL_DIR=/path/to/ghidra_12.1.4_PUBLIC
export OBJDUMP=/path/to/binutils-2.45/build/binutils/objdump   # built with --enable-targets=pru-elf
export TI_CGT=/path/to/ti-cgt-pru_2.3.3                          # optional: per-version TI comparison
test/run-tests.sh /tmp/pru-test        # report in /tmp/pru-test/report.txt
```

The TI CGT Linux installer (`ti_cgt_pru_2.3.3_linux_installer_x86.bin`) is a
32-bit BitRock installer. On current distributions, run it with
`GLIBC_TUNABLES=glibc.rtld.execstack=2` and a writable `HOME`:
`--mode unattended --prefix <dir>`.

Building the installable extension:
`GHIDRA_INSTALL_DIR=... gradle buildExtension` creates the zip in `dist/`.
`.sla` files are compiled on first use.
