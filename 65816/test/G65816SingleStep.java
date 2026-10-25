// Runs SingleStepTests/65816 cases (initial CPU/RAM state -> one instruction -> final state)
// through Ghidra's p-code emulator and reports agreement per opcode.
// Script args: <tests.json> <outfile>
// Compared: PC/PBR, S, C (A+B), X, Y, DBR, D, flags N V D I Z C, and every RAM byte the test
// lists in its final state. The M/X/E bits are decode context in this module (not run-time
// state) and are used to select the decode, not compared.
//@category Testing

import java.io.FileReader;
import java.io.PrintStream;
import java.math.BigInteger;
import java.util.*;

import com.google.gson.*;

import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;

public class G65816SingleStep extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		JsonArray tests = JsonParser.parseReader(new FileReader(args[0])).getAsJsonArray();
		PrintStream out = new PrintStream(args[1]);
		var lang = currentProgram.getLanguage();
		Register ctx = lang.getContextBaseRegister();
		Register mf = lang.getRegister("ctx_MF"), xf = lang.getRegister("ctx_XF"),
				ef = lang.getRegister("ctx_EF");
		Register pc = lang.getProgramCounter();
		String[] flags = { "CF", "ZF", "IF", "DF", null, null, "VF", "NF" };
		Map<String, int[]> perOp = new TreeMap<>();
		Map<String, String> firstFail = new TreeMap<>();
		int pass = 0, fail = 0;
		for (JsonElement el : tests) {
			JsonObject t = el.getAsJsonObject();
			String name = t.get("name").getAsString();
			JsonObject in = t.getAsJsonObject("initial"), fin = t.getAsJsonObject("final");
			String key = name.substring(0, 2) + "." + (in.get("e").getAsInt() == 1 ? "e" : "n");
			int p = in.get("p").getAsInt();
			int e = in.get("e").getAsInt();
			EmulatorHelper emu = new EmulatorHelper(currentProgram);
			String why = null;
			try {
				RegisterValue rv = new RegisterValue(ctx);
				rv = rv.assign(mf, BigInteger.valueOf(e == 1 ? 1 : (p >> 5) & 1));
				rv = rv.assign(xf, BigInteger.valueOf(e == 1 ? 1 : (p >> 4) & 1));
				rv = rv.assign(ef, BigInteger.valueOf(e));
				emu.setContextRegister(rv);
				emu.writeRegister("C", in.get("a").getAsInt());
				// Hardware invariants the test files leave out: in emulation mode S is in page 1;
				// with 8-bit index registers their high bytes are zero.
				boolean x8 = e == 1 || ((p >> 4) & 1) == 1;
				int xm = x8 ? 0xff : 0xffff;
				emu.writeRegister("X", in.get("x").getAsInt() & xm);
				emu.writeRegister("Y", in.get("y").getAsInt() & xm);
				int s = in.get("s").getAsInt();
				emu.writeRegister("SP", e == 1 ? 0x100 | (s & 0xff) : s);
				emu.writeRegister("DBR", in.get("dbr").getAsInt());
				emu.writeRegister("DP", in.get("d").getAsInt());
				emu.writeRegister("BF", 0);
				for (int b = 0; b < 8; b++) {
					if (flags[b] != null) {
						emu.writeRegister(flags[b], (p >> b) & 1);
					}
				}
				for (JsonElement m : in.getAsJsonArray("ram")) {
					JsonArray kv = m.getAsJsonArray();
					emu.writeMemory(toAddr(kv.get(0).getAsLong()),
						new byte[] { (byte) kv.get(1).getAsInt() });
				}
				long full = in.get("pbr").getAsLong() << 16 | in.get("pc").getAsLong();
				emu.writeRegister(pc, full);
				emu.getEmulator().executeInstruction(true, monitor);
				StringBuilder d = new StringBuilder();
				long gotPc = emu.readRegister(pc).longValue();
				long wantPc = fin.get("pbr").getAsLong() << 16 | fin.get("pc").getAsLong();
				if (gotPc != wantPc) {
					d.append(String.format(" PC %06x!=%06x", gotPc, wantPc));
				}
				String[][] regs = { { "C", "a" }, { "X", "x" }, { "Y", "y" }, { "SP", "s" },
					{ "DBR", "dbr" }, { "DP", "d" } };
				for (String[] r : regs) {
					long g = emu.readRegister(r[0]).longValue();
					long w = fin.get(r[1]).getAsLong();
					if (g != w) {
						d.append(String.format(" %s %x!=%x", r[0], g, w));
					}
				}
				int fp = fin.get("p").getAsInt();
				for (int b = 0; b < 8; b++) {
					if (flags[b] != null) {
						long g = emu.readRegister(flags[b]).longValue();
						if (g != ((fp >> b) & 1)) {
							d.append(String.format(" %s %d!=%d", flags[b], g, (fp >> b) & 1));
						}
					}
				}
				for (JsonElement m : fin.getAsJsonArray("ram")) {
					JsonArray kv = m.getAsJsonArray();
					byte[] g = emu.readMemory(toAddr(kv.get(0).getAsLong()), 1);
					if ((g[0] & 0xff) != kv.get(1).getAsInt()) {
						d.append(String.format(" mem[%06x] %02x!=%02x", kv.get(0).getAsLong(),
							g[0] & 0xff, kv.get(1).getAsInt()));
					}
				}
				if (d.length() > 0) {
					why = d.toString();
				}
			}
			catch (Exception ex) {
				why = " exception " + ex;
			}
			finally {
				emu.dispose();
			}
			int[] c = perOp.computeIfAbsent(key, k -> new int[2]);
			if (why == null) {
				c[0]++;
				pass++;
			}
			else {
				c[1]++;
				fail++;
				firstFail.putIfAbsent(key, name + ":" + why);
			}
		}
		for (var en : perOp.entrySet()) {
			int[] c = en.getValue();
			out.printf("%s %d/%d%s%n", en.getKey(), c[0], c[0] + c[1],
				c[1] > 0 ? "  e.g. " + firstFail.get(en.getKey()) : "");
		}
		out.printf("singlestep: %d passed, %d failed (%d opcode/mode files fully passing of %d)%n",
			pass, fail, perOp.values().stream().filter(c -> c[1] == 0).count(), perOp.size());
		out.close();
	}
}
