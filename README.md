# Ghidra-Rare

Ghidra processor modules (SLEIGH) for uncommon CPU, DSP and GPU architectures. Target: **Ghidra 12.1.4**.

This project brings to Ghidra the set of architectures covered by
[Mr-wolf-is-me/IDA-Processor-Modules](https://github.com/Mr-wolf-is-me/IDA-Processor-Modules),
a collection of IDA Pro processor modules. Each module here is the Ghidra counterpart of one
of the IDA modules listed there.

## Modules

| Module | Architecture | Language IDs | Original IDA module |
|---|---|---|---|
| [PRU](PRU/README.md) | TI PRU / PRU-ICSS, core revisions V0–V4 | `PRU:LE:32:v0` … `PRU:LE:32:v4` | [pru-ida](https://github.com/Mr-wolf-is-me/pru-ida) |
| [MicroBlaze](MicroBlaze/README.md) | AMD/Xilinx MicroBlaze, 32/64-bit, BE/LE | `MicroBlaze:{BE,LE}:{32,64}:default` | [microblaze-ida](https://github.com/Mr-wolf-is-me/microblaze-ida) |
| [xCORE](xCORE/README.md) | XMOS xCORE XS1, XS2 (xCORE-200), XS3 (xcore.ai) | `xCORE:LE:32:XS1`, `XS2`, `XS3` | [xcore-ida](https://github.com/Mr-wolf-is-me/xcore-ida) |
| [C7x](C7x/README.md) | TI C7000 DSP (C7100, C7120, C7504, C7524) | `C7x:LE:64:C7100`, `C7120`, `C7504`, `C7524` | [c7x-ida](https://github.com/Mr-wolf-is-me/c7x-ida) |
| [SASS](SASS/README.md) | NVIDIA GPU SASS (Ampere/Ada done; other generations in progress) | `SASS:LE:64:SM80`, `SM86`, `SM89` | [sass-ida](https://github.com/Mr-wolf-is-me/sass-ida) |

Each module's README lists its language variants, how closely it matches the reference
disassembler, what the p-code models, known gaps and how to run its tests. [STATUS.md](STATUS.md)
tracks what works and what doesn't across all modules, plus lessons learned.

## Relationship to the IDA modules

The IDA modules are distributed as release zips under terms that forbid derivative works; the
repositories themselves hold only READMEs, licenses and screenshots. This project is an **independent, clean-room implementation**, not a port of that code:

- No IDA module binaries, source or release archives were downloaded, unpacked, disassembled
  or otherwise used. Only the public README files were read, as a list of architectures and
  features to cover.
- Instruction encodings and semantics come from vendor documentation (TI, AMD/Xilinx, XMOS)
  and published research. Each module was checked against vendor or open-source reference
  disassemblers (TI `dispru`/`dis7x`, GNU binutils, LLVM, NVIDIA `nvdisasm`).

Credit for the idea and for choosing these architectures goes to the author of
IDA-Processor-Modules.

## Installing

Each module directory is a standard Ghidra extension.

**Build an extension zip:**

```sh
export GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC
cd PRU && gradle buildExtension      # zip lands in PRU/dist/
```

PRU and MicroBlaze include Java code (ELF loader extensions), so the build needs a full JDK 21 or
newer with `javac` (a JRE-only package is not enough); point `JAVA_HOME` at it.

Install the zip via *File → Install Extensions* in Ghidra, then restart Ghidra.

**For development**, symlink every module into a Ghidra install and compile the SLEIGH specs:

```sh
export GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC
tools/link-modules.sh
for d in */data/languages; do "$GHIDRA_INSTALL_DIR/support/sleigh" -a "$d"; done
```

`tools/ghidra-dis.sh <language-id> <raw.bin>` prints a headless linear-sweep disassembly of a
raw binary, which is useful for quick checks.

## License

[MIT](LICENSE). This license covers only the code in this repository. It does not cover the
original IDA modules, which have their own terms.
