# R_LM32_GPREL16 coverage (assembled by build.sh). GNU ld 2.45 cannot link this correctly:
# lm32_elf_assign_gp looks for _gp in the output symbol table, which does not exist yet during
# an ELF final link, so it reports "dangerous error" and uses gp = 4. The test therefore checks
# Ghidra's result against the bfd formula S + A - _gp instead of against ld.
# Public domain.
	.section .text
	.global _start
_start:
	lw	r3, gp(small_data)
	sw	gp(small_data+4), r3
	mva	r4, gp(small_data+8)
	lw	r5, gp(small_data-0x100)
	ret

	.section .data
	.align 4
	.global _gp
_gp:
small_data:
	.word	0x11223344, 0x55667788, 0x99aabbcc
