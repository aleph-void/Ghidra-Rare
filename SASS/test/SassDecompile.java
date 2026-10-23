// Headless sanity check for SASS imports: prints the language chosen for the
// program, instruction / function counts, undecodable bytes in executable blocks,
// and decompiles functions (C output written to the file given as script arg 1).
// Script args: [outfile] [maxFunctions]
//@category Testing

import java.io.PrintStream;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.mem.MemoryBlock;

public class SassDecompile extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = args.length > 0 ? new PrintStream(args[0]) : System.out;
		int max = args.length > 1 ? Integer.parseInt(args[1]) : 50;

		println("SASS-CHECK language=" + currentProgram.getLanguageID() + " compiler=" +
			currentProgram.getCompilerSpec().getCompilerSpecID());
		long insns = 0;
		InstructionIterator it = currentProgram.getListing().getInstructions(true);
		while (it.hasNext()) {
			it.next();
			insns++;
		}
		long execBytes = 0;
		for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
			if (b.isExecute() && b.isInitialized()) {
				execBytes += b.getSize();
			}
		}
		int nf = currentProgram.getFunctionManager().getFunctionCount();
		println("SASS-CHECK instructions=" + insns + " exec_bytes=" + execBytes + " functions=" + nf);

		DecompInterface di = new DecompInterface();
		di.openProgram(currentProgram);
		int ok = 0, fail = 0, n = 0;
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			if (n++ >= max || monitor.isCancelled()) {
				break;
			}
			DecompileResults r = di.decompileFunction(f, 60, monitor);
			if (r != null && r.decompileCompleted() && r.getDecompiledFunction() != null) {
				ok++;
				out.println("// ---- " + f.getName() + " @ " + f.getEntryPoint());
				out.println(r.getDecompiledFunction().getC());
			}
			else {
				fail++;
				out.println("// ---- " + f.getName() + " FAILED: " +
					(r == null ? "null" : r.getErrorMessage()));
			}
		}
		di.dispose();
		println("SASS-CHECK decompiled_ok=" + ok + " decompile_failed=" + fail);
		if (out != System.out) {
			out.close();
		}
	}
}
