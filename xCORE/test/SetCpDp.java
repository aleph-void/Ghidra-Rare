// Headless pre-analysis helper: assume cp / dp hold the start addresses of the ".cp" / ".dp"
// memory blocks (as set up by the XMOS runtime start-up code) everywhere in the program, so
// that constant-pool calls (BLA cp[n]) and dp-relative globals resolve during analysis.
//@category Testing

import java.math.BigInteger;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.MemoryBlock;

public class SetCpDp extends GhidraScript {

	@Override
	protected void run() throws Exception {
		ProgramContext ctx = currentProgram.getProgramContext();
		for (String name : new String[] { "cp", "dp" }) {
			MemoryBlock b = currentProgram.getMemory().getBlock("." + name);
			if (b == null) {
				continue;
			}
			Register r = currentProgram.getRegister(name);
			for (MemoryBlock code : currentProgram.getMemory().getBlocks()) {
				if (code.isExecute()) {
					ctx.setValue(r, code.getStart(), code.getEnd(),
						BigInteger.valueOf(b.getStart().getOffset()));
				}
			}
			println(name + " = " + b.getStart());
		}
	}
}
