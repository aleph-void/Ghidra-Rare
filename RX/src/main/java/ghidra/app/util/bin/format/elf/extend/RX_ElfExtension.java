/* SPDX-License-Identifier: MIT */
package ghidra.app.util.bin.format.elf.extend;

import ghidra.app.util.bin.format.elf.*;

/**
 * ELF loading tweaks for Renesas RX (EM_RX = 173).
 * <p>
 * GCC for RX puts zero-initialised data in a section named "B" that gas emits with the write
 * flag but without SHF_ALLOC; GNU ld still places it by name. Ghidra would skip the section, so
 * relocations against its symbols would fail in relocatable objects. The RX toolchains' standard
 * section names (P, C, D, B, R, W, L with optional _1/_2 alignment suffixes) are treated as
 * allocated.
 */
public class RX_ElfExtension extends ElfExtension {

	public static final int EM_RX = 173;

	@Override
	public boolean canHandle(ElfHeader elf) {
		return elf.e_machine() == EM_RX;
	}

	@Override
	public boolean canHandle(ElfLoadHelper elfLoadHelper) {
		return canHandle(elfLoadHelper.getElfHeader()) &&
			"RX".equals(elfLoadHelper.getProgram().getLanguage().getProcessor().toString());
	}

	@Override
	public String getDataTypeSuffix() {
		return "_RX";
	}

	@Override
	public Boolean isSectionAllocated(ElfSectionHeader section) {
		if (section.getNameAsString().matches("[PCDBRWL](_[12])?") &&
			(section.getType() == ElfSectionHeaderConstants.SHT_PROGBITS ||
				section.getType() == ElfSectionHeaderConstants.SHT_NOBITS)) {
			return true;
		}
		return super.isSectionAllocated(section);
	}
}
