#!/usr/bin/env bash
# Build a GNU rx-elf toolchain (binutils 2.45, GCC 14.3.0 C only, newlib 4.5.0.20241231) from
# pinned GNU/sourceware tarballs:  test/real/build-toolchain.sh <workdir> <prefix>
# GCC 14 targets RXv1 CPUs only (-mcpu=rx100/rx200/rx600/rx610); gas also assembles RXv2/RXv3
# (-mcpu=rxv2 / rxv3 / rxv3-dfpu). Takes about 20 minutes with 12 jobs and ~6 GB of build space.
set -euo pipefail
W=$(readlink -m "$1"); P=$(readlink -m "$2"); J=${JOBS:-12}
mkdir -p "$W" && cd "$W"
fetch() {   # url sha256
	local f=${1##*/}
	[[ -f $f ]] || curl -fsSLO "$1"
	echo "$2  $f" | sha256sum -c --quiet
}
fetch https://ftp.gnu.org/gnu/binutils/binutils-2.45.tar.xz c50c0e7f9cb188980e2cc97e4537626b1672441815587f1eab69d2a1bfbef5d2
fetch https://ftp.gnu.org/gnu/gcc/gcc-14.3.0/gcc-14.3.0.tar.xz e0dc77297625631ac8e50fa92fffefe899a4eb702592da5c32ef04e2293aca3a
fetch https://sourceware.org/pub/newlib/newlib-4.5.0.20241231.tar.gz 33f12605e0054965996c25c1382b3e463b0af91799001f5bb8c0630f2ec8c852
for t in binutils-2.45.tar.xz gcc-14.3.0.tar.xz newlib-4.5.0.20241231.tar.gz; do
	[[ -d ${t%.tar.*} ]] || tar xf "$t"
done
export PATH=$P/bin:$PATH
mkdir -p b-bu b-gcc b-nl
(cd b-bu && ../binutils-2.45/configure --target=rx-elf --prefix="$P" --disable-nls --disable-werror \
	--disable-gdb --disable-sim --disable-gprofng >/dev/null && make -j"$J" MAKEINFO=true >/dev/null \
	&& make install MAKEINFO=true >/dev/null)
(cd b-gcc && ../gcc-14.3.0/configure --target=rx-elf --prefix="$P" --enable-languages=c --with-newlib \
	--disable-nls --disable-libssp --disable-shared --disable-threads --disable-libquadmath \
	--disable-werror >/dev/null && make -j"$J" MAKEINFO=true >/dev/null && make install MAKEINFO=true >/dev/null)
(cd b-nl && ../newlib-4.5.0.20241231/configure --target=rx-elf --prefix="$P" --disable-nls >/dev/null \
	&& make -j"$J" MAKEINFO=true >/dev/null && make install MAKEINFO=true >/dev/null)
echo "toolchain in $P/bin"
