// Real-binary check, run as a postScript after a normal (auto-analyzed) ELF import.
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
		// symbols the ELF loader placed in its fake EXTERNAL block (for linking a relocatable
		// object at Ghidra's addresses in the relocation check)
		StringBuilder ext = new StringBuilder();
		for (ghidra.program.model.symbol.Symbol s : currentProgram.getSymbolTable()
				.getAllSymbols(false)) {
			MemoryBlock b = currentProgram.getMemory().getBlock(s.getAddress());
			if (b != null && b.getName().equals(MemoryBlock.EXTERNAL_BLOCK_NAME) &&
				s.isPrimary()) {
				ext.append(String.format(" %s@%s", s.getName(), s.getAddress()));
			}
		}
		sum.printf("external symbols:%s%n", ext);

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
		Iterator<Bookmark> bi = currentProgram.getBookmarkManager().getBookmarksIterator();
		StringBuilder errs = new StringBuilder();
		while (bi.hasNext()) {
			Bookmark b = bi.next();
			String k = b.getTypeString() + "/" + b.getCategory();
			int n = bm.merge(k, 1, Integer::sum);
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
		sum.printf("bad-instruction bookmarks: %d%n", bm.getOrDefault("Error/Bad Instruction", 0));
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
				String m = String.valueOf(r.getErrorMessage());
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
		sum.printf("functions whose C contains: %s%n", warn);
		sum.close();
	}
}
