// Headless pre-analysis helper: assume cp / dp hold the values the XMOS runtime start-up code
// loads (the linker symbols _cp / _dp of a linked .xe tile image, or else the start of the
// ".cp" / ".dp" memory blocks) everywhere in the program, so that constant-pool calls
// (BLA cp[n]) and cp/dp-relative globals resolve during analysis.
//@category Testing

import java.math.BigInteger;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Symbol;

public class SetCpDp extends GhidraScript {

	@Override
	protected void run() throws Exception {
		ProgramContext ctx = currentProgram.getProgramContext();
		for (String name : new String[] { "cp", "dp" }) {
			Long val = null;
			for (Symbol s : currentProgram.getSymbolTable().getGlobalSymbols("_" + name)) {
				val = s.getAddress().getOffset();
			}
			MemoryBlock b = currentProgram.getMemory().getBlock("." + name);
			if (val == null && b != null) {
				val = b.getStart().getOffset();
			}
			if (val == null) {
				continue;
			}
			Register r = currentProgram.getRegister(name);
			for (MemoryBlock code : currentProgram.getMemory().getBlocks()) {
				if (code.isExecute()) {
					ctx.setValue(r, code.getStart(), code.getEnd(),
						BigInteger.valueOf(val));
				}
			}
			println(name + " = " + Long.toHexString(val));
		}
	}
}
