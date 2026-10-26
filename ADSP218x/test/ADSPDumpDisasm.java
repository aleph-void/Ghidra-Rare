// Disassembly dump for the ADSP-218x decode tests (no analysis).
// Prints "<word-hex> <instruction text>" for every 24-bit word, "BAD" when it does not decode.
// Script args: <outfile> [<corpus file>]
//   Without a corpus file the pm block of the imported program is decoded in place
//   ("<address> <word> <text>").  With one, the corpus (24-bit big-endian words, any length)
//   is copied through the pm block 64K words at a time, so one Ghidra run covers any number
//   of words; lines are then "<word> <text>".
//@category Testing

import java.io.BufferedOutputStream;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.PrintStream;

import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.InstructionPrototype;
import ghidra.program.model.lang.Language;
import ghidra.program.model.lang.ProcessorContextImpl;
import ghidra.program.model.mem.DumbMemBufferImpl;
import ghidra.program.model.mem.MemBuffer;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;

public class ADSPDumpDisasm extends GhidraScript {

	private Language lang;
	private Memory mem;

	private String decode(Address a) {
		try {
			MemBuffer buf = new DumbMemBufferImpl(mem, a);
			ProcessorContextImpl ctx = new ProcessorContextImpl(lang);
			InstructionPrototype p = lang.parse(buf, ctx, false);
			return new PseudoInstruction(a, p, buf, ctx).toString();
		}
		catch (Exception e) {
			return "BAD";
		}
	}

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		lang = currentProgram.getLanguage();
		mem = currentProgram.getMemory();
		MemoryBlock block = null;
		for (MemoryBlock b : mem.getBlocks()) {
			if (b.isInitialized() && b.getStart().getAddressSpace().getName().equals("pm")) {
				block = b;
				break;
			}
		}
		try (PrintStream out =
			new PrintStream(new BufferedOutputStream(new FileOutputStream(args[0]), 1 << 20))) {
			if (args.length < 2) {
				byte[] b = new byte[(int) block.getSize()];
				block.getBytes(block.getStart(), b);
				Address a = block.getStart();
				for (int k = 0; k < b.length / 3; k++) {
					int w = ((b[3 * k] & 0xff) << 16) | ((b[3 * k + 1] & 0xff) << 8) |
						(b[3 * k + 2] & 0xff);
					out.printf("%04x %06x %s%n", a.getAddressableWordOffset() & 0xffff, w,
						decode(a));
					if (3 * (k + 1) < b.length) {
						a = a.addWrap(3);
					}
				}
				return;
			}
			int cap = (int) (block.getSize() / 3);
			byte[] chunk = new byte[cap * 3];
			try (InputStream in = new FileInputStream(args[1])) {
				int n;
				while ((n = in.readNBytes(chunk, 0, chunk.length)) > 0) {
					mem.setBytes(block.getStart(), chunk, 0, n);
					Address a = block.getStart();
					for (int k = 0; k < n / 3; k++) {
						int w = ((chunk[3 * k] & 0xff) << 16) | ((chunk[3 * k + 1] & 0xff) << 8) |
							(chunk[3 * k + 2] & 0xff);
						out.printf("%06x %s%n", w, decode(a));
						a = a.addWrap(3);
					}
				}
			}
		}
	}
}
