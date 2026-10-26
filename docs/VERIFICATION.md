# Verification bar

A module is called **done** here only when it meets this bar, or when its README and
[STATUS.md](../STATUS.md) say exactly which part it doesn't meet and why. The bar is the same for
modules written here and for community modules imported from other authors.

The principle: every claim needs a number from a test that can fail. "Decodes correctly" means a
differential test against an independent reference with the differences bucketed, not that
someone looked at the output.

## 1. It builds

- Every `.slaspec` compiles with the SLEIGH compiler of each supported Ghidra release (the three
  newest: see the [release workflow](../.github/workflows/release.yml)). The release zip builds
  with `tools/build-module.sh`.
- Each `.sla` is under 16 MB.
- Language IDs don't collide with Ghidra's own or with another module here.

## 2. Decode agrees with a reference

Pick an independent reference disassembler and run it as a black box (a GNU binutils `objdump`,
LLVM, MAME `unidasm`, a vendor tool). Then:

- Compare on **every encoding that can be enumerated** (or every opcode/field combination) and on
  **tens of thousands of random words**.
- Report *exact* agreement (same text) and *semantic* agreement (same instruction, different
  spelling) separately.
- **Bucket every difference** into a class and either fix it or explain it. Typical explained
  classes: the reference accepts an encoding the manual calls reserved; a confirmed reference-tool
  bug; display-only differences. Nothing may stay "unexplained".
- Reference tools have bugs. Before changing the module to match a difference, confirm it against
  the vendor manual. List every confirmed reference bug in the module README.
- If no reference exists, say so and use a vendor assembler's output or the manual's tables
  instead; mark the result accordingly.

## 3. Every entry is reachable

An every-entry test proves that each SLEIGH constructor (or table/opcode entry) decodes at least
one instruction. This is what catches a pattern shadowed by an earlier one, which a "both
undefined" differential result can hide. Report `reached/total`.

## 4. Semantics are checked, not just decoded

- P-code models real behaviour: ALU results, carries and flags, loads and stores in every
  addressing mode, branches, calls and returns, and whatever the ISA has (delay slots, bundles,
  predication, hardware loops, segments). A pcodeop is acceptable only for something p-code can't
  express (privileged or hardware state), and must be listed under *Doesn't work*.
- At least **20 hand-computed sequences** run in Ghidra's emulator (`EmulatorHelper`, run from a
  Java `GhidraScript`; Ghidra 12 ships no Jython), with expected register, memory and flag
  results worked out by hand from the manual, never copied from the module's own output.
- **A deliberately broken expectation must fail.** Each suite runs one wrong expectation and
  checks that it is reported, to prove the test can fail.

## 5. It works on real code

- Run real third-party or self-built binaries through headless import. Prefer an auto-detecting
  import (no forced language) when the module ships an opinion.
- Report instructions, functions, bad-instruction bookmarks, error bookmarks and decompile
  failures. Compare the disassembly with the reference at the same addresses, or with the
  assembler source or listing when you have it.
- Test inputs must be freely licensed (GPL, MIT, BSD, public domain, or redistributable by the
  vendor) or built by you from public source with a free toolchain. **Never commit them:** fetch
  them with a script that pins the URL and SHA-256. If a sample's license forbids disassembly, don't
  use it. If no legal binary or toolchain exists, test with assembled programs and say so under
  *Unverified*.

## 6. Spec files and loaders

- The `.cspec` has a `<global>` range and a sensible default prototype; the `.pspec` is present.
- An ELF opinion (`e_machine`/`e_flags`) when the architecture has ELF binaries, with relocation
  handling for the relocation types the binaries use.
- A `.dwarf` register mapping if a compiler for the ISA emits DWARF.
- A loader or analyzer where real binaries need one (vector tables, switch tables, firmware
  formats).

## 7. Known gaps are closed

Everything testing finds is fixed before the module is reported done, unless it is inherent:
hardware state Ghidra can't model, a decompiler limit outside the module, or no legally usable
test input. Each remaining item needs a stated reason. "Not modelled" and "is a pcodeop" are not
reasons when p-code can express the behaviour.

For community modules this includes the upstream's own known limitations: its README's
limitation/TODO/"experimental" sections, stale claims, open and closed-unfixed issues, and
`TODO`/`FIXME` comments.

## 8. The report

Each module reports its results in the shape [STATUS.md](../STATUS.md) uses, and the module
README repeats them with the details:

| Area | What goes in it |
|---|---|
| Decode | corpus sizes, agree / both-invalid / explained counts, `reached/total` constructors |
| Semantics | what the p-code covers, emulator case count, "broken expectation detected" |
| Real code | what was run, counts of instructions, functions, bookmarks, decompile failures |
| Doesn't work | each remaining gap with its reason |
| Unverified | what no test covered (hardware behaviour, missing samples, other variants) |

Also list every confirmed bug in the reference tools.

## 9. Test suite layout

Each module has a `test/run-tests.sh` that runs everything that needs no non-redistributable input,
and exits non-zero on any failure. `--real <workdir>` adds the steps that fetch or build real
binaries. A typical suite:

1. the generator (if any) reproduces the checked-in generated SLEIGH;
2. the specs compile;
3. emulator cases pass, and the broken expectation is reported;
4. every constructor is reached;
5. the decode differential has 0 unexplained differences;
6. with `--real`, the real-code checks.

`tools/new-module-skeleton` creates a module directory with this layout. The finished modules
(for example `XA/`, `Z8/`, `RX/`) show full suites.

## Local-only inputs

Vendor firmware whose license forbids disassembly may be analysed locally, if the maintainer
approves it. Nothing derived from it (results, names, numbers, samples) is committed or
published. Test publicly on freely licensed samples instead.
