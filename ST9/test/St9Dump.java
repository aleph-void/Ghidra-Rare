// Decode dump for the ST9 tests (no analysis). Disassembles every <stride> bytes (stride 0 = linear
// sweep) and prints "<offset-hex> <length> <instruction text>" per decode.
// Script args: <outfile|outdir/> <stride> [ctx]   (a directory: writes <outdir>/<program name>.txt)   ctx: "name=value,..." context assignments over the image
//@category Testing

import java.io.PrintStream;
import java.math.BigInteger;

import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoDisassembler;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.MemoryBlock;

public class St9Dump extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		String o = args[0];
		if (o.endsWith("/")) {
			o = o + currentProgram.getName() + ".txt";
		}
		PrintStream out = new PrintStream(o);
		int stride = Integer.decode(args[1]);
		ProgramContext ctx = currentProgram.getProgramContext();
		MemoryBlock block = currentProgram.getMemory().getBlocks()[0];
		if (args.length > 2 && !args[2].equals("-")) {
			for (String kv : args[2].split(",")) {
				String[] p = kv.split("=");
				ctx.setValue(ctx.getRegister(p[0]), block.getStart(), block.getEnd(),
					BigInteger.valueOf(Long.decode(p[1])));
			}
		}
		PseudoDisassembler dis = new PseudoDisassembler(currentProgram);
		Address a = block.getStart();
		Address end = block.getEnd();
		while (a.compareTo(end) <= 0) {
			String text;
			int n;
			try {
				PseudoInstruction ins = dis.disassemble(a);
				text = ins.toString();
				n = ins.getLength();
			}
			catch (Exception e) {
				text = "BAD";
				n = 1;
			}
			out.printf("%x %d %s%n", a.subtract(block.getStart()), n, text);
			long step = stride > 0 ? stride : n;
			if (a.getOffset() + step > end.getOffset()) {
				break;
			}
			a = a.add(step);
		}
		out.close();
	}
}
