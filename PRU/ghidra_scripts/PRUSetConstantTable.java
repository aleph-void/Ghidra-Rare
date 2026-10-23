// Sets the PRU constant-table registers c0..c31 (LBCO/SBCO bases) over the
// whole code space so the decompiler and constant propagation can resolve
// LBCO/SBCO data addresses.
//
// Script arguments (headless) or interactive prompt:
//   <device> [cN=value ...]
//   device: am335x (also AM437x/AM57xx PRU-ICSS local view, see note) | none
//   cN=value overrides a single entry, e.g. c28=0x10000 c31=0x80001000
// Entries C24..C31 are partly programmable (CTBIR0/1, CTPPR0/1); the defaults
// below are the reset values (all block indexes / pointers zero).
// Source: AM335x TRM (SPRUH73) Table 4-9 "PRU0/1 Constants Table".
//@category PRU

import java.math.BigInteger;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.ProgramContext;

public class PRUSetConstantTable extends GhidraScript {

	private static final long[] AM335X = {
		0x00020000L, 0x48040000L, 0x4802A000L, 0x00030000L, 0x00026000L, 0x48060000L,
		0x48030000L, 0x00028000L, 0x46000000L, 0x4A100000L, 0x48318000L, 0x48022000L,
		0x48024000L, 0x48310000L, 0x481CC000L, 0x481D0000L, 0x481A0000L, 0x4819C000L,
		0x48300000L, 0x48302000L, 0x48304000L, 0x00032400L, 0x480C8000L, 0x480CA000L,
		// C24..C31 at reset: PRU own DRAM, other DRAM, IEP, MII_RT, shared RAM, TPCC, OCMC, DDR
		0x00000000L, 0x00002000L, 0x0002E000L, 0x00032000L, 0x00000000L, 0x49000000L,
		0x40000000L, 0x80000000L };

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		String device;
		if (args.length > 0) {
			device = args[0];
		}
		else if (isRunningHeadless()) {
			device = "am335x";
		}
		else {
			device = askChoice("PRU constant table", "Device", java.util.List.of("am335x", "none"),
				"am335x");
		}
		Long[] vals = new Long[32];
		if (device.equalsIgnoreCase("am335x")) {
			for (int i = 0; i < 32; i++) {
				vals[i] = AM335X[i];
			}
		}
		for (int a = 1; a < args.length; a++) {
			String[] kv = args[a].toLowerCase().split("=");
			int idx = Integer.parseInt(kv[0].substring(1));
			vals[idx] = Long.decode(kv[1]);
		}
		AddressSpace code = currentProgram.getAddressFactory().getAddressSpace("code");
		Address start = code.getMinAddress();
		Address end = code.getMaxAddress();
		ProgramContext ctx = currentProgram.getProgramContext();
		int n = 0;
		for (int i = 0; i < 32; i++) {
			if (vals[i] == null) {
				continue;
			}
			Register r = currentProgram.getRegister("c" + i);
			ctx.setValue(r, start, end, BigInteger.valueOf(vals[i]));
			n++;
		}
		println("PRUSetConstantTable: set " + n + " constant-table entries (" + device + ")");
	}
}
