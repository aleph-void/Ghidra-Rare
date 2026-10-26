// Every-entry decode test for the ADSP-218x module: decodes a corpus of 24-bit big-endian
// words (copied through the pm block 64K words at a time) once per context setting and records
// which SLEIGH constructors, in every subtable, were used.  Prints the constructors never
// reached and a total.
// Script args: <outfile> <corpus> <ctx>[:<nwords>]...
//   <ctx> is "-" (default context) or "name=value,..." (e.g. lpend=1,lpterm=14); <nwords>
//   limits that pass to the first n words of the corpus.
//@category Testing

import java.io.FileInputStream;
import java.io.InputStream;
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
import ghidra.program.model.lang.Language;
import ghidra.program.model.lang.ProcessorContextImpl;
import ghidra.program.model.lang.Register;
import ghidra.program.model.mem.DumbMemBufferImpl;
import ghidra.program.model.mem.Memory;
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
		Language lang = currentProgram.getLanguage();
		Memory mem = currentProgram.getMemory();
		MemoryBlock block = mem.getBlock(currentProgram.getAddressFactory()
			.getAddressSpace("pm").getAddress(0));
		int cap = (int) (block.getSize() / 3);
		byte[] chunk = new byte[cap * 3];
		long n = 0;
		for (int k = 2; k < args.length; k++) {
			String[] spec = args[k].split(":");
			long limit = spec.length > 1 ? Long.decode(spec[1]) : Long.MAX_VALUE;
			long done = 0;
			try (InputStream in = new FileInputStream(args[1])) {
				int got;
				while (done < limit && (got = in.readNBytes(chunk, 0, chunk.length)) > 0) {
					mem.setBytes(block.getStart(), chunk, 0, got);
					Address a = block.getStart();
					for (int i = 0; i < got / 3 && done < limit; i++, done++) {
						ProcessorContextImpl ctx = new ProcessorContextImpl(lang);
						if (!spec[0].equals("-")) {
							for (String kv : spec[0].split(",")) {
								String[] p = kv.split("=");
								Register r = lang.getRegister(p[0]);
								ctx.setValue(r, BigInteger.valueOf(Long.decode(p[1])));
							}
						}
						try {
							SleighInstructionPrototype p = (SleighInstructionPrototype) lang
								.parse(new DumbMemBufferImpl(mem, a), ctx, false);
							walk(p.getRootState());
							n++;
						}
						catch (Exception e) {
							// undecodable word
						}
						a = a.addWrap(3);
					}
				}
			}
		}
		int total = 0, missed = 0;
		try (PrintStream out = new PrintStream(args[0])) {
			for (Symbol sym : ((SleighLanguage) lang).getSymbolTable().getSymbolList()) {
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
		}
	}
}
