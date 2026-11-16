// Every-entry decode test (adapted from aleph-void/ghidra-sh and Ghidra-Rare's RX module, MIT): decodes the imported slot image (one instruction per <stride> bytes)
// once per context setting and records which SLEIGH constructors (in every subtable) were used.
// Prints the constructors never reached and a total. Script args: <outfile> <stride> <ctx>...
// where <ctx> is "-" (program default) or "name=value,name=value" assignments applied over the
// whole code block.
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
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.InstructionPrototype;
import ghidra.program.model.lang.ProcessorContextImpl;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.MemoryBufferImpl;
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
		MemoryBlock block = null;
		for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
			if (b.isInitialized() && b.isExecute() || block == null && b.isInitialized()) {
				block = b;
			}
		}
		long n = 0;
		int stride = Integer.decode(args[1]);
		for (int k = 2; k < args.length; k++) {
			Address a = block.getStart();
			while (a.compareTo(block.getEnd()) <= 0) {
				int len = stride;
				try {
					// parse like DumpDisasm does: PseudoDisassembler rejects a delayed branch whose
					// delay slot holds another branch, which would hide the branch constructor
					ProcessorContextImpl pctx = new ProcessorContextImpl(currentProgram.getLanguage());
					if (!args[k].equals("-") && !args[k].equals("default")) {
						for (String kv : args[k].split(",")) {
							String[] p = kv.split("=");
							pctx.setValue(currentProgram.getLanguage().getRegister(p[0]),
								BigInteger.valueOf(Long.decode(p[1])));
						}
					}
					MemoryBufferImpl buf = new MemoryBufferImpl(currentProgram.getMemory(), a);
					InstructionPrototype p = currentProgram.getLanguage().parse(buf, pctx, false);
					walk(((SleighInstructionPrototype) p).getRootState());
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
		SleighLanguage lang = (SleighLanguage) currentProgram.getLanguage();
		int total = 0, missed = 0;
		for (Symbol sym : lang.getSymbolTable().getSymbolList()) {
			if (!(sym instanceof SubtableSymbol st)) {
				continue;
			}
			for (int i = 0; i < st.getNumConstructors(); i++) {
				total++;
				String k = key(st.getConstructor(i));
				out.println("ALL " + k);
				if (!seen.contains(k)) {
					missed++;
					out.println("NOT REACHED " + k);
				}
			}
		}
		for (String k : seen) {
			out.println("SEEN " + k);
		}
		out.printf("every-entry: %d decodes, %d/%d constructors reached, %d not reached%n", n,
			total - missed, total, missed);
		out.close();
	}
}
