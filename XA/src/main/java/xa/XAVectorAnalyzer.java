package xa;

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
import ghidra.program.model.data.WordDataType;
import ghidra.program.model.lang.Processor;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.listing.Program;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.util.CodeUnitInsertionException;
import ghidra.util.exception.CancelledException;
import ghidra.util.task.TaskMonitor;

/**
 * XA interrupt vector table (XA User Guide 4.8.2): code memory 0000h-011Bh holds 71 entries of
 * two little-endian words, the PSW loaded for the handler and the handler address (segment 0,
 * word aligned). Entries 0-15 are exceptions (0 = reset), 16-31 TRAP 0-15, 32-63 event
 * interrupts (39 = NMI on the core), 64-70 software interrupts. Each entry becomes a PSW word and
 * a pointer; an entry whose address is even, not FFFFh (erased EPROM) or 0000h and lies in
 * initialized memory outside the table is disassembled and made a function. The reset handler
 * becomes an entry point.
 */
public class XAVectorAnalyzer extends AbstractAnalyzer {

	private static final String NAME = "XA Interrupt Vectors";
	private static final String DESCRIPTION =
		"Marks up the XA exception/trap/interrupt vector table at 0000h-011Bh and makes functions of the handlers.";
	private static final int ENTRIES = 71;
	private static final int TABLE_END = ENTRIES * 4;

	public XAVectorAnalyzer() {
		super(NAME, DESCRIPTION, AnalyzerType.BYTE_ANALYZER);
		setPriority(AnalysisPriority.FORMAT_ANALYSIS.before());
		setDefaultEnablement(true);
		setSupportsOneTimeAnalysis();
	}

	@Override
	public boolean canAnalyze(Program program) {
		return program.getLanguage()
				.getProcessor()
				.equals(Processor.findOrPossiblyCreateProcessor("XA"));
	}

	static String vectorName(int i) {
		String[] exc = { "reset", "breakpoint", "trace", "stack_overflow", "divide_by_zero",
			"user_reti" };
		if (i < exc.length) {
			return exc[i];
		}
		if (i < 16) {
			return "exception" + i;
		}
		if (i < 32) {
			return "trap" + (i - 16);
		}
		if (i == 39) {
			return "nmi";
		}
		if (i < 64) {
			return "event" + (i - 32);
		}
		return "swi" + (i - 63);
	}

	@Override
	public boolean added(Program program, AddressSetView set, TaskMonitor monitor, MessageLog log)
			throws CancelledException {
		AddressSpace code = program.getAddressFactory().getAddressSpace("code");
		Memory mem = program.getMemory();
		Listing listing = program.getListing();
		FunctionManager fm = program.getFunctionManager();
		AddressSetView init = mem.getAllInitializedAddressSet();
		Address v0 = code.getAddress(0);
		if (!init.contains(v0, code.getAddress(3))) {
			return true; // the image does not start at the vector table
		}
		PointerDataType p16 = new PointerDataType(null, 2, program.getDataTypeManager());
		Map<Address, String> handlers = new LinkedHashMap<>();
		for (int i = 0; i < ENTRIES; i++) {
			monitor.checkCancelled();
			Address ve = code.getAddress(4L * i);
			if (!init.contains(ve, ve.add(3))) {
				break;
			}
			int w;
			try {
				w = mem.getShort(ve.add(2), false) & 0xffff;
			}
			catch (MemoryAccessException e) {
				continue;
			}
			boolean used = w != 0xffff && w != 0 && (w & 1) == 0 && w >= TABLE_END &&
				init.contains(code.getAddress(w));
			if (!used) {
				continue;
			}
			try {
				for (Function f : fm.getFunctions(new AddressSet(ve, ve.add(3)), true)) {
					fm.removeFunction(f.getEntryPoint());
				}
				listing.clearCodeUnits(ve, ve.add(3), false);
				DataUtilities.createData(program, ve, WordDataType.dataType, 2, false,
					DataUtilities.ClearDataMode.CLEAR_ALL_CONFLICT_DATA);
				DataUtilities.createData(program, ve.add(2), p16, 2, false,
					DataUtilities.ClearDataMode.CLEAR_ALL_CONFLICT_DATA);
			}
			catch (CodeUnitInsertionException | RuntimeException e) {
				// leave the bytes as they are
			}
			handlers.putIfAbsent(code.getAddress(w), vectorName(i));
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
			if (e.getValue().equals("reset")) {
				program.getSymbolTable().addExternalEntryPoint(t);
			}
		}
		return true;
	}
}
