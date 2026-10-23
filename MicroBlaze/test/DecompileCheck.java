// Post-analysis sanity check: lists functions and decompiles them.
// Script args: <outfile> [function names...]  (no names = all functions)
//@category Testing

import java.io.PrintStream;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Set;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Bookmark;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;

public class DecompileCheck extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = new PrintStream(args[0]);
		Set<String> want = new HashSet<>(Arrays.asList(args).subList(1, args.length));

		out.printf("language: %s  compiler: %s%n", currentProgram.getLanguageID(),
			currentProgram.getCompilerSpec().getCompilerSpecID());
		int ninstr = 0;
		for (Instruction i : currentProgram.getListing().getInstructions(true)) {
			ninstr++;
		}
		out.printf("instructions: %d  functions: %d  bookmarked errors: %d%n", ninstr,
			currentProgram.getFunctionManager().getFunctionCount(),
			currentProgram.getBookmarkManager().getBookmarkCount("Error"));

		Iterator<Bookmark> bi = currentProgram.getBookmarkManager().getBookmarksIterator("Error");
		while (bi.hasNext()) {
			Bookmark b = bi.next();
			out.printf("  error bookmark @ %s: %s %s%n", b.getAddress(), b.getCategory(), b.getComment());
		}

		DecompInterface dec = new DecompInterface();
		dec.openProgram(currentProgram);
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			if (!want.isEmpty() && !want.contains(f.getName())) {
				continue;
			}
			out.printf("%n==== %s @ %s  (%s)%n", f.getName(), f.getEntryPoint(),
				f.getSignature().getPrototypeString());
			DecompileResults r = dec.decompileFunction(f, 60, monitor);
			if (r.decompileCompleted()) {
				out.println(r.getDecompiledFunction().getC());
			}
			else {
				out.println("DECOMPILE FAILED: " + r.getErrorMessage());
			}
		}
		dec.dispose();
		out.close();
	}
}
