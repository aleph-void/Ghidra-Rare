// Prepares a PXF column image for analysis: applies a symbol file (optional; one
// "<hex packet address> <name>" per line),
// creates functions at the symbols, then disassembles every packet of the block (PXF
// instruction memory holds only instructions, so a linear sweep is safe).
//
// Import the column first: Raw Binary, language PXF:BE:16:NSE-100, base address 0x800.
// Headless use: -postScript PxfColumnSetup.java [colN.syms]
//@category PXF

import java.io.File;
import java.nio.file.Files;

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.SourceType;

public class PxfColumnSetup extends GhidraScript {
	@Override
	protected void run() throws Exception {
		AddressSpace code = currentProgram.getAddressFactory().getDefaultAddressSpace();
		String[] args = getScriptArgs();
		File syms = null;
		if (args.length > 0) {
			syms = new File(args[0]);
		}
		else if (!isRunningHeadless()) {
			try {
				syms = askFile("PXF symbol file (cancel for none)", "Apply");
			}
			catch (ghidra.util.exception.CancelledException e) {
				syms = null;
			}
		}
		AddressSet starts = new AddressSet();
		if (syms != null) {
			for (String line : Files.readAllLines(syms.toPath())) {
				String[] f = line.trim().split("\\s+", 2);
				if (f.length < 2) {
					continue;
				}
				// symbol files hold packet addresses; Ghidra addresses count bytes
				Address a = code.getAddressInThisSpaceOnly(Long.parseLong(f[0], 16) * 8);
				createLabel(a, f[1], true, SourceType.IMPORTED);
				starts.add(a);
			}
		}
		for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
			if (b.isInitialized() && b.getStart().getAddressSpace() == code) {
				starts.add(b.getStart());
			}
		}
		for (AddressRange r : starts) {
			new DisassembleCommand(r.getMinAddress(), null, true).applyTo(currentProgram, monitor);
		}
		for (Address a : starts.getAddresses(true)) {
			if (getFunctionAt(a) == null && getInstructionAt(a) != null) {
				createFunction(a, null);
			}
		}
		int linear = 0;
		for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
			if (!b.isInitialized() || b.getStart().getAddressSpace() != code) {
				continue;
			}
			for (Address a = b.getStart(); a.compareTo(b.getEnd()) < 0; a = a.add(8)) {
				if (getInstructionContaining(a) == null) {
					new DisassembleCommand(a, new AddressSet(a, a.add(7)), false)
							.applyTo(currentProgram, monitor);
					linear++;
				}
			}
		}
		println("PXF: " + currentProgram.getListing().getNumInstructions() + " packets disassembled (" +
			linear + " by linear sweep), " + currentProgram.getFunctionManager().getFunctionCount() +
			" functions");
	}
}
