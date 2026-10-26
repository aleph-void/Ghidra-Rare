// Every-entry decode test: decodes every 4-word record of the imported corpus chunk(s) once per
// context setting and records which SLEIGH constructors (in every subtable) took part. At the end
// (last program) prints the constructors never reached and a total.
// Script args: <outfile> <ctx>...   ctx: "-" (pspec defaults) or "name=value,..." over the image.
//@category Testing

import java.io.PrintStream;
import java.math.BigInteger;
import java.util.Set;
import java.util.TreeSet;

import ghidra.app.plugin.processors.sleigh.ConstructState;
import ghidra.app.plugin.processors.sleigh.Constructor;
import ghidra.app.plugin.processors.sleigh.SleighInstructionPrototype;
import ghidra.app.plugin.processors.sleigh.SleighLanguage;
import ghidra.app.plugin.processors.sleigh.symbol.SubtableSymbol;
import ghidra.app.plugin.processors.sleigh.symbol.Symbol;
import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoDisassemblerContext;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.InstructionPrototype;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.mem.MemoryBufferImpl;

public class EveryEntry extends GhidraScript {

	private static final Set<String> SEEN = new TreeSet<>();
	private static long decodes = 0;

	private static String key(Constructor c) {
		return String.format("%s:%d %s", c.getSourceFile(), c.getLineno(), c.getParent().getName());
	}

	private void walk(ConstructState s) {
		if (s == null || s.getConstructor() == null) {
			return;
		}
		SEEN.add(key(s.getConstructor()));
		for (int i = 0; i < s.getNumSubStates(); i++) {
			walk(s.getSubState(i));
		}
	}

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		ProgramContext ctx = currentProgram.getProgramContext();
		MemoryBlock block = currentProgram.getMemory().getBlocks()[0];
		for (int k = 1; k < args.length; k++) {
			if (!args[k].equals("-")) {
				for (String kv : args[k].split(",")) {
					String[] p = kv.split("=");
					ctx.setValue(ctx.getRegister(p[0]), block.getStart(), block.getEnd(),
						BigInteger.valueOf(Long.decode(p[1])));
				}
			}
			for (long off = 0; off + 8 <= block.getSize(); off += 8) {
				Address a = block.getStart().add(off);
				try {
					MemoryBufferImpl buf = new MemoryBufferImpl(currentProgram.getMemory(), a);
					PseudoDisassemblerContext pc = new PseudoDisassemblerContext(ctx);
					pc.flowStart(a);
					InstructionPrototype pr = currentProgram.getLanguage().parse(buf, pc, false);
					PseudoInstruction ins = new PseudoInstruction(currentProgram, a, pr, buf, pc);
					walk(((SleighInstructionPrototype) ins.getPrototype()).getRootState());
					decodes++;
				}
				catch (Exception e) {
					// undecodable record
				}
			}
		}
		SleighLanguage lang = (SleighLanguage) currentProgram.getLanguage();
		int total = 0, missed = 0;
		PrintStream out = new PrintStream(args[0]);
		for (Symbol sym : lang.getSymbolTable().getSymbolList()) {
			if (!(sym instanceof SubtableSymbol st)) {
				continue;
			}
			for (int i = 0; i < st.getNumConstructors(); i++) {
				total++;
				String k = key(st.getConstructor(i));
				if (!SEEN.contains(k)) {
					missed++;
					out.println("NOT REACHED " + k);
				}
			}
		}
		out.printf("every-entry: %d decodes, %d/%d constructors reached, %d not reached%n", decodes,
			total - missed, total, missed);
		out.close();
	}
}
