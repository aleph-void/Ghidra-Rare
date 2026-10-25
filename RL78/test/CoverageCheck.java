// Every-entry decode test: for every constructor of the language's root instruction table, build
// instruction bytes (and context) from its decision-tree pattern, filling free bits at random,
// decode them, and record every constructor (root and subtable) that appears in the resulting
// constructor tree. Constructors that are never reached are reported: they are shadowed by a
// more specific pattern or unreachable, which random differential fuzzing cannot see when the
// reference tool also rejects the encoding.
// Script args: <outfile> [tries-per-pattern (default 64)] [seed]
// Output: "unreached <table> <file>:<line> <print pieces>" lines, then a summary line.
//@category Testing

import java.io.PrintStream;
import java.math.BigInteger;
import java.util.*;

import ghidra.app.plugin.processors.sleigh.*;
import ghidra.app.plugin.processors.sleigh.pattern.DisjointPattern;
import ghidra.app.plugin.processors.sleigh.pattern.PatternBlock;
import ghidra.app.plugin.processors.sleigh.symbol.SubtableSymbol;
import ghidra.app.plugin.processors.sleigh.symbol.Symbol;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.*;
import ghidra.program.model.mem.ByteMemBufferImpl;

public class CoverageCheck extends GhidraScript {

	private static final byte[] SPECIAL = { 0x00, (byte) 0xff, (byte) 0xf8, (byte) 0xf9,
		(byte) 0xfa, (byte) 0xfb, (byte) 0xfc, (byte) 0xfd, (byte) 0xfe, (byte) 0x80, 0x7f, 0x01,
		0x20, 0x1f };

	private static void collect(DecisionNode n, List<DisjointPattern> pats, List<Constructor> cons) {
		if (n == null) {
			return;
		}
		pats.addAll(n.getPatterns());
		cons.addAll(n.getConstructors());
		for (DecisionNode c : n.getChildren()) {
			collect(c, pats, cons);
		}
	}

	private static String key(Constructor c) {
		return c.getParent().getName() + " " + c.getSourceFile() + ":" + c.getLineno();
	}

	private static void walk(ConstructState s, Set<String> seen) {
		if (s == null) {
			return;
		}
		if (s.getConstructor() != null) {
			seen.add(key(s.getConstructor()));
		}
		for (int i = 0; i < s.getNumSubStates(); i++) {
			walk(s.getSubState(i), seen);
		}
	}

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = new PrintStream(args[0]);
		int tries = args.length > 1 ? Integer.parseInt(args[1]) : 64;
		Random rnd = new Random(args.length > 2 ? Long.parseLong(args[2]) : 1);
		SleighLanguage lang = (SleighLanguage) currentProgram.getLanguage();
		Register ctxReg = lang.getContextBaseRegister();
		int ctxBits = ctxReg == null || ctxReg == Register.NO_CONTEXT ? 0 : ctxReg.getBitLength();
		BigInteger ctxDefault = BigInteger.ZERO;
		if (ctxBits > 0) {
			RegisterValue dv = currentProgram.getProgramContext().getDefaultDisassemblyContext();
			if (dv != null && dv.getUnsignedValueIgnoreMask() != null) {
				ctxDefault = dv.getUnsignedValueIgnoreMask();
			}
		}

		// all constructors of all tables
		Map<String, Constructor> all = new TreeMap<>();
		List<DisjointPattern> rootPats = new ArrayList<>();
		List<Constructor> rootCons = new ArrayList<>();
		for (Symbol sym : lang.getSymbolTable().getSymbolList()) {
			if (sym instanceof SubtableSymbol st) {
				for (int i = 0; i < st.getNumConstructors(); i++) {
					all.put(key(st.getConstructor(i)), st.getConstructor(i));
				}
				if (st.getName().equals("instruction")) {
					collect(st.getDecisionNode(), rootPats, rootCons);
				}
			}
		}

		Set<String> seen = new HashSet<>();
		Address addr = currentProgram.getMinAddress();
		int decoded = 0, failed = 0;
		for (int p = 0; p < rootPats.size(); p++) {
			DisjointPattern dp = rootPats.get(p);
			PatternBlock ib = dp.getInstructionBlock();
			PatternBlock cb = dp.getContextBlock();
			for (int t = 0; t < tries; t++) {
				byte[] bytes = new byte[16];
				rnd.nextBytes(bytes);
				// bias free bytes towards boundary values so that equality-constrained
				// subtable entries (register aliases, special fields) are reached
				for (int i = 0; i < bytes.length; i++) {
					if (rnd.nextInt(3) == 0) {
						bytes[i] = SPECIAL[rnd.nextInt(SPECIAL.length)];
					}
				}
				if (ib != null) {
					int off = ib.getOffset();
					int[] m = ib.getMaskVector(), v = ib.getValueVector();
					for (int w = 0; w < m.length; w++) {
						for (int b = 0; b < 4; b++) {
							int i = off + w * 4 + b;
							if (i >= bytes.length) {
								continue;
							}
							int mb = (m[w] >>> (24 - 8 * b)) & 0xff;
							int vb = (v[w] >>> (24 - 8 * b)) & 0xff;
							bytes[i] = (byte) ((bytes[i] & ~mb) | (vb & mb));
						}
					}
				}
				ProcessorContextImpl ctx = new ProcessorContextImpl(lang);
				if (ctxBits > 0) {
					// half the tries keep the default context for unconstrained bits, half randomize
					BigInteger val = t % 2 == 0 ? ctxDefault : new BigInteger(ctxBits, rnd);
					if (cb != null) {
						int[] m = cb.getMaskVector(), v = cb.getValueVector();
						int words = (ctxBits + 31) / 32;
						for (int w = 0; w < m.length && w < words; w++) {
							int shift = ctxBits - 32 * (w + 1);
							BigInteger mm = BigInteger.valueOf(m[w] & 0xffffffffL);
							BigInteger vv = BigInteger.valueOf(v[w] & 0xffffffffL);
							if (shift >= 0) {
								mm = mm.shiftLeft(shift);
								vv = vv.shiftLeft(shift);
							}
							else {
								mm = mm.shiftRight(-shift);
								vv = vv.shiftRight(-shift);
							}
							val = val.andNot(mm).or(vv.and(mm));
						}
					}
					ctx.setRegisterValue(new RegisterValue(ctxReg, val));
				}
				try {
					SleighInstructionPrototype proto = (SleighInstructionPrototype) lang.parse(
						new ByteMemBufferImpl(addr, bytes, lang.isBigEndian()), ctx, false);
					walk(proto.getRootState(), seen);
					decoded++;
				}
				catch (Exception e) {
					failed++;
				}
			}
		}
		int unreached = 0;
		for (Map.Entry<String, Constructor> e : all.entrySet()) {
			if (!seen.contains(e.getKey())) {
				unreached++;
				out.println("unreached " + e.getKey() + " " +
					String.join("", e.getValue().getPrintPieces()).trim());
			}
		}
		out.printf("coverage: %d constructors, %d reached, %d unreached; %d root patterns, " +
			"%d decodes, %d rejected%n", all.size(), all.size() - unreached, unreached,
			rootPats.size(), decoded, failed);
		out.close();
	}
}
