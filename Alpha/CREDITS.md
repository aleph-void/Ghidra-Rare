# Credits

## Upstream

This module is the DEC Alpha processor module from
[kkaempf/ghidra-alpha](https://github.com/kkaempf/ghidra-alpha), imported at commit
`77e083fa65f1c72bc80c81b5b66fab57f68948ff` (2026-08-16, "Merge pull request #7 from
mattst88/fix-fetch-test-expectations"). License: Apache License 2.0 (`LICENSE`, unchanged).

Original authors (from the upstream history, 109 commits):

- Klaus Kämpf ([@kkaempf](https://github.com/kkaempf)): the module, its OS-specific
  variants and the 21064/21164 PALcode support (73 commits as Klaus Kämpf).
- Matt Turner ([@mattst88](https://github.com/mattst88)): semantics fixes, objdump
  pseudo-op idioms, the gp-relative reference analyzer, NT calling-convention fixes
  (36 commits).

Upstream files keep their copyright and license headers. Changes made here are also licensed
under Apache-2.0 and exist as commits on top of the upstream history (branch `ghidra-rare` of
the fork:
[aleph-void/ghidra-alpha](https://github.com/aleph-void/ghidra-alpha/tree/ghidra-rare), commit
`fa2c39cc2e1c6a83b2ac9afa9ee9ea99c3196cb0`).

## Compared, not used

- [claesmnyberg/ghidra-cpu-alpha](https://github.com/claesmnyberg/ghidra-cpu-alpha) has no
  license, so nothing was taken from it. It was only measured with the same decode test (see
  README): 50.5% of random words and 133 of 670 EV6 opcode-table entries agree with objdump.

## Reference material

- GNU binutils 2.45 `objdump` (decode oracle) and its opcode table, read at test time from a
  local build (`test/dumpopc.c`); binutils itself is GPL and is not copied into this module.
- MAME `unidasm` (`alpha_unix`, `alpha_nt`, `alpha_vms`) for the per-OS CALL_PAL function
  names; the UNIX names follow the Linux kernel's `asm/pal.h`.
- QEMU `qemu-alpha` user-mode emulation as the reference for the p-code differential test.
- Alpha Architecture Handbook (EC-QD2KC-TE), 21064/21164/21264 hardware reference manuals.

## Ghidra-Rare changes

Commits on branch `ghidra-rare` (upstream `77e083f..`):

1. `5ed8caa` Decode brought in line with GNU objdump on every opcode-table entry:
   - PALcode instructions rewritten per implementation (21064 HW_MFPR/HW_MTPR register-file
     selects and HW_LD/HW_ST{L,Q} /P /A /R; 21164 16-bit IPR index and HW_LD/HW_ST
     /P /A /W /V /L and /C modes with 10-bit displacement, HW_REI_STALL; 21264+ HW_MFPR/HW_MTPR
     index plus scoreboard mask, HW_LD/HW_ST access types, HW_JMP/HW_JSR/HW_RET/HW_JCR with
     /STALL).
   - Named CALL_PAL functions per OS PALcode (new `alpha_pal_{unix,nt,vms}.sinc`).
   - MOV pseudo-op matched the literal form `bis ra,lit,rc` when the literal bits equalled Ra
     and computed `rc = lit` (wrong result).
   - RET/JSR_COROUTINE hints printed as raw values; JMP (Rb), LDAH Ra,disp and UNOP pseudo-ops.
   - Must-be-R31 / must-equal-Ra operands enforced (AMASK, FETCH, ECB, WH64, MT_FPCR, ...).
   - Floating-point qualifier sets per instruction (SQRT qualifiers added; compares, CVTQS/CVTQT,
     CVTQF/CVTQG restricted to the valid sets).
   - Reserved opcodes no longer decode as `OPC01`..`OPC14` unimplemented instructions.
   - Semantics: ZAP/ZAPNOT byte selection for bytes 4-7, RPCC/RC/RS wrote a temporary, STS stored
     8 bytes, single/double conversions for LDS/STS/ITOFS/FTOIS and S arithmetic, FP compare
     results (2.0 / 0.5), CVTLQ/CVTQL and IEEE conversions in p-code, F31 load targets, HW_LD/ST
     access sizes.
2. `19e7be2` Branch-free ZAP/ZAPNOT (constant masks fold; was the source of most "unreachable
   block" decompiler warnings and blocked switch recovery); CTLZ/CTTZ via lzcount/popcount.
3. `d841181` ELF opinion (EM_ALPHA 0x9026 and 41; Debian alpha binaries had no load spec),
   `Alpha_ElfRelocationHandler`, DWARF register maps, corrected language descriptions.
4. `54bcbea` UNIX/Linux cspec: LP64 data organization, no stack shift, argument registers,
   ra and gp unaffected by calls (gp-relative globals resolve after calls).
5. `3b52b39` gp seeded at the second (post-`ldgp`) entry point of procedures.
6. `9125985` EXTxH at byte position 0, NEGS/NEGT of zero (found against QEMU); CALLSYS/CHMK,
   RDUNIQ, RDTEB return their result registers (30 libc functions failed to decompile).
7. `b662c3e` UNPKBW/UNPKBL/PKWB/PKLB without bit-range stores (crashed Ghidra's emulator).
8. `bf16777` certification.manifest entries for the new files.

Ghidra-Rare-only additions: `README.md`, this file, `build.gradle`, `extension.properties`,
`ghidra_scripts/AlphaPALcodeEntries.java` and everything under `test/`.
