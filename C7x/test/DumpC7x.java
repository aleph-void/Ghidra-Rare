// Packet-aware linear disassembly dump for C7x (no auto-analysis).
// Disassembles each block by fall-through flow so that the execute-packet context
// (p-bit chaining, CSTX constant extensions, CCEXT condition extensions) propagates
// exactly as it does during normal Ghidra flow disassembly.
// Prints one line per instruction: "<offset-hex> <bytes-hex> <instruction text>"
// Script args: <outfile>
//@category Testing

import java.io.PrintStream;

import ghidra.app.script.GhidraScript;
import ghidra.program.disassemble.Disassembler;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.mem.MemoryBlock;

public class DumpC7x extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = args.length > 0 ? new PrintStream(args[0]) : System.out;
		Disassembler dis = Disassembler.getDisassembler(currentProgram, monitor, null);
		for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
			if (!block.isInitialized()) {
				continue;
			}
			AddressSet set = new AddressSet(block.getStart(), block.getEnd());
			Address base = block.getStart();
			Address end = block.getEnd();
			Address a = base;
			while (a.compareTo(end) <= 0) {
				Instruction ins = currentProgram.getListing().getInstructionAt(a);
				if (ins == null) {
					dis.disassemble(a, set, false);
					ins = currentProgram.getListing().getInstructionAt(a);
				}
				String text;
				int n;
				if (ins != null) {
					text = ins.toString();
					n = ins.getLength();
				}
				else {
					text = "BAD";
					n = 4;
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
				out.printf("%08x %s %s%n", a.subtract(base), hex, text);
				if (a.getOffset() + n > end.getOffset()) {
					break;
				}
				a = a.add(n);
			}
		}
		out.flush();
		if (out != System.out) {
			out.close();
		}
	}
}
