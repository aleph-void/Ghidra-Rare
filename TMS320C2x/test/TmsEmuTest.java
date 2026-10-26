// P-code semantics check for the TMS320C2x and TMS320C5x languages. Each case writes its code
// words at prog:0100, initialises registers, context and data memory, steps until the PC reaches
// the word after the code and compares hand-computed results.
//
// cases.txt format (one directive per line, '#' comments):
//   case <name> [c2x|c5x] [xfail]   start a case (family filter; xfail = must fail)
//   code <word> <word> ...          16-bit code words (hex)
//   set <REG|space:addr> <value>     register, or one 16-bit word of memory (data:/prog:/io:)
//   context <name> <value>           context field over the code range
//   expect <REG|space:addr> <value>  expected register value / memory word
//   steps <n>                        step limit (default 1000)
//   end
//
// Script args: <cases.txt> <outfile>
//@category Testing

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.PrintStream;
import java.math.BigInteger;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;
import ghidra.program.model.listing.ProgramContext;

public class TmsEmuTest extends GhidraScript {

	private static class Case {
		String name;
		String flags = " ";
		List<Integer> code = new ArrayList<>();
		Map<String, Long> set = new LinkedHashMap<>();
		Map<String, Long> expect = new LinkedHashMap<>();
		Map<String, Long> context = new LinkedHashMap<>();
		int steps = 1000;
	}

	private boolean big;

	private List<Case> load(String path) throws Exception {
		List<Case> cases = new ArrayList<>();
		Case c = null;
		try (BufferedReader r = new BufferedReader(new FileReader(path))) {
			String line;
			while ((line = r.readLine()) != null) {
				int h = line.indexOf('#');
				if (h >= 0) {
					line = line.substring(0, h);
				}
				line = line.trim();
				if (line.isEmpty()) {
					continue;
				}
				String[] f = line.split("\\s+");
				switch (f[0]) {
					case "case":
						c = new Case();
						c.name = f[1];
						for (int i = 2; i < f.length; i++) {
							c.flags += f[i] + " ";
						}
						break;
					case "code":
						for (int i = 1; i < f.length; i++) {
							c.code.add(Integer.parseInt(f[i], 16));
						}
						break;
					case "set":
						c.set.put(f[1], Long.decode(f[2]));
						break;
					case "context":
						c.context.put(f[1], Long.decode(f[2]));
						break;
					case "expect":
						c.expect.put(f[1], Long.decode(f[2]));
						break;
					case "steps":
						c.steps = Integer.parseInt(f[1]);
						break;
					case "end":
						cases.add(c);
						break;
					default:
						throw new IllegalArgumentException("bad line: " + line);
				}
			}
		}
		return cases;
	}

	/** space:wordaddr -> Address (Ghidra offsets in word-addressed spaces are byte offsets). */
	private Address addr(String loc) {
		String[] p = loc.split(":");
		return currentProgram.getAddressFactory().getAddressSpace(p[0]).getAddress(
			Long.parseLong(p[1], 16) * 2);
	}

	private byte[] word(long v) {
		return big ? new byte[] { (byte) (v >> 8), (byte) v } : new byte[] { (byte) v, (byte) (v >> 8) };
	}

	private String runCase(Case c) throws Exception {
		Address start = addr("prog:0100");
		Address end = start.add(2L * c.code.size());
		AddressSet body = new AddressSet(start, end.subtract(1));
		clearListing(body);
		for (int i = 0; i < c.code.size(); i++) {
			setBytes(start.add(2L * i), word(c.code.get(i)));
		}
		ProgramContext ctx = currentProgram.getProgramContext();
		// back to the pspec defaults (cases must not inherit each other's context)
		ctx.remove(start, end, currentProgram.getLanguage().getContextBaseRegister());
		for (Map.Entry<String, Long> e : c.context.entrySet()) {
			ctx.setValue(ctx.getRegister(e.getKey()), start, end, BigInteger.valueOf(e.getValue()));
		}
		Register creg = currentProgram.getLanguage().getContextBaseRegister();
		RegisterValue cval = ctx.getRegisterValue(creg, start);
		EmulatorHelper emu = new EmulatorHelper(currentProgram);
		try {
			for (Map.Entry<String, Long> e : c.set.entrySet()) {
				if (e.getKey().contains(":")) {
					emu.writeMemory(addr(e.getKey()), word(e.getValue()));
				}
				else {
					emu.writeRegister(e.getKey(), e.getValue());
				}
			}
			emu.writeRegister(emu.getPCRegister(), start.getAddressableWordOffset());
			emu.setContextRegister(cval);
			int steps = 0;
			while (!emu.getExecutionAddress().equals(end)) {
				if (++steps > c.steps) {
					return "did not reach the end (pc " + emu.getExecutionAddress() + ")";
				}
				if (!emu.step(monitor)) {
					return "emulation error at " + emu.getExecutionAddress() + ": " +
						emu.getLastError();
				}
			}
			StringBuilder bad = new StringBuilder();
			for (Map.Entry<String, Long> e : c.expect.entrySet()) {
				long got;
				if (e.getKey().contains(":")) {
					byte[] b = emu.readMemory(addr(e.getKey()), 2);
					got = big ? ((b[0] & 0xff) << 8) | (b[1] & 0xff) : ((b[1] & 0xff) << 8) | (b[0] & 0xff);
				}
				else {
					got = emu.readRegister(e.getKey()).longValue();
				}
				if (got != e.getValue()) {
					bad.append(String.format(" %s=0x%x (expected 0x%x)", e.getKey(), got,
						e.getValue()));
				}
			}
			return bad.length() == 0 ? null : bad.toString().trim();
		}
		finally {
			emu.dispose();
		}
	}

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		big = currentProgram.getLanguage().isBigEndian();
		String fam = currentProgram.getLanguageID().getIdAsString().startsWith("TMS320C5x") ? "c5x" : "c2x";
		String other = fam.equals("c5x") ? "c2x" : "c5x";
		List<Case> cases = load(args[0]);
		PrintStream out = new PrintStream(args[1]);
		int pass = 0, fail = 0, xfail = 0;
		for (Case c : cases) {
			if (c.flags.contains(" " + other + " ")) {
				continue;
			}
			String err = runCase(c);
			boolean expectFail = c.flags.contains(" xfail ");
			if (expectFail) {
				if (err != null) {
					xfail++;
					out.println("XFAIL " + c.name + " (failed as required): " + err);
				}
				else {
					fail++;
					out.println("FAIL " + c.name + ": broken expectation was not detected");
				}
			}
			else if (err == null) {
				pass++;
				out.println("PASS " + c.name);
			}
			else {
				fail++;
				out.println("FAIL " + c.name + ": " + err);
			}
		}
		out.printf("emulation (%s): %d passed, %d failed, %d broken expectations detected%n",
			currentProgram.getLanguageID(), pass, fail, xfail);
		out.close();
	}
}
