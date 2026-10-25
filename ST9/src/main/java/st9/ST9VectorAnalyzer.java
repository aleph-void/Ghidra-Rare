package st9;

import java.util.LinkedHashMap;
import java.util.Map;

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.services.AbstractAnalyzer;
import ghidra.app.services.AnalysisPriority;
import ghidra.app.services.AnalyzerType;
import ghidra.app.util.importer.MessageLog;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.address.AddressSetView;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.data.DataUtilities;
import ghidra.program.model.data.PointerDataType;
import ghidra.program.model.lang.Processor;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.listing.Program;
import ghidra.program.model.util.CodeUnitInsertionException;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.symbol.SourceType;
import ghidra.util.exception.CancelledException;
import ghidra.util.task.TaskMonitor;

/**
 * Mark up the three fixed ST9 vectors: reset at 0000h, divide-by-zero at 0002h and the
 * top-priority interrupt at 0004h. Other vector locations are selected by peripheral control
 * registers, so this analyzer does not assume that every pointer in the first 256 bytes is used.
 */
public class ST9VectorAnalyzer extends AbstractAnalyzer {

	private static final String NAME = "ST9 Fixed Vectors";
	private static final String DESCRIPTION =
		"Marks up the ST9 reset, divide-by-zero and top-priority interrupt vectors.";

	public ST9VectorAnalyzer() {
		super(NAME, DESCRIPTION, AnalyzerType.BYTE_ANALYZER);
		setPriority(AnalysisPriority.FORMAT_ANALYSIS.before());
		setDefaultEnablement(true);
		setSupportsOneTimeAnalysis();
	}

	@Override
	public boolean canAnalyze(Program program) {
		return program.getLanguage()
				.getProcessor()
				.equals(Processor.findOrPossiblyCreateProcessor("ST9"));
	}

	@Override
	public boolean added(Program program, AddressSetView set, TaskMonitor monitor, MessageLog log)
			throws CancelledException {
		AddressSpace code = program.getAddressFactory().getAddressSpace("code");
		Memory mem = program.getMemory();
		Listing listing = program.getListing();
		FunctionManager fm = program.getFunctionManager();
		Address v0 = code.getAddress(0);
		Address v5 = code.getAddress(5);
		if (!mem.getAllInitializedAddressSet().contains(v0, v5)) {
			return true; // the image does not start at the vector table
		}
		for (Function f : fm.getFunctions(new AddressSet(v0, v5), true)) {
			fm.removeFunction(f.getEntryPoint());
		}
		listing.clearCodeUnits(v0, v5, false);
		PointerDataType p16 = new PointerDataType(null, 2, program.getDataTypeManager());
		Map<Address, String> handlers = new LinkedHashMap<>();
		for (int irq = 0; irq < 3; irq++) {
			monitor.checkCancelled();
			Address va = code.getAddress(2 * irq);
			int w;
			try {
				w = mem.getShort(va) & 0xffff;
				DataUtilities.createData(program, va, p16, 2, false,
					DataUtilities.ClearDataMode.CLEAR_ALL_CONFLICT_DATA);
			}
			catch (MemoryAccessException | CodeUnitInsertionException | RuntimeException e) {
				continue;
			}
			if (w < 6 || w == 0xffff) {
				continue; // unused or erased
			}
			Address t = code.getAddress(w);
			if (mem.getAllInitializedAddressSet().contains(t)) {
				handlers.putIfAbsent(t, new String[] { "RESET", "DIVZERO_handler", "TOPLEVEL_handler" }[irq]);
			}
		}
		if (handlers.isEmpty()) {
			return true;
		}
		AddressSet targets = new AddressSet();
		handlers.keySet().forEach(targets::add);
		new DisassembleCommand(targets, null, true).applyTo(program, monitor);
		for (Map.Entry<Address, String> e : handlers.entrySet()) {
			Address t = e.getKey();
			if (listing.getInstructionAt(t) == null) {
				continue;
			}
			if (fm.getFunctionAt(t) == null) {
				new CreateFunctionCmd(t).applyTo(program, monitor);
			}
			Function f = fm.getFunctionAt(t);
			if (f != null && f.getSymbol().getSource() == SourceType.DEFAULT) {
				try {
					f.setName(e.getValue(), SourceType.ANALYSIS);
				}
				catch (Exception ex) {
					// keep the default name
				}
			}
		}
		return true;
	}
}
