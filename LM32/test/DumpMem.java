// Dump the bytes of every initialized, loaded memory block (except the ELF loader's EXTERNAL
// block) as "<address-hex> <byte-hex>" lines, for the relocation check (reloc-check.sh).
// Script args: <outfile>
//@category Testing

import java.io.PrintStream;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.mem.MemoryBlock;

public class DumpMem extends GhidraScript {

	@Override
	protected void run() throws Exception {
		PrintStream out = new PrintStream(getScriptArgs()[0]);
		for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
			if (!b.isInitialized() || !b.isLoaded() ||
				b.getName().equals(MemoryBlock.EXTERNAL_BLOCK_NAME)) {
				continue;
			}
			byte[] data = new byte[(int) b.getSize()];
			b.getBytes(b.getStart(), data);
			for (int i = 0; i < data.length; i++) {
				out.printf("%08x %02x%n", b.getStart().getOffset() + i, data[i] & 0xff);
			}
		}
		out.close();
	}
}
