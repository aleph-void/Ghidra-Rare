; RXv2 test routines for the RX module's real-code check (assembled with gas -mcpu=rxv2).
; C prototypes: int fir_q15(const short *x, const short *h, int n);
;               int atomic_add(int *p, int v);   long long mac64(int a, int b, long long acc);
	.text
	.global	_fir_q15
_fir_q15:			; r1 = x, r2 = h, r3 = n
	mov.l	#0, r4
	mvtachi	r4, a0
	mvtaclo	r4, a0
	cmp	#0, r3
	ble	2f
1:	mov.w	[r1+], r4
	mov.w	[r2+], r5
	maclo	r4, r5, a0
	sub	#1, r3
	bne	1b
2:	racw	#1, a0
	mvfachi	#0, a0, r1
	rts

	.global	_atomic_add
_atomic_add:			; r1 = p, r2 = v
1:	movli	[r1], r3
	add	r2, r3
	mov.l	r3, r4
	movco	r4, [r1]
	cmp	#0, r4
	bne	1b
	mov.l	r3, r1
	rts

	.global	_mac64
_mac64:				; r1 = a, r2 = b, r3:r4 = acc (lo, hi)
	mvtachi	r4, a1
	mvtaclo	r3, a1
	emaca	r1, r2, a1
	mvfaclo	#0, a1, r1
	mvfachi	#0, a1, r2
	rts

	.global	_fdist
_fdist:				; float fdist(float x, float y) = sqrt(x*x + y*y)
	fmul	r1, r1, r3
	fmul	r2, r2, r4
	fadd	r3, r4, r1
	fsqrt	r1, r1
	rts

	.global	_to_unsigned
_to_unsigned:			; unsigned to_unsigned(float f)
	ftou	r1, r1
	rts
