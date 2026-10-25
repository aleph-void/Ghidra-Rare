// Fixed-stride disassembly dump for the 65816 test harness (no analysis).
// Decodes one instruction at the start of every <stride>-byte record with the given M/X/E
// context, so each record is checked independently of its neighbours.
// One line per record: "<address-hex6> <bytes-hex> <instruction text>"; with mode "pcode" the
// flow type and p-code ops follow, indented.
// Script args: <outfile> <stride> <MF> <XF> <EF> [mode]
//@category Testing

import java.io.PrintStream;
import java.math.BigInteger;

import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.InstructionPrototype;
import ghidra.program.model.lang.ProcessorContextImpl;
import ghidra.program.model.lang.Register;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.mem.MemoryBufferImpl;
import ghidra.program.model.pcode.PcodeOp;

public class G65816DumpDisasm extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = new PrintStream(args[0]);
		int stride = Integer.parseInt(args[1]);
		long mf = Long.parseLong(args[2]), xf = Long.parseLong(args[3]), ef = Long.parseLong(args[4]);
		boolean pcode = args.length > 5 && args[5].equals("pcode");
		var lang = currentProgram.getLanguage();
		Register ctxMF = lang.getRegister("ctx_MF");
		Register ctxXF = lang.getRegister("ctx_XF");
		Register ctxEF = lang.getRegister("ctx_EF");

		for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
			if (!block.isInitialized()) {
				continue;
			}
			Address end = block.getEnd();
			for (Address a = block.getStart(); a.compareTo(end) <= 0; a = a.add(stride)) {
				String text;
				String hex = "";
				PseudoInstruction ins = null;
				try {
					ProcessorContextImpl ctx = new ProcessorContextImpl(lang);
					ctx.setValue(ctxMF, BigInteger.valueOf(mf));
					ctx.setValue(ctxXF, BigInteger.valueOf(xf));
					ctx.setValue(ctxEF, BigInteger.valueOf(ef));
					MemoryBufferImpl buf = new MemoryBufferImpl(currentProgram.getMemory(), a);
					InstructionPrototype p = lang.parse(buf, ctx, false);
					ins = new PseudoInstruction(currentProgram, a, p, buf, ctx);
					text = ins.toString();
					StringBuilder sb = new StringBuilder();
					for (byte b : ins.getBytes()) {
						sb.append(String.format("%02x", b & 0xff));
					}
					hex = sb.toString();
				}
				catch (Exception e) {
					text = "BAD (" + String.valueOf(e.getMessage()).split("\n")[0] + ")";
					hex = String.format("%02x", currentProgram.getMemory().getByte(a) & 0xff);
				}
				out.printf("%06x %s %s%n", a.getOffset(), hex, text);
				if (pcode && ins != null) {
					out.printf("    flow=%s%n", ins.getFlowType());
					for (PcodeOp op : ins.getPcode()) {
						out.printf("    %s%n", op);
					}
				}
				if (a.add(stride - 1).compareTo(end) > 0 || a.getOffset() + stride > end.getOffset() + 1) {
					break;
				}
			}
		}
		out.close();
	}
}
