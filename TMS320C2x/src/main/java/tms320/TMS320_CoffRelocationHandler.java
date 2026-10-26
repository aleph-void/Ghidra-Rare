package tms320;

import ghidra.app.util.bin.format.RelocationException;
import ghidra.app.util.bin.format.coff.CoffFileHeader;
import ghidra.app.util.bin.format.coff.CoffRelocation;
import ghidra.app.util.bin.format.coff.CoffSectionHeader;
import ghidra.app.util.bin.format.coff.CoffSymbol;
import ghidra.app.util.bin.format.coff.relocation.CoffRelocationContext;
import ghidra.app.util.bin.format.coff.relocation.CoffRelocationHandler;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Program;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.reloc.Relocation.Status;
import ghidra.program.model.reloc.RelocationResult;

/**
 * Relocations for TI COFF objects of the TMS320C1x/C2x/C2xx/C5x code generation tools (target ID
 * 0092h). Relocation types per the TMS320C1x/C2x/C2xx/C5x Assembly Language Tools User's Guide
 * (SPRU018D) Table A-9: R_RELBYTE (0Fh), R_RELWORD (10h), R_PARTLS7 (28h), R_PARTMS9 (29h) and
 * R_REL (2Ah, 13-bit).
 * <p>
 * The patched field holds the assembly-time value. Assembled sections start at address 0, so the
 * relocation amount is the address the loader placed the referenced symbol's section at (for an
 * internal relocation, the current section's), or the symbol's address when it is undefined in
 * this object. Addresses are 16-bit word addresses; Ghidra's COFF loader passes the field
 * address as if the virtual address counted bytes, so it is recomputed here from the section.
 */
public class TMS320_CoffRelocationHandler implements CoffRelocationHandler {

	public static final short R_ABS = 0x0000;
	public static final short R_RELBYTE = 0x000F;
	public static final short R_RELWORD = 0x0010;
	public static final short R_PARTLS7 = 0x0028;
	public static final short R_PARTMS9 = 0x0029;
	public static final short R_REL13 = 0x002A;

	// The factory makes a handler instance per load and asks canRelocate() first; keep the header
	// to resolve section symbols, which the loader does not map to program symbols.
	private CoffFileHeader header;

	@Override
	public boolean canRelocate(CoffFileHeader fileHeader) {
		if (fileHeader.getMachine() == 0x0092) {
			header = fileHeader;
			return true;
		}
		return false;
	}

	private static long word(Address a) {
		return a.getAddressableWordOffset();
	}

	@Override
	public RelocationResult relocate(Address address, CoffRelocation relocation,
			CoffRelocationContext context) throws MemoryAccessException, RelocationException {
		Program program = context.getProgram();
		Memory mem = program.getMemory();
		CoffSectionHeader section = context.getSection();
		Address secStart = section.getPhysicalAddress(program.getLanguage());
		Address field = secStart.add(2L * (relocation.getAddress() - section.getVirtualAddress()));
		short type = relocation.getType();
		if (type == R_ABS) {
			return RelocationResult.SKIPPED;
		}
		long amount;
		if (relocation.getSymbolIndex() == 0xFFFF || relocation.getSymbolIndex() == -1 ||
			relocation.getSymbolIndex() == 0xFFFFFFFFL) {
			amount = word(secStart);
		}
		else {
			CoffSymbol cs = header != null ? header.getSymbolAtIndex(relocation.getSymbolIndex()) : null;
			if (cs != null && cs.getSectionNumber() > 0 &&
				cs.getSectionNumber() <= header.getSections().size()) {
				// defined in this object: the displacement of its section (assembled at 0)
				CoffSectionHeader s = header.getSections().get(cs.getSectionNumber() - 1);
				amount = word(s.getPhysicalAddress(program.getLanguage()));
			}
			else {
				Address symAddr;
				try {
					symAddr = context.getSymbolAddress(relocation);
				}
				catch (RelocationException e) {
					symAddr = null;
				}
				if (symAddr == null || symAddr.isExternalAddress()) {
					throw new RelocationException("unresolved external symbol" +
						(cs != null ? " " + cs.getName() : ""));
				}
				amount = word(symAddr);
			}
		}
		boolean big = program.getLanguage().isBigEndian();
		byte[] b = new byte[2];
		mem.getBytes(field, b);
		int w = big ? ((b[0] & 0xff) << 8) | (b[1] & 0xff) : ((b[1] & 0xff) << 8) | (b[0] & 0xff);
		int nw;
		switch (type) {
			case R_RELWORD:
				nw = (int) ((w + amount) & 0xffff);
				break;
			case R_RELBYTE:
				nw = (w & 0xff00) | (int) ((w + amount) & 0xff);
				break;
			case R_PARTLS7:
				nw = (w & ~0x7f) | (int) ((w + amount) & 0x7f);
				break;
			case R_PARTMS9: {
				// the field holds address bits 15-7; the low bits are assumed to be those of the
				// section displacement-free address, so carries from bits 6-0 are not seen
				long v = ((long) (w & 0x1ff) << 7) + amount;
				nw = (w & ~0x1ff) | (int) ((v >> 7) & 0x1ff);
				break;
			}
			case R_REL13:
				nw = (w & ~0x1fff) | (int) ((w + amount) & 0x1fff);
				break;
			default:
				return RelocationResult.UNSUPPORTED;
		}
		b = big ? new byte[] { (byte) (nw >> 8), (byte) nw } : new byte[] { (byte) nw, (byte) (nw >> 8) };
		mem.setBytes(field, b);
		return new RelocationResult(Status.APPLIED, 2);
	}
}
