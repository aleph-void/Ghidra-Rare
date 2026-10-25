/* ###
 * IP: GHIDRA
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package ghidra.app.plugin.core.analysis;

import java.math.BigInteger;

import ghidra.app.util.importer.MessageLog;
import ghidra.framework.options.OptionType;
import ghidra.framework.options.Options;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSetView;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.lang.Processor;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.ContextChangeException;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Program;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.util.SymbolicPropogator;
import ghidra.util.exception.CancelledException;
import ghidra.util.task.TaskMonitor;

/**
 * Constant-reference analyzer for the DEC Alpha.
 *
 * <p>Alpha addresses static data gp-relative: a quadword load such as
 * {@code ldq t0, off(gp)} where {@code gp} ($29) holds the module's global
 * pointer. The generic constant-propagation analyzer cannot create those
 * references because nothing in the instruction stream tells it what
 * {@code gp} holds.
 *
 * <p>By calling convention a procedure is entered with the procedure value
 * (its own entry address) in $27 (named {@code t12} on NT, {@code pv} on
 * UNIX/Linux), and standard prologues recompute gp ($29) from it:
 *
 * <pre>
 *     ldah gp, X($27)
 *     lda  gp, Y(gp)        ; gp = entry + (X &lt;&lt; 16) + Y
 * </pre>
 *
 * <p>Seeding $27 with the entry address before propagation lets the
 * existing prologue resolve gp on its own, after which the base class creates
 * the gp-relative data references. For flat firmware images that share one
 * fixed gp and may reach code without a recomputing prologue, an optional
 * override seeds gp directly with a user-supplied value.
 *
 * <p>This does not apply to OpenVMS Alpha, which has no global pointer: $29 is
 * the frame pointer and $27 holds the address of a procedure descriptor rather
 * than an entry point. The analyzer declines those language variants.
 */
public class AlphaAddressAnalyzer extends ConstantPropagationAnalyzer {

	private static final String PROCESSOR_NAME = "Alpha";

	private static final String OPTION_NAME_PV = "Recover GP from procedure value";
	private static final String OPTION_DESC_PV =
		"Seed the procedure-value register (t12) with each function's entry " +
		"address so a standard ldgp prologue resolves gp, enabling gp-relative " +
		"data references.";
	private static final boolean OPTION_DEFAULT_PV = true;

	private static final String OPTION_NAME_GLOBAL_GP = "Assume a single global GP value";
	private static final String OPTION_DESC_GLOBAL_GP =
		"For flat firmware that shares one global pointer, seed gp directly " +
		"with the value below instead of (or in addition to) recovering it " +
		"from each prologue.";
	private static final boolean OPTION_DEFAULT_GLOBAL_GP = false;

	private static final String OPTION_NAME_GP_VALUE = "Global GP value (hex)";
	private static final String OPTION_DESC_GP_VALUE =
		"The fixed gp value to seed when 'Assume a single global GP value' is " +
		"enabled, e.g. 0x13a9a8.";
	private static final String OPTION_DEFAULT_GP_VALUE = "0x0";

	private boolean recoverGpFromPv = OPTION_DEFAULT_PV;
	private boolean assumeGlobalGp = OPTION_DEFAULT_GLOBAL_GP;
	private String globalGpText = OPTION_DEFAULT_GP_VALUE;

	static {
		// Suppress the generic constant-reference analyzer for Alpha so this
		// subclass runs in its place.
		claimProcessor(PROCESSOR_NAME);
	}

	public AlphaAddressAnalyzer() {
		super(PROCESSOR_NAME);
	}

	@Override
	public boolean canAnalyze(Program program) {
		if (!program.getLanguage().getProcessor().equals(
			Processor.findOrPossiblyCreateProcessor(PROCESSOR_NAME))) {
			return false;
		}
		// OpenVMS Alpha has no global pointer: $27 holds the address of the
		// procedure descriptor rather than the entry point, and $29 is FP.
		// Neither seed is meaningful, and both can create bogus references.
		return !program.getLanguage().getLanguageID().getIdAsString().endsWith(":vms");
	}

	@Override
	public AddressSetView flowConstants(Program program, Address flowStart,
			AddressSetView flowSet, SymbolicPropogator symEval, TaskMonitor monitor)
			throws CancelledException {

		seedRegisters(program, flowStart);

		return super.flowConstants(program, flowStart, flowSet, symEval, monitor);
	}

	/**
	 * Set the disassembly-context register values the propagator reads as its
	 * starting state. $27 (pv) is seeded per function; the optional global
	 * gp ($29) is seeded at every flow start.
	 *
	 * <p>Registers are looked up by their Alpha integer-register number rather
	 * than by name so the code works across the supported ABI variants: NT
	 * names them {@code t12}/{@code gp} and UNIX/Linux name them
	 * {@code pv}/{@code GP}.
	 */
	private void seedRegisters(Program program, Address flowStart) {
		ProgramContext context = program.getProgramContext();
		AddressSpace regSpace = program.getAddressFactory().getRegisterSpace();

		if (recoverGpFromPv) {
			// $27 — procedure value (pv / t12 / PV depending on ABI)
			Register pv = program.getLanguage().getRegister(regSpace, 27 * 8, 8);
			Function func = program.getFunctionManager().getFunctionAt(flowStart);
			if (pv != null && func != null) {
				Address entry = func.getEntryPoint();
				if (entry != null) {
					setContext(context, pv, entry, entry.getOffsetAsBigInteger());
				}
			}
		}

		if (recoverGpFromPv) {
			seedNoGpEntry(program, flowStart);
		}

		if (assumeGlobalGp) {
			// $29 — global pointer (gp / GP depending on ABI)
			Register gp = program.getLanguage().getRegister(regSpace, 29 * 8, 8);
			BigInteger gpValue = parseGpValue();
			if (gp != null && gpValue != null) {
				setContext(context, gp, flowStart, gpValue);
			}
		}
	}

	/**
	 * gcc gives every procedure that sets up gp a second entry point just past its two-instruction
	 * {@code ldgp} prologue ({@code ldah gp,hi($27); lda gp,lo(gp)}); calls from inside the same
	 * module ({@code bsr}) enter there with the caller's gp, which is the value that prologue
	 * computes. When a function starts right after such a prologue, seed gp with that value so
	 * gp-relative references resolve in the second entry too.
	 */
	private static void seedNoGpEntry(Program program, Address entry) {
		Function func = program.getFunctionManager().getFunctionAt(entry);
		if (func == null || entry.getOffset() < 8) {
			return;
		}
		Address prologue = entry.subtract(8);
		int ldah, lda;
		try {
			ldah = program.getMemory().getInt(prologue);
			lda = program.getMemory().getInt(entry.subtract(4));
		}
		catch (Exception e) {
			return;
		}
		// ldah $29,hi($27) ; lda $29,lo($29)
		if ((ldah >>> 26) != 0x09 || ((ldah >> 21) & 31) != 29 || ((ldah >> 16) & 31) != 27 ||
			(lda >>> 26) != 0x08 || ((lda >> 21) & 31) != 29 || ((lda >> 16) & 31) != 29) {
			return;
		}
		long gpValue = prologue.getOffset() + ((long) (short) (ldah & 0xffff) << 16) +
			(short) (lda & 0xffff);
		AddressSpace regSpace = program.getAddressFactory().getRegisterSpace();
		Register gp = program.getLanguage().getRegister(regSpace, 29 * 8, 8);
		if (gp != null) {
			setContext(program.getProgramContext(), gp, entry, BigInteger.valueOf(gpValue));
		}
	}

	private static void setContext(ProgramContext context, Register reg, Address at,
			BigInteger value) {
		try {
			context.setValue(reg, at, at, value);
		}
		catch (ContextChangeException e) {
			// An instruction already occupies this address with conflicting
			// context; leave the existing value in place.
		}
	}

	private BigInteger parseGpValue() {
		String text = globalGpText.trim();
		if (text.isEmpty()) {
			return null;
		}
		int radix = 10;
		if (text.startsWith("0x") || text.startsWith("0X")) {
			text = text.substring(2);
			radix = 16;
		}
		try {
			return new BigInteger(text, radix);
		}
		catch (NumberFormatException e) {
			return null;
		}
	}

	@Override
	public void registerOptions(Options options, Program program) {
		super.registerOptions(options, program);

		options.registerOption(OPTION_NAME_PV, OptionType.BOOLEAN_TYPE,
			recoverGpFromPv, null, OPTION_DESC_PV);
		options.registerOption(OPTION_NAME_GLOBAL_GP, OptionType.BOOLEAN_TYPE,
			assumeGlobalGp, null, OPTION_DESC_GLOBAL_GP);
		options.registerOption(OPTION_NAME_GP_VALUE, OptionType.STRING_TYPE,
			globalGpText, null, OPTION_DESC_GP_VALUE);
	}

	@Override
	public void optionsChanged(Options options, Program program) {
		super.optionsChanged(options, program);

		recoverGpFromPv = options.getBoolean(OPTION_NAME_PV, recoverGpFromPv);
		assumeGlobalGp = options.getBoolean(OPTION_NAME_GLOBAL_GP, assumeGlobalGp);
		globalGpText = options.getString(OPTION_NAME_GP_VALUE, globalGpText);
	}
}
