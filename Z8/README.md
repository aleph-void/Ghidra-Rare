# Zilog Z8 for Ghidra

An independent SLEIGH module for the Zilog Z8 family, including Z8601, Z86xx,
Z86Cxx and the UB8830/UB8840 clones. It targets Ghidra 12.1.4. Instruction
encodings and behavior were implemented from Zilog's *Z8 CPU User Manual*
(UM0016); MAME `unidasm -arch z8` is a black-box decode reference.

## Languages and memory model

| Language | Stack |
|---|---|
| `Z8:BE:16:default` | Internal register-file stack, using SPL |
| `Z8:BE:16:extstack` | External data-memory stack, using SPH:SPL |

The language has separate 64 KiB program (`code`) and external data (`data`)
spaces, a 256-byte register file (`rf`), and an expanded register file (`erf`).
The register pointer selects a working-register group and expanded bank. Its
value is tracked after `SRP` or a constant write to RP; when unknown, the
p-code computes the register address at run time. The processor specification
marks the six interrupt vectors at 0000h–000Bh and the reset entry at 000Ch.
`Z8VectorAnalyzer` types valid vectors and discovers their handlers.

Arithmetic, flags, branches, calls, memory transfers and stack operations
have p-code. HALT, STOP and watchdog actions are user-defined p-code
operations; device timing, interrupts and peripherals are outside the CPU
language model.

## Verification

- The opcode corpus plus 50,000 random slots was checked against MAME with
  several RP contexts: 0 unexplained differences. The remaining differences
  are MAME's reversed `D7` operand order and CMOS opcodes present in UM0016
  that its older Z8601 decoder calls illegal. All 410 SLEIGH constructors were
  reached.
- Emulator checks: 102/102 internal-stack and 96/96 external-stack cases.
- Seven Apache-2.0/MIT source programs assembled with `libasm` were checked.
  The two instruction-form suites decode all 698 listed instructions without
  boundary conflicts. Five analysed programs yielded 1,622 instructions
  identical to MAME, 38/38 functions decompiled, and no bad-instruction
  bookmarks. Some assembler-listed instructions were not reached by analysis.

These tests do not validate peripheral behavior or cycle timing on hardware.
For images using an external stack, select the `extstack` language at import.

## Build and test

```sh
export GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC
python3 Z8/tools/gen_z8.py > Z8/data/languages/z8_gen.sinc
"$GHIDRA_INSTALL_DIR/support/sleigh" -a Z8/data/languages
(cd Z8 && gradle buildExtension)
Z8/test/emu-test.sh
Z8/test/run-decode.sh "$HOME/.cache/ghidra-rare-scratch/z8-decode" 50000 0x00 0x0f 0x70 0xf0 0xfc
```

`test/real/fetch-and-build.sh` fetches pinned, checksum-verified source from
[89Mods/misc-computers](https://github.com/89Mods/misc-computers) (MIT) and
[tgtakaoka/libasm](https://github.com/tgtakaoka/libasm) (Apache-2.0), then
assembles it locally. `test/real-check.sh` runs Ghidra analysis and compares
the listing to MAME and the assembler. Neither downloaded sources nor built
samples are committed.

This module is MIT-licensed; see [LICENSE](LICENSE).
