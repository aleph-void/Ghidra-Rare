/* ###
 * Ghidra-Rare IA-64 module (MIT).
 *
 * ELF extension for IA-64: the global pointer, functions from the unwind table, and names for
 * the import (PLT) stubs.
 */
package ghidra.app.util.bin.format.elf.extend;

import java.math.BigInteger;

import ghidra.app.util.bin.format.elf.*;
import ghidra.app.util.bin.format.elf.relocation.IA64GpUtil;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Program;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.util.exception.CancelledException;
import ghidra.util.task.TaskMonitor;

public class IA64_ElfExtension extends ElfExtension {

	public static final int EM_IA_64 = 50;

	public static final ElfProgramHeaderType PT_IA_64_ARCHEXT =
		new ElfProgramHeaderType(0x70000000, "PT_IA_64_ARCHEXT", "Architecture extensions");
	public static final ElfProgramHeaderType PT_IA_64_UNWIND =
		new ElfProgramHeaderType(0x70000001, "PT_IA_64_UNWIND", "Unwind table");

	public static final ElfSectionHeaderType SHT_IA_64_EXT =
		new ElfSectionHeaderType(0x70000000, "SHT_IA_64_EXT", "Architecture extensions");
	public static final ElfSectionHeaderType SHT_IA_64_UNWIND =
		new ElfSectionHeaderType(0x70000001, "SHT_IA_64_UNWIND", "Unwind table");

	public static final ElfDynamicType DT_IA_64_PLT_RESERVE = new ElfDynamicType(0x70000000,
		"DT_IA_64_PLT_RESERVE", "Reserved PLT descriptor area", ElfDynamicType.ElfDynamicValueType.ADDRESS);

	@Override
	public boolean canHandle(ElfHeader elf) {
		return elf.e_machine() == EM_IA_64;
	}

	@Override
	public boolean canHandle(ElfLoadHelper elfLoadHelper) {
		return "IA64".equals(elfLoadHelper.getProgram().getLanguage().getProcessor().toString());
	}

	@Override
	public String getDataTypeSuffix() {
		return "_IA64";
	}

	@Override
	public void processElf(ElfLoadHelper helper, TaskMonitor monitor) throws CancelledException {
		Long gp = IA64GpUtil.findGp(helper);
		if (gp != null) {
			setGp(helper, gp);
		}
		processUnwind(helper, monitor);
		if (gp != null) {
			namePltStubs(helper, gp, monitor);
		}
	}

	/** r1 holds the module's gp at every function entry: make it a known register value. */
	private void setGp(ElfLoadHelper helper, long gp) {
		Program program = helper.getProgram();
		Register r1 = program.getRegister("r1");
		ProgramContext ctx = program.getProgramContext();
		for (MemoryBlock b : program.getMemory().getBlocks()) {
			if (b.isExecute() && b.isInitialized() && b.getStart().isMemoryAddress()) {
				try {
					ctx.setValue(r1, b.getStart(), b.getEnd(), BigInteger.valueOf(gp));
				}
				catch (Exception e) {
					helper.log("Failed to set r1 (gp) on " + b.getName() + ": " + e.getMessage());
				}
			}
		}
		try {
			Address a = helper.getDefaultAddress(gp);
			if (program.getSymbolTable().getSymbols(a).length == 0 || program.getSymbolTable()
					.getGlobalSymbols("__gp").isEmpty()) {
				helper.createSymbol(a, "__gp", false, false, null);
			}
		}
		catch (Exception e) {
			// symbol is informational
		}
		helper.log("IA-64 gp (r1) = 0x" + Long.toHexString(gp));
	}

	private long textBase(ElfLoadHelper helper) {
		long base = Long.MAX_VALUE;
		for (ElfProgramHeader ph : helper.getElfHeader().getProgramHeaders()) {
			if (ph.getType() == ElfProgramHeaderConstants.PT_LOAD && ph.isExecute()) {
				base = Math.min(base, ph.getVirtualAddress());
			}
		}
		if (base == Long.MAX_VALUE) {
			return 0;
		}
		return base + helper.getImageBaseWordAdjustmentOffset();
	}

	/**
	 * The unwind table (SHT_IA_64_UNWIND) lists every function that has unwind information as
	 * {start, end, info} offsets relative to the text segment: create those functions.
	 */
	private void processUnwind(ElfLoadHelper helper, TaskMonitor monitor) throws CancelledException {
		ElfHeader elf = helper.getElfHeader();
		Program program = helper.getProgram();
		Memory mem = program.getMemory();
		boolean relocatable = elf.isRelocatable();
		long base = relocatable ? 0 : textBase(helper);
		int created = 0;
		for (ElfSectionHeader sh : elf.getSections()) {
			if (sh.getType() != SHT_IA_64_UNWIND.value) {
				continue;
			}
			Address start = helper.findLoadAddress(sh, 0);
			if (start == null) {
				continue;
			}
			long n = sh.getSize() / 24;
			for (long i = 0; i < n; i++) {
				monitor.checkCancelled();
				try {
					long fs = mem.getLong(start.add(24 * i));
					long fe = mem.getLong(start.add(24 * i + 8));
					if (fs == 0 && fe == 0) {
						continue;
					}
					long entry = relocatable ? fs : base + fs;
					Address a = helper.getDefaultAddress(entry);
					if ((a.getOffset() & 0xf) != 0 || mem.getBlock(a) == null ||
						!mem.getBlock(a).isExecute()) {
						continue;
					}
					if (program.getFunctionManager().getFunctionAt(a) == null) {
						helper.createOneByteFunction(null, a, false);
						created++;
					}
				}
				catch (Exception e) {
					break;
				}
			}
		}
		if (created > 0) {
			helper.log("IA-64 unwind table: created " + created + " functions");
		}
	}

	/** addl r15 = imm22, r1 in slot 0 of an import stub bundle -> imm22, or null */
	private static Long stubOffset(byte[] b) {
		BigInteger v = BigInteger.ZERO;
		for (int i = 15; i >= 0; i--) {
			v = v.shiftLeft(8).or(BigInteger.valueOf(b[i] & 0xff));
		}
		long slot = v.shiftRight(5).and(BigInteger.ONE.shiftLeft(41).subtract(BigInteger.ONE)).longValue();
		if ((slot >>> 37) != 9 || ((slot >>> 6) & 0x7f) != 15 || ((slot >>> 20) & 3) != 1) {
			return null;
		}
		long imm = (slot >>> 13) & 0x7f | ((slot >>> 27) & 0x1ff) << 7 | ((slot >>> 22) & 0x1f) << 16;
		if (((slot >>> 36) & 1) != 0) {
			imm -= 1L << 21;
		}
		return imm;
	}

	/**
	 * Import stubs load the function descriptor at gp + imm22 that an IPLT relocation fills in:
	 * name each stub after the relocation's symbol and make it a thunk of the import.
	 */
	private void namePltStubs(ElfLoadHelper helper, long gp, TaskMonitor monitor)
			throws CancelledException {
		ElfHeader elf = helper.getElfHeader();
		Program program = helper.getProgram();
		Memory mem = program.getMemory();
		java.util.Map<Long, String> byDescriptor = new java.util.HashMap<>();
		java.util.Set<String> external = new java.util.HashSet<>();
		long adjust = helper.getImageBaseWordAdjustmentOffset();
		for (ElfRelocationTable table : elf.getRelocationTables()) {
			ElfSymbolTable st = table.getAssociatedSymbolTable();
			for (ElfRelocation r : table.getRelocations()) {
				if (r.getType() != 0x81 && r.getType() != 0x80) {
					continue;
				}
				if (st == null) {
					continue;
				}
				ElfSymbol s = st.getSymbol(r.getSymbolIndex());
				if (s == null) {
					continue;
				}
				String name = s.getNameAsString();
				byDescriptor.put(r.getOffset() + adjust, name);
				if (s.getSectionHeaderIndex() == ElfSectionHeaderConstants.SHN_UNDEF) {
					external.add(name);
				}
			}
		}
		if (byDescriptor.isEmpty()) {
			return;
		}
		int named = 0;
		for (ElfSectionHeader sh : elf.getSections()) {
			if (!".plt".equals(sh.getNameAsString())) {
				continue;
			}
			Address start = helper.findLoadAddress(sh, 0);
			if (start == null) {
				continue;
			}
			byte[] b = new byte[16];
			for (long off = 0; off + 16 <= sh.getSize(); off += 16) {
				monitor.checkCancelled();
				try {
					Address a = start.add(off);
					mem.getBytes(a, b);
					Long imm = stubOffset(b);
					if (imm == null) {
						continue;
					}
					String name = byDescriptor.get(gp + imm);
					if (name == null) {
						continue;
					}
					if (external.contains(name)) {
						helper.createExternalFunctionLinkage(name, a, null);
					}
					else {
						Function f = helper.createOneByteFunction(name + "@plt", a, false);
						if (f == null) {
							continue;
						}
					}
					named++;
				}
				catch (Exception e) {
					helper.log("IA-64 PLT stub naming failed: " + e.getMessage());
					break;
				}
			}
		}
		if (named > 0) {
			helper.log("IA-64: named " + named + " import stubs");
		}
	}
}
