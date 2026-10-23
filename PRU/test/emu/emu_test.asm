; Semantics test program for test/PruEmuTest.java (assembled with TI clpru -v3).
; Expected register values are listed in PruEmuTest.java.
	.text
	.global start
start:
	zero	&r0, 124            ; clear r0..r30
	jal	r25.w0, t_alu       ; link = word address 2
t_alu:
	ldi32	r1, 0xffffffff
	add	r2, r1, 1           ; 0, carry=1
	adc	r3, r0, 0           ; 1
	ldi	r4, 0x00ff
	add	r5.b0, r4.b0, 1     ; r5 = 0, carry=1 (bit 8)
	adc	r6, r0, 0           ; 1
	ldi	r7, 5
	sub	r8, r7, 6           ; 0xffffffff, borrow=1
	suc	r9, r7, 1           ; 5 - 1 - 1 = 3
	rsb	r10, r7, 10         ; 5
	lsl	r11, r7, 4          ; 0x50
	lsr	r12, r1, 28         ; 0xf
	lmbd	r13, r11, 1         ; 6
	lmbd	r14, r0, 1          ; 32
	not	r15.w0, r7.b0       ; r15 = 0x0000fffa
	clr	r16, r1, 31         ; 0x7fffffff
	set	r17, r0, 3          ; 8
	min	r18, r7, 3          ; 3
	max	r19, r7, 3          ; 5
	ldi32	r20, 0x11223344
	and	r21, r20.w1, r20.w1 ; 0x2233
	ldi	r22, 0x100
	sbbo	&r20, r22, 0, 4     ; data[0x100..0x103] = 44 33 22 11
	lbbo	&r23.b1, r22, 1, 2  ; r23 = 0x00223300
	ldi	r1.b0, &r20.b2      ; register-file pointer 82
	mvib	r24, *r1.b0++       ; r24 = 0x22, r1.b0 = 83
	ldi	r26, 0
	loop	endl, 5
	add	r26, r26, 3         ; executed 5 times -> 15
endl:
	fill	&r27, 4             ; 0xffffffff
	ldi	r28, 7
	qbgt	skip, r7, 6         ; 6 > 5 -> taken
	ldi	r28, 99
skip:
	lmbd	r29.b0, r20.w0, 0   ; 0x3344: highest clear bit within 16 bits = 15
	ldi	r30, 0
	jal	r3.w2, fn           ; call / ret round trip, twice
	jal	r3.w2, fn           ; r30 = 2
	ldi	r4.w0, $CODE(fn2)   ; register-indirect jump (word address)
	jmp	r4.w0
	ldi	r30, 99             ; skipped
fn:
	add	r30, r30, 1
	jmp	r3.w2
fn2:
	ldi	r22.w2, 0x55        ; r22 = 0x00550100
	halt
