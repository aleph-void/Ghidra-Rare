// Disassembly dump for the DSP56000 decode tests (no analysis).
// Prints "<word-address-hex> <instruction words hex> <instruction text>" per instruction.
// Script args: <outfile> [stride] [ctx]
//   stride: 0 (default) = linear sweep; n > 0 = decode only at block start + k*n words (slot
//           images, one test instruction per slot)
//   ctx:    "name=value,..." context assignments over the code block
//@category Testing

import java.io.PrintStream;
import java.math.BigInteger;

import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoDisassembler;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.MemoryBlock;

public class DspDumpDisasm extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = new PrintStream(args[0]);
		int stride = args.length > 1 ? Integer.decode(args[1]) : 0;
		ProgramContext ctx = currentProgram.getProgramContext();
		for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
			if (!block.isInitialized() || !block.getStart().getAddressSpace().getName().equals("p")) {
				continue;
			}
			int unit = block.getStart().getAddressSpace().getAddressableUnitSize();
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
				int words;
				try {
					PseudoInstruction ins = dis.disassemble(a);
					text = ins.toString();
					words = ins.getLength() / unit;
				}
				catch (Exception e) {
					text = "BAD";
					words = 1;
				}
				StringBuilder hex = new StringBuilder();
				for (int i = 0; i < words; i++) {
					byte[] b = new byte[unit];
					try {
						currentProgram.getMemory().getBytes(a.add((long) i * unit), b);
					}
					catch (Exception e) {
						break;
					}
					if (i > 0) {
						hex.append(' ');
					}
					for (byte x : b) {
						hex.append(String.format("%02x", x & 0xff));
					}
				}
				out.printf("%04x %s %s%n", a.getAddressableWordOffset(), hex, text);
				long step = (long) (stride > 0 ? stride : words) * unit;
				if (a.getOffset() + step > end.getOffset()) {
					break;
				}
				a = a.add(step);
			}
		}
		out.close();
	}
}
