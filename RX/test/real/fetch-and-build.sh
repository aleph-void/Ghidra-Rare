#!/usr/bin/env bash
# Build the real-code test binaries:  test/real/fetch-and-build.sh <workdir>
# RX_TC = rx-elf toolchain prefix (test/real/build-toolchain.sh), default
# ~/.cache/ghidra-rare-scratch/tools/x-rx-elf. Nothing built here is committed.
#   tour_*.elf     test/real/src/tour.c with newlib (libc + libm) in four configurations
#   zlib_*.elf     zlib 1.3.1 example.c / minigzip.c (pinned tarball, SHA-256 checked)
#   zlib_obj/*.o   zlib library objects (relocatable ELF: relocation handler check)
#   asm_v2.elf     RXv2 routines (src/dsp_v2.s, gas -mcpu=rxv2) called from C
#   asm_v3.elf     RXv2 + RXv3 routines (src/dfpu_v3.s, gas -mcpu=rxv3-dfpu)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "$1"); TC=${RX_TC:-$HOME/.cache/ghidra-rare-scratch/tools/x-rx-elf}
CC=$TC/bin/rx-elf-gcc AS=$TC/bin/rx-elf-as
mkdir -p "$W/bin" "$W/src" "$W/obj"
cd "$W/src"
f=zlib-1.3.1.tar.gz
[[ -f $f ]] || curl -fsSL -o $f https://github.com/madler/zlib/releases/download/v1.3.1/zlib-1.3.1.tar.gz
echo "9a93b2b7dfdac77ceba5a558a580e74667dd6fede4585b91eefb60f03b72df23  $f" | sha256sum -c --quiet
[[ -d zlib-1.3.1 ]] || tar xzf $f
S=$HERE/src B=$W/bin O=$W/obj
cfg() {   # name flags...
	local n=$1; shift
	"$CC" "$@" -g -o "$B/tour_$n.elf" "$S/tour.c" -lm
}
cfg rx610_O2 -mcpu=rx610 -O2
cfg rx200_Os -mcpu=rx200 -Os -mnofpu
cfg rx610_d64 -mcpu=rx610 -O2 -m64bit-doubles
cfg rx600_O1 -mcpu=rx600 -O1   # -O0 -g hits a GCC 14 ICE (dwarf2cfi) in poly()
Z=zlib-1.3.1
mkdir -p "$O/zlib"
for c in adler32 crc32 deflate infback inffast inflate inftrees trees zutil compress uncompr gzclose gzlib gzread gzwrite; do
	"$CC" -mcpu=rx610 -O2 -g -DHAVE_UNISTD_H -c "$Z/$c.c" -o "$O/zlib/$c.o"
done
"$CC" -mcpu=rx610 -O2 -g -o "$B/zlib_example.elf" -I"$Z" "$Z/test/example.c" "$O"/zlib/*.o
"$CC" -mcpu=rx610 -O2 -g -o "$B/zlib_minigzip.elf" -I"$Z" "$Z/test/minigzip.c" "$O"/zlib/*.o
"$AS" -mcpu=rxv2 -o "$O/dsp_v2.o" "$S/dsp_v2.s"
"$AS" -mcpu=rxv3-dfpu -o "$O/dfpu_v3.o" "$S/dfpu_v3.s"
"$CC" -mcpu=rx610 -O2 -c -o "$O/m2.o" "$S/main_asm.c"
"$CC" -mcpu=rx610 -O2 -DV3 -c -o "$O/m3.o" "$S/main_asm.c"
"$CC" -o "$B/asm_v2.elf" "$O/m2.o" "$O/dsp_v2.o"
"$CC" -o "$B/asm_v3.elf" "$O/m3.o" "$O/dsp_v2.o" "$O/dfpu_v3.o"
mkdir -p "$B/obj"
cp "$O"/zlib/{deflate,inflate,trees}.o "$O/dfpu_v3.o" "$O/dsp_v2.o" "$B/obj/"
ls "$B"/*.elf "$B"/obj/*.o
