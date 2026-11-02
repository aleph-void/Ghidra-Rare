# TC32

Telink TC32 processor module for Ghidra (SLEIGH). TC32 is the 16-bit core in Telink's TLSR82xx
and TLSR8x5x Bluetooth LE / Zigbee / mesh SoCs (the SDK's B80, B85 and B87 chip families, e.g.
TLSR8232, TLSR8251/8253/8258, TLSR8266-8269, TLSR8278). It has the Thumb-1 instruction formats with
the major opcodes reassigned and its own mnemonics (`tmov`, `tadd`, `tjl`, ...), plus interrupt
return and status-register moves.

> **Status: verified** against the Telink tc32 toolchain installed by Telink's VS Code extension
> (decode differential, gas round trip, emulator, every-entry and 20 real SDK firmware images).

Written clean-room for Ghidra-Rare (MIT). No earlier TC32 Ghidra, IDA, Binary Ninja or radare2
module and no Telink GCC/binutils source was read.

## Languages

| Language ID | Description |
|---|---|
| `TC32:LE:32:default` | TC32, little-endian. ELF (`tc32-elf`, e_machine 0x8800) is detected by the opinion |

## Sources

- Telink tc32-elf toolchain (GNU binutils 2.20 / GCC 4.5.1 port, "Telink TC32 version 2.01build"),
  as installed by Telink's VS Code extension (`telink.tlk` 1.4.3, command *tlk: Install Toolchain*, from
  `https://doc.telink-semi.cn/tools/vsc/linux/toolchains/tc32_130_Linux.tar.xz` into `~/.Telink_Tools/tc32`;
  `tc32-elf-objdump` SHA-256 8f5c7879a32b82475714d9cef8fbf7bf94d8a685b377ca3c07dc9f6193713f8f), run only as a black box: `tc32-elf-objdump` decodes every halfword and the 32-bit `tjl` pairs,
  `tc32-elf-as` round-trips them, and `tc32-elf-gcc` output shows the calling convention, the
  carry convention (unsigned compares use `tjcs`/`tjcc` the ARM way), the DWARF numbering and the
  relocations. The binaries are GPL (GNU); nothing from their sources is used.
- Telink `tc_platform_sdk` (Apache-2.0, https://github.com/telink-semi/tc_platform_sdk, commit
  19fbf0cd289e558a4c299734380746e91ebdcd3f): the startup files (`chip/B85/boot/cstartup_flash.S`
  and others) describe the image header (vector at 0, `KNLT` magic at 8, IRQ entry at 0x10), what
  `tmcsr`, `tmrss`, `tmssr` and `treti` do in the IRQ entry and exit, and the CPSR modes (IRQ 0x12,
  SVC 0x13). `boot.link` gives the memory map (flash image from 0, registers at 0x800000, SRAM from
  0x840000).
- ARM's public Thumb (ARMv4T) instruction descriptions, for the ALU, shift, carry and overflow
  rules wherever the toolchain shows TC32 matches Thumb.

## Raw images

Import an ELF when you have one: the ELF extension uses the symbol table. For a raw flash image
(`.bin`), choose `TC32:LE:32:default` with base address 0. Offsets 0 (`__reset`) and 0x10 (`__irq_entry`)
are `tj` instructions and are marked as code entry points. Default analysis only finds code reachable
from them, so code reached only through function-pointer tables is missed; enable **Aggressive
Instruction Finder** in Auto Analyze. On the SDK's `BQB_EMI_Demo.bin` (20,940 bytes, checked against
objdump of the matching ELF) default analysis found 3,881 of the ELF's 7,430 instructions and 69
functions; with Aggressive Instruction Finder 6,519 instructions and 119 functions, all identical to
objdump and no false code.

## Encoding map

| TC32 major opcode | Instructions (Thumb-1 equivalent) |
|---|---|
| 00-03 | `tands txors tshftls tshftrs tasrs taddcs tsubcs trotrs tnand tnegs tcmp tcmpn tors tmuls tbclrs tmovns` (ALU) |
| 04-07 | `tadd tcmp tmov` with high registers, `tnop`, `tjex` (BX) |
| 08-0F | `tloadr Rd, [pc, #]` |
| 10-1F | register-offset `tstorer/h/b`, `tloadr/h/b/sb/sh` |
| 20-2F, 40-4F, 50-5F | imm5-offset halfword, byte and word loads and stores |
| 30-3F | sp-relative `tstorer`/`tloadr` |
| 60-6F | `tadd/tsub sp`, `tpush`, `tpop`, `treti`, `tmcsr tmrcs tmssr tmrss` |
| 70-7F | `tadd Rd, pc/sp, #` |
| 80-87 | `tj` |
| 90-97 + 98-9F | `tjl` (BL pair) |
| A0-BF | `tmovs tcmp tadds tsubs` with an 8-bit immediate |
| C0-CD, CF | `tj<cond>`, `tserv` (SWI) |
| D0-DF | `tstorem`/`tloadm` |
| E0-EF | `tasrs` imm5, 3-operand `tadds`/`tsubs` |
| F0-FF | `tshftls`/`tshftrs` imm5 (`tmovs Rd, Rs` for a 0 shift) |

## Results

Bar: [docs/VERIFICATION.md](../docs/VERIFICATION.md).

| Area | State |
|---|---|
| Decode | tc32-elf-objdump differential, 0 unexplained: all 65,536 halfwords (56,752 exact, 8,784 both invalid); 151,552 `tjl` pair slots (8,313 exact, 122,238 both invalid, 21,001 explained `tjlex`); 50,000 random words (41,910 exact, 6,417 both invalid, 185 explained). gas round trip: the module's text for all 56,752 valid halfwords assembled with tc32-elf-as gives back 55,965 identical halfwords; the other 768 are explained (below) and 19 empty register lists have no gas syntax. 2,177/2,177 constructors reached |
| Semantics | Full p-code: ALU with ARMv4T N/Z/C/V rules (register shifts by the low byte, shifts of 32 and more), all load/store forms, push/pop/ldm/stm lists, branches, `tjl` calls, `tjex`/`tmov pc`/`tpop {pc}` returns, CPSR/SPSR moves and `treti`. Emulator 56/56 hand-computed cases; broken expectation detected |
| Real code | 20 Telink `tc_platform_sdk` B85 driver demos (Apache-2.0, pinned commit, built with tc32-elf-gcc by `test/real-build.sh`), imported as ELF with auto-detection: 92,476 instructions, all identical to objdump at the same addresses, 0 objdump-only or Ghidra-only code addresses, 2,754 functions decompiled with 0 failures, 0 timeouts, 0 bad-instruction data |
| Doesn't work | `tserv` is a pcodeop (software interrupt; no vector documented). Mode-banked sp/lr (IRQ vs SVC) are one register set. `tjl` to a `tjex rN` call-via stub shows as an unrecovered jump table in the decompiler (GCC's `_call_via_rN`; a decompiler limit shared with ARM Thumb) |
| Unverified | Hardware behaviour of encodings the compiler never emits: `tjex` with bit 7 set (objdump prints `tjex`; ARMv5 would call), empty register lists, `treti` without `pc`, whether `tjl` sets lr bit 0 |

Explained decode differences:

- **gas round trip**: gas writes the flag-setting forms without the `s` and the two-operand ALU forms as
  `Rd, Rd, Rm`; the round trip converts the module's (objdump-style) text first. 320 halfwords come back
  as another encoding the module decodes to the same instruction (for example `tadds r0,r0,#1` as the
  8-bit-immediate form, `tjex` with its reserved low bits cleared). 128 high-register-format `tadd`/`tcmp`/
  `tmov` with two low registers come back as the low-register encodings, and 64 `tmovs Rd,Rm` (shift by 0,
  C kept) as `tadds Rd,Rm,#0` (C and V cleared): the two syntaxes are ambiguous for these. 256 `tserv`
  are a **toolchain inconsistency**: gas encodes `tserv n` as 0xDFnn, which objdump (and the module)
  decode as `tloadm`, while objdump decodes 0xCFnn as `tserv`. The compiler never emits `tserv`; the module
  follows objdump.
- **ELF import**: tc32-elf marks function symbols with bit 0 set like ARM Thumb and emits `$t`/`$d`
  mapping symbols and absolute linker constants. `TC32_ElfExtension` moves function symbols to the even
  address, types `$d` ranges as data and drops absolute non-function symbols; without it 60 % of the SDK
  functions decompiled from the middle of an instruction and the image header was disassembled.

- **`tjlex`**: objdump decodes a `tjl` prefix followed by a 0xC000-0xCFFF or 0xE000-0xEFFF halfword
  as `tjlex` (the ARMv5 BLX-immediate pair). TC32 has no second instruction state, gas does not
  accept `tjlex`, and the compiler never emits it, so the module leaves it undecoded.

## Tests

```sh
export GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC
TC32/test/build-jar.sh                      # lib/TC32.jar (ELF relocation handler)
TC32_OBJDUMP=~/.Telink_Tools/tc32/bin/tc32-elf-objdump TC32/test/run-tests.sh [--real <workdir>]
# --real clones telink-semi/tc_platform_sdk at the pinned commit, builds the B85 demos (test/real-build.sh)
# and checks every ELF (test/real-check.sh); test/gas_roundtrip.py is the assembler round trip
```
