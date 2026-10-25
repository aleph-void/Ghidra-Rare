// Runs the RL78 p-code semantic tests produced by emu_tests.py in Ghidra's p-code emulator.
// The program must be emu.bin imported raw at address 0.
// Script args: <tests.txt> <outfile>
//   tests.txt lines: <name> <start-hex> <stop-hex> <init key=val,...|-> <expect key=val,...>
//   keys: register names, or m1:/m2:/m3:<hex address> for 1/2/3-byte little-endian memory
// The segment() userop (the pspec segmentop: zext(seg) << 16 | zext(offset)) is supplied as a callback,
// as Ghidra's emulator does not run segmentop p-code injections.
//@category Testing

import java.io.PrintStream;
import java.math.BigInteger;
import java.nio.file.Files;
import java.nio.file.Path;

import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.pcode.emulate.BreakCallBack;
import ghidra.pcode.emulate.EmulateExecutionState;
import ghidra.pcode.memstate.MemoryState;
import ghidra.pcode.pcoderaw.PcodeOpRaw;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;

public class EmuCheck extends GhidraScript {

	// PSW bit ranges (SLEIGH bitranges are not Ghidra registers)
	private static final java.util.Map<String, Integer> FLAGS = java.util.Map.of("CY", 0, "ISP0", 1,
		"ISP1", 2, "RBS0", 3, "AC", 4, "RBS1", 5, "Z", 6, "IE", 7);

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = new PrintStream(args[1]);
		int pass = 0, fail = 0;
		for (String line : Files.readAllLines(Path.of(args[0]))) {
			line = line.trim();
			if (line.isEmpty() || line.startsWith("#")) {
				continue;
			}
			String[] f = line.split("\\s+");
			String err = runOne(f);
			if (err == null) {
				pass++;
				out.println("PASS " + f[0]);
			}
			else {
				fail++;
				out.println("FAIL " + f[0] + ": " + err);
			}
		}
		out.printf("emulator tests: %d passed, %d failed%n", pass, fail);
		out.close();
	}

	private void put(EmulatorHelper emu, String k, BigInteger v) throws Exception {
		if (k.startsWith("m")) {
			int n = k.charAt(1) - '0';
			long a = Long.parseLong(k.substring(3), 16);
			byte[] b = new byte[n];
			for (int i = 0; i < n; i++) {
				b[i] = v.shiftRight(8 * i).byteValue();
			}
			emu.writeMemory(toAddr(a), b);
		}
		else {
			emu.writeRegister(k, v);
		}
	}

	private BigInteger get(EmulatorHelper emu, String k) throws Exception {
		if (k.startsWith("m")) {
			int n = k.charAt(1) - '0';
			long a = Long.parseLong(k.substring(3), 16);
			byte[] b = emu.readMemory(toAddr(a), n);
			BigInteger v = BigInteger.ZERO;
			for (int i = n - 1; i >= 0; i--) {
				v = v.shiftLeft(8).or(BigInteger.valueOf(b[i] & 0xff));
			}
			return v;
		}
		Integer bit = FLAGS.get(k);
		if (bit != null) {
			return emu.readRegister("PSW").shiftRight(bit).and(BigInteger.ONE);
		}
		Register r = currentProgram.getRegister(k);
		BigInteger mask = BigInteger.ONE.shiftLeft(r.getBitLength()).subtract(BigInteger.ONE);
		return emu.readRegister(r).and(mask);
	}

	private String runOne(String[] f) throws Exception {
		Address start = toAddr(Long.parseUnsignedLong(f[1], 16));
		Address stop = toAddr(Long.parseUnsignedLong(f[2], 16));
		EmulatorHelper emu = new EmulatorHelper(currentProgram);
		try {
			emu.registerCallOtherCallback("segment", new BreakCallBack() {
				@Override
				public boolean pcodeCallback(PcodeOpRaw op) {
					MemoryState st = emulate.getMemoryState();
					long base = st.getValue(op.getInput(1));
					long inner = st.getValue(op.getInput(2)) & 0xffff;
					st.setValue(op.getOutput(), ((base & 0xf) << 16) | inner);
					return true;
				}
			});
			for (String r : new String[] { "AX", "BC", "DE", "HL", "PSW", "CS", "ES" }) {
				emu.writeRegister(r, 0);
			}
			emu.writeRegister("SP", 0xfe80);
			emu.writeRegister("NEARSEG", 0xf);
			if (!f[3].equals("-")) {
				for (String kv : f[3].split(",")) {
					String[] p = kv.split("=");
					put(emu, p[0], new BigInteger(p[1], 16));
				}
			}
			emu.writeRegister(emu.getPCRegister(), start.getOffset());
			emu.setBreakpoint(stop);
			emu.run(start, null, monitor);
			if (emu.getEmulateExecutionState() != EmulateExecutionState.BREAKPOINT ||
				!emu.getExecutionAddress().equals(stop)) {
				return "did not reach " + stop + " (state " + emu.getEmulateExecutionState() +
					" at " + emu.getExecutionAddress() + ", " + emu.getLastError() + ")";
			}
			StringBuilder bad = new StringBuilder();
			for (String kv : f[4].split(",")) {
				String[] p = kv.split("=");
				BigInteger want = new BigInteger(p[1], 16);
				BigInteger got = get(emu, p[0]);
				if (!want.equals(got)) {
					bad.append(String.format(" %s=%x (want %x)", p[0], got, want));
				}
			}
			return bad.length() == 0 ? null : bad.toString().trim();
		}
		finally {
			emu.dispose();
		}
	}
}
