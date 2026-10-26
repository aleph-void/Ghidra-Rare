/* Bare-metal link map for the i860 test programs. */
ENTRY(_start)
SECTIONS
{
	. = 0x10000;
	.text : { *(.text .text.*) }
	. = ALIGN(16);
	.rodata : { *(.rodata .rodata.*) }
	. = ALIGN(16);
	.data : { *(.data .data.*) }
	. = ALIGN(16);
	__bss_start = .;
	.bss : { *(.bss .bss.* COMMON) }
	. = ALIGN(16);
	_end = .;
	. += 0x40000;
	__stack_top = .;
}
