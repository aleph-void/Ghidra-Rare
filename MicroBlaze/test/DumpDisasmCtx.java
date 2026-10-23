// Linear-sweep disassembly dump that, unlike tools/DumpDisasm.java, uses the real Ghidra
// Disassembler so that context set with globalset() (the MicroBlaze imm/imml prefixes) is
// carried to the following instruction.
// Prints one line per instruction: "<offset-hex> <bytes-hex> <instruction text>"
// Script args: [step] [outfile]
//@category Testing

import java.io.PrintStream;
import java.math.BigInteger;

import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoDisassembler;
import ghidra.app.util.PseudoInstruction;
import ghidra.program.disassemble.Disassembler;
import ghidra.program.model.lang.InstructionPrototype;
import ghidra.program.model.lang.Language;
import ghidra.program.model.lang.ProcessorContextImpl;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;
import ghidra.program.model.mem.DumbMemBufferImpl;
import ghidra.program.model.mem.MemBuffer;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.MemoryBlock;

public class DumpDisasmCtx extends GhidraScript {

	// Parse a single instruction directly with the language (no delay-slot checks), using the
	// context value stored in the program at that address.
	private PseudoInstruction parseOne(Address a) throws Exception {
		Language lang = currentProgram.getLanguage();
		ProcessorContextImpl ctx = new ProcessorContextImpl(lang);
		Register cr = lang.getContextBaseRegister();
		if (cr != null && cr != Register.NO_CONTEXT) {
			RegisterValue v = currentProgram.getProgramContext().getDisassemblyContext(a);
			if (v != null) {
				ctx.setRegisterValue(v);
			}
		}
		// If the real disassembler refused this instruction, the context that a preceding
		// imm/imml prefix set with globalset() was never committed to the program. Recreate it
		// from the prefix words (same rule as the SLEIGH spec) so the text can be compared.
		long p1 = word(a, -4), p2 = word(a, -8);
		boolean imml1 = p1 >= 0 && (p1 >>> 24) == 0xb2 && lang.getRegister("immlcnt") != null;
		boolean imml2 = imml1 && p2 >= 0 && (p2 >>> 24) == 0xb2;
		if (imml1) {
			ctx.setValue(lang.getRegister("immlcnt"), BigInteger.valueOf(imml2 ? 2 : 1));
			ctx.setValue(lang.getRegister("immlb"), BigInteger.valueOf(p1 & 0xffffff));
			if (imml2) {
				ctx.setValue(lang.getRegister("immla"), BigInteger.valueOf(p2 & 0xffffff));
			}
		}
		else if (p1 >= 0 && (p1 & 0xffff0000L) == 0xb0000000L) {
			ctx.setValue(lang.getRegister("immflag"), BigInteger.ONE);
			ctx.setValue(lang.getRegister("immhi"), BigInteger.valueOf(p1 & 0xffff));
		}
		MemBuffer buf = new DumbMemBufferImpl(currentProgram.getMemory(), a);
		InstructionPrototype proto = lang.parse(buf, ctx, false);
		return new PseudoInstruction(currentProgram, a, proto, buf, ctx);
	}

	private long word(Address a, int delta) {
		try {
			Address b = a.add(delta);
			byte[] x = new byte[4];
			if (currentProgram.getMemory().getBytes(b, x) != 4) {
				return -1;
			}
			long v = 0;
			for (int i = 0; i < 4; i++) {
				int k = currentProgram.getLanguage().isBigEndian() ? i : 3 - i;
				v = (v << 8) | (x[k] & 0xff);
			}
			return v;
		}
		catch (Exception e) {
			return -1;
		}
	}

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		int step = args.length > 0 ? Integer.decode(args[0]) : 4;
		PrintStream out = args.length > 1 ? new PrintStream(args[1]) : System.out;

		Listing listing = currentProgram.getListing();
		Disassembler dis = Disassembler.getDisassembler(currentProgram, monitor, null);
		PseudoDisassembler pdis = new PseudoDisassembler(currentProgram);
		for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
			if (!block.isInitialized()) {
				continue;
			}
			Address base = block.getStart();
			Address end = block.getEnd();
			Address a = base;
			while (a.compareTo(end) <= 0) {
				Instruction ins = listing.getInstructionAt(a);
				if (ins == null && listing.getInstructionContaining(a) == null) {
					Address last = a.add(7).compareTo(end) > 0 ? end : a.add(7);
					dis.disassemble(a, new AddressSet(a, last), false);
					ins = listing.getInstructionAt(a);
				}
				String text;
				int n;
				if (ins != null) {
					text = ins.toString();
					n = ins.getLength();
				}
				else {
					// Real disassembly can refuse an instruction (e.g. a branch whose delay slot is
					// another branch, or runs off the block); fall back to the pseudo disassembler,
					// which still sees any prefix context already committed to the program.
					try {
						PseudoInstruction pi = parseOne(a);
						text = pi.toString();
						n = pi.getLength();
					}
					catch (Exception e) {
						text = "BAD (" + String.valueOf(e.getMessage()).split("\n")[0] + ")";
						n = step;
					}
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
