// Post-analysis check of an imported 65816 program (real-binary test).
// Writes <out>.summary (counts) and <out>.lst (one line per instruction:
// "<addr-hex6> <M> <X> <E> <bytes-hex> <text>"), and decompiles every function.
// Script args: <out-prefix> [decompile-timeout-seconds]
//@category Testing

import java.io.PrintStream;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.*;

public class G65816RealCheck extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		String prefix = args[0];
		int timeout = args.length > 1 ? Integer.parseInt(args[1]) : 30;
		var lang = currentProgram.getLanguage();
		Register mf = lang.getRegister("ctx_MF"), xf = lang.getRegister("ctx_XF"),
				ef = lang.getRegister("ctx_EF");

		PrintStream lst = new PrintStream(prefix + ".lst");
		int ninsn = 0;
		for (Instruction ins : currentProgram.getListing().getInstructions(true)) {
			StringBuilder hex = new StringBuilder();
			for (byte b : ins.getBytes()) {
				hex.append(String.format("%02x", b & 0xff));
			}
			lst.printf("%06x %s %s %s %s %s%n", ins.getAddress().getOffset(),
				ins.getValue(mf, false), ins.getValue(xf, false), ins.getValue(ef, false), hex, ins);
			ninsn++;
		}
		lst.close();

		var bm = currentProgram.getBookmarkManager();
		int bad = 0, errors = 0;
		StringBuilder errText = new StringBuilder();
		var it = bm.getBookmarksIterator("Error");
		while (it.hasNext()) {
			var b = it.next();
			errors++;
			if (b.getCategory().contains("Bad Instruction")) {
				bad++;
			}
			if (errors <= 20) {
				errText.append(String.format("  error %s %s: %s%n", b.getAddress(), b.getCategory(),
					b.getComment()));
			}
		}

		DecompInterface dec = new DecompInterface();
		dec.openProgram(currentProgram);
		int nfunc = 0, fail = 0;
		StringBuilder failText = new StringBuilder();
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			nfunc++;
			DecompileResults r = dec.decompileFunction(f, timeout, monitor);
			if (r == null || !r.decompileCompleted()) {
				fail++;
				if (fail <= 20) {
					failText.append(String.format("  decompile failed %s %s: %s%n", f.getEntryPoint(),
						f.getName(), r == null ? "null" : r.getErrorMessage().trim()));
				}
			}
		}
		dec.dispose();

		PrintStream sum = new PrintStream(prefix + ".summary");
		sum.printf("language %s, loader-format %s%n", lang.getLanguageID(),
			currentProgram.getExecutableFormat());
		sum.printf("instructions %d, functions %d, bad-instruction bookmarks %d, error bookmarks %d, decompile failures %d%n",
			ninsn, nfunc, bad, errors, fail);
		sum.print(errText);
		sum.print(failText);
		sum.close();
	}
}
