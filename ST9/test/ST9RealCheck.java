// ST9 smoke-program check (run as -postScript after auto-analysis).
// Writes three files with the given prefix:
//   <prefix>.summary  language, counts (functions, instructions, code coverage,
//                     bookmarks, decompile failures/timeouts/warnings)
//   <prefix>.dis      "<addr-hex> <bytes-hex> <instruction>" for every
//                     instruction the analysis created in executable code blocks
//                     (same format as Z8DumpDisasm, for test/compare.py)
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

public class ST9RealCheck extends GhidraScript {

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

		long codeBytes = 0, insBytes = 0;
		int nins = 0;
		for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
			if (!b.isInitialized() || !b.getStart().getAddressSpace().getName().equals("code")) {
				continue;
			}
			codeBytes += b.getSize();
			for (Instruction i : currentProgram.getListing().getInstructions(
				new ghidra.program.model.address.AddressSet(b.getStart(), b.getEnd()), true)) {
				insBytes += i.getLength();
				StringBuilder hex = new StringBuilder();
				for (byte x : i.getBytes()) {
					hex.append(String.format("%02x", x & 0xff));
				}
				dis.printf("%04x %s %s%n", i.getAddress().getOffset(), hex, i.toString());
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
		sum.printf("code coverage: %d / %d bytes of the image are instructions%n", insBytes,
			codeBytes);
		sum.println("bookmarks: " + bm);
		sum.println("decompile: " + (nf - fail - tmo) + " ok, " + fail + " failed, " + tmo +
			" timeouts; " + warnFns + " with warnings; " + badFns + " with bad data");
		sum.close();
		dis.close();
		cout.close();
	}
}
