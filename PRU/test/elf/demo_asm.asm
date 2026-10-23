; Hand-written PRU assembly exercising LBCO/SBCO, LOOP, MVI, XFR and SLP.
	.text
	.global asm_sum_shared
; uint32_t asm_sum_shared(uint32_t n): sum n (1..255) words of shared RAM (C28)
asm_sum_shared:
	zero	&r0, 8
	loop	sum_end, r14.b0
	lbco	&r1, c28, r0.w2, 4
	add	r0.w0, r0.w0, r1.w0
	add	r0.w2, r0.w2, 4
sum_end:
	mov	r14, r0.w0
	jmp	r3.w2

	.global asm_intc_ack
; void asm_intc_ack(uint32_t ev): write SICR of the local INTC (C0 + 0x24)
asm_intc_ack:
	sbco	&r14, c0, 0x24, 4
	lbco	&r15, c0, 0x04, 4
	ldi	r1.b0, &r15.b0
	mvib	r16.b0, *r1.b0
	xout	10, &r14, 8
	jmp	r3.w2
