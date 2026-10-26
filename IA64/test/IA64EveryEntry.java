// Every-entry decode test: decodes every slot of a raw bundle image (as IA64DumpSlots does) once
// per frame-context triple and records which SLEIGH constructors (in every subtable) were used.
// Writes "SEEN <key>" for used constructors and "ALL <key>" for every constructor;
// test/every-entry.sh merges runs and lists the constructors never reached.
// Script args: <outfile> [sol,out,sor ...]   (default 0,0,0)
//@category Testing

import java.io.PrintStream;
import java.math.BigInteger;
import java.util.*;

import ghidra.app.plugin.processors.sleigh.*;
import ghidra.app.plugin.processors.sleigh.symbol.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoDisassembler;
import ghidra.app.util.PseudoDisassemblerContext;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.MemoryBlock;

public class IA64EveryEntry extends GhidraScript {

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
		Register base = ctx.getBaseContextRegister();
		Register slot = ctx.getRegister("slot"), tmpl = ctx.getRegister("tmpl");
		Register s1lo = ctx.getRegister("s1lo"), s2lo = ctx.getRegister("s2lo");
		Register rsol = ctx.getRegister("cfm_sol"), rout = ctx.getRegister("cfm_out"),
				rsor = ctx.getRegister("cfm_sor");
		MemoryBlock block = currentProgram.getMemory().getBlocks()[0];
		Address start = block.getStart();
		byte[] all = new byte[(int) block.getSize()];
		block.getBytes(start, all);
		long n = all.length / 16;
		List<long[]> triples = new ArrayList<>();
		for (int i = 1; i < args.length; i++) {
			String[] p = args[i].split(",");
			triples.add(new long[] { Long.parseLong(p[0]), Long.parseLong(p[1]), Long.parseLong(p[2]) });
		}
		if (triples.isEmpty()) {
			triples.add(new long[] { 0, 0, 0 });
		}
		PseudoDisassembler dis = new PseudoDisassembler(currentProgram);
		int[] offs = { 0, 6, 11 };
		for (long[] tr : triples) {
			for (long b = 0; b < n; b++) {
				int o = (int) (16 * b);
				int t = all[o] & 0x1f;
				Address a = start.add(16 * b);
				for (int s = 0; s < 3; s++) {
					Address sa = a.add(offs[s]);
					RegisterValue v = new RegisterValue(base, BigInteger.ZERO);
					v = v.assign(slot, BigInteger.valueOf(s)).assign(rsol, BigInteger.valueOf(tr[0]))
							.assign(rout, BigInteger.valueOf(tr[1])).assign(rsor, BigInteger.valueOf(tr[2]));
					if (s > 0) {
						v = v.assign(tmpl, BigInteger.valueOf(t))
								.assign(s1lo, BigInteger.valueOf((all[o + 5] >> 6) & 3))
								.assign(s2lo, BigInteger.valueOf((all[o + 10] >> 7) & 1));
					}
					PseudoDisassemblerContext pc = new PseudoDisassemblerContext(ctx);
					pc.setValue(base, sa, v.getUnsignedValue());
					try {
						PseudoInstruction ins = dis.disassemble(sa, pc, false);
						walk(((SleighInstructionPrototype) ins.getPrototype()).getRootState());
						if (s == 1 && ins.getLength() == 10) {
							break;
						}
					}
					catch (Exception e) {
						// undecodable slot
					}
				}
			}
		}
		for (String k : seen) {
			out.println("SEEN " + k);
		}
		SleighLanguage lang = (SleighLanguage) currentProgram.getLanguage();
		for (Symbol sym : lang.getSymbolTable().getSymbolList()) {
			if (sym instanceof SubtableSymbol st) {
				for (int i = 0; i < st.getNumConstructors(); i++) {
					out.println("ALL " + key(st.getConstructor(i)));
				}
			}
		}
		// root constructors
		out.close();
	}
}
