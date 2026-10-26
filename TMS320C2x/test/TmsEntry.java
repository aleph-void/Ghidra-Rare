// Pre-analysis script: marks the given word addresses in program memory as entry points (used for
// images loaded at a base address other than 0, where the reset vector is not part of the image).
// Script args: <word-address-hex>...
//@category Testing

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;

public class TmsEntry extends GhidraScript {

	@Override
	protected void run() throws Exception {
		for (String a : getScriptArgs()) {
			Address addr = currentProgram.getAddressFactory().getAddressSpace("prog")
					.getAddress(Long.parseLong(a.replaceFirst("^0x", ""), 16) * 2);
			currentProgram.getSymbolTable().addExternalEntryPoint(addr);
		}
	}
}
