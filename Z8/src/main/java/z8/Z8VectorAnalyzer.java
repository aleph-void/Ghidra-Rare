package z8;

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
 * Z8 interrupt vectors (Zilog UM0016): program memory 0000h-000Bh holds six big-endian 16-bit
 * handler addresses for IRQ0-IRQ5, and execution starts at 000Ch after reset. Each vector becomes
 * a pointer; a vector that holds an address past the table (and not FFFFh, erased EPROM) is
 * disassembled and made a function IRQn_handler. Unused vectors usually hold 0000h; they are left
 * as pointers and not followed, so the vector table is never decoded as code.
 */
public class Z8VectorAnalyzer extends AbstractAnalyzer {

	private static final String NAME = "Z8 Interrupt Vectors";
	private static final String DESCRIPTION =
		"Marks up the Z8 IRQ0-IRQ5 vector table at 0000h-000Bh and makes functions of the handlers.";

	public Z8VectorAnalyzer() {
		super(NAME, DESCRIPTION, AnalyzerType.BYTE_ANALYZER);
		setPriority(AnalysisPriority.FORMAT_ANALYSIS.before());
		setDefaultEnablement(true);
		setSupportsOneTimeAnalysis();
	}

	@Override
	public boolean canAnalyze(Program program) {
		return program.getLanguage()
				.getProcessor()
				.equals(Processor.findOrPossiblyCreateProcessor("Z8"));
	}

	@Override
	public boolean added(Program program, AddressSetView set, TaskMonitor monitor, MessageLog log)
			throws CancelledException {
		AddressSpace code = program.getAddressFactory().getAddressSpace("code");
		Memory mem = program.getMemory();
		Listing listing = program.getListing();
		FunctionManager fm = program.getFunctionManager();
		Address v0 = code.getAddress(0);
		Address v5 = code.getAddress(0xb);
		if (!mem.getAllInitializedAddressSet().contains(v0, v5)) {
			return true; // the image does not start at the vector table
		}
		for (Function f : fm.getFunctions(new AddressSet(v0, v5), true)) {
			fm.removeFunction(f.getEntryPoint());
		}
		listing.clearCodeUnits(v0, v5, false);
		PointerDataType p16 = new PointerDataType(null, 2, program.getDataTypeManager());
		Map<Address, String> handlers = new LinkedHashMap<>();
		for (int irq = 0; irq < 6; irq++) {
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
			if (w < 0xc || w == 0xffff) {
				continue; // unused or erased
			}
			Address t = code.getAddress(w);
			if (mem.getAllInitializedAddressSet().contains(t)) {
				handlers.putIfAbsent(t, "IRQ" + irq + "_handler");
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
