// Post-analysis sanity check: report language/instruction statistics and decompile selected
// functions of an imported C7x ELF.
// Script args: <outfile> [all] [max=N] [function names...]
//   names given: decompile (and print) only those, unless "all" is also given (then every function is
//   decompiled and only the named ones are printed).  No names: decompile every function.
//@category Testing

import java.io.PrintStream;
import java.util.*;

import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;

public class DecompC7x extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = args.length > 0 ? new PrintStream(args[0]) : System.out;
		Set<String> want = new HashSet<>();
		int max = Integer.MAX_VALUE;
		boolean all = false;
		for (int i = 1; i < args.length; i++) {
			if (args[i].equals("all")) {
				all = true;
			}
			else if (args[i].startsWith("max=")) {
				max = Integer.parseInt(args[i].substring(4));
			}
			else {
				want.add(args[i]);
			}
		}
		Listing listing = currentProgram.getListing();
		out.println("LANGUAGE " + currentProgram.getLanguageID() + " compiler " +
			currentProgram.getCompilerSpec().getCompilerSpecID());
		long ninstr = listing.getNumInstructions();
		int nfunc = currentProgram.getFunctionManager().getFunctionCount();
		out.println("INSTRUCTIONS " + ninstr + " FUNCTIONS " + nfunc);
		int bad = currentProgram.getBookmarkManager().getBookmarkCount("Error");
		out.println("ERROR_BOOKMARKS " + bad);
		java.util.Iterator<ghidra.program.model.listing.Bookmark> bi =
			currentProgram.getBookmarkManager().getBookmarksIterator("Error");
		for (int i = 0; i < 20 && bi.hasNext(); i++) {
			ghidra.program.model.listing.Bookmark b = bi.next();
			out.println("  " + b.getAddress() + " " + b.getCategory() + ": " + b.getComment());
		}
		long exbytes = 0, inbytes = 0;
		for (ghidra.program.model.mem.MemoryBlock blk : currentProgram.getMemory().getBlocks()) {
			if (blk.isExecute() && blk.isInitialized()) {
				exbytes += blk.getSize();
				for (Instruction ins : listing.getInstructions(
					new ghidra.program.model.address.AddressSet(blk.getStart(), blk.getEnd()), true)) {
					inbytes += ins.getLength();
				}
			}
		}
		out.println("EXEC_BYTES " + exbytes + " IN_INSTRUCTIONS " + inbytes);

		DecompInterface ifc = new DecompInterface();
		ifc.openProgram(currentProgram);
		int ok = 0, fail = 0;
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			if (!all && !want.isEmpty() && !want.contains(f.getName())) {
				continue;
			}
			if (ok + fail >= max) {
				break;
			}
			DecompileResults res = ifc.decompileFunction(f, 60, monitor);
			if (res != null && res.decompileCompleted() && res.getDecompiledFunction() != null) {
				ok++;
				if (want.contains(f.getName())) {
					out.println("==== " + f.getName() + " @ " + f.getEntryPoint());
					out.println(res.getDecompiledFunction().getC());
				}
			}
			else {
				fail++;
				out.println("FAILED " + f.getName() + ": " + (res == null ? "null" : res.getErrorMessage()));
			}
		}
		out.println("DECOMPILED " + ok + " FAILED " + fail);
		ifc.dispose();
		if (out != System.out) {
			out.close();
		}
	}
}
