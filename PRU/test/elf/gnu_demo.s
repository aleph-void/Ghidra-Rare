# GNU as (pru-elf) test program: calls, loops, LBCO, data references.
	.text
	.global _start
_start:
	ldi32	sp, 0x1f00
	ldi	r14, 5
	call	twice
	ldi32	r1, counter
	sbbo	&r14, r1, 0, 4
	call	sum_words
	halt

	.global twice
twice:
	lsl	r14, r14, 1
	ret

	.global sum_words
sum_words:
	zero	&r0, 4
	ldi	r1, words
	loop	1f, 4
	lbbo	&r2, r1, 0, 4
	add	r0, r0, r2
	add	r1, r1, 4
1:
	lbco	&r3, 24, 0, 4
	add	r14, r0, r3
	qbne	sum_words_done, r14, 0
	jmp	sum_words
sum_words_done:
	ret

	.data
counter:
	.word	0
words:
	.word	1, 2, 3, 4
