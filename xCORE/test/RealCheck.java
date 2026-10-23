// Headless real-binary check: language, function/instruction counts, bookmarks, code in
// non-executable memory, decompile of every function, and a listing dump (with the dual-issue
// context bit) for comparison against a reference disassembler.
// Script args: <summary.txt> <listing.txt> <decomp.txt> [timeoutSec]
//@category Testing

import java.io.PrintStream;
import java.math.BigInteger;
import java.util.Iterator;
import java.util.Map;
import java.util.TreeMap;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.Bookmark;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.MemoryBlock;

public class RealCheck extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] a = getScriptArgs();
		PrintStream sum = new PrintStream(a[0]);
		PrintStream lst = new PrintStream(a[1]);
		PrintStream dec = new PrintStream(a[2]);
		int timeout = a.length > 3 ? Integer.parseInt(a[3]) : 60;

		sum.printf("language %s%n", currentProgram.getLanguageID());
		sum.printf("functions %d%n", currentProgram.getFunctionManager().getFunctionCount());
		sum.printf("instructions %d%n", currentProgram.getListing().getNumInstructions());

		Map<String, Integer> bm = new TreeMap<>();
		for (Iterator<Bookmark> it = currentProgram.getBookmarkManager().getBookmarksIterator(); it.hasNext();) {
			Bookmark b = it.next();
			if (b.getTypeString().equals("Analysis") || b.getTypeString().equals("Info")) {
				continue;
			}
			String k = b.getTypeString() + "/" + b.getCategory();
			bm.merge(k, 1, Integer::sum);
			if (bm.get(k) <= 10) {
				sum.printf("  bookmark %s %s: %s%n", k, b.getAddress(), b.getComment());
			}
		}
		for (Map.Entry<String, Integer> e : bm.entrySet()) {
			sum.printf("bookmarks %s %d%n", e.getKey(), e.getValue());
		}

		// code outside executable blocks / overlapping data symbols
		int nonExec = 0;
		Register dual = currentProgram.getRegister("dual");
		int dualIns = 0;
		for (Instruction ins : currentProgram.getListing().getInstructions(true)) {
			MemoryBlock b = currentProgram.getMemory().getBlock(ins.getAddress());
			if (b == null || !b.isExecute()) {
				nonExec++;
			}
			int d = 0;
			if (dual != null) {
				BigInteger v = ins.getValue(dual, false);
				d = v == null ? 0 : v.intValue();
			}
			dualIns += d;
			StringBuilder hex = new StringBuilder();
			for (byte x : ins.getBytes()) {
				hex.append(String.format("%02x", x & 0xff));
			}
			Function f = getFunctionContaining(ins.getAddress());
			lst.printf("%08x %s %d %s\t%s%n", ins.getAddress().getOffset(), hex, d, ins,
				f == null ? "-" : f.getName());
		}
		sum.printf("instructions in non-executable blocks %d%n", nonExec);
		sum.printf("instructions decoded with dual=1 %d%n", dualIns);

		DecompInterface ifc = new DecompInterface();
		ifc.openProgram(currentProgram);
		int n = 0, fail = 0, tmo = 0, baddata = 0, warn = 0, dataFn = 0;
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			if (monitor.isCancelled()) {
				break;
			}
			MemoryBlock fb = currentProgram.getMemory().getBlock(f.getEntryPoint());
			if (f.isExternal() || fb == null || !fb.isExecute()) {
				// e.g. lib_xud's PidJumpTable: a table of code pointers typed STT_FUNC in .dp.data
				dataFn++;
				sum.printf("  function outside executable memory (skipped): %s @ %s%n", f.getName(),
					f.getEntryPoint());
				continue;
			}
			n++;
			DecompileResults r = ifc.decompileFunction(f, timeout, monitor);
			dec.printf("%n==== %s @ %s%n", f.getName(), f.getEntryPoint());
			if (r.decompileCompleted()) {
				String c = r.getDecompiledFunction().getC();
				if (c.contains("halt_baddata")) {
					baddata++;
				}
				if (c.contains("WARNING")) {
					warn++;
				}
				dec.println(c);
			}
			else {
				String m = String.valueOf(r.getErrorMessage());
				if (r.isTimedOut() || m.toLowerCase().contains("timeout")) {
					tmo++;
				}
				else {
					fail++;
				}
				dec.println("DECOMPILE FAILED: " + m);
				sum.printf("  decompile failed %s @ %s: %s%n", f.getName(), f.getEntryPoint(),
					m.split("\n")[0]);
			}
		}
		ifc.dispose();
		sum.printf("decompiled %d failed %d timeouts %d halt_baddata %d with-warnings %d (skipped %d non-code)%n",
			n, fail, tmo, baddata, warn, dataFn);
		sum.close();
		lst.close();
		dec.close();
	}
}
