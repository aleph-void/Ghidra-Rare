// Pre-analysis helper for RAM images without a vector table: disassemble at the given address,
// make it a function and an entry point. Script args: <hex address>
//@category Testing

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;

public class XAEntry extends GhidraScript {

	@Override
	protected void run() throws Exception {
		Address a = currentProgram.getAddressFactory()
				.getAddressSpace("code")
				.getAddress(Long.decode(getScriptArgs()[0]));
		new DisassembleCommand(a, null, true).applyTo(currentProgram, monitor);
		new CreateFunctionCmd(a).applyTo(currentProgram, monitor);
		currentProgram.getSymbolTable().addExternalEntryPoint(a);
	}
}
