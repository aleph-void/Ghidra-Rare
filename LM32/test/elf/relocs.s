# Relocation-type coverage for the LM32 ELF relocation handler test (assembled by build.sh).
# Public domain.
	.section .text
	.global _start
_start:
	mvhi	r1, hi(target_data)
	ori	r1, r1, lo(target_data)
	orhi	r2, r0, hi(target_data+0x12345)
	ori	r2, r2, lo(target_data+0x12345)
	calli	ext_func
	calli	local_func
	be	r1, r2, ext_func
	bne	r1, r2, local_func
	bi	ext_func
	mvhi	r5, hi(ext_data+4)
	ori	r5, r5, lo(ext_data+4)
	ret
local_func:
	ret

	.section .data
	.align 4
target_data:
	.word	local_func
	.word	ext_func
	.word	target_data + 4
	.word	ext_data + 8
