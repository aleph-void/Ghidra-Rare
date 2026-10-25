// Marks up the RL78 vector table (00000-0007F) and CALLT table (00080-000BF) of a raw firmware
// image: each 16-bit entry becomes a pointer, and its target (if it is not erased flash) is
// disassembled and made a function named after the vector.
//@category RL78

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.data.WordDataType;
import ghidra.program.model.symbol.SourceType;

public class RL78Vectors extends GhidraScript {

	@Override
	protected void run() throws Exception {
		int made = 0;
		for (int a = 0; a < 0xC0; a += 2) {
			Address va = toAddr(a);
			if (!currentProgram.getMemory().contains(va, va.add(1))) {
				continue;
			}
			int w = (getByte(va) & 0xff) | ((getByte(va.add(1)) & 0xff) << 8);
			if (w == 0xffff || w == 0 || w < 0xC0) {
				continue;
			}
			Address t = toAddr(w);
			if (!currentProgram.getMemory().contains(t)) {
				continue;
			}
			String name = a == 0 ? "RESET" : a < 0x80 ? String.format("vector_%02x", a)
					: String.format("callt_%02x", a);
			clearListing(va, va.add(1));
			createData(va, WordDataType.dataType);
			createLabel(va, name, true, SourceType.ANALYSIS);
			currentProgram.getReferenceManager().addMemoryReference(va, t,
				ghidra.program.model.symbol.RefType.DATA, SourceType.ANALYSIS, 0);
			if (getInstructionAt(t) == null) {
				new DisassembleCommand(t, null, true).applyTo(currentProgram, monitor);
			}
			if (getFunctionAt(t) == null && createFunction(t, a == 0 ? "reset_handler"
					: (a < 0x80 ? "isr_" : "callt_fn_") + String.format("%02x", a)) != null) {
				made++;
			}
		}
		println("RL78Vectors: " + made + " functions created");
		analyzeChanges(currentProgram);
	}
}
