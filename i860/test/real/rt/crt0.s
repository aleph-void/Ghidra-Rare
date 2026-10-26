# Minimal start-up code for the i860 test programs (bare metal, no OS): set up the stack,
# clear .bss, call main and stop in a trap with main's result in r16.
	.text
	.align 8
	.globl _start
_start:
	orh	[__stack_top]@h,%r0,%sp
	or	[__stack_top]@l,%sp,%sp
	mov	%sp,%fp
	orh	[__bss_start]@h,%r0,%r4
	or	[__bss_start]@l,%r4,%r4
	orh	[_end]@h,%r0,%r5
	or	[_end]@l,%r5,%r5
1:	subu	%r4,%r5,%r0
	bc	2f
	st.b	%r0,0(%r4)
	br	1b
	addu	1,%r4,%r4
2:	call	main
	nop
	.globl	_exit
_exit:
	trap	%r16,%r0,%r0
	br	_exit
	nop
