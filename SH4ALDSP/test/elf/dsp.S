! Hand-written SH4AL-DSP routines linked into the real-code samples, so that the ELF files carry
! DSP instructions (gcc -m4al emits none): an FIR inner product with an extended repeat loop,
! parallel X/Y loads, PADD/PMULS and rounding; DSP context save/restore with MOVS; an atomic
! increment with MOVLI/MOVCO; a modulo-addressed ring buffer copy.  Not executed.
	.text
	.align	2
	.global	_dsp_fir
! int dsp_fir(const short *x /* r4, X memory */, int n /* r5 */, const short *h /* r6, Y memory */)
_dsp_fir:
	pclr	a0
	pclr	m0
	movx.w	@r4+,x0	movy.w	@r6+,y0
	ldrs	1f
	ldre	2f
	ldrc	r5
	nop
1:	pmuls	x0,y0,m0
2:	padd	a0,m0,a0	pmuls	x0,y0,m0	movx.w	@r4+,x0	movy.w	@r6+,y0
	padd	a0,m0,a0
	prnd	a0,a0
	sts	a0,r0
	rts
	shar	r0

	.global	_dsp_save
! void dsp_save(void *area /* r2 */): store the DSP registers
_dsp_save:
	movs.l	a0,@r2+
	movs.l	a0g,@r2+
	movs.l	a1,@r2+
	movs.l	a1g,@r2+
	movs.l	x0,@r2+
	movs.l	x1,@r2+
	movs.l	y0,@r2+
	movs.l	y1,@r2+
	movs.l	m0,@r2+
	movs.l	m1,@r2+
	sts	dsr,r0
	rts
	mov.l	r0,@r2

	.global	_dsp_restore
_dsp_restore:
	movs.l	@r2+,a0
	movs.l	@r2+,a0g
	movs.l	@r2+,a1
	movs.l	@r2+,a1g
	movs.l	@r2+,x0
	movs.l	@r2+,x1
	movs.l	@r2+,y0
	movs.l	@r2+,y1
	movs.l	@r2+,m0
	movs.l	@r2+,m1
	mov.l	@r2,r0
	rts
	lds	r0,dsr

	.global	_atomic_inc
! int atomic_inc(int *p /* r4 */)
_atomic_inc:
1:	movli.l	@r4,r0
	add	#1,r0
	movco.l	r0,@r4
	bf	1b
	rts
	nop

	.global	_ring_copy
! void ring_copy(short *ring /* r4, X memory, MOD set by the caller */, short *dst /* r5 */, int n /* r6 */)
_ring_copy:
	setdmx
2:	movx.w	@r4+,x0
	movs.w	x0,@r5+
	dt	r6
	bf	2b
	rts
	clrdmxy
