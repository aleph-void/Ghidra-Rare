! (From aleph-void/ghidra-sh, MIT.)  Minimal startup for the real-code samples (the code is analysed, not run): set the stack,
! call main, loop.  The same source assembles for either byte order.
	.text
	.global	_start
_start:
	mov.l	stkp,r15
	mov.l	mainp,r0
	jsr	@r0
	nop
1:	bra	1b
	nop
	.align	2
stkp:	.long	0x00ff0000
mainp:	.long	_main
