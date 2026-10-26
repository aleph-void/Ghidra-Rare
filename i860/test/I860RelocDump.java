// Relocation check helper: prints the start of each loaded section and the 32-bit words of every
// initialized block, so test/reloc-check.sh can link the same object with GNU ld at the same
// addresses and compare. Script args: <outfile>
//@category Testing

import java.io.PrintStream;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.mem.MemoryBlock;

public class I860RelocDump extends GhidraScript {
	@Override
	protected void run() throws Exception {
		PrintStream out = new PrintStream(getScriptArgs()[0]);
		for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
			if (!b.isInitialized() || b.getName().startsWith(".rela") || b.getName().startsWith("_elf")) {
				continue;
			}
			out.printf("section %s %08x %d%n", b.getName(), b.getStart().getOffset(), b.getSize());
			for (long a = 0; a + 4 <= b.getSize(); a += 4) {
				out.printf("word %08x %08x%n", b.getStart().getOffset() + a,
					currentProgram.getMemory().getInt(b.getStart().add(a)) & 0xffffffffL);
			}
		}
		out.close();
	}
}
