// Headless sanity check: print language, function count, bad-instruction bookmarks and the
// decompilation of selected (or the first N) functions.
// Script args: <outfile> [maxFunctions] [nameRegex] [maxInstructionsListed]
//@category Testing

import java.io.PrintStream;
import java.util.regex.Pattern;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Bookmark;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;

public class DecompileDump extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = new PrintStream(args[0]);
		int max = args.length > 1 ? Integer.parseInt(args[1]) : 20;
		Pattern pat = args.length > 2 && !args[2].isEmpty() ? Pattern.compile(args[2]) : null;
		int maxIns = args.length > 3 ? Integer.parseInt(args[3]) : 60;

		out.printf("language %s / %s%n", currentProgram.getLanguageID(),
			currentProgram.getCompilerSpec().getCompilerSpecID());
		out.printf("functions %d, instructions %d%n", currentProgram.getFunctionManager().getFunctionCount(),
			currentProgram.getListing().getNumInstructions());
		int errs = 0;
		for (java.util.Iterator<Bookmark> it = currentProgram.getBookmarkManager().getBookmarksIterator("Error"); it.hasNext();) {
			Bookmark b = it.next();
			if (errs++ < 15) {
				out.printf("error bookmark %s: %s%n", b.getAddress(), b.getComment());
			}
		}
		out.printf("error bookmarks %d%n", errs);

		DecompInterface ifc = new DecompInterface();
		ifc.openProgram(currentProgram);
		int n = 0;
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			if (pat != null && !pat.matcher(f.getName()).find()) {
				continue;
			}
			if (n++ >= max) {
				break;
			}
			out.printf("%n==== %s @ %s%n", f.getName(), f.getEntryPoint());
			int k = 0;
			for (Instruction ins : currentProgram.getListing().getInstructions(f.getBody(), true)) {
				if (k++ >= maxIns) {
					out.println("    ...");
					break;
				}
				out.printf("    %s  %s%n", ins.getAddress(), ins);
			}
			DecompileResults r = ifc.decompileFunction(f, 60, monitor);
			if (r.decompileCompleted()) {
				out.println(r.getDecompiledFunction().getC());
			}
			else {
				out.println("DECOMPILE FAILED: " + r.getErrorMessage());
			}
		}
		ifc.dispose();
		out.close();
	}
}
