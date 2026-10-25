// P-code semantics check for the ST9 and ST9+ languages. Each case writes code at code:1000,
// initializes registers and memory, steps through it and checks hand-computed results.
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

public class ST9EmuTest extends GhidraScript {

	private static class Case {
		String name;
		String flags = "";
		byte[] code;
		Map<String, Long> set = new LinkedHashMap<>();
		Map<String, Long> expect = new LinkedHashMap<>();
		Map<String, Long> context = new LinkedHashMap<>();
	}

	private List<Case> load(String path) throws Exception {
		List<Case> cases = new ArrayList<>();
		Case c = null;
		try (BufferedReader r = new BufferedReader(new FileReader(path))) {
			String line;
			while ((line = r.readLine()) != null) {
				line = line.trim();
				if (line.isEmpty() || line.startsWith("#")) {
					continue;
				}
				String[] f = line.split("\\s+");
				switch (f[0]) {
					case "case":
						c = new Case();
						c.name = f[1];
						for (int i = 2; i < f.length; i++) {
							c.flags += " " + f[i];
						}
						c.flags += " ";
						break;
					case "code":
						c.code = new byte[f[1].length() / 2];
						for (int i = 0; i < c.code.length; i++) {
							c.code[i] = (byte) Integer.parseInt(f[1].substring(2 * i, 2 * i + 2), 16);
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

	private Address addr(String loc) {
		String[] p = loc.split(":");
		return currentProgram.getAddressFactory().getAddressSpace(p[0]).getAddress(
			Long.parseLong(p[1], 16));
	}

	private String runCase(Case c) throws Exception {
		Address start = addr("code:1000");
		Address end = start.add(c.code.length);
		AddressSet body = new AddressSet(start, end);
		clearListing(body);
		setBytes(start, c.code);
		ProgramContext ctx = currentProgram.getProgramContext();
		Map<String, Long> defaults = new LinkedHashMap<>();
		defaults.put("rmode", 0L);
		defaults.put("rpk0", 0L);
		defaults.put("rpk1", 0L);
		defaults.put("ppk", 0L);
		defaults.put("dp", 1L);
		defaults.put("sstk", 0L);
		defaults.put("ustk", 0L);
		if (currentProgram.getLanguageID().getIdAsString().endsWith("ST9+")) {
			defaults.put("encsr", 0L);
		}
		for (Map.Entry<String, Long> e : defaults.entrySet()) {
			ctx.setValue(ctx.getRegister(e.getKey()), start, end,
				BigInteger.valueOf(e.getValue()));
		}
		for (Map.Entry<String, Long> e : c.context.entrySet()) {
			ctx.setValue(ctx.getRegister(e.getKey()), start, end,
				BigInteger.valueOf(e.getValue()));
		}
		Register creg = currentProgram.getLanguage().getContextBaseRegister();
		RegisterValue cval = ctx.getRegisterValue(creg, start);

		EmulatorHelper emu = new EmulatorHelper(currentProgram);
		try {
			for (Map.Entry<String, Long> e : c.set.entrySet()) {
				if (e.getKey().contains(":")) {
					emu.writeMemory(addr(e.getKey()), new byte[] { (byte) (long) e.getValue() });
				}
				else {
					emu.writeRegister(e.getKey(), e.getValue());
				}
			}
			emu.writeRegister(emu.getPCRegister(), start.getOffset());
			emu.setContextRegister(cval);
			int steps = 0;
			while (!emu.getExecutionAddress().equals(end)) {
				if (++steps > 500) {
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
					got = emu.readMemory(addr(e.getKey()), 1)[0] & 0xff;
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
		List<Case> cases = load(args[0]);
		PrintStream out = new PrintStream(args[1]);
		String variant = currentProgram.getLanguageID().getIdAsString().endsWith("ST9+")
				? "plus" : "base";
		String other = variant.equals("plus") ? "base" : "plus";
		int pass = 0, fail = 0;
		for (Case c : cases) {
			if (c.flags.contains(" " + other + " ")) {
				continue;
			}
			String err = runCase(c);
			if (err == null) {
				pass++;
				out.println("PASS " + c.name);
			}
			else {
				fail++;
				out.println("FAIL " + c.name + ": " + err);
			}
		}
		out.printf("emulation (%s): %d passed, %d failed%n",
			currentProgram.getLanguageID(), pass, fail);
		out.close();
	}
}
