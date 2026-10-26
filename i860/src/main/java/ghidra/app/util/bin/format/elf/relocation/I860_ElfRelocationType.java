package ghidra.app.util.bin.format.elf.relocation;

/**
 * Intel i860 ELF relocation types (EM_860 = 7), as numbered in the i860 System V ABI and
 * reported by GNU readelf.
 */
public enum I860_ElfRelocationType implements ElfRelocationType {

	R_860_NONE(0x00),
	R_860_32(0x01),
	R_860_COPY(0x02),
	R_860_GLOB_DAT(0x03),
	R_860_JUMP_SLOT(0x04),
	R_860_RELATIVE(0x05),
	R_860_PC26(0x30),
	R_860_PLT26(0x31),
	R_860_PC16(0x32),
	R_860_LOW0(0x40),
	R_860_SPLIT0(0x42),
	R_860_LOW1(0x44),
	R_860_SPLIT1(0x46),
	R_860_LOW2(0x48),
	R_860_SPLIT2(0x4a),
	R_860_LOW3(0x4c),
	R_860_LOGOT0(0x50),
	R_860_SPGOT0(0x52),
	R_860_LOGOT1(0x54),
	R_860_SPGOT1(0x56),
	R_860_LOGOTOFF0(0x60),
	R_860_SPGOTOFF0(0x62),
	R_860_LOGOTOFF1(0x64),
	R_860_SPGOTOFF1(0x66),
	R_860_LOGOTOFF2(0x68),
	R_860_LOGOTOFF3(0x6c),
	R_860_LOPC(0x70),
	R_860_HIGHADJ(0x80),
	R_860_HAGOT(0x90),
	R_860_HAGOTOFF(0xa0),
	R_860_HAPC(0xb0),
	R_860_HIGH(0xc0),
	R_860_HIGOT(0xd0),
	R_860_HIGOTOFF(0xe0);

	public final int typeId;

	private I860_ElfRelocationType(int typeId) {
		this.typeId = typeId;
	}

	@Override
	public int typeId() {
		return typeId;
	}
}
