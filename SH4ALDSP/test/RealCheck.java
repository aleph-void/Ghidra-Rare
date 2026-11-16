// Real-binary check (from aleph-void/ghidra-sh, MIT), run as a postScript after a normal (auto-analyzed) ELF import.
// Writes a summary, a listing of every instruction in executable blocks, and the decompiled C
// of every function.
// Script args: <summary.txt> <listing.txt> <decomp.txt> [timeoutSeconds]
//   summary : language, counts of functions/instructions/bookmarks, decompile statistics
//   listing : "<address-hex> <bytes-hex> <instruction text>" per instruction (for the objdump diff)
//   decomp  : decompiled C (or the failure message) per function (timeoutSeconds 0: skip)
//@category Testing

import java.io.PrintStream;
import java.util.Iterator;
import java.util.Map;
import java.util.TreeMap;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Bookmark;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.reloc.Relocation;

public class RealCheck extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream sum = new PrintStream(args[0]);
		PrintStream lst = new PrintStream(args[1]);
		PrintStream dec = new PrintStream(args[2]);
		int timeout = args.length > 3 ? Integer.parseInt(args[3]) : 60;
		Listing listing = currentProgram.getListing();

		sum.printf("language: %s  compiler: %s%n", currentProgram.getLanguageID(),
			currentProgram.getCompilerSpec().getCompilerSpecID());
		sum.printf("image base: 0x%x%n", currentProgram.getImageBase().getOffset());
		StringBuilder blocks = new StringBuilder();
		for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
			if (b.isLoaded()) {
				blocks.append(String.format(" %s@%s", b.getName(), b.getStart()));
			}
		}
		sum.printf("blocks:%s%n", blocks);

		// Instructions in executable blocks; also count instructions that fall through into
		// defined data (disassembly running into data) and executable bytes left undefined.
		long ninstr = 0, intoData = 0, exeBytes = 0, undefBytes = 0;
		for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
			if (!b.isExecute() || !b.isInitialized()) {
				continue;
			}
			exeBytes += b.getSize();
			Address a = b.getStart();
			while (a != null && a.compareTo(b.getEnd()) <= 0) {
				Instruction ins = listing.getInstructionAt(a);
				if (ins != null) {
					ninstr++;
					StringBuilder hex = new StringBuilder();
					for (byte x : ins.getBytes()) {
						hex.append(String.format("%02x", x & 0xff));
					}
					lst.printf("%08x %s %s%n", a.getOffset(), hex, ins.toString());
					Address ft = ins.getFallThrough();
					if (ft != null) {
						Data d = listing.getDefinedDataAt(ft);
						if (d != null) {
							intoData++;
						}
					}
					a = ins.getMaxAddress().next();
					continue;
				}
				Data d = listing.getDefinedDataAt(a);
				if (d == null) {
					undefBytes++;
					a = a.next();
				}
				else {
					a = d.getMaxAddress().next();
				}
			}
		}
		lst.close();

		Map<String, Integer> bm = new TreeMap<>();
		Map<String, Integer> badByBlock = new TreeMap<>();
		StringBuilder badExec = new StringBuilder();
		int badAfterCall = 0, badOther = 0;
		Iterator<Bookmark> bi = currentProgram.getBookmarkManager().getBookmarksIterator();
		StringBuilder errs = new StringBuilder();
		while (bi.hasNext()) {
			Bookmark b = bi.next();
			String k = b.getTypeString() + "/" + b.getCategory();
			int n = bm.merge(k, 1, Integer::sum);
			if (k.equals("Error/Bad Instruction")) {
				// classify: the disassembler ran off a CALL (its delay slot is the last
				// instruction before the bad word) into the literal pool that follows a call to a
				// function it did not yet know to be non-returning
				String c = String.valueOf(b.getComment());
				int fi = c.indexOf("flow from ");
				boolean afterCall = false;
				if (fi >= 0) {
					Address from = toAddr(Long.parseLong(c.substring(fi + 10).replace(")", "").trim(), 16));
					Instruction fin = from == null ? null : currentProgram.getListing().getInstructionAt(from);
					// walk back over physically contiguous instructions: the chain that begins
					// with a call (and its delay slot) and runs through literal-pool words that
					// happen to decode
					Instruction cur = fin;
					for (int step = 0; cur != null && step < 16 && !afterCall; step++) {
						afterCall = cur.getFlowType().isCall();
						Instruction prev = cur.getPrevious();
						cur = prev != null && prev.getMaxAddress().next() != null &&
							prev.getMaxAddress().next().equals(cur.getMinAddress()) ? prev : null;
					}
				}
				badAfterCall += afterCall ? 1 : 0;
				badOther += afterCall ? 0 : 1;
				MemoryBlock mb = currentProgram.getMemory().getBlock(b.getAddress());
				String bn = mb == null ? "?" : mb.getName() + (mb.isExecute() ? "(x)" : "");
				badByBlock.merge(bn, 1, Integer::sum);
				if (mb != null && mb.isExecute()) {
					badExec.append(String.format("  bad in executable block @ %s: %s%n", b.getAddress(), b.getComment()));
				}
			}
			// first 20 of each Error/Warning category
			if ((b.getTypeString().equals("Error") || b.getTypeString().equals("Warning")) &&
				n <= 20) {
				errs.append(String.format("  %s @ %s: %s %s%n", b.getTypeString(), b.getAddress(), b.getCategory(),
					b.getComment()));
			}
		}
		Map<String, Integer> rel = new TreeMap<>();
		Iterator<Relocation> ri = currentProgram.getRelocationTable().getRelocations();
		while (ri.hasNext()) {
			Relocation r = ri.next();
			rel.merge(r.getStatus().toString(), 1, Integer::sum);
		}

		int nfunc = currentProgram.getFunctionManager().getFunctionCount();
		int nthunk = 0;
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			if (f.isThunk()) {
				nthunk++;
			}
		}
		int next = 0;
		for (Function f : currentProgram.getFunctionManager().getExternalFunctions()) {
			next++;
		}
		sum.printf("functions: %d  (thunks %d, external %d)%n", nfunc, nthunk, next);
		sum.printf("instructions: %d  (executable bytes %d, undefined executable bytes %d)%n",
			ninstr, exeBytes, undefBytes);
		sum.printf("fallthrough into defined data: %d%n", intoData);
		sum.printf("bad-instruction bookmarks: %d  by block %s%n", bm.getOrDefault("Error/Bad Instruction", 0), badByBlock);
		sum.printf("bad instructions directly after a call (literal pool after a non-returning call): %d, others: %d%n", badAfterCall, badOther);
		sum.print(badExec);
		sum.printf("error bookmarks: %d%n",
			bm.entrySet().stream().filter(e -> e.getKey().startsWith("Error/"))
				.mapToInt(Map.Entry::getValue).sum());
		sum.printf("relocations: %s%n", rel);
		sum.printf("bookmarks: %s%n", bm);
		sum.print(errs);

		if (timeout <= 0) { // decompilation disabled
			dec.close();
			sum.close();
			return;
		}
		DecompInterface di = new DecompInterface();
		DecompileOptions opts = new DecompileOptions();
		opts.grabFromProgram(currentProgram);
		di.setOptions(opts);
		di.openProgram(currentProgram);
		int ok = 0, fail = 0, tmo = 0;
		Map<String, Integer> fails = new TreeMap<>();
		Map<String, Integer> warn = new TreeMap<>();
		String[] pats = { "halt_baddata", "Bad instruction", "Could not recover jumptable",
			"Unable to track spacebase", "Removing unreachable block", "unimpl",
			"Treating indirect jump as call", "in_r", "unaff_r", "Control flow encountered bad instruction" };
		int nskip = 0;
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			if (monitor.isCancelled()) {
				break;
			}
			// external-linkage stubs the ELF loader places in the fake EXTERNAL block
			MemoryBlock fb = currentProgram.getMemory().getBlock(f.getEntryPoint());
			if (fb == null || fb.getName().equals(MemoryBlock.EXTERNAL_BLOCK_NAME)) {
				nskip++;
				continue;
			}
			dec.printf("%n==== %s @ %s  (%s)%n", f.getName(), f.getEntryPoint(),
				f.getSignature().getPrototypeString());
			DecompileResults r = di.decompileFunction(f, timeout, monitor);
			if (r.decompileCompleted()) {
				ok++;
				String c = r.getDecompiledFunction().getC();
				dec.println(c);
				for (String p : pats) {
					if (c.contains(p)) {
						warn.merge(p, 1, Integer::sum);
					}
				}
			}
			else {
				String m = String.valueOf(r.getErrorMessage()).trim().replace('\n', ' ');
				fails.merge(m.replaceAll("^Exception while decompiling [0-9a-f]+: ", ""), 1,
					Integer::sum);
				if (r.isTimedOut() || m.toLowerCase().contains("timeout")) {
					tmo++;
				}
				else {
					fail++;
				}
				dec.println("DECOMPILE FAILED: " + m);
			}
		}
		di.dispose();
		dec.close();
		sum.printf("decompile: %d ok, %d failed, %d timed out (of %d; %d EXTERNAL-block stubs skipped)%n",
			ok, fail, tmo, nfunc, nskip);
		sum.printf("decompile failures by message: %s%n", fails);
		sum.printf("functions whose C contains: %s%n", warn);
		sum.close();
	}
}
