#!/usr/bin/env bash
# Download the public real-world Alpha binaries used by test/real-binaries.sh. Nothing is
# committed; the files land in <dest> (default: ./real-samples), checked against pinned SHA-256.
#
#   test/fetch-real-samples.sh [dest]
#
# Sources: Debian ports (alpha), unstable as of 2026-10-25. The .deb files are fetched from
# deb.debian.org/debian-ports and, once they leave the pool, from snapshot.debian.org.
#   glibc 2.43-5      libc6.1        LGPL-2.1+   lib/alpha-linux-gnu/libc.so.6.1
#   zlib 1.3.2-3      zlib1g         Zlib        usr/lib/alpha-linux-gnu/libz.so.1.3.2
#   coreutils 9.10-1  coreutils      GPL-3+      usr/bin/ls, usr/bin/sort
#   busybox 1.38.0-3  busybox-static GPL-2       usr/bin/busybox (static)
# and QEMU's EV6 PALcode for the emulated Clipper board (qemu-palcode, GPL-2.0+), shipped as
# pc-bios/palcode-clipper in the QEMU source tree, tag v10.1.0: PALcode-only HW_* instructions.
set -euo pipefail
DEST=${1:-real-samples}
mkdir -p "$DEST"
cd "$DEST"
POOL=https://deb.debian.org/debian-ports
SNAP=https://snapshot.debian.org/archive/debian-ports/20261025T000000Z

debs=(
"pool-alpha/main/g/glibc/libc6.1_2.43-5_alpha.deb f7e86fdd3574eb4657b5d911852da50726a539f292bba7aabead2c52d857ef01"
"pool-alpha/main/z/zlib/zlib1g_1.3.dfsg+really1.3.2-3_alpha.deb 514b177dc3ca4dd8eb79d8fe1788e5470147f5c6ad2639217f90b66cad64b99c"
"pool-alpha/main/c/coreutils/coreutils_9.10-1_alpha.deb 9c2ecf6277f9da4f5e80dafc78430e7f051de34063a5b168c208a65e0267464d"
"pool-alpha/main/b/busybox/busybox-static_1.38.0-3_alpha.deb 8f8a4f49d2bead4b7f9551db8619d11203b867165f6f7396c233f5ed9a48a177"
)
for e in "${debs[@]}"; do
	set -- $e
	f=$(basename "$1")
	if [[ ! -s $f ]]; then
		curl -fsSL --retry 3 -o "$f.part" "$POOL/$1" || curl -fsSL --retry 3 -o "$f.part" "$SNAP/$1"
		mv "$f.part" "$f"
	fi
	echo "$2  $f" | sha256sum -c -
done
extract() { # deb member out
	local t
	t=$(mktemp -d .x.XXXXXX)
	(cd "$t" && ar x "../$1" && tar xf data.tar.* "./$2")
	cp "$t/$2" "$3"
	rm -rf "$t"
}
if [[ ! -s palcode-clipper ]]; then
	curl -fsSL --retry 3 -o palcode-clipper.part \
		https://raw.githubusercontent.com/qemu/qemu/v10.1.0/pc-bios/palcode-clipper
	mv palcode-clipper.part palcode-clipper
fi
[[ -s libc.so.6.1 ]] || extract libc6.1_2.43-5_alpha.deb usr/lib/alpha-linux-gnu/libc.so.6.1 libc.so.6.1
[[ -s libz.so.1.3.2 ]] || extract zlib1g_1.3.dfsg+really1.3.2-3_alpha.deb usr/lib/alpha-linux-gnu/libz.so.1.3.2 libz.so.1.3.2
[[ -s ls ]] || extract coreutils_9.10-1_alpha.deb usr/bin/ls ls
[[ -s sort ]] || extract coreutils_9.10-1_alpha.deb usr/bin/sort sort
[[ -s busybox ]] || extract busybox-static_1.38.0-3_alpha.deb usr/bin/busybox busybox
sha256sum -c - <<'SUMS'
d593d519089267cf118311baf2884f10898459a98274f7e61031bad1419dcd33  libc.so.6.1
cc1e8fea87b13de40aa54de6c474772538dc5c54ca6c1f85d39b18c059341a9d  libz.so.1.3.2
33733e3854267b30b42a735f10fe635b2f0dd08fa3291709b7aa411c90570155  ls
715c3222feaf30be15b4188c54ee446a5cd026a69baea1aaa67cf3bced4b3f00  sort
cf79d06bf4faf0d89b5360bb98552b0c5e91f908f454b0ee14be6b83344d9e58  busybox
9f8da7264c7438fe4a24a2215e81893586f5cfafcd6e5fd0059fccc31a4e8839  palcode-clipper
SUMS
