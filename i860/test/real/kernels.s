# Hand-written i860 kernels that use what GCC never emits: the floating-point pipelines,
# dual-instruction mode, bla loops and the graphics unit. Written for this module (MIT) from
# the Programmer's Reference Manual (chapters 7 and 8). test/real/kernel-emu.sh assembles them
# with GNU as, analyses them in Ghidra and runs them in Ghidra's p-code emulator.
#
# Calling convention as GCC's: arguments in r16-r19, single-precision result in f8, return
# address in r1.

	.text
	.align	8
# float dot_pipe(float *a, float *b, int n), n >= 1: products through the 3-stage multiplier
# pipeline, sums through the 3-stage adder pipeline (three interleaved partial sums).
	.globl	dot_pipe
dot_pipe:
	pfmul.ss	%f0,%f0,%f0
	pfmul.ss	%f0,%f0,%f0
	pfmul.ss	%f0,%f0,%f0
	pfadd.ss	%f0,%f0,%f0
	pfadd.ss	%f0,%f0,%f0
	pfadd.ss	%f0,%f0,%f0
	adds	-4,%r16,%r16
	adds	-4,%r17,%r17
	adds	-1,%r0,%r5
	adds	-1,%r18,%r6
	bla	%r5,%r6,.L1
	nop
.L1:	fld.l	4(%r16)++,%f2
	fld.l	4(%r17)++,%f3
	pfmul.ss	%f2,%f3,%f4
	bla	%r5,%r6,.L1
	pfadd.ss	%f4,%f5,%f5
	pfmul.ss	%f0,%f0,%f4
	pfadd.ss	%f4,%f5,%f5
	pfmul.ss	%f0,%f0,%f4
	pfadd.ss	%f4,%f5,%f5
	pfmul.ss	%f0,%f0,%f4
	pfadd.ss	%f4,%f5,%f5
	pfadd.ss	%f0,%f0,%f6
	pfadd.ss	%f0,%f0,%f7
	pfadd.ss	%f0,%f0,%f8
	fadd.ss	%f6,%f7,%f6
	bri	%r1
	fadd.ss	%f6,%f8,%f8

# float dot_dual(float *a, float *b, int n), n >= 1: the same in dual-instruction mode. Each
# pair's floating-point operation reads f2/f3 before the companion load replaces them, so the
# loads run one element ahead.
	.align	8
	.globl	dot_dual
dot_dual:
	pfmul.ss	%f0,%f0,%f0
	pfmul.ss	%f0,%f0,%f0
	pfmul.ss	%f0,%f0,%f0
	pfadd.ss	%f0,%f0,%f0
	pfadd.ss	%f0,%f0,%f0
	pfadd.ss	%f0,%f0,%f0
	fld.l	0(%r16),%f2
	fld.l	0(%r17),%f3
	adds	-1,%r0,%r5
	adds	-1,%r18,%r6
	bla	%r5,%r6,.L2
	nop
.L2:	nop
	nop
	d.fnop
	nop
.L3:	d.pfmul.ss	%f2,%f3,%f4
	fld.l	4(%r16)++,%f2
	d.pfadd.ss	%f4,%f5,%f5
	fld.l	4(%r17)++,%f3
	d.fnop
	bla	%r5,%r6,.L3
	d.fnop
	nop
	fnop
	nop
	fnop
	nop
	pfmul.ss	%f0,%f0,%f4
	pfadd.ss	%f4,%f5,%f5
	pfmul.ss	%f0,%f0,%f4
	pfadd.ss	%f4,%f5,%f5
	pfmul.ss	%f0,%f0,%f4
	pfadd.ss	%f4,%f5,%f5
	pfadd.ss	%f0,%f0,%f6
	pfadd.ss	%f0,%f0,%f7
	pfadd.ss	%f0,%f0,%f8
	fadd.ss	%f6,%f7,%f6
	bri	%r1
	fadd.ss	%f6,%f8,%f8

# void zbuf8(unsigned short *z, unsigned short *znew, unsigned short *pix, unsigned short *pnew):
# eight 16-bit pixels with 16-bit z values: keep the nearer z and store the pixels that won.
	.align	8
	.globl	zbuf8
zbuf8:
	ld.c	%psr,%r4
	andnoth	0x00c0,%r4,%r4
	orh	0x0040,%r4,%r4		# PS = 1 (16-bit pixels)
	st.c	%r4,%psr
	fld.d	0(%r16),%f2
	fld.d	0(%r17),%f4
	fzchks	%f2,%f4,%f6
	fld.d	8(%r16),%f2
	fld.d	8(%r17),%f4
	fzchks	%f2,%f4,%f8
	fst.d	%f6,0(%r16)
	fst.d	%f8,8(%r16)
	fld.d	0(%r19),%f10
	pst.d	%f10,0(%r18)
	fld.d	8(%r19),%f10
	pst.d	%f10,8(%r18)
	bri	%r1
	nop

# double poly_dual(double x): Horner's rule 3x^3 + 2x^2 + x + 5 with the dual-operation
# multiply-add pipeline (r2p1/r2pt style through KR) -- scalar-step version using m12apm-free
# r2p1.dd with KR = x; drained step by step. Result in f8:f9.
	.align	8
	.globl	poly_dual
poly_dual:
	r2apt.dd	%f8,%f0,%f0	# KR <- x (K load), T <- M last, junk elsewhere
	pfmul.dd	%f0,%f0,%f0	# clear the 2-stage multiplier
	pfmul.dd	%f0,%f0,%f0
	pfadd.dd	%f0,%f0,%f0	# clear the adder
	pfadd.dd	%f0,%f0,%f0
	pfadd.dd	%f0,%f0,%f0
	fmul.dd	%f8,%f8,%f2		# x^2
	fmul.dd	%f2,%f8,%f4		# x^3
	orh	0x4008,%r0,%r4		# 3.0
	ixfr	%r0,%f10
	ixfr	%r4,%f11
	fmul.dd	%f10,%f4,%f4		# 3x^3
	orh	0x4000,%r0,%r4		# 2.0
	ixfr	%r4,%f11
	fmul.dd	%f10,%f2,%f2		# 2x^2
	fadd.dd	%f4,%f2,%f2
	fadd.dd	%f2,%f8,%f2
	orh	0x4014,%r0,%r4		# 5.0
	ixfr	%r4,%f11
	bri	%r1
	fadd.dd	%f2,%f10,%f8
