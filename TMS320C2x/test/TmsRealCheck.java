// TMS320C2x/C5x real-program check (run as -postScript after auto-analysis).
// Writes three files with the given prefix:
//   <prefix>.summary  language, counts (functions, instructions, code coverage,
//                     bookmarks, decompile failures/timeouts/warnings)
//   <prefix>.dis      "<word-addr-hex> <words-hex> <instruction>" for every instruction the
//                     analysis created in program memory (for test/real-compare.py)
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

public class TmsRealCheck extends GhidraScript {

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
			if (!b.isInitialized() || !b.getStart().getAddressSpace().getName().equals("prog")) {
				continue;
			}
			codeBytes += b.getSize();
			for (Instruction i : currentProgram.getListing().getInstructions(
				new ghidra.program.model.address.AddressSet(b.getStart(), b.getEnd()), true)) {
				insBytes += i.getLength();
				StringBuilder hex = new StringBuilder();
				byte[] bs = i.getBytes();
				boolean big = currentProgram.getLanguage().isBigEndian();
				for (int k = 0; k + 1 < bs.length; k += 2) {
					int w = big ? ((bs[k] & 0xff) << 8) | (bs[k + 1] & 0xff)
							: ((bs[k + 1] & 0xff) << 8) | (bs[k] & 0xff);
					hex.append(String.format("%04x", w));
				}
				dis.printf("%04x %s %s%n", i.getAddress().getAddressableWordOffset(), hex, i.toString());
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
		sum.printf("code coverage: %d / %d words of the image are instructions%n", insBytes / 2,
			codeBytes / 2);
		sum.println("bookmarks: " + bm);
		sum.println("decompile: " + (nf - fail - tmo) + " ok, " + fail + " failed, " + tmo +
			" timeouts; " + warnFns + " with warnings; " + badFns + " with bad data");
		sum.close();
		dis.close();
		cout.close();
	}
}
