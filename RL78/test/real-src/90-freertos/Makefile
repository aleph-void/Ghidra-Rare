PROJECT=90-freertos
FRK ?= ../../frk
SRC_C = main.c ../common/option_bytes.c $(FRK)/tasks.c $(FRK)/queue.c $(FRK)/list.c \
	$(FRK)/portable/GCC/RL78/port.c $(FRK)/portable/MemMang/heap_1.c
SRC_S = $(FRK)/portable/GCC/RL78/portasm.S
include ../common/Makefile.mk
INCLUDE += -I$(FRK)/include -I$(FRK)/portable/GCC/RL78
CFLAGS  := $(subst -mcpu=g13,-mcpu=g14,$(CFLAGS)) -I$(FRK)/include -I$(FRK)/portable/GCC/RL78
ASFLAGS += -I$(FRK)/portable/GCC/RL78 -I. -I$(FRK)/include -I../common -mcpu=g14
LDFLAGS := $(subst -mcpu=g13,-mcpu=g14,$(LDFLAGS)) -Wl,--defsym=_stack=__stack
