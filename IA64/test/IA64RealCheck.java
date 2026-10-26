// Real-binary check for the IA-64 module (run after auto-analysis):
// counts functions, instructions, bad-instruction and error bookmarks, decompiles every
// function, and writes the disassembly ("<address> <instruction>") for comparison with GNU
// objdump. Script args: <out-prefix> [decompile timeout seconds, default 60]
// Writes <prefix>.summary, <prefix>.dis, <prefix>.decomp-failures
//@category Testing

import java.io.PrintStream;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;

public class IA64RealCheck extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		String prefix = args[0];
		int timeout = args.length > 1 ? Integer.parseInt(args[1]) : 60;
		Address imageBase = currentProgram.getImageBase();
		PrintStream dis = new PrintStream(prefix + ".dis");
		long nins = 0;
		for (Instruction ins : currentProgram.getListing().getInstructions(true)) {
			dis.printf("%x %s%n", ins.getAddress().getOffset(), ins.toString());
			nins++;
		}
		dis.close();
		int bad = 0, errors = 0, warnings = 0;
		PrintStream bm = new PrintStream(prefix + ".bookmarks");
		var it = currentProgram.getBookmarkManager().getBookmarksIterator();
		while (it.hasNext()) {
			var b = it.next();
			if (b.getTypeString().equals("Error")) {
				errors++;
				if (b.getCategory().contains("Bad Instruction")) {
					bad++;
				}
				bm.println("ERROR " + b.getAddress() + " " + b.getCategory() + ": " + b.getComment());
			}
			else if (b.getTypeString().equals("Warning")) {
				warnings++;
				bm.println("WARNING " + b.getAddress() + " " + b.getCategory() + ": " + b.getComment());
			}
		}
		bm.close();
		DecompInterface di = new DecompInterface();
		di.setOptions(new DecompileOptions());
		di.openProgram(currentProgram);
		int nf = 0, ok = 0, fail = 0, timeouts = 0, jt = 0, baddata = 0, unimpl = 0;
		PrintStream wf = new PrintStream(prefix + ".decomp-warnings");
		PrintStream ff = new PrintStream(prefix + ".decomp-failures");
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			if (f.isThunk() || f.isExternal()) {
				continue;
			}
			nf++;
			DecompileResults r = di.decompileFunction(f, timeout, monitor);
			if (r != null && r.decompileCompleted()) {
				ok++;
				String c = r.getDecompiledFunction() != null ? r.getDecompiledFunction().getC() : "";
				for (String line : c.split("\n")) {
					if (line.contains("Could not recover jumptable")) {
						jt++;
						wf.println(f.getEntryPoint() + " " + line.trim());
					}
					if (line.contains("halt_baddata")) {
						baddata++;
						wf.println(f.getEntryPoint() + " " + line.trim());
					}
					if (line.contains("Unimplemented")) {
						unimpl++;
						wf.println(f.getEntryPoint() + " " + line.trim());
					}
				}
			}
			else {
				String msg = r == null ? "null" : r.getErrorMessage();
				if (msg != null && msg.toLowerCase().contains("timeout")) {
					timeouts++;
				}
				fail++;
				ff.println(f.getEntryPoint() + " " + f.getName() + ": " +
					(msg == null ? "" : msg.replace('\n', ' ')));
			}
		}
		ff.close();
		wf.close();
		di.dispose();
		int thunks = 0, all = 0;
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			all++;
			if (f.isThunk()) {
				thunks++;
			}
		}
		PrintStream s = new PrintStream(prefix + ".summary");
		s.printf("image base %s%n", imageBase);
		s.printf("functions %d (thunks %d)%n", all, thunks);
		s.printf("instructions %d%n", nins);
		s.printf("bad-instruction bookmarks %d%n", bad);
		s.printf("error bookmarks %d (warnings %d)%n", errors, warnings);
		s.printf("decompiled %d/%d (failures %d, timeouts %d)%n", ok, nf, fail, timeouts);
		s.printf("decompiler warnings: unrecovered jump tables %d, halt_baddata %d, unimplemented %d%n",
			jt, baddata, unimpl);
		s.close();
	}
}
