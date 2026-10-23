// Post-analysis sanity check for PRU ELF imports: prints the language, the
// memory map, every function with its call/flow summary, and decompiler output.
// Script args: [outfile]
//@category Testing

import java.io.PrintStream;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;

public class PruElfCheck extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = args.length > 0 ? new PrintStream(args[0]) : System.out;
		out.println("language: " + currentProgram.getLanguageID() + " / " +
			currentProgram.getCompilerSpec().getCompilerSpecID());
		for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
			out.printf("block %-20s %s - %s %s%s%s%n", b.getName(), b.getStart(), b.getEnd(),
				b.isRead() ? "r" : "-", b.isWrite() ? "w" : "-", b.isExecute() ? "x" : "-");
		}
		int nins = 0;
		for (Instruction i : currentProgram.getListing().getInstructions(true)) {
			nins++;
		}
		out.println("instructions: " + nins);
		DecompInterface ifc = new DecompInterface();
		ifc.openProgram(currentProgram);
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			out.println("==== " + f.getName() + " @ " + f.getEntryPoint() + "  " + f.getSignature());
			for (Instruction i : currentProgram.getListing().getInstructions(f.getBody(), true)) {
				StringBuilder refs = new StringBuilder();
				for (Reference r : i.getReferencesFrom()) {
					refs.append(" ").append(r.getReferenceType()).append("->").append(r.getToAddress());
				}
				out.printf("  %s  %-36s%s%n", i.getAddress(), i.toString(), refs);
			}
			DecompileResults res = ifc.decompileFunction(f, 60, monitor);
			if (res.decompileCompleted()) {
				out.println(res.getDecompiledFunction().getC());
			}
			else {
				out.println("  DECOMPILE FAILED: " + res.getErrorMessage());
			}
		}
		ifc.dispose();
		out.flush();
		if (out != System.out) {
			out.close();
		}
	}
}
