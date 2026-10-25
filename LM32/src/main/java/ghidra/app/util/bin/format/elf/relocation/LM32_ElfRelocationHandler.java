/* SPDX-License-Identifier: MIT */
package ghidra.app.util.bin.format.elf.relocation;

import ghidra.app.util.bin.format.elf.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Program;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.reloc.Relocation.Status;
import ghidra.program.model.reloc.RelocationResult;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolIterator;
import ghidra.util.exception.NotFoundException;

/**
 * ELF relocation handler for LatticeMico32 (EM_LATTICEMICO32 = 138).
 * <p>
 * Semantics follow binutils bfd/elf32-lm32.c: HI16/LO16 patch the 16-bit immediate with the
 * high/low half of S + A (no carry adjustment: the low half is used with the zero-extending
 * ori); GPREL16 is S + A - _gp; CALL and BRANCH are word displacements (26 and 16 bits);
 * GOTOFF_HI16/LO16 are offsets from the GOT, with the high half adjusted for the
 * sign-extending addi; dynamic RELATIVE = B + A, 32/GLOB_DAT/JMP_SLOT = S + A.
 * 16_GOT needs a linker-built GOT and COPY a run-time copy; both are reported.
 */
public class LM32_ElfRelocationHandler
		extends AbstractElfRelocationHandler<LM32_ElfRelocationType, ElfRelocationContext<?>> {

	public static final int EM_LATTICEMICO32 = 138;

	public LM32_ElfRelocationHandler() {
		super(LM32_ElfRelocationType.class);
	}

	@Override
	public boolean canRelocate(ElfHeader elf) {
		return elf.e_machine() == EM_LATTICEMICO32;
	}

	@Override
	public int getRelrRelocationType() {
		return LM32_ElfRelocationType.R_LM32_RELATIVE.typeId;
	}

	private static void putBits(Memory mem, Address a, int mask, long value)
			throws MemoryAccessException {
		int insn = mem.getInt(a);
		mem.setInt(a, (insn & ~mask) | ((int) value & mask));
	}

	private static Long symbolValue(Program program, String name) {
		SymbolIterator it = program.getSymbolTable().getSymbols(name);
		while (it.hasNext()) {
			Symbol s = it.next();
			return s.getAddress().getOffset();
		}
		return null;
	}

	@Override
	protected RelocationResult relocate(ElfRelocationContext<?> ctx, ElfRelocation relocation,
			LM32_ElfRelocationType type, Address relocationAddress, ElfSymbol elfSymbol,
			Address symbolAddr, long symbolValue, String symbolName)
			throws MemoryAccessException {

		Program program = ctx.getProgram();
		Memory mem = program.getMemory();
		long A = relocation.getAddend();
		long P = relocationAddress.getOffset();
		int symIndex = relocation.getSymbolIndex();

		switch (type) {
			case R_LM32_NONE:
			case R_LM32_GNU_VTINHERIT:
			case R_LM32_GNU_VTENTRY:
				return RelocationResult.SKIPPED;

			case R_LM32_RELATIVE:
				mem.setInt(relocationAddress, (int) (ctx.getImageBaseWordAdjustmentOffset() + A));
				return new RelocationResult(Status.APPLIED, 4);

			default:
				break;
		}

		if (handleUnresolvedSymbol(ctx, relocation, relocationAddress)) {
			return RelocationResult.FAILURE;
		}

		long v = symbolValue + A;
		switch (type) {
			case R_LM32_32:
			case R_LM32_GLOB_DAT:
			case R_LM32_JMP_SLOT:
				mem.setInt(relocationAddress, (int) v);
				return new RelocationResult(Status.APPLIED, 4);

			case R_LM32_16:
				mem.setShort(relocationAddress, (short) v);
				return new RelocationResult(Status.APPLIED, 2);

			case R_LM32_8:
				mem.setByte(relocationAddress, (byte) v);
				return new RelocationResult(Status.APPLIED, 1);

			case R_LM32_HI16:
				putBits(mem, relocationAddress, 0xffff, v >> 16);
				return new RelocationResult(Status.APPLIED, 4);

			case R_LM32_LO16:
				putBits(mem, relocationAddress, 0xffff, v);
				return new RelocationResult(Status.APPLIED, 4);

			case R_LM32_CALL:
				putBits(mem, relocationAddress, 0x03ffffff, (v - P) >> 2);
				return new RelocationResult(Status.APPLIED, 4);

			case R_LM32_BRANCH:
				putBits(mem, relocationAddress, 0xffff, (v - P) >> 2);
				return new RelocationResult(Status.APPLIED, 4);

			case R_LM32_GPREL16: {
				Long gp = symbolValue(program, "_gp");
				if (gp == null) {
					markAsError(program, relocationAddress, type, symbolName, symIndex,
						"_gp not defined", ctx.getLog());
					return RelocationResult.FAILURE;
				}
				putBits(mem, relocationAddress, 0xffff, v - gp);
				return new RelocationResult(Status.APPLIED, 4);
			}

			case R_LM32_GOTOFF_HI16:
			case R_LM32_GOTOFF_LO16: {
				long got;
				try {
					got = ctx.getGOTValue();
				}
				catch (NotFoundException e) {
					markAsError(program, relocationAddress, type, symbolName, symIndex,
						"_GLOBAL_OFFSET_TABLE_ not found", ctx.getLog());
					return RelocationResult.FAILURE;
				}
				long off = v - got;
				if (type == LM32_ElfRelocationType.R_LM32_GOTOFF_HI16) {
					off = (off + ((off & 0x8000) != 0 ? 0x10000 : 0)) >> 16;
				}
				putBits(mem, relocationAddress, 0xffff, off);
				return new RelocationResult(Status.APPLIED, 4);
			}

			case R_LM32_COPY:
				markAsUnsupportedCopy(program, relocationAddress, type, symbolName, symIndex,
					elfSymbol.getSize(), ctx.getLog());
				return RelocationResult.UNSUPPORTED;

			default:
				// R_LM32_16_GOT needs a linker-built GOT
				markAsUnhandled(program, relocationAddress, type, symIndex, symbolName,
					ctx.getLog());
				return RelocationResult.UNSUPPORTED;
		}
	}
}
