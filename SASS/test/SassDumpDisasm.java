// Linear-sweep disassembly dump used by the SASS test harness (no analysis).
// Like tools/DumpDisasm.java, but for the 64-bit SASS variants it first marks the
// scheduling control word at the start of every bundle (context bit "ctl").
// Prints one line per instruction: "<offset-hex> <bytes-hex> <instruction text>"
// Script args: [step] [outfile]  - step is bytes to skip after a decode failure (default 4)
//@category Testing

import java.io.PrintStream;

import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoDisassembler;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.MemoryBlock;

public class SassDumpDisasm extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		int step = args.length > 0 ? Integer.decode(args[0]) : 4;
		PrintStream out = args.length > 1 ? new PrintStream(args[1]) : System.out;

		String id = currentProgram.getLanguageID().getIdAsString();
		int stride = id.endsWith(":SM35") ? 64
				: (id.endsWith(":SM52") || id.endsWith(":SM60")) ? 32 : 0;
		ghidra.program.model.lang.Register ctl = currentProgram.getRegister("ctl");
		if (stride != 0 && ctl != null) {
			for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
				if (!block.isInitialized()) {
					continue;
				}
				for (long o = 0; o + 8 <= block.getSize(); o += stride) {
					Address x = block.getStart().add(o);
					currentProgram.getProgramContext()
							.setValue(ctl, x, x, java.math.BigInteger.ONE);
				}
			}
		}
		PseudoDisassembler dis = new PseudoDisassembler(currentProgram);
		for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
			if (!block.isInitialized()) {
				continue;
			}
			Address base = block.getStart();
			Address end = block.getEnd();
			Address a = base;
			while (a.compareTo(end) <= 0) {
				String text;
				int n;
				try {
					PseudoInstruction ins = dis.disassemble(a);
					text = ins.toString();
					n = ins.getLength();
				}
				catch (Exception e) {
					text = "BAD (" + String.valueOf(e.getMessage()).split("\n")[0] + ")";
					n = step;
				}
				StringBuilder hex = new StringBuilder();
				for (int i = 0; i < n; i++) {
					try {
						hex.append(String.format("%02x", block.getByte(a.add(i)) & 0xff));
					}
					catch (Exception e) {
						break;
					}
				}
				out.printf("%08x %s %s%n", a.subtract(base), hex, text);
				if (a.getOffset() + n > end.getOffset()) {
					break;
				}
				a = a.add(n);
			}
		}
		out.flush();
		if (out != System.out) {
			out.close();
		}
	}
}
