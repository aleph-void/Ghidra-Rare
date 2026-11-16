#!/usr/bin/env bash
# Build real-code samples with the free toolchain for SH4AL-DSP (gcc -m4al, as -isa=sh4al-dsp so
# that the ELF header says EF_SH4AL_DSP): zlib 1.3.1 (its example.c test program), Lua 5.4.7 (the
# stand-alone interpreter) and a small DSP routine in assembly (test/elf/dsp.S), linked statically
# against newlib, big and little endian.  Sources are fetched by URL and SHA-256; nothing is
# committed.  (After aleph-void/ghidra-sh test/build-samples.sh, MIT.)
#   SH_TOOLS=<sh-elf bin dir> test/build-samples.sh <workdir>
# Output: <workdir>/elf/{zlib,lua}_{be,le}.elf
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "$1"); mkdir -p "$W/src" "$W/elf"
CC=${SH_TOOLS:-$HOME/.cache/ghidra-rare-scratch/tools/x-sh-elf/bin}/sh-elf-gcc
fetch() {   # <url> <sha256> <file>
	if [[ ! -f $W/src/$3 ]] || ! echo "$2  $W/src/$3" | sha256sum -c --status; then
		curl -fsSL -o "$W/src/$3.part" "$1"
		echo "$2  $W/src/$3.part" | sha256sum -c --status || { echo "SHA-256 mismatch: $3" >&2; exit 1; }
		mv "$W/src/$3.part" "$W/src/$3"
	fi
}
fetch https://github.com/madler/zlib/releases/download/v1.3.1/zlib-1.3.1.tar.gz \
	9a93b2b7dfdac77ceba5a558a580e74667dd6fede4585b91eefb60f03b72df23 zlib-1.3.1.tar.gz
fetch https://www.lua.org/ftp/lua-5.4.7.tar.gz \
	9fbf5e28ef86c69858f6d3d34eccc32e911c1a28b4120ff3e84aaa70cfbf1e30 lua-5.4.7.tar.gz
[[ -d $W/src/zlib-1.3.1 ]] || tar -xzf "$W/src/zlib-1.3.1.tar.gz" -C "$W/src"
[[ -d $W/src/lua-5.4.7 ]] || tar -xzf "$W/src/lua-5.4.7.tar.gz" -C "$W/src"
ZSRC="adler32 compress crc32 deflate gzclose gzlib gzread gzwrite infback inffast inflate inftrees trees uncompr zutil"
LSRC="lapi lcode lctype ldebug ldo ldump lfunc lgc llex lmem lobject lopcodes lparser lstate lstring ltable ltm lundump lvm lzio lauxlib lbaselib lcorolib ldblib liolib lmathlib loadlib loslib lstrlib ltablib lutf8lib linit lua"
for v in "be -mb" "le -ml"; do
	set -- $v; n=$1; shift
	F=(-m4al "$@" -Wa,-isa=sh4al-dsp)
	"$CC" "${F[@]}" -c "$HERE/elf/start.S" -o "$W/elf/start_$n.o"
	"$CC" "${F[@]}" -c "$HERE/elf/dsp.S" -o "$W/elf/dsp_$n.o"
	zo=(); for f in $ZSRC; do
		"$CC" "${F[@]}" -O2 -DHAVE_UNISTD_H -c "$W/src/zlib-1.3.1/$f.c" -o "$W/elf/z_${n}_$f.o"; zo+=("$W/elf/z_${n}_$f.o"); done
	"$CC" "${F[@]}" -O2 -c "$W/src/zlib-1.3.1/test/example.c" -I"$W/src/zlib-1.3.1" -o "$W/elf/z_${n}_example.o"
	"$CC" "${F[@]}" -specs=nosys.specs -nostartfiles -Wl,-e,_start -o "$W/elf/zlib_$n.elf" \
		"$W/elf/start_$n.o" "$W/elf/z_${n}_example.o" "${zo[@]}" "$W/elf/dsp_$n.o" -lm
	lo=(); for f in $LSRC; do
		"$CC" "${F[@]}" -O2 -DLUA_32BITS -DLUA_USE_C89 -c "$W/src/lua-5.4.7/src/$f.c" -o "$W/elf/l_${n}_$f.o"; lo+=("$W/elf/l_${n}_$f.o"); done
	"$CC" "${F[@]}" -specs=nosys.specs -nostartfiles -Wl,-e,_start -o "$W/elf/lua_$n.elf" \
		"$W/elf/start_$n.o" "${lo[@]}" "$W/elf/dsp_$n.o" -lm
	rm -f "$W"/elf/[zl]_${n}_*.o "$W/elf/start_$n.o" "$W/elf/dsp_$n.o"
	echo "built $n"
done
ls -l "$W"/elf/*.elf
