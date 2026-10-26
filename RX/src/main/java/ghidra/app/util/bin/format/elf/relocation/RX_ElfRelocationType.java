/* SPDX-License-Identifier: MIT */
package ghidra.app.util.bin.format.elf.relocation;

/**
 * Renesas RX ELF relocation types (EM_RX = 173). The numbers and names were read from GNU
 * readelf's output for a crafted object (readelf used as a black box); the semantics follow the
 * names: DIRn = S + A in an n-bit field, _PCREL = S + A - P, UL/UW = value scaled down by 4/2
 * (scaled displacements), _REV = big-endian field, DIR3U_PCREL = the 3-bit BRA.S/BCnd.S field.
 * ABSn and OPxxx form the stack machine for complex expressions: SYM pushes S + A, OPxxx pops
 * operands and pushes the result, ABSn pops the value and stores it.
 */
public enum RX_ElfRelocationType implements ElfRelocationType {

	R_RX_NONE(0x00),
	R_RX_DIR32(0x01),
	R_RX_DIR24S(0x02),
	R_RX_DIR16(0x03),
	R_RX_DIR16U(0x04),
	R_RX_DIR16S(0x05),
	R_RX_DIR8(0x06),
	R_RX_DIR8U(0x07),
	R_RX_DIR8S(0x08),
	R_RX_DIR24S_PCREL(0x09),
	R_RX_DIR16S_PCREL(0x0a),
	R_RX_DIR8S_PCREL(0x0b),
	R_RX_DIR16UL(0x0c),
	R_RX_DIR16UW(0x0d),
	R_RX_DIR8UL(0x0e),
	R_RX_DIR8UW(0x0f),
	R_RX_DIR32_REV(0x10),
	R_RX_DIR16_REV(0x11),
	R_RX_DIR3U_PCREL(0x12),
	R_RX_RH_3_PCREL(0x20),
	R_RX_RH_16_OP(0x21),
	R_RX_RH_24_OP(0x22),
	R_RX_RH_32_OP(0x23),
	R_RX_RH_24_UNS(0x24),
	R_RX_RH_8_NEG(0x25),
	R_RX_RH_16_NEG(0x26),
	R_RX_RH_24_NEG(0x27),
	R_RX_RH_32_NEG(0x28),
	R_RX_RH_DIFF(0x29),
	R_RX_RH_GPRELB(0x2a),
	R_RX_RH_GPRELW(0x2b),
	R_RX_RH_GPRELL(0x2c),
	R_RX_RH_RELAX(0x2d),
	R_RX_ABS32(0x41),
	R_RX_ABS24S(0x42),
	R_RX_ABS16(0x43),
	R_RX_ABS16U(0x44),
	R_RX_ABS16S(0x45),
	R_RX_ABS8(0x46),
	R_RX_ABS8U(0x47),
	R_RX_ABS8S(0x48),
	R_RX_ABS24S_PCREL(0x49),
	R_RX_ABS16S_PCREL(0x4a),
	R_RX_ABS8S_PCREL(0x4b),
	R_RX_ABS16UL(0x4c),
	R_RX_ABS16UW(0x4d),
	R_RX_ABS8UL(0x4e),
	R_RX_ABS8UW(0x4f),
	R_RX_ABS32_REV(0x50),
	R_RX_ABS16_REV(0x51),
	R_RX_SYM(0x80),
	R_RX_OPneg(0x81),
	R_RX_OPadd(0x82),
	R_RX_OPsub(0x83),
	R_RX_OPmul(0x84),
	R_RX_OPdiv(0x85),
	R_RX_OPshla(0x86),
	R_RX_OPshra(0x87),
	R_RX_OPsctsize(0x88),
	R_RX_OPscttop(0x8d),
	R_RX_OPand(0x90),
	R_RX_OPor(0x91),
	R_RX_OPxor(0x92),
	R_RX_OPnot(0x93),
	R_RX_OPmod(0x94),
	R_RX_OPromtop(0x95),
	R_RX_OPramtop(0x96);

	public final int typeId;

	private RX_ElfRelocationType(int typeId) {
		this.typeId = typeId;
	}

	@Override
	public int typeId() {
		return typeId;
	}
}
