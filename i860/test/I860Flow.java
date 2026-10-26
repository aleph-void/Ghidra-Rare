// Flow disassembly dump for the i860 tests: disassembles from the given entry points following
// flow (as auto-analysis does) and prints each instruction with its dual-mode context.
// Script args: <outfile> <entry-hex>...
//@category Testing

import java.io.PrintStream;

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.Instruction;

public class I860Flow extends GhidraScript {
	private static int val(Instruction ins, Register r) {
		java.math.BigInteger v = ins.getValue(r, false);
		return v == null ? 0 : v.intValue();
	}

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = new PrintStream(args[0]);
		AddressSet starts = new AddressSet();
		for (int i = 1; i < args.length; i++) {
			starts.add(toAddr(Long.decode(args[i])));
		}
		new DisassembleCommand(starts, null, true).applyTo(currentProgram, monitor);
		Register dual = currentProgram.getRegister("dual");
		Register slot = currentProgram.getRegister("slot");
		for (Instruction ins : currentProgram.getListing().getInstructions(true)) {
			out.printf("%06x %s%s %s%n", ins.getAddress().getOffset(), val(ins, dual) == 1 ? "D" : "-",
				val(ins, slot) == 1 ? "1" : "0", ins);
		}
		out.close();
	}
}
