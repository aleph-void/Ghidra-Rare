package ghidra.app.util.bin.format.elf.relocation;

/**
 * Telink TC32 ELF relocation types (e_machine 0x8800), numbered as tc32-elf-readelf reports them
 * in objects built by tc32-elf-gcc/as (REL sections, addends in place).
 */
public enum TC32_ElfRelocationType implements ElfRelocationType {

	R_TC32_NONE(0),
	R_TC32_ABS32(2),
	R_TC32_CALL(10);

	public final int typeId;

	private TC32_ElfRelocationType(int typeId) {
		this.typeId = typeId;
	}

	@Override
	public int typeId() {
		return typeId;
	}
}
