// P-code emulation test for the 65816 module: runs every case of emu_cases.txt with
// EmulatorHelper and compares registers and memory with hand-computed results.
// Script args: <cases.txt> <labels.lbl> <outfile>
//@category Testing

import java.io.PrintStream;
import java.math.BigInteger;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;

public class G65816EmuTest extends GhidraScript {

	private Map<String, Long> labels = new HashMap<>();

	private long value(String v) {
		if (v.startsWith("@")) {
			String[] p = v.substring(1).split("\\+");
			long a = labels.get(p[0]);
			return p.length > 1 ? a + Long.parseLong(p[1]) : a;
		}
		return Long.parseLong(v, 16);
	}

	private byte[] bytes(String kind, String v) {
		if (kind.equals("mem16")) {
			long x = value(v);
			return new byte[] { (byte) x, (byte) (x >> 8) };
		}
		byte[] b = new byte[v.length() / 2];
		for (int i = 0; i < b.length; i++) {
			b[i] = (byte) Integer.parseInt(v.substring(2 * i, 2 * i + 2), 16);
		}
		return b;
	}

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		for (String l : Files.readAllLines(Path.of(args[1]))) {
			String[] p = l.trim().split("\\s+");
			if (p.length == 3 && p[0].equals("al")) {
				labels.put(p[2].replaceFirst("^\\.", ""), Long.parseLong(p[1], 16));
			}
		}
		PrintStream out = new PrintStream(args[2]);
		var lang = currentProgram.getLanguage();
		Register ctxreg = lang.getContextBaseRegister();
		Register mf = lang.getRegister("ctx_MF"), xf = lang.getRegister("ctx_XF"),
				ef = lang.getRegister("ctx_EF");
		String[] flags = { "NF", "VF", "DF", "IF", "ZF", "CF", "BF" };
		int pass = 0, fail = 0;
		for (String line : Files.readAllLines(Path.of(args[0]))) {
			line = line.trim();
			if (line.isEmpty() || line.startsWith("#")) {
				continue;
			}
			String[] halves = line.split("\\|");
			String[] init = halves[0].trim().split("\\s+");
			String[] expect = halves.length > 1 ? halves[1].trim().split("\\s+") : new String[0];
			String name = init[0];
			String mxe = init[1];
			Address start = toAddr(labels.get(name));

			RegisterValue rv = new RegisterValue(ctxreg);
			rv = rv.assign(mf, BigInteger.valueOf(mxe.charAt(0) - '0'));
			rv = rv.assign(xf, BigInteger.valueOf(mxe.charAt(1) - '0'));
			rv = rv.assign(ef, BigInteger.valueOf(mxe.charAt(2) - '0'));
			// (Re)disassemble the case with its own entry context.
			clearListing(start, start.add(0x40));
			DisassembleCommand cmd = new DisassembleCommand(start, null, true);
			cmd.setInitialContext(rv);
			cmd.applyTo(currentProgram, monitor);

			EmulatorHelper emu = new EmulatorHelper(currentProgram);
			StringBuilder why = new StringBuilder();
			try {
				emu.setContextRegister(rv);
				for (String f : flags) {
					emu.writeRegister(f, 0);
				}
				for (String r : new String[] { "C", "X", "Y", "DP", "DBR" }) {
					emu.writeRegister(r, 0);
				}
				emu.writeRegister("SP", 0x1fff);
				emu.writeRegister("PBR", 0);
				for (int i = 2; i < init.length; i++) {
					String[] kv = init[i].split("=", 2);
					if (kv[0].contains(":")) {
						String[] ka = kv[0].split(":");
						emu.writeMemory(toAddr(Long.parseLong(ka[1], 16)), bytes(ka[0], kv[1]));
					}
					else {
						emu.writeRegister(kv[0], value(kv[1]));
					}
				}
				emu.writeRegister(lang.getProgramCounter(), start.getOffset());
				int steps = 0;
				while (steps++ < 500) {
					Address pc = emu.getExecutionAddress();
					if ((currentProgram.getMemory().getByte(pc) & 0xff) == 0xdb) {
						break; // STP ends the case
					}
					try {
						emu.getEmulator().executeInstruction(true, monitor);
					}
					catch (Exception ex) {
						why.append(" emulation error at ").append(pc).append(": ").append(ex);
						StackTraceElement[] st = ex.getStackTrace();
						for (int k = 0; k < Math.min(4, st.length); k++) {
							why.append(" @").append(st[k]);
						}
						break;
					}
				}
				for (String e : expect) {
					String[] kv = e.split("=", 2);
					if (kv[0].contains(":")) {
						String[] ka = kv[0].split(":");
						byte[] want = bytes(ka[0], kv[1]);
						byte[] got = emu.readMemory(toAddr(Long.parseLong(ka[1], 16)), want.length);
						if (!java.util.Arrays.equals(want, got)) {
							why.append(String.format(" %s: want %s got %s", kv[0], hex(want), hex(got)));
						}
					}
					else {
						long want = value(kv[1]);
						long got = emu.readRegister(kv[0]).longValue();
						if (want != got) {
							why.append(String.format(" %s: want %x got %x", kv[0], want, got));
						}
					}
				}
			}
			catch (Exception ex) {
				why.append(" exception: ").append(ex);
			}
			finally {
				emu.dispose();
			}
			if (why.length() == 0) {
				pass++;
				out.println("PASS " + name);
			}
			else {
				fail++;
				out.println("FAIL " + name + why);
			}
		}
		out.printf("emulator: %d passed, %d failed%n", pass, fail);
		out.close();
	}

	private static String hex(byte[] b) {
		StringBuilder s = new StringBuilder();
		for (byte x : b) {
			s.append(String.format("%02x", x & 0xff));
		}
		return s.toString();
	}
}
