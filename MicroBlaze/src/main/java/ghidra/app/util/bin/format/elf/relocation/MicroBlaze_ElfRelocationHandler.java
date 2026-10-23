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
 * ELF relocation handler for AMD/Xilinx MicroBlaze (EM_MICROBLAZE = 189, and the old
 * unofficial 0xBAAB).
 * <p>
 * Semantics follow binutils bfd/elf32-microblaze.c (and the AMD/Xilinx elf64-microblaze.c for
 * the 64-bit types) and the glibc dynamic linker:
 * <ul>
 * <li>Dynamic: REL = B + A, GLOB_DAT / JUMP_SLOT / 32 = S + A (one word).</li>
 * <li>"_64" types patch an {@code imm} (or {@code imml}) prefix plus the following Type B
 * instruction: the high bits go into the prefix, the low 16 bits into the instruction.</li>
 * <li>"_LO" types patch the 16-bit immediate of one instruction.</li>
 * </ul>
 * Types that need a linker-built GOT/PLT (GOT_64, TLSGD, TLSLD, ...) in relocatable objects,
 * and the TLS module/offset relocations, are reported but not applied.
 */
public class MicroBlaze_ElfRelocationHandler
		extends AbstractElfRelocationHandler<MicroBlaze_ElfRelocationType, ElfRelocationContext<?>> {

	public static final int EM_MICROBLAZE = 189;
	public static final int EM_MICROBLAZE_OLD = 0xBAAB;

	public MicroBlaze_ElfRelocationHandler() {
		super(MicroBlaze_ElfRelocationType.class);
	}

	@Override
	public boolean canRelocate(ElfHeader elf) {
		return elf.e_machine() == EM_MICROBLAZE || elf.e_machine() == EM_MICROBLAZE_OLD;
	}

	@Override
	public int getRelrRelocationType() {
		return MicroBlaze_ElfRelocationType.R_MICROBLAZE_REL.typeId;
	}

	/** Patch the low 16 bits of the instruction word at {@code a}. */
	private static void putLo16(Memory mem, Address a, long value) throws MemoryAccessException {
		int insn = mem.getInt(a);
		mem.setInt(a, (insn & 0xffff0000) | (int) (value & 0xffff));
	}

	/**
	 * Patch an imm/imml prefix at {@code a} and the instruction at {@code a+4} with
	 * {@code value} (binutils microblaze_bfd_write_imm_value_64).
	 */
	private static void putImmPair(Memory mem, Address a, long value)
			throws MemoryAccessException {
		int hi = mem.getInt(a);
		if ((hi & 0xff000000) == 0xb2000000) { // imml (64-bit MicroBlaze): 24-bit field
			hi = (hi & 0xff000000) | (int) ((value >> 16) & 0xffffff);
		}
		else {
			hi = (hi & 0xffff0000) | (int) ((value >> 16) & 0xffff);
		}
		mem.setInt(a, hi);
		putLo16(mem, a.add(4), value);
	}

	private static Long symbolValue(Program program, String name) {
		SymbolIterator it = program.getSymbolTable().getSymbols(name);
		while (it.hasNext()) {
			Symbol s = it.next();
			if (s.isGlobal()) {
				return s.getAddress().getOffset();
			}
		}
		return null;
	}

	@Override
	protected RelocationResult relocate(ElfRelocationContext<?> ctx, ElfRelocation relocation,
			MicroBlaze_ElfRelocationType type, Address relocationAddress, ElfSymbol elfSymbol,
			Address symbolAddr, long symbolValue, String symbolName)
			throws MemoryAccessException {

		Program program = ctx.getProgram();
		Memory mem = program.getMemory();
		boolean is64 = ctx.getElfHeader().is64Bit();
		long addend = relocation.getAddend();
		long P = relocationAddress.getOffset();
		int symIndex = relocation.getSymbolIndex();

		// Types that need no symbol
		switch (type) {
			case R_MICROBLAZE_NONE:
			case R_MICROBLAZE_32_NONE:
			case R_MICROBLAZE_64_NONE:
			case R_MICROBLAZE_32_SYM_OP_SYM:
			case R_MICROBLAZE_GNU_VTINHERIT:
			case R_MICROBLAZE_GNU_VTENTRY:
				return RelocationResult.SKIPPED;

			case R_MICROBLAZE_REL: {
				long v = ctx.getImageBaseWordAdjustmentOffset() + addend;
				if (is64) {
					mem.setLong(relocationAddress, v);
					return new RelocationResult(Status.APPLIED, 8);
				}
				mem.setInt(relocationAddress, (int) v);
				return new RelocationResult(Status.APPLIED, 4);
			}

			case R_MICROBLAZE_TLSDTPMOD32:
				// Module ID is assigned by the dynamic linker at run time.
				return RelocationResult.SKIPPED;

			default:
				break;
		}

		if (handleUnresolvedSymbol(ctx, relocation, relocationAddress)) {
			return RelocationResult.FAILURE;
		}

		long S = symbolValue;
		switch (type) {
			case R_MICROBLAZE_32:
			case R_MICROBLAZE_GLOB_DAT:
			case R_MICROBLAZE_JUMP_SLOT:
				// R_MICROBLAZE_32 is a 4-byte field even in ELF64 (elf64-microblaze bfd_put_32)
				mem.setInt(relocationAddress, (int) (S + addend));
				return new RelocationResult(Status.APPLIED, 4);

			case R_MICROBLAZE_IMML_64:
				mem.setLong(relocationAddress, S + addend);
				return new RelocationResult(Status.APPLIED, 8);

			case R_MICROBLAZE_32_PCREL:
				mem.setInt(relocationAddress, (int) (S + addend - P));
				return new RelocationResult(Status.APPLIED, 4);

			case R_MICROBLAZE_64:
				putImmPair(mem, relocationAddress, S + addend);
				return new RelocationResult(Status.APPLIED, 8);

			case R_MICROBLAZE_64_PCREL:
			case R_MICROBLAZE_PLT_64: // no PLT in a relocatable object: branch to the symbol
				putImmPair(mem, relocationAddress, S + addend - (P + 4));
				return new RelocationResult(Status.APPLIED, 8);

			case R_MICROBLAZE_32_LO:
				putLo16(mem, relocationAddress, S + addend);
				return new RelocationResult(Status.APPLIED, 4);

			case R_MICROBLAZE_32_PCREL_LO:
				putLo16(mem, relocationAddress, S + addend - P);
				return new RelocationResult(Status.APPLIED, 4);

			case R_MICROBLAZE_SRO32:
			case R_MICROBLAZE_SRW32: {
				String base = type == MicroBlaze_ElfRelocationType.R_MICROBLAZE_SRO32
						? "_SDA2_BASE_"
						: "_SDA_BASE_";
				Long sda = symbolValue(program, base);
				if (sda == null) {
					markAsError(program, relocationAddress, type, symbolName, symIndex,
						base + " not defined", ctx.getLog());
					return RelocationResult.FAILURE;
				}
				putLo16(mem, relocationAddress, S + addend - sda);
				return new RelocationResult(Status.APPLIED, 4);
			}

			case R_MICROBLAZE_GOTPC_64:
			case R_MICROBLAZE_GOTOFF_64:
			case R_MICROBLAZE_GOTOFF_32: {
				long got;
				try {
					got = ctx.getGOTValue();
				}
				catch (NotFoundException e) {
					markAsError(program, relocationAddress, type, symbolName, symIndex,
						"_GLOBAL_OFFSET_TABLE_ not found", ctx.getLog());
					return RelocationResult.FAILURE;
				}
				if (type == MicroBlaze_ElfRelocationType.R_MICROBLAZE_GOTOFF_32) {
					mem.setInt(relocationAddress, (int) (S + addend - got));
					return new RelocationResult(Status.APPLIED, 4);
				}
				long v = type == MicroBlaze_ElfRelocationType.R_MICROBLAZE_GOTPC_64
						? got + addend - (P + 4)
						: S + addend - got;
				putImmPair(mem, relocationAddress, v);
				return new RelocationResult(Status.APPLIED, 8);
			}

			case R_MICROBLAZE_COPY:
				markAsUnsupportedCopy(program, relocationAddress, type, symbolName, symIndex,
					elfSymbol.getSize(), ctx.getLog());
				return RelocationResult.UNSUPPORTED;

			case R_MICROBLAZE_TLS:
			case R_MICROBLAZE_TLSGD:
			case R_MICROBLAZE_TLSLD:
			case R_MICROBLAZE_TLSDTPREL32:
			case R_MICROBLAZE_TLSDTPREL64:
			case R_MICROBLAZE_TLSGOTTPREL32:
			case R_MICROBLAZE_TLSTPREL32:
				markAsWarning(program, relocationAddress, type, symbolName, symIndex,
					"Thread Local Symbol relocation not supported", ctx.getLog());
				return RelocationResult.UNSUPPORTED;

			default:
				// GOT_64, TEXTPCREL_64, TEXTREL_64, TEXTREL_32_LO, GPC_64: need linker-built
				// GOT or output-section layout
				markAsUnhandled(program, relocationAddress, type, symIndex, symbolName,
					ctx.getLog());
				return RelocationResult.UNSUPPORTED;
		}
	}
}
