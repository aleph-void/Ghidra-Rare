package ghidra.app.util.bin.format.elf.relocation;

import ghidra.app.util.bin.format.elf.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Program;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.reloc.Relocation.Status;
import ghidra.program.model.reloc.RelocationResult;

/**
 * ELF relocation handler for the Intel i860 (EM_860 = 7), written for Ghidra-Rare and checked
 * against GNU ld 2.30 (see test/reloc-check.sh). With V = S + A:
 * <ul>
 * <li>32: the word V; RELATIVE: B + A; GLOB_DAT, JUMP_SLOT: V.</li>
 * <li>PC26, PLT26: (V - (P + 4)) / 4 in bits 25-0 (br, call, bc, bnc).</li>
 * <li>PC16: (V - (P + 4)) / 4 split into bits 20-16 (high 5 bits) and 10-0 (bte, btne, bla).</li>
 * <li>HIGH: V &gt;&gt; 16; HIGHADJ: (V + 0x8000) &gt;&gt; 16 (for a signed low half), in bits
 * 15-0. HAPC and LOPC: the same and the low half of V - P.</li>
 * <li>LOWn: the low 16 bits of V in bits 15-0, keeping the instruction's low n bits (operand
 * size and autoincrement bits of ld.s/ld.l, fld/fst/pfld/pst).</li>
 * <li>SPLITn: the low 16 bits of V split between bits 20-16 and 10-0 (st.x), keeping the low n
 * bits.</li>
 * </ul>
 * GOT/PLT-relative forms are reported as unsupported (Ghidra has no i860 GOT model).
 */
public class I860_ElfRelocationHandler
		extends AbstractElfRelocationHandler<I860_ElfRelocationType, ElfRelocationContext<?>> {

	public static final int EM_860 = 7;

	public I860_ElfRelocationHandler() {
		super(I860_ElfRelocationType.class);
	}

	@Override
	public boolean canRelocate(ElfHeader elf) {
		return elf.e_machine() == EM_860;
	}

	@Override
	public int getRelrRelocationType() {
		return I860_ElfRelocationType.R_860_RELATIVE.typeId;
	}

	private static int low16(int insn, long v, int keep) {
		return (insn & ~0xffff) | ((int) v & 0xffff & ~keep) | (insn & keep);
	}

	private static int split16(int insn, long v, int keep) {
		int x = ((int) v & 0xffff & ~keep) | (insn & keep);
		return (insn & ~(0x1f << 16) & ~0x7ff) | (((x >> 11) & 0x1f) << 16) | (x & 0x7ff);
	}

	@Override
	protected RelocationResult relocate(ElfRelocationContext<?> ctx, ElfRelocation relocation,
			I860_ElfRelocationType type, Address relocationAddress, ElfSymbol elfSymbol,
			Address symbolAddr, long symbolValue, String symbolName)
			throws MemoryAccessException {

		Program program = ctx.getProgram();
		Memory mem = program.getMemory();
		long A = relocation.getAddend();
		long P = relocationAddress.getOffset();
		int symIndex = relocation.getSymbolIndex();

		switch (type) {
			case R_860_NONE:
				return RelocationResult.SKIPPED;
			case R_860_RELATIVE:
				mem.setInt(relocationAddress,
					(int) (ctx.getImageBaseWordAdjustmentOffset() + A +
						(relocation.hasAddend() ? 0 : mem.getInt(relocationAddress))));
				return new RelocationResult(Status.APPLIED, 4);
			case R_860_COPY:
				markAsUnsupportedCopy(program, relocationAddress, type, symbolName, symIndex,
					elfSymbol.getSize(), ctx.getLog());
				return RelocationResult.UNSUPPORTED;
			default:
				break;
		}

		if (handleUnresolvedSymbol(ctx, relocation, relocationAddress)) {
			return RelocationResult.FAILURE;
		}
		long v = symbolValue + A;
		int insn = mem.getInt(relocationAddress);
		int out;
		switch (type) {
			case R_860_32:
			case R_860_GLOB_DAT:
			case R_860_JUMP_SLOT:
				out = (int) v;
				break;
			case R_860_PC26:
			case R_860_PLT26:
				out = (insn & ~0x3ffffff) | ((int) ((v - (P + 4)) >> 2) & 0x3ffffff);
				break;
			case R_860_PC16:
				out = split16(insn, (v - (P + 4)) >> 2, 0);
				break;
			case R_860_HIGH:
				out = (insn & ~0xffff) | ((int) (v >> 16) & 0xffff);
				break;
			case R_860_HIGHADJ:
				out = (insn & ~0xffff) | ((int) ((v + 0x8000) >> 16) & 0xffff);
				break;
			case R_860_HAPC:
				out = (insn & ~0xffff) | ((int) ((v - P + 0x8000) >> 16) & 0xffff);
				break;
			case R_860_LOPC:
				out = low16(insn, v - P, 0);
				break;
			case R_860_LOW0:
				out = low16(insn, v, 0);
				break;
			case R_860_LOW1:
				out = low16(insn, v, 1);
				break;
			case R_860_LOW2:
				out = low16(insn, v, 3);
				break;
			case R_860_LOW3:
				out = low16(insn, v, 7);
				break;
			case R_860_SPLIT0:
				out = split16(insn, v, 0);
				break;
			case R_860_SPLIT1:
				out = split16(insn, v, 1);
				break;
			case R_860_SPLIT2:
				out = split16(insn, v, 3);
				break;
			default:
				markAsUnhandled(program, relocationAddress, type, symIndex, symbolName,
					ctx.getLog());
				return RelocationResult.UNSUPPORTED;
		}
		mem.setInt(relocationAddress, out);
		return new RelocationResult(Status.APPLIED, 4);
	}
}
