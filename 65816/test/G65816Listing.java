// Flow-disassemble a raw 65816 image from given entry points and dump the listing with the
// M/X/E decode context of each instruction (used by the context-tracking tests).
// Script args: <outfile> <entry-hex>[:MXE] ...    (MXE e.g. 111 = emulation mode reset state)
//@category Testing

import java.io.PrintStream;
import java.math.BigInteger;

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;
import ghidra.program.model.listing.Instruction;

public class G65816Listing extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = new PrintStream(args[0]);
		var lang = currentProgram.getLanguage();
		Register ctxreg = lang.getContextBaseRegister();
		Register mf = lang.getRegister("ctx_MF"), xf = lang.getRegister("ctx_XF"),
				ef = lang.getRegister("ctx_EF");
		for (int i = 1; i < args.length; i++) {
			String[] p = args[i].split(":");
			Address a = toAddr(Long.parseLong(p[0], 16));
			DisassembleCommand cmd = new DisassembleCommand(a, null, true);
			if (p.length > 1) {
				RegisterValue rv = new RegisterValue(ctxreg);
				rv = rv.assign(mf, BigInteger.valueOf(p[1].charAt(0) - '0'));
				rv = rv.assign(xf, BigInteger.valueOf(p[1].charAt(1) - '0'));
				rv = rv.assign(ef, BigInteger.valueOf(p[1].charAt(2) - '0'));
				cmd.setInitialContext(rv);
			}
			cmd.applyTo(currentProgram, monitor);
		}
		for (Instruction ins : currentProgram.getListing().getInstructions(true)) {
			StringBuilder hex = new StringBuilder();
			for (byte b : ins.getBytes()) {
				hex.append(String.format("%02x", b & 0xff));
			}
			out.printf("%06x %-8s M%s X%s E%s %s%n", ins.getAddress().getOffset(), hex,
				ins.getValue(mf, false), ins.getValue(xf, false), ins.getValue(ef, false), ins);
		}
		out.close();
	}
}
