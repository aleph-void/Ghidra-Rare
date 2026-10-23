/* Ghidra-Rare SASS module - MIT licensed */
package ghidra.app.util.bin.format.elf.extend;

import java.util.HashMap;
import java.util.Map;
import java.util.WeakHashMap;

import ghidra.app.util.bin.format.elf.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSpace;
import java.math.BigInteger;

import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.Program;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Symbol;
import ghidra.util.exception.CancelledException;
import ghidra.util.exception.NoValueException;
import ghidra.util.task.TaskMonitor;

/**
 * ELF load support for NVIDIA CUDA cubins (EM_CUDA = 190).
 * <p>
 * cubins are ET_EXEC files in which every section - one {@code .text.<kernel>} per
 * function, per-kernel constant banks, shared memory descriptors - has address 0,
 * and the program headers overlap at 0 as well.  Code inside a section is
 * position independent (branches and calls are PC relative) and symbol values are
 * section offsets.  This extension therefore
 * <ul>
 * <li>ignores the program headers (so sections are loaded individually),</li>
 * <li>gives every allocated section its own address range in the default space,
 * in section order, starting at 0x10000, and</li>
 * <li>resolves symbols relative to their section.</li>
 * </ul>
 */
public class SASS_CubinElfExtension extends ElfExtension {

	public static final short EM_CUDA = 190;
	private static final long BASE = 0x10000;

	private static final Map<ElfHeader, Map<ElfSectionHeader, Long>> LAYOUT = new WeakHashMap<>();

	@Override
	public boolean canHandle(ElfHeader elf) {
		return elf.e_machine() == EM_CUDA;
	}

	@Override
	public boolean canHandle(ElfLoadHelper elfLoadHelper) {
		return canHandle(elfLoadHelper.getElfHeader()) &&
			"SASS".equals(elfLoadHelper.getProgram().getLanguage().getProcessor().toString());
	}

	@Override
	public String getDataTypeSuffix() {
		return "_SASS";
	}

	@Override
	public long getAdjustedLoadSize(ElfProgramHeader elfProgramHeader) {
		return 0;
	}

	@Override
	public long getAdjustedMemorySize(ElfProgramHeader elfProgramHeader) {
		return 0;
	}

	private static synchronized Map<ElfSectionHeader, Long> layout(ElfHeader elf) {
		Map<ElfSectionHeader, Long> m = LAYOUT.get(elf);
		if (m != null) {
			return m;
		}
		m = new HashMap<>();
		long cur = BASE;
		for (ElfSectionHeader s : elf.getSections()) {
			if (!s.isAlloc() || s.getSize() == 0) {
				continue;
			}
			long align = Math.max(s.getAddressAlignment(), s.isExecutable() ? 0x80 : 0x10);
			cur = (cur + align - 1) / align * align;
			m.put(s, cur);
			cur += s.getSize();
		}
		LAYOUT.put(elf, m);
		return m;
	}

	@Override
	public Address getPreferredSectionAddress(ElfLoadHelper elfLoadHelper,
			ElfSectionHeader elfSectionHeader) {
		Long a = layout(elfLoadHelper.getElfHeader()).get(elfSectionHeader);
		if (a == null) {
			return super.getPreferredSectionAddress(elfLoadHelper, elfSectionHeader);
		}
		AddressSpace space = elfLoadHelper.getProgram().getAddressFactory().getDefaultAddressSpace();
		return space.getAddress(a);
	}

	private Address sectionRelative(ElfLoadHelper elfLoadHelper, ElfSymbol elfSymbol) {
		ElfHeader elf = elfLoadHelper.getElfHeader();
		int idx = Short.toUnsignedInt(elfSymbol.getSectionHeaderIndex());
		ElfSectionHeader[] secs = elf.getSections();
		if (idx <= 0 || idx >= secs.length) {
			return null;
		}
		Long base = layout(elf).get(secs[idx]);
		if (base == null) {
			return null;
		}
		return elfLoadHelper.getProgram()
				.getAddressFactory()
				.getDefaultAddressSpace()
				.getAddress(base + elfSymbol.getValue());
	}

	@Override
	public Address calculateSymbolAddress(ElfLoadHelper elfLoadHelper, ElfSymbol elfSymbol)
			throws NoValueException {
		Address a = sectionRelative(elfLoadHelper, elfSymbol);
		return a != null ? a : super.calculateSymbolAddress(elfLoadHelper, elfSymbol);
	}

	@Override
	public Address evaluateElfSymbol(ElfLoadHelper elfLoadHelper, ElfSymbol elfSymbol,
			Address address, boolean isExternal) {
		if (isExternal || elfSymbol.isSection()) {
			return address;
		}
		Address a = sectionRelative(elfLoadHelper, elfSymbol);
		if (a == null || a.equals(address)) {
			return address;
		}
		// symbol values in cubins are section offsets: place the symbol in its section
		elfLoadHelper.setElfSymbolAddress(elfSymbol, a);
		return a;
	}

	/**
	 * Symbol values in cubins are offsets into their section, but Ghidra's ELF loader treats
	 * them as absolute for ET_EXEC files.  Re-create every symbol at section start + value,
	 * make functions (kernel entries, STO_CUDA_ENTRY, become entry points) and drop the
	 * misplaced copies.
	 */
	@Override
	public void processElf(ElfLoadHelper elfLoadHelper, TaskMonitor monitor)
			throws CancelledException {
		if (!canHandle(elfLoadHelper)) {
			return;
		}
		Program program = elfLoadHelper.getProgram();
		markControlWords(program, monitor);
		ElfHeader elf = elfLoadHelper.getElfHeader();
		ElfSectionHeader[] secs = elf.getSections();
		for (ElfSymbolTable st : elf.getSymbolTables()) {
			for (ElfSymbol sym : st.getSymbols()) {
				monitor.checkCancelled();
				if (sym.isSection() || sym.isFile()) {
					continue;
				}
				int idx = Short.toUnsignedInt(sym.getSectionHeaderIndex());
				String name = sym.getNameAsString();
				if (idx <= 0 || idx >= secs.length || name == null || name.isEmpty()) {
					continue;
				}
				MemoryBlock block = program.getMemory().getBlock(secs[idx].getNameAsString());
				if (block == null) {
					continue;
				}
				Address addr = block.getStart().add(sym.getValue());
				for (Symbol old : program.getSymbolTable().getGlobalSymbols(name)) {
					Address oa = old.getAddress();
					if (!oa.equals(addr) && oa.isMemoryAddress() && !block.contains(oa)) {
						if (program.getFunctionManager().getFunctionAt(oa) != null) {
							program.getFunctionManager().removeFunction(oa);
						}
						old.delete();
					}
				}
				try {
					boolean entry = (sym.getOther() & 0x10) != 0;
					if (sym.isFunction() && block.isExecute()) {
						elfLoadHelper.markAsCode(addr);
						elfLoadHelper.createOneByteFunction(name, addr, entry);
					}
					else {
						elfLoadHelper.createSymbol(addr, name, true, false, null);
					}
				}
				catch (Exception e) {
					elfLoadHelper.log("SASS: cannot place symbol " + name + ": " + e.getMessage());
				}
			}
		}
	}

	/**
	 * 64-bit encodings (Kepler, Maxwell, Pascal) interleave scheduling control words with
	 * the instructions: every bundle of 32 bytes (Kepler: 64 bytes) starts with one.  Mark
	 * them with the "ctl" context bit so the disassembler decodes them as SCHED words.
	 */
	public static void markControlWords(Program program, TaskMonitor monitor)
			throws CancelledException {
		int stride = bundleSize(program);
		if (stride == 0) {
			return;
		}
		Register ctl = program.getRegister("ctl");
		if (ctl == null) {
			return;
		}
		ProgramContext pc = program.getProgramContext();
		for (MemoryBlock b : program.getMemory().getBlocks()) {
			if (!b.isExecute() || !b.isInitialized()) {
				continue;
			}
			long off = b.getStart().getOffset();
			long first = (off + stride - 1) / stride * stride;
			for (long a = first; a + 8 <= b.getEnd().getOffset() + 1; a += stride) {
				monitor.checkCancelled();
				Address addr = b.getStart().getNewAddress(a);
				try {
					pc.setValue(ctl, addr, addr, BigInteger.ONE);
				}
				catch (Exception e) {
					// context can not be set (e.g. existing instruction): ignore
				}
			}
		}
	}

	/** Bundle size in bytes for 64-bit encodings, 0 for 128-bit ones. */
	public static int bundleSize(Program program) {
		String v = program.getLanguageID().getIdAsString();
		if (v.endsWith(":SM35")) {
			return 64;
		}
		if (v.endsWith(":SM52") || v.endsWith(":SM60")) {
			return 32;
		}
		return 0;
	}
}
