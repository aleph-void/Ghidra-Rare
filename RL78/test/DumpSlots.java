// Decode the first instruction of every fixed-size slot of the current program's first block
// with the language's default context (optionally overriding context fields).
// Prints "<offset-hex> <len> <text>" per slot, "<offset> 0 BAD" when the language rejects it.
// Script args: <slot> <outfile> [ctxfield=value ...]
//@category Testing

import java.io.PrintStream;
import java.math.BigInteger;

import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.InstructionPrototype;
import ghidra.program.model.lang.Language;
import ghidra.program.model.lang.ProcessorContextImpl;
import ghidra.program.model.lang.Register;
import ghidra.program.model.mem.DumbMemBufferImpl;
import ghidra.program.model.mem.MemBuffer;
import ghidra.program.model.mem.MemoryBlock;

public class DumpSlots extends GhidraScript {
	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		int slot = Integer.decode(args[0]);
		PrintStream out = new PrintStream(args[1]);
		Language lang = currentProgram.getLanguage();
		ProcessorContextImpl ctx = new ProcessorContextImpl(lang);
		Register cr = lang.getContextBaseRegister();
		if (cr != null && cr != Register.NO_CONTEXT) {
			ctx.setRegisterValue(currentProgram.getProgramContext().getDefaultDisassemblyContext());
		}
		for (int i = 2; i < args.length; i++) {
			String[] kv = args[i].split("=");
			ctx.setValue(lang.getRegister(kv[0]), new BigInteger(kv[1]));
		}
		MemoryBlock block = currentProgram.getMemory().getBlocks()[0];
		Address base = block.getStart();
		long size = block.getSize();
		for (long off = 0; off + slot <= size; off += slot) {
			Address a = base.add(off);
			String text;
			int n;
			try {
				MemBuffer buf = new DumbMemBufferImpl(currentProgram.getMemory(), a);
				InstructionPrototype proto = lang.parse(buf, ctx, false);
				PseudoInstruction pi = new PseudoInstruction(currentProgram, a, proto, buf, ctx);
				text = pi.toString();
				n = pi.getLength();
			}
			catch (Exception e) {
				text = "BAD";
				n = 0;
			}
			out.printf("%08x %d %s%n", off, n, text);
		}
		out.close();
	}
}
