; RXv3 test routines (gas -mcpu=rxv3-dfpu): double-precision coprocessor, bit fields, XOR with
; three operands and the register bank save instructions.
; C prototypes: int dpoly(const double *c, int n, const double *x);   (Horner, truncated)
;               unsigned bf(unsigned a, unsigned b);   unsigned x3(unsigned a, unsigned b);
	.text
	.global	_dpoly
_dpoly:				; r1 = c, r2 = n, r3 = x
	dpushm.d dr4-dr6
	dmov.d	[r3], dr5
	dmov.d	#0, drh4
1:	dmul	dr4, dr5, dr4
	dmov.d	[r1], dr6
	dadd	dr4, dr6, dr4
	add	#8, r1
	sub	#1, r2
	bne	1b
	dcmplt	dr4, dr5
	mvfdr
	dtoi	dr4, dr4
	dmov.l	drl4, r1
	dpopm.d	dr4-dr6
	rts

	.global	_bf
_bf:
	bfmov	#4, #8, #8, r1, r2
	bfmovz	#0, #0, #4, r2, r1
	rts

	.global	_x3
_x3:
	xor	r1, r2, r3
	mov.l	r3, r1
	rts

	.global	_isr_bank
_isr_bank:
	save	#0
	add	#1, r1
	rstr	#0
	rte
