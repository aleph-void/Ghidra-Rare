# Relocation-type coverage for the ELF relocation handler test (assembled by build.sh).
# Public domain.
	.section .text
	.global _start
_start:
	l.movhi	r3, hi(target_data)
	l.ori	r3, r3, lo(target_data)
	l.movhi	r4, ha(target_data+0x9000)
	l.lwz	r5, lo(target_data+0x9000)(r4)
	l.sw	lo(target_data+0x10)(r4), r5
	l.adrp	r6, target_data
	l.addi	r6, r6, po(target_data)
	l.lwz	r7, po(target_data+8)(r6)
	l.sw	po(target_data+12)(r6), r7
	l.j	far_func
	l.nop
	l.jal	plt(far_func)
	l.nop
	l.bf	_start
	l.nop
	l.j	ext_func
	l.nop
	l.jal	plt(ext_func)
	l.nop
	l.movhi	r8, hi(ext_data+4)
	l.ori	r8, r8, lo(ext_data+4)
	l.jr	r9
	l.nop
far_func:
	l.jr	r9
	l.nop

	.section .data
	.align 4
target_data:
	.word	0x11223344, 0x55667788, 0, 0, 0, 0
	.word	far_func
	.word	target_data + 4
	.word	far_func - .
	.word	ext_data + 8
	.word	ext_func - .
# (R_OR1K_16/8 against these addresses overflow, and GNU ld 2.43 asserts on R_OR1K_16_PCREL,
#  so the 16- and 8-bit data relocations are not part of the check)
	.align 2
