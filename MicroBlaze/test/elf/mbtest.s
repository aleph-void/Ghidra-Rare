# Hand-compiled MicroBlaze (32-bit) version of mbtest.c, written in the style of
# microblaze-elf-gcc -O2 output (standard ABI: args r5-r10 then stack at r1+28.., result r3,
# link r15, callee-saved r19-r31, return via "rtsd r15,8" with a filled delay slot).
# Assembled with gas and linked with ld (see build.sh); used by the Ghidra import/decompile check.

	.text
	.globl	add3
	.type	add3, @function
add3:
	addk	r3,r5,r6
	rtsd	r15,8
	addk	r3,r3,r7
	.size	add3, .-add3

	.globl	checksum
	.type	checksum, @function
checksum:			# u32 checksum(const unsigned char *p, int n)
	blei	r6,.Lck_zero
	addk	r4,r5,r6
	addk	r3,r0,r0
.Lck_loop:
	lbui	r7,r5,0
	bslli	r8,r3,5
	addk	r3,r8,r3
	addk	r3,r3,r7
	addik	r5,r5,1
	rsubk	r18,r5,r4
	bnei	r18,.Lck_loop
	rtsd	r15,8
	nop
.Lck_zero:
	rtsd	r15,8
	addk	r3,r0,r0
	.size	checksum, .-checksum

	.globl	strlen_local
	.type	strlen_local, @function
strlen_local:
	addk	r3,r0,r0
.Lsl_loop:
	lbu	r4,r5,r3
	bneid	r4,.Lsl_loop
	addik	r3,r3,1
	rtsd	r15,8
	addik	r3,r3,-1
	.size	strlen_local, .-strlen_local

	.globl	classify
	.type	classify, @function
classify:			# switch lowered to a lookup table
	addik	r18,r0,6
	cmpu	r18,r5,r18
	blti	r18,.Lcl_default
	bslli	r5,r5,2
	lwi	r3,r5,CSWTCH
	rtsd	r15,8
	nop
.Lcl_default:
	rtsd	r15,8
	addik	r3,r0,-1
	.size	classify, .-classify

	.globl	add64
	.type	add64, @function
add64:				# u64 add64(u64 a, u64 b) { return a + b + 0x0123456789abcdef; }
				# (big-endian word order: high word in r5/r7/r3; in the LE build the
				# decompiler therefore shows the halves swapped, which is correct)
	add	r4,r6,r8
	addc	r3,r5,r7
	addi	r4,r4,0x89abcdef
	rtsd	r15,8
	addic	r3,r3,0x01234567
	.size	add64, .-add64

	.globl	many_args
	.type	many_args, @function
many_args:			# a - b + c - d + e - f + g * h
	rsubk	r3,r6,r5
	addk	r3,r3,r7
	rsubk	r3,r8,r3
	addk	r3,r3,r9
	rsubk	r3,r10,r3
	lwi	r4,r1,28
	lwi	r11,r1,32
	mul	r4,r4,r11
	rtsd	r15,8
	addk	r3,r3,r4
	.size	many_args, .-many_args

	.globl	uart_puts
	.type	uart_puts, @function
uart_puts:
	lbui	r3,r5,0
	beqid	r3,.Lup_end
	addik	r4,r0,0x40600004
.Lup_loop:
	swi	r3,r4,0
	addik	r5,r5,1
	lbui	r3,r5,0
	bnei	r3,.Lup_loop
.Lup_end:
	rtsd	r15,8
	nop
	.size	uart_puts, .-uart_puts

	.globl	call_chain
	.type	call_chain, @function
call_chain:
	addik	r1,r1,-44
	swi	r15,r1,0
	swi	r19,r1,40
	addk	r19,r5,r0
	addik	r6,r0,1
	brlid	r15,add3
	addik	r7,r0,2
	lwi	r4,r0,global_counter
	addk	r4,r4,r3
	swi	r4,r0,global_counter
	addik	r3,r0,6
	swi	r3,r1,28
	addik	r3,r0,7
	swi	r3,r1,32
	addk	r5,r19,r0
	addik	r6,r0,1
	addik	r7,r0,2
	addik	r8,r0,3
	addik	r9,r0,4
	brlid	r15,many_args
	addik	r10,r0,5
	andi	r5,r19,7
	brlid	r15,classify
	addk	r19,r3,r0
	addk	r3,r19,r3
	lwi	r15,r1,0
	lwi	r19,r1,40
	rtsd	r15,8
	addik	r1,r1,44
	.size	call_chain, .-call_chain

	.globl	main
	.type	main, @function
main:
	addik	r1,r1,-32
	swi	r15,r1,0
	swi	r19,r1,28
	addik	r5,r0,message
	brlid	r15,uart_puts
	nop
	addik	r5,r0,message
	brlid	r15,strlen_local
	nop
	brlid	r15,call_chain
	addk	r5,r3,r0
	addk	r19,r3,r0
	addik	r5,r0,message
	brlid	r15,checksum
	addik	r6,r0,5
	addk	r3,r19,r3
	lwi	r15,r1,0
	lwi	r19,r1,28
	rtsd	r15,8
	addik	r1,r1,32
	.size	main, .-main

	.globl	_start
	.type	_start, @function
_start:
	addik	r1,r0,_stack_top
	brlid	r15,main
	nop
.Lhang:
	bri	.Lhang
	.size	_start, .-_start

	.section .rodata
	.align	2
	.type	CSWTCH, @object
CSWTCH:
	.word	10, 22, 37, 41, 59, 63, 78
	.size	CSWTCH, .-CSWTCH
	.type	message, @object
message:
	.asciz	"hello, microblaze"
	.size	message, .-message

	.bss
	.align	2
	.globl	global_counter
	.type	global_counter, @object
global_counter:
	.space	4
	.size	global_counter, 4
	.align	3
stack:
	.space	1024
_stack_top:
