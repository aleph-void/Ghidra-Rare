package ghidra.app.util.bin.format.elf.relocation;

import ghidra.app.util.bin.format.elf.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Program;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.reloc.Relocation.Status;
import ghidra.program.model.reloc.RelocationResult;

/**
 * ELF relocation handler for Telink TC32 (e_machine 0x8800), written for Ghidra-Rare from the
 * relocations tc32-elf-as emits (run as a black box). REL sections: the addend is the value in
 * place. With S the symbol value, A the addend and P the place:
 * <ul>
 * <li>ABS32: the word S + A.</li>
 * <li>CALL: the tjl pair (prefix 0x90-0x97 with offset bits 22-12, suffix 0x98-0x9F with bits
 * 11-1); A is the pair's current offset, and the new offset is S + A - P.</li>
 * </ul>
 */
public class TC32_ElfRelocationHandler
		extends AbstractElfRelocationHandler<TC32_ElfRelocationType, ElfRelocationContext<?>> {

	public static final int EM_TC32 = 0x8800;

	public TC32_ElfRelocationHandler() {
		super(TC32_ElfRelocationType.class);
	}

	@Override
	public boolean canRelocate(ElfHeader elf) {
		return elf.e_machine() == (short) EM_TC32;
	}

	@Override
	protected RelocationResult relocate(ElfRelocationContext<?> ctx, ElfRelocation relocation,
			TC32_ElfRelocationType type, Address relocationAddress, ElfSymbol elfSymbol,
			Address symbolAddr, long symbolValue, String symbolName)
			throws MemoryAccessException {

		Program program = ctx.getProgram();
		Memory mem = program.getMemory();
		long P = relocationAddress.getOffset();
		int symIndex = relocation.getSymbolIndex();

		if (type == TC32_ElfRelocationType.R_TC32_NONE) {
			return RelocationResult.SKIPPED;
		}
		if (handleUnresolvedSymbol(ctx, relocation, relocationAddress)) {
			return RelocationResult.FAILURE;
		}
		switch (type) {
			case R_TC32_ABS32: {
				long A = relocation.hasAddend() ? relocation.getAddend()
						: mem.getInt(relocationAddress);
				mem.setInt(relocationAddress, (int) (symbolValue + A));
				return new RelocationResult(Status.APPLIED, 4);
			}
			case R_TC32_CALL: {
				int hi = mem.getShort(relocationAddress) & 0xffff;
				int lo = mem.getShort(relocationAddress.add(2)) & 0xffff;
				long A;
				if (relocation.hasAddend()) {
					A = relocation.getAddend();
				}
				else {
					A = ((long) (((hi & 0x7ff) << 21) >> 21) << 12) | ((lo & 0x7ff) << 1);
				}
				long off = (symbolValue + A - P) >> 1;
				hi = (hi & 0xf800) | (int) ((off >> 11) & 0x7ff);
				lo = (lo & 0xf800) | (int) (off & 0x7ff);
				mem.setShort(relocationAddress, (short) hi);
				mem.setShort(relocationAddress.add(2), (short) lo);
				return new RelocationResult(Status.APPLIED, 4);
			}
			default:
				markAsUnhandled(program, relocationAddress, type, symIndex, symbolName,
					ctx.getLog());
				return RelocationResult.UNSUPPORTED;
		}
	}
}
