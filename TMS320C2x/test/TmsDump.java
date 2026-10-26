// Decode dump for the TMS320C2x/C5x tests (no analysis). Disassembles the first memory block
// every <stride> words (stride 0 = linear sweep) and prints
// "<word-offset-hex> <length-in-words> <instruction text>" per decode. With "pcode" as the
// fourth argument, also prints each instruction's p-code and flows.
// Script args: <outfile|outdir/> <stride> [ctx|-] [pcode]
//   a directory: writes <outdir>/<program name>.txt;  ctx: "name=value,..." over the image
//@category Testing

import java.io.PrintStream;
import java.math.BigInteger;

import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoDisassemblerContext;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.InstructionPrototype;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.mem.MemoryBufferImpl;
import ghidra.program.model.pcode.PcodeOp;

public class TmsDump extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		String o = args[0];
		if (o.endsWith("/")) {
			o = o + currentProgram.getName() + ".txt";
		}
		PrintStream out = new PrintStream(o);
		int stride = Integer.decode(args[1]);
		boolean pcode = args.length > 3 && args[3].equals("pcode");
		ProgramContext ctx = currentProgram.getProgramContext();
		MemoryBlock block = currentProgram.getMemory().getBlocks()[0];
		if (args.length > 2 && !args[2].equals("-")) {
			for (String kv : args[2].split(",")) {
				String[] p = kv.split("=");
				ctx.setValue(ctx.getRegister(p[0]), block.getStart(), block.getEnd(),
					BigInteger.valueOf(Long.decode(p[1])));
			}
		}
		if (pcode) {
			out.println("# block " + block.getName() + " " + block.getStart() + "-" + block.getEnd() +
				" size " + block.getSize() + " space " + block.getStart().getAddressSpace().getName() +
				" unit " + block.getStart().getAddressSpace().getAddressableUnitSize());
		}
		Address a = block.getStart();
		Address end = block.getEnd();
		while (a.compareTo(end) <= 0) {
			String text;
			int n;
			PseudoInstruction ins = null;
			try {
				// PseudoDisassembler.disassemble() returns null for word-addressed spaces; parse
				// directly with the program context at the address instead.
				MemoryBufferImpl buf = new MemoryBufferImpl(currentProgram.getMemory(), a);
				PseudoDisassemblerContext pc = new PseudoDisassemblerContext(ctx);
				pc.flowStart(a);
				InstructionPrototype pr = currentProgram.getLanguage().parse(buf, pc, false);
				ins = new PseudoInstruction(currentProgram, a, pr, buf, pc);
				text = ins.toString();
				n = ins.getLength() / 2;
			}
			catch (Exception e) {
				text = "BAD " + (pcode ? e.toString() : "");
				n = 1;
			}
			out.printf("%x %d %s%n", a.subtract(block.getStart()) / 2, n, text);
			if (pcode && ins != null) {
				for (PcodeOp op : ins.getPcode()) {
					out.println("    " + op);
				}
				for (Address f : ins.getFlows()) {
					out.println("    flow " + f);
				}
				out.println("    flowtype " + ins.getFlowType() + " delay " + ins.getDelaySlotDepth());
			}
			long step = 2L * (stride > 0 ? stride : n);
			if (end.subtract(a) < step) {
				break;
			}
			a = a.add(step);
		}
		out.close();
	}
}
