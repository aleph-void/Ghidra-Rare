# TI TMS320C2x and TMS320C5x for Ghidra

An independent SLEIGH module for the Texas Instruments TMS320C2x (TMS32020, C25, C26) and
TMS320C5x (C50, C51, C52, C53, C56, C57) fixed-point DSPs, targeting Ghidra 12.1.4. Encodings and
semantics were written from TI's *TMS320C2x User's Guide* (SPRU014C, 1993) and *TMS320C5x User's
Guide* (SPRU056D, 1998); TI COFF details come from the *TMS320C1x/C2x/C2xx/C5x Assembly Language
Tools User's Guide* (SPRU018D). MAME `unidasm -arch tms320c2x` / `tms320c5x` was used as a
black-box decode reference. This is a new implementation for parity with IDA's support for these
DSPs; it does not derive from an IDA module.

## Languages and memory model

| Language | Word order | Use |
|---|---|---|
| `TMS320C2x:BE:16:default` | high byte first | C2x ROM images, MAME `tms320c2x` |
| `TMS320C2x:LE:16:default` | low byte first | C2x TI COFF / little-endian dumps |
| `TMS320C5x:BE:16:default` | high byte first | C5x EPROM-pair images |
| `TMS320C5x:LE:16:default` | low byte first | TI COFF (target ID 0092h), MAME `tms320c5x` |

The C5x re-encodes the C2x instruction set, so the two families have separate opcode tables.
`tools/gen_tms320.py` generates both from one source, sharing the addressing modes, mode tracking,
repeat handling and semantics helpers.

Program (`prog`), data (`data`) and I/O (`io`) are separate word-addressed 64K spaces. The C5x
memory-mapped CPU registers (IMR, PMST, RPTC, BRCR, PASR, PAER, TREG0-2, DBMR, AR0-AR7, INDX,
ARCR, CBSR/CBER/CBCR, BMAR) are defined in data page 0, so `SAMM`, `LMMR` or a plain store to
data address 12h writes AR2. On the C2x the auxiliary registers and TREG are registers. The
8-level hardware stack is modelled as STK0-STK7 (STK0 = top).

SLEIGH context tracks the auxiliary register pointer (ARP), data page (DP), SXM, OVM and PM:
`LARP`, `MAR`, any indirect `,ARn`, `LDPK`/`LDP #k`, `SSXM`/`SETC SXM` and the like set them for
the following instructions, and `LST` makes them unknown. Known values give direct register
accesses, absolute data references and straight-line p-code; unknown values fall back to p-code
that reads ARP, DP, SXM, OVM or PM at run time. SXM=1, OVM=0 and PM=0 (their reset values) are
assumed at the start of the image. On the C5x the context fields `ndx` and `trm` select the
PMST.NDX/TRM behaviour (reset value 0: indexing and CMPR use AR0, loading TREG0 also loads TREG1 and
TREG2), and `circ=1` enables the circular-buffer check on every AR modification (off by default,
because it puts a CBCR test into every indirect access).

Repeats are modelled in p-code: `RPT`/`RPTK`/`RPTZ` loop the next instruction RPTC+1 times, and
instructions that step a prefetch counter in a repeat (`BLKD`, `BLKP`, `BLDD`, `BLPD`, `MAC`,
`MACD`, `TBLR`, `TBLW`, `IN`, `OUT`, `LMMR`, `SMMR`) advance their long address per iteration.
`RPTB` marks the block's last instruction (also when the block ends in the second word of a
two-word instruction) with a loop back to the block start while BRCR counts down. C5x delayed
branches, calls and returns have two-word delay slots; `XC` skips one or two words.
`TMS320VectorAnalyzer` disassembles interrupt-vector slots that hold a branch and names the
handlers. TI COFF files load through Ghidra's COFF loader (`tms320.opinion`), and
`TMS320_CoffRelocationHandler` applies R_RELBYTE, R_RELWORD, R_PARTLS7, R_PARTMS9 and R_REL
relocations in relocatable objects.

## Verification

- **Decode vs MAME**, 98,304 records per family (every 16-bit first word with a random second word,
  plus 32,768 random records): 0 unexplained differences. C2x: 92,668 identical, 5,636 explained;
  C5x: 79,940 identical, 18,364 explained. The explained classes are listed in `test/compare.py`:
  reserved indirect mode ARU=011 (MAME prints `??`, the module rejects it), MAME's CFxx (MPYU)
  shown as MPYS, a spurious ADDC shift operand, ADRK/SBRK constants >= 80h shown as indirect,
  C5x `MPY #k` (C000h-DFFFh) not decoded by MAME, MAME ignoring bit 7 of branch/call words,
  NORM/MACD lengths, CMPR/SPM don't-care bits. The other byte-order language decodes the
  byte-swapped corpus identically.
- **Every-entry**: every constructor reached under mode/context combinations: 448/448 (C2x) and
  1,655/1,655 (C5x).
- **Round trip**: Ghidra's text re-assembled by an independent assembler gives the same words:
  C5x with c5xasm (MIT, conformance-checked against TI's assembler) 91,684 records, 0 unexplained
  (21,912 explained: ignored next-AR bits, equivalent condition encodings, one c5xasm encoding
  difference for AND/OR/XOR #lk,16 where SPRU056D gives BE81h-BE83h); C2x with the Macroassembler
  AS (320C25/C26) 84,298 records, 0 unexplained.
- **Emulator**: 41 hand-computed p-code cases per language (four languages), all passing, plus one
  deliberately broken expectation per family that is detected. Covers accumulator arithmetic,
  carry/overflow and saturation, shifts, product shifter, indirect and bit-reversed addressing,
  RPT/RPTB/XC, delayed branch and call, MAC/MACD/BLKD/BLDD block moves, status registers,
  SST/LST, circular buffers, and unknown (run-time) ARP/DP/SXM/PM/OVM.
- **Real programs** (MIT sources, pinned): a TMS320C25 program and register-dump routine
  (c25_debugger) and nine TI-assembled C5x example images (c5xtools): 0 error bookmarks, every
  function decompiles, and the instruction listing is identical to MAME on all instructions except
  the explained classes above. A c5xlnk-linked TI COFF executable loads as TMS320C5x with no
  errors, and a relocatable COFF object with R_PARTMS9, R_PARTLS7 and R_RELWORD relocations
  against .bss, .data, .text and an external symbol relocates to the expected values.
- `.sla` files are 49-105 KB; all four specs compile on Ghidra 12.1.3, 12.1.4 and 12.2.
- Not tested: no TI-licensed firmware was used (none is needed), and there is no hardware
  check of cycle behaviour; `unidasm` is wrong or silent on the classes above, which were
  confirmed against the manuals.

## Known gaps

- Peripherals, interrupts, wait states, HOLD, the C2x/C5x pipeline (delayed effects of
  memory-mapped register writes, XC sampling conditions a cycle early) and the CNF/OVLY on-chip
  RAM remapping are not modelled. `IDLE`/`IDLE2`, the RETI/RETE shadow-register restore and the
  undocumented C5x emulation instructions are p-code operations; BIO and XF are plain registers.
- ARP, DP and the mode bits are assumed preserved across calls, as the TI C runtime does; a
  callee that changes them leaves the context of the caller's following instructions stale.
  Set the context fields over a range to correct it.
- With NDX=0 the C5x writes AR0 into INDX and ARCR. The module models this by using AR0 for
  indexing and CMPR; a direct write to INDX or ARCR while NDX=0 is not seen.
- `RPTB` loop-back is attached to the end address when the `RPTB` is disassembled; a block end
  that analysis reaches only through another path first gets no loop.
- The C5x vector analyzer, `TRAP`, `NMI` and `INTR` assume IPTR=0 for analysis (the p-code reads
  IPTR from PMST). The TMS32020 has no separate language; the C25 decoder accepts the C25-only
  instructions on it.
- Ghidra's COFF loader puts every section in program memory: TI's memory page (data sections)
  is ignored, so data sections of a COFF file must be moved to the `data` space by hand.
  `R_PARTMS9` assumes no carry out of the low seven address bits beyond the symbol's own.
- The decompiler prints "Globals starting with '_' overlap smaller symbols" on word-addressed
  data; the output is otherwise unaffected.

## Build and test

```sh
export GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC
python3 TMS320C2x/tools/gen_tms320.py TMS320C2x/data/languages
"$GHIDRA_INSTALL_DIR/support/sleigh" -a TMS320C2x/data/languages
(cd TMS320C2x && gradle buildExtension)
ASL_DIR=/path/to/asl/bin TMS320C2x/test/run-tests.sh "$HOME/.cache/ghidra-rare-scratch/tms320-tests"
```

`test/run-tests.sh` runs the decode differential, every-entry, round-trip, emulator and
real-program tests. It needs MAME's `unidasm`, a C compiler and make (for c5xasm), and the
Macroassembler AS for the C2x round trip. `test/fetch-inputs.sh` fetches the inputs by pinned
URL and SHA-256: [c0demaster8051/tms320c25_debugger](https://github.com/c0demaster8051/tms320c25_debugger)
(MIT; a TMS320C25 program and register-dump routine) and
[wgrzegorz/c5xtools](https://github.com/wgrzegorz/c5xtools) (MIT; example DSP programs assembled
by TI's tools, an ISA conformance corpus, and the c5xasm/c5xlnk assembler and linker). Nothing
downloaded is committed. c5xtools' instruction table was also consulted, as MIT-licensed
reference data, for the encodings of the undocumented C5x emulation instructions.

The module's code is MIT-licensed (repository LICENSE). No firmware, TI tool output beyond the
fetched MIT examples, or reference-disassembler source is included.
