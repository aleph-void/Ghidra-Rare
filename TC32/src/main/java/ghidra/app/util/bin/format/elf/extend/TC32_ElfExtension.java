/* Ghidra-Rare (MIT). ELF loader extension for Telink TC32 (tc32-elf, e_machine 0x8800). */
package ghidra.app.util.bin.format.elf.extend;

import ghidra.app.util.bin.format.elf.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.data.ByteDataType;
import ghidra.program.model.data.DWordDataType;
import ghidra.program.model.data.WordDataType;
import ghidra.program.model.lang.Language;

/**
 * tc32-elf marks code symbols the way ARM marks Thumb code: function symbols carry bit 0 set
 * (`sleep_us` is 0x48d in the symbol table while the code and every `tjl` to it are at 0x48c), and
 * the assembler emits `$t` / `$d` mapping symbols. Without this extension Ghidra creates functions at
 * the odd address and decodes them from the middle of an instruction. Function symbols are moved to
 * the even address; mapping symbols are not turned into labels or functions, and `$d` marks data so
 * that disassembly does not run into the image header or literal pools.
 */
public class TC32_ElfExtension extends ElfExtension {

	static final short EM_TC32 = (short) 0x8800;

	@Override
	public boolean canHandle(ElfHeader elf) {
		return elf.e_machine() == EM_TC32;
	}

	@Override
	public boolean canHandle(ElfLoadHelper elfLoadHelper) {
		Language language = elfLoadHelper.getProgram().getLanguage();
		return canHandle(elfLoadHelper.getElfHeader()) &&
			"TC32".equals(language.getProcessor().toString());
	}

	@Override
	public String getDataTypeSuffix() {
		return "_TC32";
	}

	@Override
	public Address evaluateElfSymbol(ElfLoadHelper elfLoadHelper, ElfSymbol elfSymbol,
			Address address, boolean isExternal) {
		if (isExternal) {
			return address;
		}
		String name = elfSymbol.getNameAsString();
		if (name != null && (name.equals("$t") || name.equals("$d") || name.equals("$a") ||
			name.startsWith("$t.") || name.startsWith("$d.") || name.startsWith("$a."))) {
			// $d starts data inside a code section (image header words, literal pools): a one-byte
			// undefined data item there stops disassembly from flowing into it. $t is code.
			if (name.startsWith("$d")) {
				int len = (int) Math.max(1, Math.min(dataLength(elfSymbol), 0x10000));
				// defined words (not undefined bytes, which later analysis may disassemble over)
				for (int off = 0; off < len;) {
					Address a = address.add(off);
					int n = (len - off >= 4 && (a.getOffset() & 3) == 0) ? 4 : (len - off >= 2 && (a.getOffset() & 1) == 0) ? 2 : 1;
					elfLoadHelper.createData(a, n == 4 ? DWordDataType.dataType : n == 2 ? WordDataType.dataType : ByteDataType.dataType);
					off += n;
				}
			}
			else if (name.startsWith("$t")) {
				elfLoadHelper.markAsCode(address);
			}
			return null;
		}
		if (elfSymbol.isAbsolute() && !elfSymbol.isFunction()) {
			// linker constants (__LOAD_FLASH = 1, _ramcode_size_div_256_ = 0x0a, ...): not addresses;
			// placing them as labels made analysis disassemble the image header at their value
			return null;
		}
		if (elfSymbol.isFunction() && (address.getOffset() & 1) != 0) {
			return address.subtract(1);
		}
		return address;
	}

	/** Bytes from a $d symbol to the next mapping or function symbol of the same section. */
	private static long dataLength(ElfSymbol d) {
		long start = d.getValue(), next = Long.MAX_VALUE;
		for (ElfSymbol s : d.getSymbolTable().getSymbols()) {
			if (s.getSectionHeaderIndex() != d.getSectionHeaderIndex()) {
				continue;
			}
			String n = s.getNameAsString();
			boolean marks = n != null && (n.startsWith("$t") || n.startsWith("$a"));
			long v = s.getValue() & ~1L;
			if ((marks || s.isFunction()) && v > start && v < next) {
				next = v;
			}
		}
		return next == Long.MAX_VALUE ? 1 : next - start;
	}

	@Override
	public Address creatingFunction(ElfLoadHelper elfLoadHelper, Address functionAddress) {
		if ((functionAddress.getOffset() & 1) != 0) {
			return functionAddress.subtract(1);
		}
		return functionAddress;
	}
}
