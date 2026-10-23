// Prepares a linked XMOS ELF (a tile image extracted from an .xe, see test/xe_extract.py) for
// analysis:
//
// 1. Issue mode. XMOS tools emit mapping symbols "$s.N" (single issue code follows) and
//    "$d.N" (dual issue code follows), much like ARM's $a/$t. The xCORE language tracks the
//    issue mode in the "dual" context bit, which changes how pc-relative operands are decoded.
//    Ghidra only learns it by flowing through DUALENTSP/ENTSP, so code reached indirectly
//    (event vectors, jump tables, hand-written assembly such as lib_xud) and leaf functions
//    called from the other mode get decoded in the wrong mode. This script pins "dual" on every
//    mapped range and re-disassembles code that was already decoded in the wrong mode.
// 2. cp / dp. The runtime start-up code loads cp and dp from the linker symbols _cp and _dp.
//    The script assumes those values in all executable memory so that cp/dp-relative loads,
//    BLACP and BLA cp[n] calls resolve.
//
// Run it before auto-analysis (headless: -preScript XcoreElfSetup.java), or afterwards in the
// GUI (it fixes existing code; re-run auto-analysis afterwards to update functions).
// Stripped images (no mapping symbols): run it after analysis (-postScript); it then gives the
// targets of LDAP (event vectors, thread entry points) the issue mode of the LDAP.
// Script args (optional): "nocpdp" to skip step 2, "nomode" to skip step 1.
//@category xCORE

import java.math.BigInteger;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.TreeMap;
import java.util.regex.Pattern;

import ghidra.app.plugin.core.clear.ClearFlowAndRepairCmd;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.ContextChangeException;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.ProgramContext;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolIterator;

public class XcoreElfSetup extends GhidraScript {

	private static final Pattern MAP = Pattern.compile("\\$([sd])(\\.\\d+)?");

	@Override
	protected void run() throws Exception {
		List<String> args = Arrays.asList(getScriptArgs());
		if (!currentProgram.getLanguage().getProcessor().toString().equals("xCORE")) {
			printerr("not an xCORE program");
			return;
		}
		checkArch();
		if (!args.contains("nocpdp")) {
			setCpDp();
		}
		if (!args.contains("nomode")) {
			setIssueMode();
		}
	}

	/**
	 * XMOS ELF images carry the target architecture ("XS1"/"XS2"/"XS3") in an "XMOS" note in a
	 * .xmosnote section. e_flags is 0, so the ELF opinion cannot use it and always picks XS3;
	 * warn if the note asks for a different variant (XS3 decodes XS2 code identically, XS1 not).
	 */
	private void checkArch() {
		for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
			if (!b.getName().startsWith(".xmosnote") || !b.isInitialized() || b.getSize() > 4096) {
				continue;
			}
			try {
				byte[] d = new byte[(int) b.getSize()];
				b.getBytes(b.getStart(), d);
				java.nio.ByteBuffer bb = java.nio.ByteBuffer.wrap(d).order(java.nio.ByteOrder.LITTLE_ENDIAN);
				while (bb.remaining() >= 12) {
					int nsz = bb.getInt(), dsz = bb.getInt();
					bb.getInt();
					if (nsz < 0 || dsz < 0 || nsz + dsz > bb.remaining() + 8) {
						break;
					}
					byte[] nm = new byte[nsz];
					bb.get(nm);
					bb.position((bb.position() + 3) & ~3);
					byte[] desc = new byte[Math.min(dsz, bb.remaining())];
					bb.get(desc);
					bb.position(Math.min(bb.limit(), (bb.position() + 3) & ~3));
					String name = new String(nm).replace("\0", "");
					String val = new String(desc).replace("\0", "").trim();
					if (name.startsWith("XMOS") && val.matches("XS[123][A-Za-z]*")) {
						String want = val.substring(0, 3);
						String have = currentProgram.getLanguageID().getIdAsString();
						println("ELF note: architecture " + val + ", language " + have);
						if (!have.endsWith(want) && !(want.equals("XS2") && have.endsWith("XS3"))) {
							printerr("WARNING: image is built for " + want + " but the language is " + have +
								"; re-import with language xCORE:LE:32:" + want);
						}
						return;
					}
				}
			}
			catch (Exception e) {
				// not a note we understand
			}
		}
	}

	private void setCpDp() throws Exception {
		ProgramContext ctx = currentProgram.getProgramContext();
		for (String name : new String[] { "cp", "dp" }) {
			Long val = null;
			for (Symbol s : currentProgram.getSymbolTable().getGlobalSymbols("_" + name)) {
				val = s.getAddress().getOffset();
			}
			if (val == null) {
				MemoryBlock b = currentProgram.getMemory().getBlock("." + name);
				if (b != null) {
					val = b.getStart().getOffset();
				}
			}
			if (val == null) {
				println(name + ": no _" + name + " symbol, left unset");
				continue;
			}
			Register r = currentProgram.getRegister(name);
			for (MemoryBlock code : currentProgram.getMemory().getBlocks()) {
				if (code.isExecute()) {
					ctx.setValue(r, code.getStart(), code.getEnd(), BigInteger.valueOf(val));
				}
			}
			println(name + " = 0x" + Long.toHexString(val));
		}
	}

	private int mode(Instruction ins, Register dual) {
		BigInteger v = ins.getValue(dual, false);
		return v == null ? 0 : v.intValue();
	}

	/** First bundle sets the mode itself (ENTSP / DUALENTSP at the entry or right after it). */
	private boolean setsMode(Instruction ins) {
		for (int k = 0; k < 2 && ins != null; k++) {
			String m = ins.getMnemonicString().toLowerCase();
			if (m.equals("entsp") || m.equals("dualentsp")) {
				return true;
			}
			ins = ins.getNext();
		}
		return false;
	}

	private void redisassemble(Address a, Register dual, int v) throws Exception {
		new ClearFlowAndRepairCmd(a, true, false, true).applyTo(currentProgram, monitor);
		if (getInstructionContaining(a) != null) {
			return;    // something else flows here; leave it
		}
		currentProgram.getProgramContext().setValue(dual, a, a, BigInteger.valueOf(v));
		disassemble(a);
	}

	private void setIssueMode() throws Exception {
		Register dual = currentProgram.getRegister("dual");
		if (dual == null) {
			println("XS1 language: no issue modes");
			return;
		}
		TreeMap<Address, Integer> marks = new TreeMap<>();
		SymbolIterator it = currentProgram.getSymbolTable().getAllSymbols(true);
		while (it.hasNext()) {
			Symbol s = it.next();
			java.util.regex.Matcher m = MAP.matcher(s.getName());
			if (!m.matches()) {
				continue;
			}
			MemoryBlock b = currentProgram.getMemory().getBlock(s.getAddress());
			if (b != null && b.isExecute()) {
				marks.put(s.getAddress(), m.group(1).equals("d") ? 1 : 0);
			}
		}
		if (marks.isEmpty()) {
			inferFromLdap(dual);
			return;
		}
		ProgramContext ctx = currentProgram.getProgramContext();
		int nd = 0, ns = 0, fixed = 0;
		List<Address> redo = new ArrayList<>();
		for (Address start : marks.keySet()) {
			MemoryBlock b = currentProgram.getMemory().getBlock(start);
			Address nxt = marks.higherKey(start);
			Address end = (nxt == null || !b.contains(nxt)) ? b.getEnd() : nxt.previous();
			int v = marks.get(start);
			if (v == 1) {
				nd++;
			}
			else {
				ns++;
			}
			// Code already decoded in another mode (only when run after analysis, or the entry
			// bundle of a function reached from a caller in the other mode) must be cleared
			// before the context can be written; disassemble it again from the range start and
			// from every referenced instruction in it.
			AddressSet range = new AddressSet(start, end);
			boolean conflict = false;
			for (Instruction ins : currentProgram.getListing().getInstructions(range, true)) {
				if (mode(ins, dual) != v) {
					conflict = true;
					break;
				}
			}
			if (!conflict) {
				try {
					ctx.setValue(dual, start, end, BigInteger.valueOf(v));
				}
				catch (ContextChangeException e) {
					// existing code (script run after analysis) already has the right mode
				}
				continue;
			}
			fixed++;
			for (Instruction ins : currentProgram.getListing().getInstructions(range, true)) {
				Address a = ins.getAddress();
				Instruction prev = ins.getPrevious();
				boolean fallIn = prev != null && a.equals(prev.getFallThrough());
				if (a.equals(start) || !fallIn || getReferencesTo(a).length > 0 || getFunctionAt(a) != null) {
					redo.add(a);
				}
			}
			Instruction first = getInstructionContaining(start);
			if (first != null && !first.getAddress().equals(start)) {
				redo.add(first.getAddress());
			}
			Instruction last = getInstructionContaining(end);
			if (last != null && last.getMaxAddress().compareTo(end) > 0 && end.next() != null) {
				redo.add(end.next());
			}
			Address cs = first != null ? first.getAddress() : start;
			Address ce = last != null ? last.getMaxAddress() : end;
			currentProgram.getListing().clearCodeUnits(cs, ce, false);
			ClearFlowAndRepairCmd.clearBadBookmarks(currentProgram, cs, ce, monitor);
			ctx.setValue(dual, start, end, BigInteger.valueOf(v));
		}
		for (Address a : redo) {
			if (getInstructionContaining(a) == null) {
				disassemble(a);
			}
		}
		println(String.format("issue mode: %d dual / %d single ranges from mapping symbols, %d ranges re-disassembled",
			nd, ns, fixed));
	}

	/**
	 * No mapping symbols (stripped image). Compiled functions set their mode in the first bundle
	 * (ENTSP / DUALENTSP), so flow analysis gets them right. What goes wrong is hand-written
	 * assembly entered through a code pointer: event vectors ("ldap r11, handler; setv ...") and
	 * jump tables (lib_xud's PidJumpTable). Two heuristics, applied after auto-analysis:
	 *  1. an LDAP target runs in the issue mode of the code that took its address;
	 *  2. a code head that nothing flows into (no fall-through, no branch/call reference) and
	 *     that does not set its own mode runs in the mode of the code just before it
	 *     (assembly files switch mode with .issue_mode, not per label).
	 */
	private void inferFromLdap(Register dual) throws Exception {
		if (currentProgram.getListing().getNumInstructions() == 0) {
			println("no $s/$d mapping symbols and no code yet: issue mode comes from DUALENTSP/ENTSP " +
				"flow only; run this script again after analysis (-postScript) for stripped images");
			return;
		}
		List<Instruction> ldaps = new ArrayList<>();
		for (Instruction ins : currentProgram.getListing().getInstructions(true)) {
			if (ins.getMnemonicString().equalsIgnoreCase("ldap")) {
				ldaps.add(ins);
			}
		}
		int fixed = 0;
		for (Instruction ins : ldaps) {
			int d = mode(ins, dual);
			for (Reference r : ins.getReferencesFrom()) {
				Address t = r.getToAddress();
				MemoryBlock b = currentProgram.getMemory().getBlock(t);
				if (b == null || !b.isExecute()) {
					continue;
				}
				Instruction ti = getInstructionAt(t);
				if (ti != null && (mode(ti, dual) == d || setsMode(ti))) {
					continue;
				}
				if (ti == null && getInstructionContaining(t) != null) {
					continue;
				}
				redisassemble(t, dual, d);
				fixed++;
			}
		}
		int heads = 0;
		for (int pass = 0; pass < 6; pass++) {
			List<Instruction[]> todo = new ArrayList<>();
			for (Instruction ins : currentProgram.getListing().getInstructions(true)) {
				Address a = ins.getAddress();
				Instruction prev = getInstructionBefore(a);
				if (prev == null || a.subtract(prev.getMaxAddress()) > 256) {
					continue;   // only heads preceded by nearby code (alignment padding, undecoded code)
				}
				if (a.equals(prev.getFallThrough()) || setsMode(ins)) {
					continue;
				}
				boolean flowIn = false;
				for (Reference r : getReferencesTo(a)) {
					if (r.getReferenceType().isFlow()) {
						flowIn = true;
						break;
					}
				}
				if (!flowIn && mode(ins, dual) != mode(prev, dual)) {
					todo.add(new Instruction[] { ins, prev });
				}
			}
			if (todo.isEmpty()) {
				break;
			}
			for (Instruction[] p : todo) {
				Address a = p[0].getAddress();
				if (getInstructionAt(a) == null) {
					continue;
				}
				redisassemble(a, dual, mode(p[1], dual));
				heads++;
			}
		}
		println(String.format("no $s/$d mapping symbols: %d LDAP targets and %d unreferenced code heads " +
			"re-disassembled in the issue mode of their LDAP / preceding code", fixed, heads));
	}
}
