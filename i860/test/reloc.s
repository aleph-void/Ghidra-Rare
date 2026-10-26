# Relocation test object for test/reloc-check.sh: every relocation type GNU as emits for the
# i860, against symbols with addends, low halves above 0x8000 (HIGHADJ carries) and
# branch targets in another section.
	.text
	.globl	start
start:	orh	[sym]@h,%r0,%r4
	or	[sym]@l,%r4,%r4
	orh	[sym+0x1234]@ha,%r0,%r31
	ld.b	[sym+0x1234]@l(%r31),%r5
	ld.s	[sym2]@l(%r31),%r5
	ld.l	[sym2+4]@l(%r31),%r5
	fld.l	[sym2+8]@l(%r31),%f2
	pfld.l	[sym2+12]@l(%r31),%f2
	fld.d	[sym2+16]@l(%r31),%f2
	fld.d	[sym2+16]@l(%r31)++,%f2
	fld.q	[sym2+32]@l(%r31),%f4
	pst.d	%f2,[sym2+48]@l(%r31)
	st.b	%r5,[sym+3]@l(%r31)
	st.s	%r5,[sym2+2]@l(%r31)
	st.l	%r5,[sym2+4]@l(%r31)
	adds	[sym]@l,%r0,%r6
	orh	[far]@ha,%r0,%r7
	addu	[far]@l,%r7,%r7
	call	other
	nop
	br	other+8
	nop
	bc	start
	bte	%r4,%r5,other
	bla	%r4,%r5,start
	nop
	.data
	.long	sym
	.long	sym2+8
	.long	other
	.space	0x9000
	.globl	sym
sym:	.long	1
	.align	16
sym2:	.space	64
	.section .text2,"ax"
	.globl	other
other:	bri	%r1
	nop
	.section .far,"aw"
	.space	0x30
far:	.long	0
