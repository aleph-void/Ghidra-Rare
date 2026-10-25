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
| [SASS](SASS/README.md) | NVIDIA GPU SASS, Kepler through Blackwell | `SASS:LE:64:SM35`, `SM52`, `SM60`, `SM70`, `SM75`, `SM80`, `SM86`, `SM89`, `SM90`, `SM100`, `SM120` | [sass-ida](https://github.com/Mr-wolf-is-me/sass-ida) |

Each module's README lists its language variants, how closely it matches the reference
disassembler, what the p-code models, known gaps and how to run its tests. [STATUS.md](STATUS.md)
tracks what works and what doesn't across all modules, plus lessons learned.

## Community modules

SLEIGH modules written by others for CPUs Ghidra doesn't support, collected from GitHub and from
unmerged Ghidra pull requests ([candidates](community/CANDIDATES.md)), then tested to the same
standard as the modules above and fixed where testing found problems. Each module's `CREDITS.md`
names its original authors, the upstream commit and every change made here. Fixes are kept as
commits on an `aleph-void` fork of the original repository, under the original license.

| Module | Processor | Language IDs | Original authors | License |
|---|---|---|---|---|
| [65816](65816/README.md) | WDC 65C816 (SNES) and 65802, with a LoROM/HiROM SNES ROM loader | `65816:LE:16:default`, `65802:LE:16:default` | Adrian Chan (@achan1989), Greg Kennedy (@greg-kennedy), Kay (@kaayzouee) | MIT |
| [Alpha](Alpha/README.md) | DEC Alpha 21064/21164/21264/21364/21464 for UNIX/Linux, OpenVMS and Windows NT | 15 languages, see module README | Klaus Kämpf (@kkaempf), Matt Turner (@mattst88) | Apache-2.0 |
| [LM32](LM32/README.md) | Lattice LatticeMico32 | `lm32:BE:32:default`, `lm32:LE:32:default` | Jevin Sweval (@jevinskie), with @cyrozap | MIT |
| [OpenRISC](OpenRISC/README.md) | OpenRISC 1000 (ORBIS32, ORFPX32/64A32) | `OpenRISC:BE:32:default`, `OpenRISC:LE:32:default` | Samuel Holland (@smaeul), Jeroen Domburg (@Spritetm) | Apache-2.0 |
| [RL78](RL78/README.md) | Renesas RL78 (S1/S2 and S3 cores) | `RL78:LE:16:default` (S3), `RL78:LE:16:S2` | Callum Thomson (@CUB3D) | Apache-2.0 |

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

**Prebuilt zips:** the [Release builds](.github/workflows/release.yml) workflow builds every
module for the three newest Ghidra releases. Each `v*` tag publishes the zips on the
[Releases](https://github.com/aleph-void/Ghidra-Rare/releases) page; other pushes keep them as
workflow artifacts. A zip only installs into the Ghidra version in its name.

**Build the extension zips yourself:**

```sh
tools/build-release.sh /opt/ghidra_12.1.4_PUBLIC dist   # one zip per module in dist/
```

The script compiles the SLEIGH specs with that Ghidra's compiler and builds each module with the
Gradle wrapper Ghidra ships in `support/gradle`. PRU, MicroBlaze and SASS include Java code (ELF
loader extensions), so the build needs a full JDK with `javac` (a JRE-only package is not
enough): JDK 21 or newer for Ghidra 12.1, JDK 25 for Ghidra 12.2. Point `JAVA_HOME` at it.

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

[MIT](LICENSE) for the five modules written here and the tooling. Community modules keep their
original licenses (each module directory has its own `LICENSE`). Neither covers the original IDA
modules, which have their own terms.
