#!/usr/bin/env bash
# Download the public real-world OpenRISC binaries used by test/real-binaries.sh. Nothing is
# committed; the files land in <dest> (default: ./real-samples) and are checked against pinned
# SHA-256 sums.
#
#   test/fetch-real-samples.sh [dest] [--keep-toolchain]
#
# Source (pinned): Bootlin toolchain openrisc--glibc--stable-2025.08-1 (gcc 14.3.0, glibc,
# big-endian or1k with delay slots; glibc is LGPL-2.1+, ldconfig GPL-2.0+). From its sysroot:
#   libc.so.6, libm.so.6, ld-linux-or1k.so.1  shared objects (PIC, GOT/PLT, dynamic relocations)
#   ldconfig                                  static executable (glibc linked in)
# The ~76 MB tarball is streamed and only these files are kept, unless --keep-toolchain is
# given (the toolchain's gcc/as/ld also rebuild test/elf and run the relocation check).
#
# Also: QEMU Advent Calendar 2018 day 20 ("Old games on OpenRISC", GPL-2.0, sources at
# qemu-advent-calendar.org/2018/download/src/): vmlinux, a Linux kernel for qemu-system-or1k
# (ELF32 big endian, built with an older gcc, with an initramfs). Kept as vmlinux-or1k.
set -euo pipefail
DEST=${1:-real-samples}
KEEP=${2:-}
URL=https://toolchains.bootlin.com/downloads/releases/toolchains/openrisc/tarballs/openrisc--glibc--stable-2025.08-1.tar.xz
TSHA=03b6e025b372970d4daf6879900b19df6fe23c9feb2c130c6743f36a48cb7d70
mkdir -p "$DEST"
cd "$DEST"
if [[ $KEEP == --keep-toolchain ]]; then
	if [[ ! -d openrisc--glibc--stable-2025.08-1 ]]; then
		curl -fsSL --retry 3 -o toolchain.tar.xz "$URL"
		echo "$TSHA  toolchain.tar.xz" | sha256sum -c -
		tar -xJf toolchain.tar.xz
		rm toolchain.tar.xz
	fi
	S=openrisc--glibc--stable-2025.08-1/or1k-buildroot-linux-gnu/sysroot
	cp $S/lib/libc.so.6 $S/lib/libm.so.6 $S/lib/ld-linux-or1k.so.1 $S/sbin/ldconfig .
elif [[ ! -s libc.so.6 || ! -s libm.so.6 || ! -s ld-linux-or1k.so.1 || ! -s ldconfig ]]; then
	tmp=$(mktemp -d .bootlin.XXXXXX)
	curl -fsSL --retry 3 "$URL" | tar -xJ -C "$tmp" --wildcards \
		'*/sysroot/lib/libc.so.6' '*/sysroot/lib/libm.so.6' '*/sysroot/lib/ld-linux-or1k.so.1' \
		'*/sysroot/sbin/ldconfig'
	for f in libc.so.6 libm.so.6 ld-linux-or1k.so.1 ldconfig; do
		cp "$(find "$tmp" -name "$f" -type f | head -1)" "$f"
	done
	rm -rf "$tmp"
fi

if [[ ! -s vmlinux-or1k ]]; then
	tmp=$(mktemp -d .advcal.XXXXXX)
	curl -fsSL --retry 3 -o "$tmp/day20.tar.xz" \
		https://qemu-advcal.gitlab.io/qac-best-of-multiarch/download/day20.tar.xz
	echo "ff9d7dd7c6bdba325bd85ee85c02db61ff653e129558aeffe6aff55bffb6763a  $tmp/day20.tar.xz" |
		sha256sum -c -
	tar -xJf "$tmp/day20.tar.xz" -C "$tmp" day20/vmlinux
	mv "$tmp/day20/vmlinux" vmlinux-or1k
	rm -rf "$tmp"
fi

sha256sum -c - <<'EOF2'
b67e880e86a3f8d7d9e05dc28ae184bdd96bb2f84d8720ea606982df7f8e3513  vmlinux-or1k
829b69fd845b28bfcbf3bc41ab9a1146a6cea254540daa2f595c75945981ef01  libc.so.6
c949dde039e2d2bb5f0b0ef80e0441a096f2ab086fb7bea4b4cbe64c05b53fbd  libm.so.6
22892710cb53d331433be604fc4cdefa6dd740b6eb0cef8f0ced3c64dbfd6818  ld-linux-or1k.so.1
687870f233e89d3c36236f13e8d381ee95a57b002907e97d649cd3b394910c84  ldconfig
EOF2
