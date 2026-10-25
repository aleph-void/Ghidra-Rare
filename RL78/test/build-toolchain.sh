#!/usr/bin/env bash
# Build the GNU RL78 toolchain the tests use: binutils 2.45 (rl78-elf-as/ld/objdump),
# GCC 14.3.0 (C only) and newlib 4.5.0, from pinned upstream tarballs.
#   test/build-toolchain.sh <workdir> <prefix>
# Afterwards put <prefix>/bin on PATH. Needs a host C/C++ compiler, make, curl; GCC's
# prerequisites (gmp, mpfr, mpc, isl) are downloaded in-tree by contrib/download_prerequisites.
set -euo pipefail
W=$(mkdir -p "$1" && cd "$1" && pwd)
P=$(mkdir -p "$2" && cd "$2" && pwd)
J=${JOBS:-$(nproc)}
fetch() { # url sha256
	local f=$W/$(basename "$1")
	[[ -f $f ]] || curl -fsSL -o "$f" "$1"
	echo "$2  $f" | sha256sum -c --quiet
}
fetch https://ftp.gnu.org/gnu/binutils/binutils-2.45.tar.xz c50c0e7f9cb188980e2cc97e4537626b1672441815587f1eab69d2a1bfbef5d2
fetch https://ftp.gnu.org/gnu/gcc/gcc-14.3.0/gcc-14.3.0.tar.xz e0dc77297625631ac8e50fa92fffefe899a4eb702592da5c32ef04e2293aca3a
fetch https://sourceware.org/pub/newlib/newlib-4.5.0.20241231.tar.gz 33f12605e0054965996c25c1382b3e463b0af91799001f5bb8c0630f2ec8c852
cd "$W"
[[ -d binutils-2.45 ]] || tar xf binutils-2.45.tar.xz
[[ -d gcc-14.3.0 ]] || { tar xf gcc-14.3.0.tar.xz; (cd gcc-14.3.0 && ./contrib/download_prerequisites); }
[[ -d newlib-4.5.0.20241231 ]] || tar xf newlib-4.5.0.20241231.tar.gz
ln -sfn ../newlib-4.5.0.20241231/newlib gcc-14.3.0/newlib
ln -sfn ../newlib-4.5.0.20241231/libgloss gcc-14.3.0/libgloss
mkdir -p build-binutils build-gcc
(cd build-binutils && ../binutils-2.45/configure --target=rl78-elf --prefix="$P" --disable-nls \
	--disable-werror --disable-gdb --disable-sim --disable-gprofng && make -j"$J" && make install)
export PATH=$P/bin:$PATH
(cd build-gcc && ../gcc-14.3.0/configure --target=rl78-elf --prefix="$P" --enable-languages=c \
	--with-newlib --disable-nls --disable-libssp --disable-shared --disable-threads \
	--disable-libquadmath --disable-werror && make -j"$J" MAKEINFO=true && make install MAKEINFO=true)
echo "toolchain in $P/bin"
