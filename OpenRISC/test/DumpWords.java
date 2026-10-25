// Decode every aligned 32-bit word of each memory block on its own (Language.parse, no flow or
// delay-slot checks), for differential testing against objdump. Unlike PseudoDisassembler this
// also decodes a branch whose "delay slot" happens to hold another branch.
// Prints one line per word: "<offset-hex> <bytes-hex> <instruction text | BAD (...)>"
// Script args: <outfile>
//@category Testing

import java.io.PrintStream;

import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.InstructionPrototype;
import ghidra.program.model.lang.Language;
import ghidra.program.model.lang.ProcessorContextImpl;
import ghidra.program.model.mem.DumbMemBufferImpl;
import ghidra.program.model.mem.MemBuffer;
import ghidra.program.model.mem.MemoryBlock;

public class DumpWords extends GhidraScript {

	@Override
	protected void run() throws Exception {
		PrintStream out = new PrintStream(getScriptArgs()[0]);
		Language lang = currentProgram.getLanguage();
		for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
			if (!block.isInitialized()) {
				continue;
			}
			Address base = block.getStart();
			for (long off = 0; off + 4 <= block.getSize(); off += 4) {
				Address a = base.add(off);
				String text;
				try {
					ProcessorContextImpl ctx = new ProcessorContextImpl(lang);
					MemBuffer buf = new DumbMemBufferImpl(currentProgram.getMemory(), a);
					InstructionPrototype proto = lang.parse(buf, ctx, false);
					text = new PseudoInstruction(currentProgram, a, proto, buf, ctx).toString();
				}
				catch (Exception e) {
					text = "BAD (" + String.valueOf(e.getMessage()).split("\n")[0] + ")";
				}
				StringBuilder hex = new StringBuilder();
				for (int i = 0; i < 4; i++) {
					hex.append(String.format("%02x", block.getByte(a.add(i)) & 0xff));
				}
				out.printf("%08x %s %s%n", off, hex, text);
			}
		}
		out.close();
	}
}
