# ST9 and ST9+ for Ghidra

An independent SLEIGH processor module for the STMicroelectronics ST9 and
ST9+ 8/16-bit MCU families, targeting Ghidra 12.1.4. The encodings and p-code
were written from the *ST9 Family 8/16 Bit MCU Programming Manual* (1991) and
the *ST9+ Family Programming Manual*. MAME `unidasm -arch st9` and `st9p` were
used as black-box decode references. This is a new implementation for parity
with IDA's built-in ST9 support; it does not derive from an IDA module.

| Language | Program addresses | Description |
|---|---:|---|
| `ST9:BE:16:default` | 16-bit | Original ST9 instruction set |
| `ST9:BE:24:ST9+` | 24-bit | ST9+ instructions and CSR-selected code segments |

Both languages have separate program, data, and register-file spaces. The
SLEIGH context tracks the register pointers, page pointer, stack location,
SPM/SDM memory selection, and on ST9+ the interrupt CSR save mode. When a
register pointer is unknown, p-code computes the register-file address at run
time. `ST9VectorAnalyzer` types the three fixed pointers at 0000h–0005h and
discovers the reset, divide-by-zero and top-priority interrupt routines.

## Verification

- For each variant, an enumerated opcode corpus plus 20,000 random records
  produced **0 unexplained decode differences** against MAME across 158,752
  records. The comparison separates reserved encodings and confirmed MAME
  display errors; `test/compare.py` records each class. Every constructor was
  reached: 961/961 ST9 and 983/983 ST9+.
- Hand-computed emulator checks pass: 17/17 per variant. They cover byte and
  word arithmetic, flags, direct and working registers, and both stack
  locations.
- A small original program imports and analyses on both variants: 11/11 code
  instructions identified, 3/3 functions decompile, and no error bookmarks.
  Its instruction text matches MAME on those 11 instructions.

No freely licensed third-party ST9 firmware was found for a real-image check.
Peripherals, interrupt timing, physical data-memory mapping through the ST9+
DPR registers, and HALT/WFI side effects are not modeled. Those instructions
use p-code operations where appropriate. Other p-code forms beyond the 17
emulator cases have not been checked against hardware.

## Build and test

```sh
export GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC
python3 ST9/tools/gen_st9.py ST9/data/languages
"$GHIDRA_INSTALL_DIR/support/sleigh" -a ST9/data/languages
(cd ST9 && gradle buildExtension)
ST9/test/run-decode.sh "$HOME/.cache/ghidra-rare-scratch/st9-decode" 20000 1
ST9/test/coverage.sh "$HOME/.cache/ghidra-rare-scratch/st9-decode"
ST9/test/emu-test.sh
ST9/test/smoke-test.sh
```

The module's code is MIT-licensed; see [LICENSE](LICENSE). Test inputs are
generated locally and no firmware or reference-disassembler source is bundled.
