PROJECT=91-newlib
SRC_C = main.c
# built in the R5F100SLAFB tree: its 512 KB linker script has room for the newlib code
include ../common/Makefile.mk
# RL78-S3 code (multiply/divide instructions)
CFLAGS  := $(subst -mcpu=g13,-mcpu=g14,$(CFLAGS))
LDFLAGS := $(subst -mcpu=g13,-mcpu=g14,$(LDFLAGS))
