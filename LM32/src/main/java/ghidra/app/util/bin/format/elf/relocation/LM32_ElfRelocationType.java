/* SPDX-License-Identifier: MIT */
package ghidra.app.util.bin.format.elf.relocation;

/**
 * LatticeMico32 ELF relocation types (binutils include/elf/lm32.h).
 */
public enum LM32_ElfRelocationType implements ElfRelocationType {

	R_LM32_NONE(0),
	R_LM32_8(1),
	R_LM32_16(2),
	R_LM32_32(3),
	R_LM32_HI16(4),
	R_LM32_LO16(5),
	R_LM32_GPREL16(6),
	R_LM32_CALL(7),
	R_LM32_BRANCH(8),
	R_LM32_GNU_VTINHERIT(9),
	R_LM32_GNU_VTENTRY(10),
	R_LM32_16_GOT(11),
	R_LM32_GOTOFF_HI16(12),
	R_LM32_GOTOFF_LO16(13),
	R_LM32_COPY(14),
	R_LM32_GLOB_DAT(15),
	R_LM32_JMP_SLOT(16),
	R_LM32_RELATIVE(17);

	public final int typeId;

	private LM32_ElfRelocationType(int typeId) {
		this.typeId = typeId;
	}

	@Override
	public int typeId() {
		return typeId;
	}
}
