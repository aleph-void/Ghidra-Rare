/* SPDX-License-Identifier: MIT */
package ghidra.app.util.bin.format.elf.extend;

import java.math.BigInteger;
import java.util.HashMap;
import java.util.Map;

import ghidra.app.util.bin.format.elf.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Language;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.ContextChangeException;
import ghidra.program.model.listing.Program;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.Symbol;
import ghidra.util.exception.InvalidInputException;
import ghidra.util.Msg;
import ghidra.util.exception.CancelledException;
import ghidra.util.task.TaskMonitor;

/**
 * ELF extension for AMD/Xilinx MicroBlaze.
 * <p>
 * Position-independent MicroBlaze PLT entries (bfd elf32-microblaze.c) are
 * <pre>
 *   imm   hi16(GOT offset)
 *   lwi   r12, r20, lo16(GOT offset)
 *   brad  r12
 *   nop
 * </pre>
 * where r20 is the GOT pointer (_GLOBAL_OFFSET_TABLE_, the start of .got.plt) set up by the
 * calling PIC function. The PLT itself never computes r20, so the stubs cannot be resolved
 * to their GOT slots. This extension records r20 = _GLOBAL_OFFSET_TABLE_ as a register value
 * over the .plt section before the standard GOT/PLT markup runs, so that thunk analysis and
 * the decompiler can follow each stub through its GOT slot. It also decodes each PLT entry,
 * matches its GOT slot with the R_MICROBLAZE_JUMP_SLOT relocation for that slot and labels the
 * entry with the relocation's symbol name; the standard PLT markup then turns those labels
 * into thunks of the named (external) functions.
 */
public class MicroBlaze_ElfExtension extends ElfExtension {

	public static final int EM_MICROBLAZE = 189;
	public static final int EM_MICROBLAZE_OLD = 0xBAAB;

	@Override
	public boolean canHandle(ElfHeader elf) {
		return elf.e_machine() == EM_MICROBLAZE || elf.e_machine() == EM_MICROBLAZE_OLD;
	}

	@Override
	public boolean canHandle(ElfLoadHelper elfLoadHelper) {
		Language language = elfLoadHelper.getProgram().getLanguage();
		return canHandle(elfLoadHelper.getElfHeader()) &&
			"MicroBlaze".equals(language.getProcessor().toString());
	}

	@Override
	public String getDataTypeSuffix() {
		return "_MicroBlaze";
	}

	@Override
	public void processGotPlt(ElfLoadHelper elfLoadHelper, TaskMonitor monitor)
			throws CancelledException {
		setPltGotPointer(elfLoadHelper);
		labelPltEntries(elfLoadHelper);
		super.processGotPlt(elfLoadHelper, monitor);
	}

	private static final int PLT_HEAD_SIZE = 16;
	private static final int PLT_ENTRY_SIZE = 16;

	/** Name each PLT entry after the JUMP_SLOT symbol of the GOT slot it jumps through. */
	private void labelPltEntries(ElfLoadHelper elfLoadHelper) {
		Program program = elfLoadHelper.getProgram();
		ElfHeader elf = elfLoadHelper.getElfHeader();
		MemoryBlock plt = program.getMemory().getBlock(ElfSectionHeaderConstants.dot_plt);
		if (plt == null || !plt.isInitialized() || elf.isRelocatable()) {
			return;
		}
		long adj = elfLoadHelper.getImageBaseWordAdjustmentOffset();
		Map<Long, String> slotNames = new HashMap<>();
		for (ElfRelocationTable table : elf.getRelocationTables()) {
			ElfSymbolTable symtab = table.getAssociatedSymbolTable();
			if (symtab == null) {
				continue;
			}
			ElfSymbol[] syms = symtab.getSymbols();
			for (ElfRelocation r : table.getRelocations()) {
				int idx = r.getSymbolIndex();
				if (r.getType() != JUMP_SLOT || idx <= 0 || idx >= syms.length) {
					continue;
				}
				String name = syms[idx].getNameAsString();
				if (name != null && !name.isEmpty()) {
					slotNames.put(r.getOffset() + adj, name);
				}
			}
		}
		if (slotNames.isEmpty()) {
			return;
		}
		Long got = elfLoadHelper.getGOTValue();
		Memory mem = program.getMemory();
		Address a = plt.getStart().add(PLT_HEAD_SIZE);
		while (a.add(PLT_ENTRY_SIZE - 1).compareTo(plt.getEnd()) <= 0) {
			try {
				int imm = mem.getInt(a);
				int lwi = mem.getInt(a.add(4));
				// imm hi16 ; lwi r12, rA, lo16 (rA = r20 for PIC, r0 otherwise)
				if ((imm & 0xffff0000) == 0xb0000000 && (lwi & 0xffe00000) == 0xe9800000) {
					int ra = (lwi >> 16) & 0x1f;
					long off = (imm << 16) | (lwi & 0xffff);
					long base = ra == 20 && got != null ? got : 0;
					String name = ra == 0 || ra == 20 ? slotNames.get((base + off) & 0xffffffffL)
							: null;
					if (name != null) {
						Symbol sym = program.getSymbolTable().getPrimarySymbol(a);
						if (sym == null || sym.getSource() == SourceType.DEFAULT) {
							program.getSymbolTable().createLabel(a, name, SourceType.IMPORTED);
						}
					}
				}
			}
			catch (MemoryAccessException | InvalidInputException e) {
				break;
			}
			a = a.add(PLT_ENTRY_SIZE);
		}
	}

	private static final int JUMP_SLOT = 17; // R_MICROBLAZE_JUMP_SLOT

	private void setPltGotPointer(ElfLoadHelper elfLoadHelper) {
		Program program = elfLoadHelper.getProgram();
		Long got = elfLoadHelper.getGOTValue();
		Register r20 = program.getRegister("r20");
		if (got == null || r20 == null) {
			return;
		}
		for (MemoryBlock block : program.getMemory().getBlocks()) {
			if (!block.getName().equals(ElfSectionHeaderConstants.dot_plt) ||
				!block.isExecute()) {
				continue;
			}
			Address start = block.getStart();
			Address end = block.getEnd();
			try {
				program.getProgramContext()
						.setValue(r20, start, end, BigInteger.valueOf(got));
			}
			catch (ContextChangeException e) {
				Msg.warn(this, "Failed to set r20 (GOT pointer) over .plt: " + e.getMessage());
			}
		}
	}
}
