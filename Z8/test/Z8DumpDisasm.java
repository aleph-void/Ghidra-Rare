// Linear-sweep disassembly dump for the Z8 decode tests (no analysis).
// Prints "<address-hex> <bytes-hex> <instruction text>" per instruction.
// Script args: <outfile> [rp]   rp: register pointer value to assume (sets the rpv/rpg/rpb
// context over the whole image); omitted = RP unknown (dynamic working registers).
//@category Testing

import java.io.PrintStream;
import java.math.BigInteger;

import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoDisassembler;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.MemoryBlock;

public class Z8DumpDisasm extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = new PrintStream(args[0]);
		ProgramContext ctx = currentProgram.getProgramContext();
		if (args.length > 1) {
			int rp = Integer.decode(args[1]);
			for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
				if (!b.getStart().getAddressSpace().getName().equals("code")) {
					continue;
				}
				ctx.setValue(ctx.getRegister("rpv"), b.getStart(), b.getEnd(), BigInteger.ONE);
				ctx.setValue(ctx.getRegister("rpg"), b.getStart(), b.getEnd(),
					BigInteger.valueOf(rp >> 4));
				ctx.setValue(ctx.getRegister("rpb"), b.getStart(), b.getEnd(),
					BigInteger.valueOf(rp & 15));
			}
		}
		PseudoDisassembler dis = new PseudoDisassembler(currentProgram);
		for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
			if (!block.isInitialized() || !block.getStart().getAddressSpace().getName().equals("code")) {
				continue;
			}
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
				out.printf("%04x %s %s%n", a.getOffset(), hex, text);
				if (a.getOffset() + n > end.getOffset()) {
					break;
				}
				a = a.add(n);
			}
		}
		out.close();
	}
}
