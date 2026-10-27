# Ghidra-Rare

[![Sponsor Aleph Void](https://img.shields.io/badge/Sponsor-Aleph%20Void-EA4AAA?logo=githubsponsors&logoColor=white)](https://github.com/sponsors/aleph-void)

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
| [XA](XA/README.md) | Philips/NXP XA (51XA), native 24-bit and page-0 16-bit modes | `XA:LE:24:default`, `XA:LE:24:page0` | Added for IDA built-in CPU parity |
| [TMS320C2x](TMS320C2x/README.md) | TI TMS320C2x (C25/C26) and TMS320C5x DSP, big and little endian, with TI COFF support | `TMS320C2x:{BE,LE}:16:default`, `TMS320C5x:{BE,LE}:16:default` | Added for IDA built-in CPU parity |
| [RX](RX/README.md) | Renesas RX, RXv1, RXv2 and RXv3 (FPU, DSP and double-precision FPU) | `RX:LE:32:RXv1`, `RXv2`, `RXv3` (each with `default` and `d64` compiler specs) | Added for IDA built-in CPU parity |
| [i860](i860/README.md) | Intel i860 XR and XP, dual-instruction mode, delay slots, FP pipeline and graphics instructions | `i860:LE:32:XR`, `i860:LE:32:XP` | Added for IDA built-in CPU parity |
| [ADSP218x](ADSP218x/README.md) | Analog Devices ADSP-218x (ADSP-2181 family), with a VisualDSP++ DXE loader | `ADSP218x:BE:16:default` | Added for IDA built-in CPU parity |
| [DSP56000](DSP56000/README.md) | Motorola DSP56000/56001/56002 and DSP56156 (DSP561xx), with a Motorola LOD loader | `DSP56000:BE:16:default`, `DSP56000:BE:16:DSP56156` | Added for IDA built-in CPU parity |
| [IA64](IA64/README.md) | Intel IA-64 (Itanium): bundles, predication, register stack, rotating registers, speculation | `IA64:LE:64:default` (Linux/Windows/VMS), `IA64:BE:64:default` (HP-UX LP64), `IA64:BE:32:default` (HP-UX ILP32) | Added for IDA built-in CPU parity |

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
| [ARC32](https://github.com/aleph-void/ghidra-arc32/blob/ghidra-rare/GHIDRA-RARE.md) | ARCtangent-A4/A5 (32-bit legacy ARC), LE and BE, with zero-overhead loop and indirect-call analyzers | `ARC32:LE:32:default`, `ARC32:BE:32:default` | @cyrozap (Ghidra PR #3233) | Apache-2.0 |
| [Alpha](https://github.com/aleph-void/ghidra-alpha/blob/ghidra-rare/GHIDRA-RARE.md) | DEC Alpha 21064/21164/21264/21364/21464 for UNIX/Linux, OpenVMS and Windows NT | 15 languages, see GHIDRA-RARE.md | Klaus Kämpf (@kkaempf), Matt Turner (@mattst88) | Apache-2.0 |
| [Blackfin](https://github.com/aleph-void/ghidra-blackfin/blob/ghidra-rare/GHIDRA-RARE.md) | Analog Devices classic Blackfin (BF53x/BF54x/BF561) | `Blackfin:LE:32:default` | @geepot | GPL-3.0-or-later |
| [C6000](https://github.com/aleph-void/ghidra-c6000/blob/ghidra-rare/GHIDRA-RARE.md) | TI C64x/C67x/C674x DSP, little and big endian | `C6000:{LE,BE}:32:default` plus analysis variants | @geepot, @roblg | Apache-2.0 |
| [EmotionEngine](https://github.com/aleph-void/ghidra-emotionengine-reloaded/blob/ghidra-rare/GHIDRA-RARE.md) | Sony PS2 Emotion Engine (MIPS R5900): MMI and VU0 macro mode in p-code, PS2 ELF loading and hardware registers | `r5900:LE:32:default` | @chaoticgd, @beardypig and contributors | Apache-2.0 |
| [F8](https://github.com/aleph-void/ghidra-f8/blob/ghidra-rare/GHIDRA-RARE.md) | Fairchild F8: F3850, MK3870/F3870 and MK3873 single-chip parts | `F8:BE:16:default`, `F8:BE:16:F3850`, `F8:BE:16:MK3870`, `F8:BE:16:F3870`, `F8:BE:16:MK3873` | Sami Saari (@polartape, Ghidra PR #9087) | Apache-2.0 |
| [FR60](https://github.com/aleph-void/ghidra-fr60/blob/ghidra-rare/GHIDRA-RARE.md) | Fujitsu FR60 and FR81, with a DVRP firmware loader | `fr60:BE:16:default`, `fr81:BE:16:default` | Darren Thompson (@desrdev) | Apache-2.0 |
| [H8](https://github.com/aleph-void/ghidra-h8-300/blob/ghidra-rare/GHIDRA-RARE.md) | Hitachi/Renesas H8/300, H8/300L, H8/300H, H8S and H8SX (normal, middle, advanced, maximum modes) | 10 languages (`h8_300`, `h8_300l`, `h8_300h`, `h8s`, `h8sx` with their modes), see GHIDRA-RARE.md | shizmob (@shizmob); the instruction set was regenerated here | WTFPL |
| [SH-3 / SH-2E](https://github.com/aleph-void/ghidra-sh/blob/ghidra-rare/GHIDRA-RARE.md) | Hitachi SH-3, SH-3E and SH-2E (Ghidra already has SH-1, SH-2, SH-2A and SH-4) | `sh3:{BE,LE}:32:default`, `sh3e:{BE,LE}:32:default`, `sh2e:BE:32:default` | @will07c5 | MIT |
| [HC11](https://github.com/aleph-void/GhidraMC6800/blob/ghidra-rare/GHIDRA-RARE.md) | Motorola MC6800, MC6801, Hitachi HD6301 and MC68HC11, with an EM_68HC11 ELF relocation handler | `MC6800:BE:16:default`, `MC6801:BE:16:default`, `HD6301:BE:16:default`, `MC68HC11:BE:16:default` | Sigurd Asgeirsson (@sigurasg), Antonio Vazquez Blanco (@antoniovazquezblanco) | Apache-2.0 |
| [Intel 8008](https://github.com/aleph-void/ghidra-8008/blob/ghidra-rare/GHIDRA-RARE.md) | Intel 8008 (i8008) | `8008:LE:16:default` | Spiro Sekulovski (@spirosekulovski, Ghidra PR #8007) | Apache-2.0 |
| [i960](https://github.com/aleph-void/ghidra-i960/blob/ghidra-rare/GHIDRA-RARE.md) | Intel i960 (80960 KA/KB/MC/CA/Jx/Hx), with ELF relocations and an Initial Boot Record analyzer | `i960:LE:32:default`, `i960:LEBE:32:lebe` | @mumbel (Ghidra PR #1452), @cglmrfreeman | Apache-2.0 |
| [LM32](https://github.com/aleph-void/ghidra-lm32/blob/ghidra-rare/GHIDRA-RARE.md) | Lattice LatticeMico32 | `lm32:BE:32:default`, `lm32:LE:32:default` | Jevin Sweval (@jevinskie), with @cyrozap | MIT |
| [MN10300](https://github.com/aleph-void/ghidra-mn103-extension/blob/ghidra-rare/GHIDRA-RARE.md) | Panasonic/Matsushita MN10300 (MN1030), AM33 and AM33-2, with ELF relocations and PLT thunks | `mn10300:LE:32:default` (AM33-2), `mn10300:LE:32:am33`, `mn10300:LE:32:mn10300` | Michael Brandi Andersen (@michaelbrandi); the instruction set was rewritten here | Apache-2.0 |
| [MN10200](https://github.com/aleph-void/ghidra-mn102-lang/blob/ghidra-rare/GHIDRA-RARE.md) | Panasonic/Matsushita MN10200 | `MN102:BE:24:default` (little-endian in fact; the ID is kept for compatibility) | Pokechu22 (@Pokechu22) | Apache-2.0 |
| [M-CORE](https://github.com/aleph-void/ghidra-mcore/blob/ghidra-rare/MCORE/GHIDRA-RARE.md) | Motorola M-CORE (MMC2001, MCORE-210/340), BE and LE | `MCORE:BE:32:default`, `MCORE:LE:32:default` | Callum Thomson (@CUB3D, also Ghidra PR #9270) | Apache-2.0 |
| [M740](https://github.com/aleph-void/ghidra-m740/blob/ghidra-rare/GHIDRA-RARE.md) | Mitsubishi MELPS 740 (M5074x and others): FST/SLW and WIT groups, T flag, MUL/DIV | `MELPS740:LE:16:default`, `MELPS740:LE:16:wit`, `MELPS740:LE:16:muldiv` | Philip Pemberton (@philpem, Ghidra PR #5012) | Apache-2.0 |
| [MC146805E2](https://github.com/aleph-void/ghidra-mc146805e2/blob/ghidra-rare/GHIDRA-RARE.md) | Motorola MC146805E2 (CMOS 6805) | `6805:BE:16:MC146805E2` | Gareth Edwards (@gareth8118, Ghidra PR #856) | Apache-2.0 |
| [MeP](https://github.com/aleph-void/VitaLoaderRedux/blob/ghidra-rare/MeP/GHIDRA-RARE.md) | Toshiba MeP-c4/c5, IVC2 coprocessor and VLIW bundles, BE and LE | `MeP-c5:{BE,LE}:32:{default,IVC2}`, `MeP-c5:LE:32:CMeP` | CreepNT (@CreepNT) | BSD-3-Clause-Clear |
| [Micronova](https://github.com/aleph-void/micronova_ghidra/blob/ghidra-rare/GHIDRA-RARE.md) | Data General microNOVA (mN601/mN602): Nova ISA with hardware stack, MUL/DIV, TRAP | `micronova:BE:16:default` | Peter Kooiman (@pkooiman) | MIT |
| [WE32100](https://github.com/aleph-void/ghidra-we32100/blob/ghidra-rare/GHIDRA-RARE.md) | AT&T/Western Electric WE32100 (3B2) | `WE32100:BE:32:default` | fletto2 (@fletto2) | MIT |
| [uPD78xx](https://github.com/aleph-void/ghidra-upd78xx/blob/ghidra-rare/GHIDRA-RARE.md) | NEC uPD78xx (78C10 CMOS family) with L0/L1 skip handling and a CALT table analyzer | `upd78:LE:16:default` | Anthony (@ajxs, Ghidra PR #7930), Vesa-Pekka Palmu (@depili, PR #1509) | Apache-2.0 |
| [NS32016](https://github.com/aleph-void/ghidra-NS32016/blob/ghidra-rare/GHIDRA-RARE.md) | National Semiconductor NS32016 with NS32081 FPU and NS32082 MMU, and the NS32532; NetBSD/pc532 a.out loader | `NS32016:LE:32:default`, `NS32016:LE:32:NS32532` | Ray Bellis (@raybellis); the instruction set was regenerated here | Apache-2.0 |
| [OpenRISC](https://github.com/aleph-void/ghidra-or1k-le-hack/blob/ghidra-rare/GHIDRA-RARE.md) | OpenRISC 1000 (ORBIS32, ORFPX32/64A32) | `OpenRISC:BE:32:default`, `OpenRISC:LE:32:default` | Samuel Holland (@smaeul), Jeroen Domburg (@Spritetm) | Apache-2.0 |
| [RH850](https://github.com/aleph-void/ghidra_v850/blob/ghidra-rare/GHIDRA-RARE.md) | Renesas RH850 (V850E3, G3/G4MH), V850E2M and V850E1/E/ES core; more complete than Ghidra's built-in V850 | `RH850:LE:32:default`, `RH850:LE:32:V850E2M`, `RH850:LE:32:V850E1` | Alexey Esaulenko (@esaulenka), with @pd0wm, @EgorKin, @HexRoman, @jbmokuz | MIT |
| [RL78](https://github.com/aleph-void/ghidra-rl78/blob/ghidra-rare/RL78/GHIDRA-RARE.md) | Renesas RL78 (S1/S2 and S3 cores) | `RL78:LE:16:default` (S3), `RL78:LE:16:S2` | Callum Thomson (@CUB3D) | Apache-2.0 |
| [s390x](https://github.com/aleph-void/ghidra-s390x/blob/ghidra-rare/GHIDRA-RARE.md) | IBM z/Architecture (s390x), g5 through z17: general, decimal, BFP/HFP/DFP, vector and vector packed-decimal instructions, XPLINK and z/OS loaders | `s390x:BE:64:default` (compiler specs `default`, `zos`, `zos_xplink`) | Paulo Pereira (@paulovitorjp) | Apache-2.0 |
| [SM83](https://github.com/aleph-void/ghidra-sm83/blob/ghidra-rare/GHIDRA-RARE.md) | Sharp SM83 (Game Boy CPU), with a ROM loader, bank analyzer and SDCC/GBDK calling conventions | `SM83:LE:16:default` | Joonas Javanainen (@Gekkio), Michal Andrzejczak (@minorum), @antoniovazquezblanco and contributors | Apache-2.0 |
| [SPC700](https://github.com/aleph-void/SPCdra/blob/ghidra-rare/GHIDRA-RARE.md) | Sony SPC700 (SNES audio), Sony and 65816-style mnemonics, with an .spc loader | `spc700:LE:16:default`, `spc700:LE:16:65816` | @qwertymodo | Apache-2.0 |
| [ST7](https://github.com/aleph-void/ghidra-st7/blob/ghidra-rare/GHIDRA-RARE.md) | STMicroelectronics ST7 and ST72 (two-bit interrupt priority), with vector-table and stack-dispatch analyzers | `ST7:BE:16:default`, `ST72:BE:16:default` | Alessandro Gatti (@agatti, Ghidra PR #3631) | Apache-2.0 |
| [TMS34010/TMS34020](https://github.com/aleph-void/Ghidra_TMS34010/blob/ghidra-rare/GHIDRA-RARE.md) | TI graphics CPUs, with bit-addressed memory and a TI COFF loader | `tms34010:LE:32:default`, `tms34020:LE:32:default` | @ZPaul2Fresh8 | Apache-2.0 |
| [Cell SPU](https://github.com/aleph-void/GhidraSPU/blob/ghidra-rare/GHIDRA-RARE.md) | Cell Broadband Engine SPU (SPU ISA v1.2), 128-bit SIMD registers, ELF relocations and switch-table analyzer | `SPU:BE:32:default` (renamed from `SPU:BE:128:default`; old programs upgrade automatically) | Adrian (@aerosoul94), @balika011, Eladash (@elad335), Nick Renieris (@VelocityRa) | Apache-2.0 |
| [TILE-Gx](https://github.com/aleph-void/ghidra-tilegx/blob/ghidra-rare/GHIDRA-RARE.md) | Tilera TILE-Gx, little/big-endian data and 32/64-bit ABI | `TILE:{LE,BE}:{32,64}:default` | Idan Freiberg (@speidy, Ghidra PR #9426) | Apache-2.0 |
| [VAX](https://github.com/aleph-void/ghidra-vax/blob/ghidra-rare/GHIDRA-RARE.md) | DEC VAX: all 306 opcodes with exact VAX floating point, packed decimal and privileged instructions; ELF relocations and an entry-mask analyzer | `VAX:LE:32:default` | Klaus Kämpf (@kkaempf) | Apache-2.0 |

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

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add a module (including
`tools/new-module-skeleton`) and the clean-room rules, and [docs/VERIFICATION.md](docs/VERIFICATION.md)
for the bar a module has to meet before it is called done.

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
