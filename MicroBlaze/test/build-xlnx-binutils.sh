#!/usr/bin/env bash
# Build the AMD/Xilinx-patched GNU binutils 2.42 (the 64-bit MicroBlaze reference: upstream
# binutils has no 64-bit MicroBlaze) from GNU binutils 2.42 + the meta-xilinx rel-v2025.1
# binutils patch series (gdb/sim hunks dropped).
#   test/build-xlnx-binutils.sh <workdir>
# Produces <workdir>/build/{gas/as-new,binutils/objdump,binutils/objcopy} and
# <workdir>/build-ld/ld/ld-new. Needs curl, filterdiff (patchutils), a host C compiler.
set -euo pipefail
W=$(mkdir -p "$1" && cd "$1" && pwd)
MX=https://raw.githubusercontent.com/Xilinx/meta-xilinx/rel-v2025.1/meta-microblaze/recipes-devtools/binutils
mkdir -p "$W/patches" && cd "$W/patches"
curl -sSf "$MX/binutils-microblaze.inc" | grep -o '[0-9]\{4\}-[^ ]*\.patch' > list.txt
for p in $(cat list.txt); do [[ -s $p ]] || curl -sSf -o "$p" "$MX/binutils/$p"; done
cd "$W"
if [[ ! -d binutils-2.42 ]]; then
	curl -sSf -o binutils-2.42.tar.xz https://ftp.gnu.org/gnu/binutils/binutils-2.42.tar.xz
	tar xf binutils-2.42.tar.xz && rm binutils-2.42.tar.xz
	cd binutils-2.42
	for p in $(cat ../patches/list.txt); do
		filterdiff -p1 -x 'gdb/*' -x 'gdbserver/*' -x 'gdbsupport/*' -x 'sim/*' "../patches/$p" > ../cur.patch
		[[ -s ../cur.patch ]] && patch -p1 -N --no-backup-if-mismatch < ../cur.patch > /dev/null || true
	done
	# the patched disassembler declares get_field_imm16 without a return type
	sed -i 's/^get_field_imm16/static char *\nget_field_imm16/' opcodes/microblaze-dis.c
	cd "$W"
fi
# GCC 14/15 reject some old-style C in the patched sources; relax it
CF="-O2 -g -std=gnu11 -Wno-incompatible-pointer-types -Wno-int-conversion -Wno-implicit-function-declaration -Wno-implicit-int"
mkdir -p build && cd build
[[ -f Makefile ]] || ../binutils-2.42/configure --target=microblaze-xilinx-elf --enable-64-bit-bfd \
	--disable-nls --disable-werror --disable-gdb --disable-sim --disable-gprofng --disable-ld --disable-gold > cfg.log
make -j"$(nproc)" MAKEINFO=true CFLAGS="$CF" all-binutils all-gas > make.log 2>&1
cd "$W" && mkdir -p build-ld && cd build-ld
[[ -f Makefile ]] || ../binutils-2.42/configure --target=microblaze-xilinx-elf --disable-nls --disable-werror \
	--disable-gdb --disable-sim --disable-gprofng --disable-gold --disable-gas --disable-binutils > cfg.log
make -j"$(nproc)" MAKEINFO=true CFLAGS="$CF" all-ld > make.log 2>&1
ls -la "$W/build/gas/as-new" "$W/build/binutils/objdump" "$W/build-ld/ld/ld-new"
