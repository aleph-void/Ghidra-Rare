// Real-code check for the DSP56000 module: run after auto-analysis of an imported program
// (LOD file). Writes into <outdir>:
//   summary.txt  functions, instructions, bad-instruction and error bookmarks, decompile
//                results (ok / failed / timed out, with the failing function names)
//   auto.txt     every instruction auto-analysis created: "<word-address> <words> <text>"
//   guided.txt   with an address file (one hex word address per line, from the assembler
//                listing): the instruction decoded at each listed address, whether or not
//                analysis reached it ("<addr> <words> <text>", BAD if undecodable)
// Script args: <outdir> [addrfile]
//@category Testing

import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoDisassembler;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.listing.Bookmark;
import ghidra.program.model.listing.BookmarkType;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;

public class DspRealCheck extends GhidraScript {

	private String words(Address a, int len, int unit) throws Exception {
		StringBuilder sb = new StringBuilder();
		for (int i = 0; i < len / unit; i++) {
			byte[] b = new byte[unit];
			currentProgram.getMemory().getBytes(a.add((long) i * unit), b);
			if (i > 0) {
				sb.append(' ');
			}
			for (byte x : b) {
				sb.append(String.format("%02x", x & 0xff));
			}
		}
		return sb.toString();
	}

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		File dir = new File(args[0]);
		dir.mkdirs();
		AddressSpace p = currentProgram.getAddressFactory().getDefaultAddressSpace();
		int unit = p.getAddressableUnitSize();

		int nins = 0;
		try (PrintStream out = new PrintStream(new File(dir, "auto.txt"))) {
			for (Instruction ins : currentProgram.getListing().getInstructions(true)) {
				nins++;
				out.printf("%04x %s %s%n", ins.getAddress().getAddressableWordOffset(),
					words(ins.getAddress(), ins.getLength(), unit), ins);
			}
		}
		int bad = 0, err = 0;
		List<String> errs = new ArrayList<>();
		Iterator<Bookmark> it = currentProgram.getBookmarkManager().getBookmarksIterator();
		while (it.hasNext()) {
			Bookmark b = it.next();
			if (b.getTypeString().equals(BookmarkType.ERROR)) {
				err++;
				if (b.getCategory().contains("Bad Instruction")) {
					bad++;
				}
				errs.add(b.getAddress() + " " + b.getCategory() + ": " + b.getComment());
			}
		}
		int nf = 0, ok = 0, fail = 0, timeout = 0;
		List<String> failed = new ArrayList<>();
		DecompInterface dec = new DecompInterface();
		dec.openProgram(currentProgram);
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			nf++;
			DecompileResults r = dec.decompileFunction(f, 60, monitor);
			if (r.decompileCompleted() && r.getDecompiledFunction() != null) {
				ok++;
			}
			else if (r.isTimedOut()) {
				timeout++;
				failed.add(f.getName() + " (timeout)");
			}
			else {
				fail++;
				failed.add(f.getName() + ": " + r.getErrorMessage());
			}
		}
		dec.dispose();
		try (PrintStream out = new PrintStream(new File(dir, "summary.txt"))) {
			out.printf("functions %d, instructions %d, bad-instruction bookmarks %d, error bookmarks %d%n",
				nf, nins, bad, err);
			out.printf("decompile: %d ok, %d failed, %d timed out%n", ok, fail, timeout);
			for (String s : failed) {
				out.println("  decompile " + s);
			}
			for (String s : errs) {
				out.println("  bookmark " + s);
			}
		}
		if (args.length > 1) {
			PseudoDisassembler dis = new PseudoDisassembler(currentProgram);
			try (PrintStream out = new PrintStream(new File(dir, "guided.txt"))) {
				for (String line : Files.readAllLines(new File(args[1]).toPath())) {
					line = line.trim();
					if (line.isEmpty()) {
						continue;
					}
					Address a = p.getAddress(Long.parseLong(line, 16) * unit);
					String text;
					String w;
					try {
						Instruction ins = currentProgram.getListing().getInstructionAt(a);
						if (ins != null) {
							text = ins.toString();
							w = words(a, ins.getLength(), unit);
						}
						else {
							PseudoInstruction pi = dis.disassemble(a);
							text = pi.toString();
							w = words(a, pi.getLength(), unit);
						}
					}
					catch (Exception e) {
						text = "BAD";
						w = words(a, unit, unit);
					}
					out.printf("%04x %s %s%n", a.getAddressableWordOffset(), w, text);
				}
			}
		}
	}
}
