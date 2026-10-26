// Listing-guided real-code check: after auto-analysis, disassemble (with flow) at every address
// in a file of hex addresses, one per line (the assembler listing's instructions), so that code
// reached only through computed jumps is decoded too, and make functions of the call targets.
// No auto-analysis runs afterwards (its repair of "non-returning" calls would clear seeded code
// again). Script args: <address file>
//@category Testing

import java.nio.file.Files;
import java.nio.file.Paths;

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.address.AddressSpace;

public class XASeed extends GhidraScript {

	@Override
	protected void run() throws Exception {
		AddressSpace code = currentProgram.getAddressFactory().getAddressSpace("code");
		AddressSet seeds = new AddressSet();
		for (String line : Files.readAllLines(Paths.get(getScriptArgs()[0]))) {
			line = line.trim();
			if (!line.isEmpty()) {
				seeds.add(code.getAddress(Long.parseLong(line, 16)));
			}
		}
		new DisassembleCommand(seeds, null, true).applyTo(currentProgram, monitor);
		// make functions of the call targets in the newly decoded code, so they are decompiled
		for (Instruction i : currentProgram.getListing().getInstructions(true)) {
			if (!i.getFlowType().isCall()) {
				continue;
			}
			for (Address t : i.getFlows()) {
				if (currentProgram.getListing().getInstructionAt(t) != null &&
					currentProgram.getFunctionManager().getFunctionAt(t) == null) {
					new CreateFunctionCmd(t).applyTo(currentProgram, monitor);
				}
			}
		}
	}
}
