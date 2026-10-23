// TI clpru/asmpru emit local code labels ($C$L1, $C$L2, loop labels in
// hand-written assembly, ...) as zero-sized STT_FUNC ELF symbols, so the ELF
// importer turns every branch target into a separate "function".  This script
// removes those functions again (the labels are kept) and re-derives the bodies
// of the real functions.  A function is treated as a mere label when
//   * it is named $C$L<n>, or
//   * (after analysis) nothing CALLs it, it is not an entry point, and it is
//     reached by a jump or by falling through from the previous instruction.
// Run it right after import (analyzeHeadless -preScript) and/or after analysis
// (-postScript, or from the Script Manager).
//@category PRU

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;

public class PRUFixupTiLabels extends GhidraScript {

	private static final Pattern TI_LABEL = Pattern.compile("^\\$C\\$L\\d+$");

	private boolean isLabelOnly(Function f) {
		Address entry = f.getEntryPoint();
		if (currentProgram.getSymbolTable().isExternalEntryPoint(entry)) {
			return false;
		}
		boolean reached = false;
		for (Reference r : currentProgram.getReferenceManager().getReferencesTo(entry)) {
			if (r.getReferenceType().isCall()) {
				return false;
			}
			if (r.getReferenceType().isJump() || r.getReferenceType().isFlow()) {
				reached = true;
			}
		}
		Instruction prev = currentProgram.getListing().getInstructionBefore(entry);
		if (prev != null && entry.equals(prev.getFallThrough())) {
			reached = true;
		}
		return reached;
	}

	@Override
	protected void run() throws Exception {
		if (!currentProgram.getLanguage().getProcessor().toString().equals("PRU")) {
			printerr("not a PRU program");
			return;
		}
		List<Function> remove = new ArrayList<>();
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			if (TI_LABEL.matcher(f.getName()).matches() || isLabelOnly(f)) {
				remove.add(f);
			}
		}
		for (Function f : remove) {
			currentProgram.getFunctionManager().removeFunction(f.getEntryPoint());
		}
		int fixed = 0;
		for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
			if (CreateFunctionCmd.fixupFunctionBody(currentProgram, f, monitor)) {
				fixed++;
			}
		}
		println("PRUFixupTiLabels: removed " + remove.size() + " label functions, re-derived " +
			fixed + " function bodies");
	}
}
