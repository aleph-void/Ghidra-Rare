/* SPDX-License-Identifier: Apache-2.0 */
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
import ghidra.util.Msg;
import ghidra.util.exception.CancelledException;
import ghidra.util.exception.InvalidInputException;
import ghidra.util.task.TaskMonitor;

/**
 * ELF extension for OpenRISC 1000.
 * <p>
 * PLT entries (bfd elf32-or1k.c) load their target from a GOT slot and jump to it:
 * <pre>
 *   PIC:      l.lwz r12, off(r16)          ; r16 = _GLOBAL_OFFSET_TABLE_, set by the caller
 *   absolute: l.movhi r12, ha(slot) ; l.lwz r12, lo(slot)(r12)
 *   adrp:     l.adrp r12, slot      ; l.lwz r12, po(slot)(r12)
 *             l.jr r12 ; l.ori r11, r0, reloc_offset
 * </pre>
 * In PIC code the PLT never computes r16 itself, so the stubs cannot be followed to their GOT
 * slots. This extension sets r16 = _GLOBAL_OFFSET_TABLE_ as a register value over .plt, and
 * labels each entry with the symbol of the R_OR1K_JMP_SLOT relocation for its slot, so that the
 * standard PLT markup turns the entries into thunks of the named functions.
 */
public class OpenRISC_ElfExtension extends ElfExtension {

	public static final int EM_OPENRISC = 92;
	public static final int EM_OR1K_OLD = 0x8472;
	private static final int JMP_SLOT = 20; // R_OR1K_JMP_SLOT

	@Override
	public boolean canHandle(ElfHeader elf) {
		return elf.e_machine() == EM_OPENRISC || elf.e_machine() == EM_OR1K_OLD;
	}

	@Override
	public boolean canHandle(ElfLoadHelper elfLoadHelper) {
		Language language = elfLoadHelper.getProgram().getLanguage();
		return canHandle(elfLoadHelper.getElfHeader()) &&
			"OpenRISC".equals(language.getProcessor().toString());
	}

	@Override
	public String getDataTypeSuffix() {
		return "_OpenRISC";
	}

	@Override
	public void processGotPlt(ElfLoadHelper elfLoadHelper, TaskMonitor monitor)
			throws CancelledException {
		setPltGotPointer(elfLoadHelper);
		labelPltEntries(elfLoadHelper);
		super.processGotPlt(elfLoadHelper, monitor);
	}

	private static long sext16(int v) {
		return (short) (v & 0xffff);
	}

	/** Name each PLT entry after the JMP_SLOT symbol of the GOT slot it jumps through. */
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
				if (r.getType() != JMP_SLOT || idx <= 0 || idx >= syms.length) {
					continue;
				}
				String name = syms[idx].getNameAsString();
				if (name != null && !name.isEmpty()) {
					slotNames.put((r.getOffset() + adj) & 0xffffffffL, name);
				}
			}
		}
		if (slotNames.isEmpty()) {
			return;
		}
		Long got = elfLoadHelper.getGOTValue();
		Memory mem = program.getMemory();
		Address a = plt.getStart();
		int prev = 0;
		Address prevAddr = null;
		while (a.add(3).compareTo(plt.getEnd()) <= 0) {
			int insn;
			try {
				insn = mem.getInt(a);
			}
			catch (MemoryAccessException e) {
				break;
			}
			// l.lwz r12, off(rA)
			if ((insn & 0xffe00000) == 0x85800000) {
				int ra = (insn >> 16) & 0x1f;
				long off = sext16(insn);
				Long slot = null;
				Address entry = a;
				if (ra == 16 && got != null) {
					slot = got + off;
				}
				else if (ra == 12 && prevAddr != null && (prev & 0xffe00000) == 0x19800000) {
					slot = ((long) (prev & 0xffff) << 16) + off; // l.movhi r12, ha(slot)
					entry = prevAddr;
				}
				else if (ra == 12 && prevAddr != null && (prev & 0xffe00000) == 0x09800000) {
					long page = (long) ((prev << 11) >> 11) << 13; // l.adrp r12, slot
					slot = page + (prevAddr.getOffset() & ~0x1fffL) + off;
					entry = prevAddr;
				}
				String name = slot == null ? null : slotNames.get(slot & 0xffffffffL);
				if (name != null) {
					try {
						Symbol sym = program.getSymbolTable().getPrimarySymbol(entry);
						if (sym == null || sym.getSource() == SourceType.DEFAULT) {
							program.getSymbolTable().createLabel(entry, name, SourceType.IMPORTED);
						}
					}
					catch (InvalidInputException e) {
						// leave unlabelled
					}
				}
			}
			prev = insn;
			prevAddr = a;
			a = a.add(4);
		}
	}

	private void setPltGotPointer(ElfLoadHelper elfLoadHelper) {
		Program program = elfLoadHelper.getProgram();
		Long got = elfLoadHelper.getGOTValue();
		Register r16 = program.getRegister("r16");
		if (got == null || r16 == null) {
			return;
		}
		for (MemoryBlock block : program.getMemory().getBlocks()) {
			if (!block.getName().equals(ElfSectionHeaderConstants.dot_plt) ||
				!block.isExecute()) {
				continue;
			}
			try {
				program.getProgramContext()
						.setValue(r16, block.getStart(), block.getEnd(), BigInteger.valueOf(got));
			}
			catch (ContextChangeException e) {
				Msg.warn(this, "Failed to set r16 (GOT pointer) over .plt: " + e.getMessage());
			}
		}
	}
}
