/* Ghidra-Rare PRU module - MIT licensed */
package ghidra.app.util.bin.format.elf.extend;

import java.math.BigInteger;
import java.util.TreeMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import ghidra.app.util.bin.format.elf.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Program;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.util.exception.CancelledException;
import ghidra.util.task.TaskMonitor;

/**
 * ELF load tweaks for TI PRU (EM_TI_PRU = 144) executables.
 * <ul>
 * <li><b>Entry point 0.</b> The PRU starts at code address 0 by default, and TI firmware is
 * usually linked with {@code e_entry = 0}. Ghidra's ELF loader ignores a zero entry point,
 * so a stripped image would get no function and no disassembly at all. This extension
 * creates the entry function at code:0 in that case.</li>
 * <li><b>TI local labels.</b> TI clpru/asmpru emit compiler and assembler local labels
 * ({@code $C$L12}, {@code $run$exit}, macro labels {@code $M$45$}, ...) as zero-size
 * {@code STT_FUNC} symbols. Names starting with '$' can never be C functions, so these
 * become plain labels instead of one-instruction pseudo-functions.</li>
 * <li><b>Constant table.</b> TI links record the base address of every constant-table
 * entry they use as {@code __PRU_CREG_BASE_C<n>} absolute symbols. Their values are applied
 * to the {@code c<n>} registers over the code, so LBCO/SBCO resolve to data addresses
 * without running PRUSetConstantTable.java.</li>
 * </ul>
 */
public class PRU_ElfExtension extends ElfExtension {

	public static final short EM_TI_PRU = 144;

	@Override
	public boolean canHandle(ElfHeader elf) {
		return elf.e_machine() == EM_TI_PRU && elf.is32Bit();
	}

	@Override
	public boolean canHandle(ElfLoadHelper elfLoadHelper) {
		return canHandle(elfLoadHelper.getElfHeader()) &&
			"PRU".equals(elfLoadHelper.getProgram().getLanguage().getProcessor().toString());
	}

	@Override
	public String getDataTypeSuffix() {
		return "_PRU";
	}

	@Override
	public Address evaluateElfSymbol(ElfLoadHelper elfLoadHelper, ElfSymbol elfSymbol,
			Address address, boolean isExternal) {
		String name = elfSymbol.getNameAsString();
		if (isExternal || elfSymbol.getType() != ElfSymbol.STT_FUNC || !elfSymbol.isLocal() ||
			elfSymbol.getSize() != 0 || name == null || !name.startsWith("$") ||
			!isCode(elfLoadHelper, address)) {
			return address;
		}
		try {
			elfLoadHelper.createSymbol(address, name, false, false, null);
		}
		catch (Exception e) {
			elfLoadHelper.log("PRU: could not create label " + name + ": " + e.getMessage());
		}
		elfLoadHelper.setElfSymbolAddress(elfSymbol, address);
		return null; // handled: label only, no function
	}

	private static final Pattern CREG_BASE = Pattern.compile("__PRU_CREG_BASE_C(\\d+)");

	@Override
	public void processElf(ElfLoadHelper elfLoadHelper, TaskMonitor monitor)
			throws CancelledException {
		applyConstantTable(elfLoadHelper);
		createZeroEntry(elfLoadHelper);
	}

	private void applyConstantTable(ElfLoadHelper elfLoadHelper) {
		Program program = elfLoadHelper.getProgram();
		TreeMap<Integer, Long> bases = new TreeMap<>();
		for (ElfSymbolTable st : elfLoadHelper.getElfHeader().getSymbolTables()) {
			for (ElfSymbol sym : st.getSymbols()) {
				String name = sym.getNameAsString();
				if (name == null || !sym.isAbsolute()) {
					continue;
				}
				Matcher m = CREG_BASE.matcher(name);
				if (m.matches()) {
					bases.put(Integer.parseInt(m.group(1)), sym.getValue() & 0xffffffffL);
				}
			}
		}
		for (var e : bases.entrySet()) {
			Register reg = program.getRegister("c" + e.getKey());
			if (reg == null) {
				continue;
			}
			for (MemoryBlock b : program.getMemory().getBlocks()) {
				if (!b.isExecute() || !b.isInitialized()) {
					continue;
				}
				try {
					program.getProgramContext()
							.setValue(reg, b.getStart(), b.getEnd(),
								BigInteger.valueOf(e.getValue()));
				}
				catch (Exception ex) {
					elfLoadHelper.log("PRU: could not set " + reg + ": " + ex.getMessage());
				}
			}
			elfLoadHelper.log(String.format("PRU: c%d = 0x%x (from __PRU_CREG_BASE_C%d)",
				e.getKey(), e.getValue(), e.getKey()));
		}
	}

	private void createZeroEntry(ElfLoadHelper elfLoadHelper) {
		ElfHeader elf = elfLoadHelper.getElfHeader();
		if (!elf.isExecutable() || elf.e_entry() != 0) {
			return; // a non-zero entry is handled by the ELF loader
		}
		Address entry = elfLoadHelper.getProgram()
				.getAddressFactory()
				.getDefaultAddressSpace()
				.getAddress(0);
		if (!isCode(elfLoadHelper, entry)) {
			return;
		}
		Function f = elfLoadHelper.getProgram().getFunctionManager().getFunctionAt(entry);
		if (f != null) {
			elfLoadHelper.getProgram().getSymbolTable().addExternalEntryPoint(entry);
			return;
		}
		elfLoadHelper.createOneByteFunction("entry", entry, true);
	}

	private static boolean isCode(ElfLoadHelper elfLoadHelper, Address address) {
		if (address == null || !address.isMemoryAddress()) {
			return false;
		}
		MemoryBlock b = elfLoadHelper.getProgram().getMemory().getBlock(address);
		return b != null && b.isExecute() && b.isInitialized();
	}
}
