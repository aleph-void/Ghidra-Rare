// Linear-sweep disassembly dump for the Alpha test harness (no analysis).
// Steps one 32-bit instruction word at a time.
// One line per instruction word:
//   "<byte-offset-hex> <word-hex> <instruction text>"        (mode "dis")
//   ... followed by indented p-code ops                          (mode "pcode")
// Script args: <outfile> [mode]
//@category Testing

import java.io.PrintStream;

import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.pcode.PcodeOp;
import ghidra.program.model.lang.InstructionPrototype;
import ghidra.program.model.mem.MemoryBufferImpl;
import ghidra.program.model.lang.ProcessorContextImpl;

public class DumpDisasm extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = args.length > 0 ? new PrintStream(args[0]) : System.out;
		boolean pcode = args.length > 1 && args[1].equals("pcode");

		for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
			if (!block.isInitialized() || !block.isExecute() && !block.getStart().getAddressSpace().getName().equals("code")) {
				continue;
			}
			Address base = block.getStart();
			Address end = block.getEnd();
			int unit = 4;
			for (Address a = base; a.compareTo(end) <= 0; a = a.add(unit)) {
				byte[] w = new byte[unit];
				try {
					currentProgram.getMemory().getBytes(a, w);
				}
				catch (Exception e) {
					break;
				}
				StringBuilder hex = new StringBuilder();
				for (int i = unit - 1; i >= 0; i--) {
					hex.append(String.format("%02x", w[i] & 0xff));
				}
				String text;
				PseudoInstruction ins = null;
				try {
					// parse the prototype directly with a default context
					ProcessorContextImpl ctx = new ProcessorContextImpl(currentProgram.getLanguage());
					MemoryBufferImpl buf = new MemoryBufferImpl(currentProgram.getMemory(), a);
					InstructionPrototype p = currentProgram.getLanguage().parse(buf, ctx, false);
					ins = new PseudoInstruction(currentProgram, a, p, buf, ctx);
					text = ins.toString();
				}
				catch (Exception e) {
					text = "BAD (" + String.valueOf(e.getMessage()).split("\n")[0] + ")";
				}
				out.printf("%08x %s %s%n", a.subtract(base), hex, text);
				if (pcode && ins != null) {
					out.printf("    flow=%s%n", ins.getFlowType());
					for (PcodeOp op : ins.getPcode()) {
						out.printf("    %s%n", op);
					}
				}
				if (a.equals(end)) {
					break;
				}
			}
		}
		out.flush();
		if (out != System.out) {
			out.close();
		}
	}
}
