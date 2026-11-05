# PXF

Processor module for the parallel forwarding processor (PXF, "Toaster") on the Cisco NSE-100,
the network services engine of the Cisco 7300/7304. Ghidra (SLEIGH). It covers the PXF columns'
microcode only. The board's MIPS RM7000 control processor is plain MIPS, which Ghidra already
supports.

> **Status: full decode; flow only.** Every M-slot, S-slot and micro-op form decodes. P-code
> models control flow only (see [Semantics](#semantics)).

## Languages

| Language ID | Description |
|---|---|
| `PXF:BE:16:NSE-100` | NSE-100 PXF: 64-bit big-endian packets, 16-bit packet addresses (code space word size 8), 32-bit data space |

## Loading microcode

Each column's instruction block is loaded at packet address 0x800. Import a column image as
**Raw Binary**, language `PXF:BE:16:NSE-100`, base address **0x800**, then run the
`PxfColumnSetup.java` script (category PXF). It applies an optional symbol file (one
`<hex packet address> <name>` per line), creates functions at the symbols and disassembles every
packet. Instruction memory holds only instructions, so a linear sweep is safe.

Ghidra shows packet addresses (0x800, 0x801, ...). Internally `Address.getOffset()` counts bytes,
8 per packet, so scripts must use `Address.add(8)` per packet and `getAddressableWordOffset()`
for the packet address.

## Encoding

A packet is two big-endian 32-bit words, H (first) and L. The M slot, S slot and micro-ops share
fields. Several fields are reused across slots, for example:

| Bits | Use |
|---|---|
| H[31:30] | M format: 3 immediate + memory, 1 register + memory, 2 indirect, 0 by class H[25:23] (immediate ALU, indirect ALU, register ALU, compare-and-branch, X unit) |
| H[29:27] + L[7:6] | M operation (`mor` … `mdread`); L[7:6] extends it only when L[9:8] = 0 |
| L[31:30] | S format: immediate ALU, register ALU, register branch / control, relative branch / special registers |
| L[9:8], L[7:6] | micro-op 1: `pfa n`, `eb n`, `tr rs0/rs2/rdm/rds` |
| L[5:3], L[2:0] | micro-ops 2 and 3: `invslog cntrst cntdec cdsbt`, `u2_op1`…`u2_op7` |
| L[31:27] = 0x19 | the L word carries a 16-bit extension of the M immediate or displacement instead of an S instruction |
| H[31:24] = 2 | the H word carries a 24-bit extension of the S immediate instead of an M instruction |

Undefined encodings (M classes 6 and 7, X opcodes 6–8 and 13–15, M operations 20–23) do not
decode.

## Display

Slots are separated by ` ; `: M instruction, S instruction, micro-ops. The first non-empty slot
gives the Ghidra mnemonic, and a packet without M or S instruction starts with `noop`. For
example `mor.wn r0, 0x38, r0 ; spr iar, 0x47 ; tr rdm`. Code addresses are padded (`0x083f`).
The extended M displacements (L[31:27] = 0x19 with L[5:3] = 2 or 3) print in hex, because SLEIGH
can print computed values only in hex.

## Semantics

Only control flow has p-code, so that Ghidra can follow code, find functions and build call
graphs, and so the decompiler shows the control structure:

- `bcf`/`bct` (branch if condition false/true), `balcf`/`balct` (calls) on the 32 condition flags,
  relative or through a register. Register branches through `lr` are returns.
- `bne`/`beq`/`balne`/`baleq` compare two registers.
- Data-path operations, memory operations, the X unit, `mbf`/`mbt` (multi-way branch), `pdone`,
  `wrpct`/`rdpct` and the micro-ops have no p-code.

`cr_zero` reads as 0, so `bcf cr_zero`/`balcf cr_zero` are unconditional. `cdsbt` is read as
"cancel delay slot, branch taken".

**Delay slots are not modelled.** The hardware executes the packet after a branch, unless `cdsbt`
cancels it on a taken branch. Microcode often places a branch in a delay slot, which Ghidra
cannot represent, so branches take effect immediately. Linear disassembly still shows every
packet.

`sp_none` is a pseudo-register that no instruction uses. It exists because the decompiler needs
some stack pointer. No PXF stack or calling convention is defined.

## Generated files

`data/languages/pxf_tables.sinc` and `pxf_branches.sinc` are generated:

```
python3 PXF/tools/gen_tables.py > PXF/data/languages/pxf_tables.sinc
python3 PXF/tools/gen_tables.py branches > PXF/data/languages/pxf_branches.sinc
```

## Known issues

- The decompiler process dies on some functions whose control flow is only branches: loops that
  jump back to packets just before a function's entry, and compare-and-branches into other code.
  No decode or p-code error has been found.

## Not covered

- Execution semantics of every data-path, memory, X-unit and micro-op instruction.
- Delay slots, the multi-way branch `mbf`/`mbt` targets, the `pdone` packet-done/wait control.
- Other Toaster generations (NSE-150, the 7200 NPE-G1/G2 PXF, 10000 series).
