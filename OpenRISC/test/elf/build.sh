#!/usr/bin/env bash
# Rebuild the committed test ELFs with the Bootlin openrisc--glibc--stable-2025.08-1 toolchain
# (gcc 14.3.0, binutils): or1ktest.o (relocatable, for the relocation handler) and or1ktest.elf
# (linked at 0x2000 with libgcc, for import/decompile checks).
# relocs.o is relocs.s assembled (relocation-type coverage).
#   test/elf/build.sh <toolchain bin dir>
set -euo pipefail
B=${1:?usage: build.sh <bootlin toolchain bin dir>}
P=$B/or1k-buildroot-linux-gnu-
cd "$(dirname "$0")"
FLAGS="-O2 -g -fdebug-prefix-map=$PWD=. -ffreestanding -fno-pic -mhard-float -mdouble-float -mcmov -msext -mror -mrori -msfimm -mshftimm -mhard-div -mhard-mul"
"${P}gcc" $FLAGS -c or1ktest.c -o or1ktest.o
"${P}gcc" $FLAGS -static -nostdlib -e _start -Wl,-Ttext=0x2000 or1ktest.o -lgcc -o or1ktest.elf
"${P}as" relocs.s -o relocs.o
