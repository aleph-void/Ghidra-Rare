// (From aleph-void/ghidra-sh, MIT.)  Prints each function's prototype and the storage of its parameters after a normal
// (auto-analyzed) import with DWARF, for test/dwarf-check.sh.   Script args: <out.txt>
//@category Testing

import java.io.PrintStream;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Parameter;

public class DwarfCheck extends GhidraScript {
	@Override
	protected void run() throws Exception {
		PrintStream out = new PrintStream(getScriptArgs()[0]);
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			StringBuilder sb = new StringBuilder(f.getSignature().getPrototypeString());
			for (Parameter p : f.getParameters()) {
				sb.append(" | ").append(p.getName()).append("@").append(p.getVariableStorage());
			}
			out.println(sb);
		}
		out.close();
	}
}
