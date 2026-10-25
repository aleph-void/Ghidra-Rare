# Ghidra-Rare

Ghidra processor modules (SLEIGH) for uncommon CPU, DSP and GPU architectures. Developed on
**Ghidra 12.1.4**; release builds cover the three newest Ghidra releases (currently 12.1.3,
12.1.4 and 12.2).

The project has two parts:

- **[Modules](#modules)** written here, which bring to Ghidra the set of architectures covered by
  [Mr-wolf-is-me/IDA-Processor-Modules](https://github.com/Mr-wolf-is-me/IDA-Processor-Modules),
  a collection of IDA Pro processor modules. Each is the Ghidra counterpart of one of the IDA
  modules listed there.
- **[Community modules](#community-modules)**: SLEIGH modules other people wrote for CPUs Ghidra
  doesn't support, imported with credit, tested to the same standard and fixed.

## Modules

| Module | Architecture | Language IDs | Original IDA module |
|---|---|---|---|
| [PRU](PRU/README.md) | TI PRU / PRU-ICSS, core revisions V0–V4 | `PRU:LE:32:v0` … `PRU:LE:32:v4` | [pru-ida](https://github.com/Mr-wolf-is-me/pru-ida) |
| [MicroBlaze](MicroBlaze/README.md) | AMD/Xilinx MicroBlaze, 32/64-bit, BE/LE | `MicroBlaze:{BE,LE}:{32,64}:default` | [microblaze-ida](https://github.com/Mr-wolf-is-me/microblaze-ida) |
| [xCORE](xCORE/README.md) | XMOS xCORE XS1, XS2 (xCORE-200), XS3 (xcore.ai) | `xCORE:LE:32:XS1`, `XS2`, `XS3` | [xcore-ida](https://github.com/Mr-wolf-is-me/xcore-ida) |
| [C7x](C7x/README.md) | TI C7000 DSP (C7100, C7120, C7504, C7524) | `C7x:LE:64:C7100`, `C7120`, `C7504`, `C7524` | [c7x-ida](https://github.com/Mr-wolf-is-me/c7x-ida) |
| [SASS](SASS/README.md) | NVIDIA GPU SASS, Kepler through Blackwell | `SASS:LE:64:SM35`, `SM52`, `SM60`, `SM70`, `SM75`, `SM80`, `SM86`, `SM89`, `SM90`, `SM100`, `SM120` | [sass-ida](https://github.com/Mr-wolf-is-me/sass-ida) |
| [Z8](Z8/README.md) | Zilog Z8 and UB8830/UB8840, internal or external stack | `Z8:BE:16:default`, `Z8:BE:16:extstack` | Added for IDA built-in CPU parity |
| [ST9](ST9/README.md) | STMicroelectronics ST9 and ST9+ | `ST9:BE:16:default`, `ST9:BE:24:ST9+` | Added for IDA built-in CPU parity |

Each module's README lists its language variants, how closely it matches the reference
disassembler, what the p-code models, known gaps and how to run its tests. [STATUS.md](STATUS.md)
tracks what works and what doesn't across all modules, plus lessons learned.

## Community modules

SLEIGH modules written by others for CPUs Ghidra doesn't support, collected from GitHub and from
unmerged Ghidra pull requests ([candidates](community/CANDIDATES.md)), then tested to the same
standard as the modules above and fixed where testing found problems. Each one lives in an
`aleph-void` fork of the original repository (for an unmerged Ghidra pull request, a standalone
repository holding the PR's commits for that processor), under the original license: branch `ghidra-rare`
carries the fixes, a `GHIDRA-RARE.md` with the test results, a `CREDITS.md` naming the original
authors and every change, the test suites and release builds. This repository includes each fork
as a git submodule under `community/`, pinned to the verified commit
([community/modules.tsv](community/modules.tsv)).

| Module | Processor | Language IDs | Original authors | License |
|---|---|---|---|---|
| [65816](https://github.com/aleph-void/ghidra-65816/blob/ghidra-rare/GHIDRA-RARE.md) | WDC 65C816 (SNES) and 65802, with a LoROM/HiROM SNES ROM loader | `65816:LE:16:default`, `65802:LE:16:default` | Adrian Chan (@achan1989), Greg Kennedy (@greg-kennedy), Kay (@kaayzouee) | MIT |
| [ARCompact](https://github.com/aleph-void/ghidra-arcompact/blob/ghidra-rare/GHIDRA-RARE.md) | Synopsys ARCompact (ARC600, ARC700), LE and BE | `ARCompact:LE:32:default`, `ARCompact:BE:32:default` | Nicolas Iooss (@niooss-ledger, Ghidra PR #3006), with Jackson Donaldson (BE layout) | Apache-2.0 |
| [Alpha](https://github.com/aleph-void/ghidra-alpha/blob/ghidra-rare/GHIDRA-RARE.md) | DEC Alpha 21064/21164/21264/21364/21464 for UNIX/Linux, OpenVMS and Windows NT | 15 languages, see GHIDRA-RARE.md | Klaus Kämpf (@kkaempf), Matt Turner (@mattst88) | Apache-2.0 |
| [Blackfin](https://github.com/aleph-void/ghidra-blackfin/blob/ghidra-rare/GHIDRA-RARE.md) | Analog Devices classic Blackfin (BF53x/BF54x/BF561) | `Blackfin:LE:32:default` | @geepot | GPL-3.0-or-later |
| [LM32](https://github.com/aleph-void/ghidra-lm32/blob/ghidra-rare/GHIDRA-RARE.md) | Lattice LatticeMico32 | `lm32:BE:32:default`, `lm32:LE:32:default` | Jevin Sweval (@jevinskie), with @cyrozap | MIT |
| [M-CORE](https://github.com/aleph-void/ghidra-mcore/blob/ghidra-rare/MCORE/GHIDRA-RARE.md) | Motorola M-CORE (MMC2001, MCORE-210/340), BE and LE | `MCORE:BE:32:default`, `MCORE:LE:32:default` | Callum Thomson (@CUB3D, also Ghidra PR #9270) | Apache-2.0 |
| [MeP](https://github.com/aleph-void/VitaLoaderRedux/blob/ghidra-rare/MeP/GHIDRA-RARE.md) | Toshiba MeP-c4/c5, IVC2 coprocessor and VLIW bundles, BE and LE | `MeP-c5:{BE,LE}:32:{default,IVC2}`, `MeP-c5:LE:32:CMeP` | CreepNT (@CreepNT) | BSD-3-Clause-Clear |
| [Micronova](https://github.com/aleph-void/micronova_ghidra/blob/ghidra-rare/GHIDRA-RARE.md) | Data General microNOVA (mN601/mN602): Nova ISA with hardware stack, MUL/DIV, TRAP | `micronova:BE:16:default` | Peter Kooiman (@pkooiman) | MIT |
| [OpenRISC](https://github.com/aleph-void/ghidra-or1k-le-hack/blob/ghidra-rare/GHIDRA-RARE.md) | OpenRISC 1000 (ORBIS32, ORFPX32/64A32) | `OpenRISC:BE:32:default`, `OpenRISC:LE:32:default` | Samuel Holland (@smaeul), Jeroen Domburg (@Spritetm) | Apache-2.0 |
| [RH850](https://github.com/aleph-void/ghidra_v850/blob/ghidra-rare/GHIDRA-RARE.md) | Renesas RH850 (V850E3, G3/G4MH), V850E2M and V850E1/E/ES core; more complete than Ghidra's built-in V850 | `RH850:LE:32:default`, `RH850:LE:32:V850E2M`, `RH850:LE:32:V850E1` | Alexey Esaulenko (@esaulenka), with @pd0wm, @EgorKin, @HexRoman, @jbmokuz | MIT |
| [RL78](https://github.com/aleph-void/ghidra-rl78/blob/ghidra-rare/RL78/GHIDRA-RARE.md) | Renesas RL78 (S1/S2 and S3 cores) | `RL78:LE:16:default` (S3), `RL78:LE:16:S2` | Callum Thomson (@CUB3D) | Apache-2.0 |
| [SPC700](https://github.com/aleph-void/SPCdra/blob/ghidra-rare/GHIDRA-RARE.md) | Sony SPC700 (SNES audio), Sony and 65816-style mnemonics, with an .spc loader | `spc700:LE:16:default`, `spc700:LE:16:65816` | @qwertymodo | Apache-2.0 |
| [TMS34010/TMS34020](https://github.com/aleph-void/Ghidra_TMS34010/blob/ghidra-rare/GHIDRA-RARE.md) | TI graphics CPUs, with bit-addressed memory and a TI COFF loader | `tms34010:LE:32:default`, `tms34020:LE:32:default` | @ZPaul2Fresh8 | Apache-2.0 |

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

**Build the extension zips yourself** (clone with `--recurse-submodules`, or run
`git submodule update --init`, to include the community modules):

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
