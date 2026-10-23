#!/usr/bin/env bash
# Download the public real-world MicroBlaze binaries used by test/real-binaries.sh.
# Nothing is committed; the files land in <dest> (default: ./real-samples) and are checked
# against pinned SHA-256 sums.
#
#   test/fetch-real-samples.sh [dest]
#
# Sources (pinned):
#   * AMD/Xilinx soc-prebuilt-firmware, tag xlnx_rel_v2025.2 (commit 7319a74d), MIT-style license.
#     PMU firmware (ZynqMP), PLM and PSM firmware (Versal): gcc-built, little-endian ELF32
#     executables with DWARF. Sources: github.com/Xilinx/embeddedsw lib/sw_apps/{zynqmp_pmufw,
#     versal_plm,versal_psmfw}.
#   * Bootlin toolchain microblazebe--glibc--stable-2025.08-1 (LGPL): big-endian glibc
#     libc.so.6 (PIC, GOT/PLT, dynamic relocations). Only libc.so.6 is extracted from the
#     ~56 MB tarball, which is streamed and not kept.
set -euo pipefail
DEST=${1:-real-samples}
mkdir -p "$DEST"
cd "$DEST"

XSHA=7319a74d19ff09ed470476fd721534d1603f04da
XURL=https://raw.githubusercontent.com/Xilinx/soc-prebuilt-firmware/$XSHA
BURL=https://toolchains.bootlin.com/downloads/releases/toolchains/microblazebe/tarballs/microblazebe--glibc--stable-2025.08-1.tar.xz

fetch() { # url out
	if [[ ! -s $2 ]]; then
		curl -fsSL --retry 3 -o "$2.part" "$1"
		mv "$2.part" "$2"
	fi
}
fetch "$XURL/zcu102-zynqmp/pmufw.elf" zcu102-zynqmp_pmufw.elf
fetch "$XURL/vck190-versal/plmfw.elf" vck190-versal_plmfw.elf
fetch "$XURL/vck190-versal/psmfw.elf" vck190-versal_psmfw.elf
if [[ ! -s libc.so.6 ]]; then
	tmp=$(mktemp -d .bootlin.XXXXXX)
	curl -fsSL --retry 3 "$BURL" | tar -xJ -C "$tmp" --wildcards '*/sysroot/lib/libc.so.6'
	cp "$(find "$tmp" -name libc.so.6 -type f | head -1)" libc.so.6
	rm -rf "$tmp"
fi

sha256sum -c - <<'EOF'
93e0d3b1ba0e3a7266cb05b817bde98c94224274753d2297e6c1dec55f83e73c  zcu102-zynqmp_pmufw.elf
9d881f2ae8a17e62ea0ba110fc093a078a4557b6a99e108ec272c26f1568fa80  vck190-versal_plmfw.elf
ca6b333e60d78d36fed61ff04e5e29efaac38f609bf3a0b67ee4544f100826e6  vck190-versal_psmfw.elf
732fa314d277354dbab942a0cabc86c8e4aaf93ff8d742cfc416869e59a3ff7b  libc.so.6
EOF
