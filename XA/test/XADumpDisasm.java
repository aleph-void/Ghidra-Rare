// Disassembly dump for the XA decode tests (no analysis).
// Prints "<address-hex> <bytes-hex> <instruction text>" per instruction.
// Script args: <outfile> [stride] [ctx]
//   stride: 0 (default) = linear sweep; n > 0 = decode only at block start + k*n (slot images,
//           one test instruction per slot)
//   ctx:    "name=value,..." context assignments over the code block (e.g. dsk=0)
//@category Testing

import java.io.PrintStream;
import java.math.BigInteger;

import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoDisassembler;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.MemoryBlock;

public class XADumpDisasm extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = new PrintStream(args[0]);
		int stride = args.length > 1 ? Integer.decode(args[1]) : 0;
		ProgramContext ctx = currentProgram.getProgramContext();
		for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
			if (!block.isInitialized() || !block.getStart().getAddressSpace().getName().equals("code")) {
				continue;
			}
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
				StringBuilder hex = new StringBuilder();
				for (int i = 0; i < n; i++) {
					try {
						hex.append(String.format("%02x", block.getByte(a.add(i)) & 0xff));
					}
					catch (Exception e) {
						break;
					}
				}
				out.printf("%06x %s %s%n", a.getOffset(), hex, text);
				int step = stride > 0 ? stride : n;
				if (a.getOffset() + step > end.getOffset()) {
					break;
				}
				a = a.add(step);
			}
		}
		out.close();
	}
}
