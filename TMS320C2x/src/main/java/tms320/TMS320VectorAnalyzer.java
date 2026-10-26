package tms320;

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.services.AbstractAnalyzer;
import ghidra.app.services.AnalysisPriority;
import ghidra.app.services.AnalyzerType;
import ghidra.app.util.importer.MessageLog;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSetView;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.lang.Processor;
import ghidra.program.model.listing.Program;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.symbol.SourceType;
import ghidra.util.exception.CancelledException;
import ghidra.util.task.TaskMonitor;

/**
 * Disassembles the TMS320C2x/C5x interrupt vectors that hold an unconditional branch.
 * <p>
 * Each vector is a two-word slot in program memory, normally a branch to the handler: C2x
 * B pma (FF80h) at the C25 vector addresses (SPRU014C Table 3-3), C5x B (7980h) or BD (7D80h) in
 * the slots of SPRU056D Table 4-14 (IPTR assumed 0). Slots holding anything else are
 * left alone, so data at those addresses is not turned into code. The branch targets become
 * functions named after the vector.
 */
public class TMS320VectorAnalyzer extends AbstractAnalyzer {

	private static final String NAME = "TMS320C2x/C5x Interrupt Vectors";
	private static final String DESCRIPTION =
		"Disassembles interrupt-vector slots that hold an unconditional branch and creates the " +
			"handler functions.";

	private static final String[] C2X = { "RS", "INT0", "INT1", "INT2" };
	private static final int[] C2X_EXTRA = { 0x18, 0x1A, 0x1C, 0x1E };
	private static final String[] C2X_EXTRA_NAMES = { "TINT", "RINT", "XINT", "TRAP" };
	private static final int[] C5X_SLOTS =
		{ 0x02, 0x04, 0x06, 0x08, 0x0A, 0x0C, 0x0E, 0x10, 0x12, 0x18, 0x22, 0x24 };
	private static final String[] C5X =
		{ "INT1", "INT2", "INT3", "TINT", "RINT", "XINT", "TRNT", "TXNT", "INT4", "HINT", "TRAP", "NMI" };

	public TMS320VectorAnalyzer() {
		super(NAME, DESCRIPTION, AnalyzerType.BYTE_ANALYZER);
		setPriority(AnalysisPriority.FORMAT_ANALYSIS.before());
		setDefaultEnablement(true);
		setSupportsOneTimeAnalysis();
	}

	private static boolean isC5x(Program p) {
		return p.getLanguage().getProcessor().equals(Processor.findOrPossiblyCreateProcessor("TMS320C5x"));
	}

	@Override
	public boolean canAnalyze(Program program) {
		Processor p = program.getLanguage().getProcessor();
		return p.equals(Processor.findOrPossiblyCreateProcessor("TMS320C2x")) || isC5x(program);
	}

	private int word(Memory mem, Address a) throws MemoryAccessException {
		byte[] b = new byte[2];
		mem.getBytes(a, b);
		return mem.isBigEndian() ? ((b[0] & 0xff) << 8) | (b[1] & 0xff)
				: ((b[1] & 0xff) << 8) | (b[0] & 0xff);
	}

	private void vector(Program program, AddressSpace prog, int slot, String name,
			boolean c5x, TaskMonitor monitor, MessageLog log) {
		Memory mem = program.getMemory();
		Address a = prog.getAddress(2L * slot);
		Address a2 = prog.getAddress(2L * (slot + 1));
		if (!mem.getLoadedAndInitializedAddressSet().contains(a) ||
			!mem.getLoadedAndInitializedAddressSet().contains(a2)) {
			return;
		}
		try {
			int w = word(mem, a);
			boolean branch = c5x ? (w == 0x7980 || w == 0x7D80) : w == 0xFF80;
			if (!branch) {
				return;
			}
			Address target = prog.getAddress(2L * word(mem, a2));
			if (!mem.getLoadedAndInitializedAddressSet().contains(target)) {
				return;
			}
			if (program.getListing().getInstructionAt(a) == null) {
				new DisassembleCommand(a, null, true).applyTo(program, monitor);
			}
			if (program.getFunctionManager().getFunctionAt(target) == null) {
				new CreateFunctionCmd(name + "_ISR", target, null, SourceType.ANALYSIS)
						.applyTo(program, monitor);
			}
		}
		catch (MemoryAccessException e) {
			log.appendMsg(NAME + ": cannot read vector " + name + " at " + a);
		}
	}

	@Override
	public boolean added(Program program, AddressSetView set, TaskMonitor monitor, MessageLog log)
			throws CancelledException {
		AddressSpace prog = program.getAddressFactory().getAddressSpace("prog");
		if (isC5x(program)) {
			for (int i = 0; i < C5X.length; i++) {
				vector(program, prog, C5X_SLOTS[i], C5X[i], true, monitor, log);
			}
			for (int slot = 0x28; slot < 0x40; slot += 2) {     // software interrupts (INTR k)
				vector(program, prog, slot, String.format("SWI%02X", slot), true, monitor, log);
			}
		}
		else {
			for (int i = 1; i < C2X.length; i++) {
				vector(program, prog, 2 * i, C2X[i], false, monitor, log);
			}
			for (int i = 0; i < C2X_EXTRA.length; i++) {
				vector(program, prog, C2X_EXTRA[i], C2X_EXTRA_NAMES[i], false, monitor, log);
			}
		}
		return true;
	}
}
