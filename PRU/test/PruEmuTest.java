// P-code semantics check: emulates test/emu/emu_test.bin (imported raw at
// code:0) with Ghidra's EmulatorHelper until HALT and compares registers with
// values worked out by hand from SPRUIJ2.  Prints PASS/FAIL lines and a total.
// Script args: [outfile]
//@category Testing

import java.io.PrintStream;
import java.math.BigInteger;

import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;

public class PruEmuTest extends GhidraScript {

	private static final Object[][] EXPECT = {
		{ "r25.w0", 2L }, // JAL link = word address of the next instruction
		{ "r2", 0L }, { "ra.w0", 1L }, { "ra.w2", 0x29L }, { "r5", 0L }, { "r6", 1L },
		{ "r8", 0xffffffffL }, { "r9", 3L }, { "r10", 5L }, { "r11", 0x50L },
		{ "r12", 0xfL }, { "r13", 6L }, { "r14", 32L }, { "r15", 0xfffaL },
		{ "r16", 0x7fffffffL }, { "r17", 8L }, { "r18", 3L }, { "r19", 5L },
		{ "r20", 0x11223344L }, { "r21", 0x2233L }, { "r23", 0x00223300L },
		{ "r24", 0x22L }, { "r1.b0", 83L }, { "r26", 15L }, { "r27", 0xffffffffL },
		{ "r28", 7L }, { "r29.b0", 15L }, { "r30", 2L }, { "r22", 0x00550100L },
	};

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = args.length > 0 ? new PrintStream(args[0]) : System.out;
		EmulatorHelper emu = new EmulatorHelper(currentProgram);
		Address pc = currentProgram.getAddressFactory().getAddressSpace("code").getAddress(0);
		disassemble(pc); // flow disassembly applies the LOOP end-of-body context
		emu.writeRegister(emu.getPCRegister(), pc.getOffset());
		int steps = 0;
		while (steps++ < 1000) {
			Address cur = emu.getExecutionAddress();
			Instruction ins = getInstructionAt(cur);
			if (ins == null) {
				disassemble(cur);
				ins = getInstructionAt(cur);
			}
			if (ins != null && ins.getMnemonicString().equals("halt")) {
				break;
			}
			if (!emu.step(monitor)) {
				out.println("emulation error at " + cur + ": " + emu.getLastError());
				break;
			}
		}
		int pass = 0, fail = 0;
		for (Object[] e : EXPECT) {
			BigInteger v = emu.readRegister((String) e[0]);
			long want = (Long) e[1];
			boolean ok = v.longValue() == want;
			out.printf("%s %-7s = 0x%x (expected 0x%x)%n", ok ? "PASS" : "FAIL", e[0], v, want);
			if (ok) {
				pass++;
			}
			else {
				fail++;
			}
		}
		byte[] mem = emu.readMemory(
			currentProgram.getAddressFactory().getAddressSpace("data").getAddress(0x100), 4);
		boolean memOk = (mem[0] & 0xff) == 0x44 && (mem[3] & 0xff) == 0x11;
		out.printf("%s data[0x100] = %02x %02x %02x %02x (expected 44 33 22 11)%n",
			memOk ? "PASS" : "FAIL", mem[0], mem[1], mem[2], mem[3]);
		if (memOk) {
			pass++;
		}
		else {
			fail++;
		}
		out.printf("emulation: %d steps, %d passed, %d failed%n", steps, pass, fail);
		emu.dispose();
		out.flush();
		if (out != System.out) {
			out.close();
		}
	}
}
