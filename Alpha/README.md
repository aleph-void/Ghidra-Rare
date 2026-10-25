# DEC Alpha processor module for Ghidra

SLEIGH processor module for the DEC/Compaq Alpha (AXP): disassembly, p-code semantics,
implementation-specific PALcode instructions, per-OS register names and CALL_PAL functions,
ELF loading with relocations. Target: **Ghidra 12.1.4** (also builds for 12.1.3 and 12.2).

This is the community module [kkaempf/ghidra-alpha](https://github.com/kkaempf/ghidra-alpha)
by Klaus Kämpf and Matt Turner (Apache-2.0), verified and fixed by Ghidra-Rare. See
[CREDITS.md](CREDITS.md) for provenance and the full list of changes.

## Languages

Fifteen languages: five CPU generations times three operating-system conventions.

| Language ID | CPU | PALcode format |
|---|---|---|
| `21064:LE:64:{unix,vms,nt}` | 21064/21066/21068 (EV4, EV45, LCA) | EV4 |
| `21164:LE:64:{unix,vms,nt}` | 21164/21164A/21164PC (EV5, EV56, PCA56) | EV5 |
| `21264:LE:64:{unix,vms,nt}` | 21264 (EV6, EV67, EV68) **ELF default** | EV6 |
| `21364:LE:64:{unix,vms,nt}` | 21364 (EV7) | EV6 |
| `21464:LE:64:{unix,vms,nt}` | 21464 (EV8) | EV6 |

User-mode code decodes identically in all of them; every language accepts the BWX, FIX, CIX
and MVI extensions. The CPU matters for PALcode (HW_MFPR/HW_MTPR, HW_LD/HW_ST, HW_REI/HW_RET
encodings) and IMPLVER. The OS selects register names (`unix`: v0, t0, ..., pv, GP, SP;
`nt`: t12, gp, sp; `vms`: R0..R28, AI, RA, PV, FP), the calling convention and the named
CALL_PAL functions (CALLSYS/RDUNIQ/... for OSF/1 and Linux, the NT and OpenVMS lists).

ELF: `EM_ALPHA` 0x9026 (what GNU toolchains write) and 41 load as `21264:LE:64:unix`.
The relocation handler applies RELATIVE, REFQUAD, GLOB_DAT, JMP_SLOT, REFLONG, SREL*, BRADDR
and HINT. The gp analyzer seeds `pv` at every function entry and `gp` at the second entry
point after an `ldgp` prologue. With `ra` and `gp` unaffected by calls, gp-relative globals
resolve in the decompiler. `ghidra_scripts/AlphaPALcodeEntries.java` marks PALcode vectors
and CALL_PAL entry points, which nothing branches to.

## Results

| Check | Result |
|---|---|
| SLEIGH | 15/15 specs compile on Ghidra 12.1.3, 12.1.4, 12.2; `.sla` 23-28 KB each |
| Decode vs GNU objdump 2.45, every opcode-table entry (16 words each, 16,000 words) | 21264/21364/21464: 100% exact+semantic. 21064: 99.78% plus 34 words of a confirmed objdump bug. 21164: 77.05% plus 3,554 words of a confirmed objdump bug. 0 unexplained differences, 0 words decoded by only one side |
| Decode, 50,000 random words | 21264+: 100.00% (99.16% exact). 21064: 99.87% + 46 objdump-bug words. 21164: 98.23% + 611 objdump-bug words. 0 differ, 0 one-sided |
| Every-entry test (all 16 words of each applicable table entry decode and agree) | EV4 716/716, EV5 880/880, EV6 670/670 |
| CALL_PAL names vs MAME `unidasm` (0x00-0x3f, 0x80-0xbf) | UNIX, NT, VMS: 128/128 each |
| Emulator, hand-computed | 37/37 (the imported upstream fails 9 of them) |
| Emulator vs `qemu-alpha -cpu ev67`, random operate instructions and inputs | 40,000/40,000 (120 mnemonics, two seeds) |
| Debian alpha `libz.so.1.3.2`, `ls`, `sort`, `libc.so.6.1`, `busybox` (static) | Opinion picks the language for all. 822,959 instructions, 100% agree with objdump at the same addresses. 0 bad-instruction and 0 error bookmarks. Relocations: 1,703 applied, 15 TLS TPREL64 reported. 13,327 functions decompiled, 0 failures, 0 timeouts |
| QEMU EV6 PALcode `palcode-clipper` | 3,749 instructions incl. 269 HW_* agree with `objdump -m alpha:ev6`. 322 functions decompile |

The upstream module as imported scored 94-95% on random words and 586-591 of 670-880 table
entries. It had no ELF opinion, so Debian binaries did not import.

Semantic agreement covers objdump's alternative spellings: `or`/`andnot`/`jcr` for the
architecture's BIS/BIC/JSR_COROUTINE, objdump pseudo-ops (`negq`, `fmov`, `sextl`, `negt/su`,
...) that the module prints in full, and OS-named CALL_PAL functions.

### Confirmed GNU objdump 2.45 bugs

- **EV5 HW_LD/HW_ST bit 10** (load LOCK, store COND) is never decoded: `EV5HWMEM_MASK` is
  `OP_MASK | 0xF800`, so the table's `hw_ldl/l`, `hw_ldq_l`, `hw_stl/c` ... entries never match
  and objdump prints the plain form. The module decodes the bit (21164 HRM).
- **EV4 HW_ST, mode 0xE**: `alpha-opc.c` names both `EV4HWMEM(0x1F,0xE)` and `0xF`
  `hw_stq/par`. 0xE is the longword form `hw_stl/par` (the generic `hw_st/par` entry
  agrees).

## Testing

```sh
export GHIDRA_INSTALL_DIR=/path/to/scratch/ghidra_12.1.4_PUBLIC   # module gets symlinked in
test/run-tests.sh /tmp/alpha-tests          # SLEIGH, decode, every-entry, emulator, QEMU diff
test/fetch-real-samples.sh samples          # Debian alpha packages + QEMU palcode, pinned SHA-256
test/real-binaries.sh samples /tmp/alpha-real
```

Needs: GNU binutils with the alpha target (`OBJDUMP`, plus `BINUTILS_SRC`/`BINUTILS_BUILD`
to dump its opcode table, see `test/dumpopc.c`), MAME `unidasm`, `qemu-alpha` (optional), a
JDK with `javac` for `lib/Alpha.jar`. Ghidra rejects project paths containing a dot-directory;
set `PROJ_DIR` when `TMPDIR` is under one.

## Known gaps

- MVI byte/word MIN/MAX and PERR, AMASK, RPCC, the FPCR, cache hints and PALcode IPR
  accesses are pcodeops. Rounding-mode and trap qualifiers are printed but not modelled.
  VAX F/G arithmetic uses IEEE float p-code, and VAX loads/stores move bits unchanged.
- LDS/STS/ITOFS/FTOIS convert by value (float2float). This is exact for normal numbers,
  zeros and infinities, but not for denormals and NaN payloads, where the hardware moves bits.
- Floating-point arguments use f16-f21 in order, independent of integer arguments. The
  calling standard shares six slots between a0-a5 and f16-f21, which Ghidra cannot express.
- About 9 of 452 decompiled `ls` functions still lose a switch table ("Too many branches"
  when the bound is held in a callee-saved register across calls).
- gcc's two entry points per procedure (before and after `ldgp`) become two overlapping
  functions.
- Relocatable objects: gp-relative relocations (LITERAL, GPDISP, GPREL*) are reported, not
  applied. TLS relocations are reported.
- NT and VMS conventions, and the 21064/21164 PALcode formats, were checked only against
  objdump and MAME, not against real NT/VMS binaries or EV4/EV5 PALcode images.
- The cspecs for NT and VMS are upstream's apart from the stack-shift fix; NT's 32-bit
  pointer model is not represented.
