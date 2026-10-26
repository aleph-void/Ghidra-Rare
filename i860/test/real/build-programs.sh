#!/usr/bin/env bash
# Build the real-code test programs with the GCC 4.0.4 / binutils 2.30 i860 toolchain
# (test/real/build-toolchain.sh) inside its i386 Debian 5 container:
#   test/real/build-programs.sh <workdir>
# <workdir>/tc/inst32 holds the toolchain, <workdir>/real/src the sources fetched by
# test/real/fetch-sources.sh. Output: <workdir>/real/bin/*.elf (bare-metal ELF executables
# linked at 0x10000 with test/real/rt: crt0, a tiny libc and libm written for this module).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -f "$1")
mkdir -p "$W/real/bin" "$W/real/obj"
docker run --rm --platform linux/386 -u "$(id -u):$(id -g)" -v "$W:/w" -v "$HERE:/m:ro" \
	i860-lenny-build bash /m/build-in-container.sh
ls "$W/real/bin"
