// Real-binary check for PRU ELF imports (run as -postScript after auto-analysis).
// Writes three files with the given prefix:
//   <prefix>.summary  language, counts (functions, instructions, code coverage,
//                     bookmarks, decompile failures/timeouts/warnings)
//   <prefix>.dis      "<byte-addr-hex> <word-hex> <instruction>" for every
//                     instruction the analysis created in executable code blocks
//                     (same format as PruDumpDisasm, for test/compare.py)
//   <prefix>.c        listing + decompiler output of every function
// Script args: <prefix> [decompile-timeout-seconds]
//@category Testing

import java.io.PrintStream;
import java.util.Map;
import java.util.TreeMap;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Bookmark;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.MemoryBlock;

public class PruRealCheck extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		String prefix = args[0];
		int timeout = args.length > 1 ? Integer.parseInt(args[1]) : 60;
		PrintStream sum = new PrintStream(prefix + ".summary");
		PrintStream dis = new PrintStream(prefix + ".dis");
		PrintStream cout = new PrintStream(prefix + ".c");

		sum.println("language: " + currentProgram.getLanguageID() + " / " +
			currentProgram.getCompilerSpec().getCompilerSpecID());

		long codeWords = 0, insWords = 0;
		int nins = 0;
		for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
			if (!b.isInitialized() || !b.isExecute()) {
				continue;
			}
			codeWords += b.getSize() / 4;
			for (Address a = b.getStart(); a.compareTo(b.getEnd()) <= 0; a = a.add(4)) {
				Instruction i = currentProgram.getListing().getInstructionAt(a);
				if (i == null) {
					continue;
				}
				insWords++;
				byte[] w = i.getBytes();
				StringBuilder hex = new StringBuilder();
				for (int k = w.length - 1; k >= 0; k--) {
					hex.append(String.format("%02x", w[k] & 0xff));
				}
				dis.printf("%08x %s %s%n", a.getOffset(), hex, i.toString());
				if (a.add(3).compareTo(b.getEnd()) >= 0) {
					break;
				}
			}
		}
		for (Instruction i : currentProgram.getListing().getInstructions(true)) {
			nins++;
		}

		Map<String, Integer> bm = new TreeMap<>();
		java.util.Iterator<Bookmark> it = currentProgram.getBookmarkManager().getBookmarksIterator();
		while (it.hasNext()) {
			Bookmark b = it.next();
			if (b.getTypeString().equals("Error") || b.getTypeString().equals("Warning")) {
				String k = b.getTypeString() + "/" + b.getCategory();
				bm.merge(k, 1, Integer::sum);
				sum.println("bookmark " + k + " @ " + b.getAddress() + ": " + b.getComment());
			}
		}

		DecompInterface ifc = new DecompInterface();
		DecompileOptions opts = new DecompileOptions();
		ifc.setOptions(opts);
		ifc.openProgram(currentProgram);
		int nf = 0, fail = 0, tmo = 0, warnFns = 0, badFns = 0;
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			if (f.isThunk() || f.isExternal()) {
				continue;
			}
			nf++;
			cout.println("==== " + f.getName() + " @ " + f.getEntryPoint() + "  " + f.getSignature());
			for (Instruction i : currentProgram.getListing().getInstructions(f.getBody(), true)) {
				cout.printf("  %s  %s%n", i.getAddress(), i.toString());
			}
			DecompileResults res = ifc.decompileFunction(f, timeout, monitor);
			if (res.decompileCompleted()) {
				String c = res.getDecompiledFunction().getC();
				cout.println(c);
				if (c.contains("WARNING")) {
					warnFns++;
				}
				if (c.contains("halt_baddata") || c.contains("Bad instruction")) {
					badFns++;
					sum.println("baddata in " + f.getName());
				}
			}
			else {
				String err = res.getErrorMessage();
				if (res.isTimedOut() || err.toLowerCase().contains("timeout")) {
					tmo++;
				}
				else {
					fail++;
				}
				cout.println("  DECOMPILE FAILED: " + err);
				sum.println("decompile failed: " + f.getName() + ": " + err.trim());
			}
		}
		ifc.dispose();

		sum.println("functions: " + nf);
		sum.println("instructions: " + nins);
		sum.printf("code coverage: %d / %d words of executable sections are instructions%n",
			insWords, codeWords);
		sum.println("bookmarks: " + bm);
		sum.println("decompile: " + (nf - fail - tmo) + " ok, " + fail + " failed, " + tmo +
			" timeouts; " + warnFns + " with warnings; " + badFns + " with bad data");
		sum.close();
		dis.close();
		cout.close();
	}
}
