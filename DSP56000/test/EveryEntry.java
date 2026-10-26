// Every-entry decode test: decodes the imported slot image (one instruction per <stride>
// addressable words of the code space) once per context setting and records which SLEIGH
// constructors (in every subtable) were used. Prints the constructors never reached and a
// total. Script args: <outfile> <stride-in-words> <ctx>... where <ctx> is "-" (program default)
// or "name=value,name=value" assignments applied over the whole code block. Several images can
// be imported into one program; every initialized block of the code space is decoded.
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
import ghidra.app.util.PseudoDisassembler;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.MemoryBlock;

public class EveryEntry extends GhidraScript {

	private final Set<String> seen = new TreeSet<>();

	private static String key(Constructor c) {
		return String.format("%s:%d %s", c.getSourceFile(), c.getLineno(), c.getParent().getName());
	}

	private void walk(ConstructState s) {
		if (s == null || s.getConstructor() == null) {
			return;
		}
		seen.add(key(s.getConstructor()));
		for (int i = 0; i < s.getNumSubStates(); i++) {
			walk(s.getSubState(i));
		}
	}

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = new PrintStream(args[0]);
		ProgramContext ctx = currentProgram.getProgramContext();
		long n = 0;
		int strideWords = Integer.decode(args[1]);
		for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
		if (!block.isInitialized() ||
			block.getStart().getAddressSpace() != currentProgram.getAddressFactory().getDefaultAddressSpace()) {
			continue;
		}
		int stride = strideWords * block.getStart().getAddressSpace().getAddressableUnitSize();
		for (int k = 2; k < args.length; k++) {
			if (!args[k].equals("-")) {
				for (String kv : args[k].split(",")) {
					String[] p = kv.split("=");
					ctx.setValue(ctx.getRegister(p[0]), block.getStart(), block.getEnd(),
						BigInteger.valueOf(Long.decode(p[1])));
				}
			}
			PseudoDisassembler dis = new PseudoDisassembler(currentProgram);
			Address a = block.getStart();
			while (a.compareTo(block.getEnd()) <= 0) {
				int len = stride;
				try {
					PseudoInstruction ins = dis.disassemble(a);
					walk(((SleighInstructionPrototype) ins.getPrototype()).getRootState());
					n++;
				}
				catch (Exception e) {
					// undecodable: step one byte
				}
				if (a.getOffset() + len > block.getEnd().getOffset()) {
					break;
				}
				a = a.add(len);
			}
		}
		}
		SleighLanguage lang = (SleighLanguage) currentProgram.getLanguage();
		int total = 0, missed = 0;
		for (Symbol sym : lang.getSymbolTable().getSymbolList()) {
			if (!(sym instanceof SubtableSymbol st)) {
				continue;
			}
			for (int i = 0; i < st.getNumConstructors(); i++) {
				total++;
				String k = key(st.getConstructor(i));
				if (!seen.contains(k)) {
					missed++;
					out.println("NOT REACHED " + k);
				}
			}
		}
		out.printf("every-entry: %d decodes, %d/%d constructors reached, %d not reached%n", n,
			total - missed, total, missed);
		for (String k : seen) {
			out.println("SEEN " + k);
		}
		out.close();
	}
}
