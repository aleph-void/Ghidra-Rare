# Dotted names for the division helpers in divide.c: tail branches (r1 still holds the
# caller's return address).
	.text
	.align	8
	.globl	.div
.div:	br	i860_div
	nop
	.globl	.udiv
.udiv:	br	i860_udiv
	nop
	.globl	.rem
.rem:	br	i860_rem
	nop
	.globl	.urem
.urem:	br	i860_urem
	nop
