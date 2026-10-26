// Slot-by-slot disassembly of a raw image of IA-64 bundles (no analysis), for the decode tests.
// For every bundle the script sets the slot context (slot, tmpl, s1lo, s2lo) at bundle+6 and
// bundle+11 from the bundle bytes, as slot 0's globalset would during flow, and decodes slot 0,
// slot 1 (or the L+X pair) and slot 2 independently.
// Prints "<slot address hex> <slot index> <instruction text>" per slot, BAD when undecodable.
// Script args: <outfile> [cfm_sol cfm_out cfm_sor]
//@category Testing

import java.io.PrintStream;
import java.math.BigInteger;

import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoDisassembler;
import ghidra.app.util.PseudoDisassemblerContext;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.MemoryBlock;

public class IA64DumpSlots extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = new PrintStream(args[0]);
		ProgramContext ctx = currentProgram.getProgramContext();
		Register base = ctx.getBaseContextRegister();
		Register slot = ctx.getRegister("slot"), tmpl = ctx.getRegister("tmpl");
		Register s1lo = ctx.getRegister("s1lo"), s2lo = ctx.getRegister("s2lo");
		MemoryBlock block = currentProgram.getMemory().getBlocks()[0];
		Address start = block.getStart();
		long n = block.getSize() / 16;
		byte[] all = new byte[(int) block.getSize()];
		block.getBytes(start, all);
		if (args.length > 3) {
			ctx.setValue(ctx.getRegister("cfm_sol"), start, block.getEnd(), new BigInteger(args[1]));
			ctx.setValue(ctx.getRegister("cfm_out"), start, block.getEnd(), new BigInteger(args[2]));
			ctx.setValue(ctx.getRegister("cfm_sor"), start, block.getEnd(), new BigInteger(args[3]));
		}
		long sol = 0, nout = 0, sor = 0;
		if (args.length > 3) {
			sol = Long.parseLong(args[1]);
			nout = Long.parseLong(args[2]);
			sor = Long.parseLong(args[3]);
		}
		Register rsol = ctx.getRegister("cfm_sol"), rout = ctx.getRegister("cfm_out"),
				rsor = ctx.getRegister("cfm_sor");
		PseudoDisassembler dis = new PseudoDisassembler(currentProgram);
		int[] offs = { 0, 6, 11 };
		for (long b = 0; b < n; b++) {
			int o = (int) (16 * b);
			int t = all[o] & 0x1f;
			int lo1 = (all[o + 5] >> 6) & 3;
			int lo2 = (all[o + 10] >> 7) & 1;
			Address a = start.add(16 * b);
			for (int s = 0; s < 3; s++) {
				Address sa = a.add(offs[s]);
				RegisterValue v = new RegisterValue(base, BigInteger.ZERO);
				v = v.assign(slot, BigInteger.valueOf(s)).assign(rsol, BigInteger.valueOf(sol))
						.assign(rout, BigInteger.valueOf(nout)).assign(rsor, BigInteger.valueOf(sor));
				if (s > 0) {
					v = v.assign(tmpl, BigInteger.valueOf(t)).assign(s1lo, BigInteger.valueOf(lo1))
							.assign(s2lo, BigInteger.valueOf(lo2));
				}
				PseudoDisassemblerContext pc = new PseudoDisassemblerContext(ctx);
				pc.setValue(base, sa, v.getUnsignedValue());
				String text;
				int len = 0;
				try {
					PseudoInstruction ins = dis.disassemble(sa, pc, false);
					text = ins.toString();
					len = ins.getLength();
				}
				catch (Exception e) {
					text = "BAD";
				}
				out.printf("%x %d %s%n", sa.getOffset(), s, text);
				if (s == 1 && len == 10) {
					break;
				}
			}
		}
		out.close();
	}
}
