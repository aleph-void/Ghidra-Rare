# Small 64-bit MicroBlaze (C_DATA_SIZE=64) test object, assembled with the AMD/Xilinx gas -m64.
# Only relocatable output is produced (the scratch ld has no elf64 MicroBlaze emulation), which is
# enough for the Ghidra ELF64 import / decompile check.

	.text
	.globl	addl3
	.type	addl3, @function
addl3:				# long addl3(long a, long b, long c)
	addlk	r3,r5,r6
	rtsd	r15,8
	addlk	r3,r3,r7
	.size	addl3, .-addl3

	.globl	sum_array
	.type	sum_array, @function
sum_array:			# long sum_array(const long *p, long n)
	addlk	r3,r0,r0
	beaeqi	r6,.Lsa_done
	addlk	r4,r0,r0
.Lsa_loop:
	ll	r7,r5,r4
	addlk	r3,r3,r7
	addlik	r4,r4,8
	addlik	r6,r6,-1
	beanei	r6,.Lsa_loop
.Lsa_done:
	rtsd	r15,8
	nop
	.size	sum_array, .-sum_array

	.globl	shift_mix
	.type	shift_mix, @function
shift_mix:			# long shift_mix(long a, long s) { return (a << s) ^ (a >> 7); }
	bslll	r3,r5,r6
	bslrai	r4,r5,7
	rtsd	r15,8
	xorl	r3,r3,r4
	.size	shift_mix, .-shift_mix

	.globl	big_const
	.type	big_const, @function
big_const:			# long big_const(long a) { return a + 0x123456789abc; }
	addlik	r3,r5,0x123456789abc
	rtsd	r15,8
	nop
	.size	big_const, .-big_const

	.globl	caller
	.type	caller, @function
caller:				# long caller(long x) { return addl3(x, 1, 2) + shift_mix(x, 3); }
	# (addlik expands to "imml; addik", so it must never sit in a delay slot)
	addlik	r1,r1,-48
	sl	r15,r1,r0
	addlik	r18,r1,8
	sl	r19,r18,r0
	addlk	r19,r5,r0
	addlik	r6,r0,1
	addlik	r7,r0,2
	brlid	r15,addl3
	nop
	addlik	r6,r0,3
	addlk	r5,r19,r0
	brlid	r15,shift_mix
	addlk	r19,r3,r0
	addlk	r3,r19,r3
	ll	r15,r1,r0
	addlik	r18,r1,8
	ll	r19,r18,r0
	addlik	r1,r1,48
	rtsd	r15,8
	nop
	.size	caller, .-caller
