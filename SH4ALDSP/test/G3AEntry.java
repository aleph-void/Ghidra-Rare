// Pre-script for raw Casio fx-CG add-in images (the code of a .g3a, loaded at 0x00300000):
// marks the add-in entry point (the first instruction) as an entry function so analysis starts.
//@category Testing

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;

public class G3AEntry extends GhidraScript {
	@Override
	protected void run() throws Exception {
		Address a = currentProgram.getMinAddress();
		currentProgram.getSymbolTable().addExternalEntryPoint(a);
		disassemble(a);
		createFunction(a, "addin_main");
	}
}
