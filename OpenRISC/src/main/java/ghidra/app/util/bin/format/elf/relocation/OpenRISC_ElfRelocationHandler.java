/* SPDX-License-Identifier: Apache-2.0 */
package ghidra.app.util.bin.format.elf.relocation;

import ghidra.app.util.bin.format.elf.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Program;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.reloc.Relocation.Status;
import ghidra.program.model.reloc.RelocationResult;

/**
 * ELF relocation handler for OpenRISC 1000 (EM_OPENRISC = 92, and the old 0x8472).
 * <p>
 * Semantics follow binutils bfd/elf32-or1k.c (or1k_elf_howto_table) and the glibc dynamic
 * linker (sysdeps/or1k/dl-machine.h):
 * <ul>
 * <li>Dynamic: RELATIVE = B + A; 32, GLOB_DAT and JMP_SLOT = S + A (one word).</li>
 * <li>Instruction fields: LO_16_IN_INSN / HI_16_IN_INSN / AHI16 patch the 16-bit immediate,
 * SLO16 / SLO13 the split store immediate (bits 25..21 and 10..0), INSN_REL_26 / PLT26 /
 * PLTA26 the 26-bit word displacement, PCREL_PG21 the 21-bit page of l.adrp and LO13 the low
 * 13 bits of a page offset.</li>
 * </ul>
 * GOT- and TLS-model relocations in relocatable objects need a linker-built GOT and are
 * reported, not applied; so are the dynamic TLS relocations, whose values exist only at run
 * time.
 */
public class OpenRISC_ElfRelocationHandler
		extends AbstractElfRelocationHandler<OpenRISC_ElfRelocationType, ElfRelocationContext<?>> {

	public static final int EM_OPENRISC = 92;
	public static final int EM_OR1K_OLD = 0x8472;

	public OpenRISC_ElfRelocationHandler() {
		super(OpenRISC_ElfRelocationType.class);
	}

	@Override
	public boolean canRelocate(ElfHeader elf) {
		return elf.e_machine() == EM_OPENRISC || elf.e_machine() == EM_OR1K_OLD;
	}

	@Override
	public int getRelrRelocationType() {
		return OpenRISC_ElfRelocationType.R_OR1K_RELATIVE.typeId;
	}

	private static void putBits(Memory mem, Address a, int mask, long value)
			throws MemoryAccessException {
		int insn = mem.getInt(a);
		mem.setInt(a, (insn & ~mask) | ((int) value & mask));
	}

	/** Split 16-bit store immediate: value bits 15..11 go to insn 25..21, bits 10..0 stay. */
	private static void putSplit(Memory mem, Address a, long value) throws MemoryAccessException {
		long v = ((value & 0xf800) << 10) | (value & 0x7ff);
		putBits(mem, a, 0x03e007ff, v);
	}

	@Override
	protected RelocationResult relocate(ElfRelocationContext<?> ctx, ElfRelocation relocation,
			OpenRISC_ElfRelocationType type, Address relocationAddress, ElfSymbol elfSymbol,
			Address symbolAddr, long symbolValue, String symbolName)
			throws MemoryAccessException {

		Program program = ctx.getProgram();
		Memory mem = program.getMemory();
		long A = relocation.getAddend();
		long P = relocationAddress.getOffset();
		int symIndex = relocation.getSymbolIndex();

		switch (type) {
			case R_OR1K_NONE:
			case R_OR1K_GNU_VTENTRY:
			case R_OR1K_GNU_VTINHERIT:
				return RelocationResult.SKIPPED;

			case R_OR1K_RELATIVE:
				mem.setInt(relocationAddress, (int) (ctx.getImageBaseWordAdjustmentOffset() + A));
				return new RelocationResult(Status.APPLIED, 4);

			case R_OR1K_TLS_DTPMOD:
			case R_OR1K_TLS_DTPOFF:
			case R_OR1K_TLS_TPOFF:
				markAsWarning(program, relocationAddress, type, symbolName, symIndex,
					"Thread-local relocation needs the run-time TLS layout", ctx.getLog());
				return RelocationResult.UNSUPPORTED;

			default:
				break;
		}

		if (handleUnresolvedSymbol(ctx, relocation, relocationAddress)) {
			return RelocationResult.FAILURE;
		}

		long S = symbolValue;
		long v = S + A;
		switch (type) {
			case R_OR1K_32:
			case R_OR1K_GLOB_DAT:
			case R_OR1K_JMP_SLOT:
				mem.setInt(relocationAddress, (int) v);
				return new RelocationResult(Status.APPLIED, 4);

			case R_OR1K_16:
				mem.setShort(relocationAddress, (short) v);
				return new RelocationResult(Status.APPLIED, 2);

			case R_OR1K_8:
				mem.setByte(relocationAddress, (byte) v);
				return new RelocationResult(Status.APPLIED, 1);

			case R_OR1K_32_PCREL:
				mem.setInt(relocationAddress, (int) (v - P));
				return new RelocationResult(Status.APPLIED, 4);

			case R_OR1K_16_PCREL:
				mem.setShort(relocationAddress, (short) (v - P));
				return new RelocationResult(Status.APPLIED, 2);

			case R_OR1K_8_PCREL:
				mem.setByte(relocationAddress, (byte) (v - P));
				return new RelocationResult(Status.APPLIED, 1);

			case R_OR1K_LO_16_IN_INSN:
				putBits(mem, relocationAddress, 0xffff, v);
				return new RelocationResult(Status.APPLIED, 4);

			case R_OR1K_HI_16_IN_INSN:
				putBits(mem, relocationAddress, 0xffff, v >> 16);
				return new RelocationResult(Status.APPLIED, 4);

			case R_OR1K_AHI16:
				putBits(mem, relocationAddress, 0xffff, (v + 0x8000) >> 16);
				return new RelocationResult(Status.APPLIED, 4);

			case R_OR1K_SLO16:
				putSplit(mem, relocationAddress, v);
				return new RelocationResult(Status.APPLIED, 4);

			case R_OR1K_LO13:
				putBits(mem, relocationAddress, 0xffff, v & 0x1fff);
				return new RelocationResult(Status.APPLIED, 4);

			case R_OR1K_SLO13:
				putSplit(mem, relocationAddress, v & 0x1fff);
				return new RelocationResult(Status.APPLIED, 4);

			case R_OR1K_INSN_REL_26:
			case R_OR1K_PLT26: // no PLT in a relocatable object: branch to the symbol
			case R_OR1K_PLTA26:
				putBits(mem, relocationAddress, 0x03ffffff, (v - P) >> 2);
				return new RelocationResult(Status.APPLIED, 4);

			case R_OR1K_PCREL_PG21:
				putBits(mem, relocationAddress, 0x001fffff, (v >> 13) - (P >> 13));
				return new RelocationResult(Status.APPLIED, 4);

			case R_OR1K_COPY:
				markAsUnsupportedCopy(program, relocationAddress, type, symbolName, symIndex,
					elfSymbol.getSize(), ctx.getLog());
				return RelocationResult.UNSUPPORTED;

			default:
				// GOT16, GOTPC_*, GOTOFF_*, GOT_PG21, GOT_LO13, GOT_AHI16 and the TLS access
				// models need a linker-built GOT
				markAsUnhandled(program, relocationAddress, type, symIndex, symbolName,
					ctx.getLog());
				return RelocationResult.UNSUPPORTED;
		}
	}
}
