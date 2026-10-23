#!/usr/bin/env bash
# Rebuild the committed test ELFs from the hand-written assembly with the AMD/Xilinx-patched
# binutils (build-xlnx-binutils.sh). No MicroBlaze C compiler is needed.
#   test/elf/build.sh [xilinx-binutils-build-dir] [xilinx-ld-build-dir]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
S=${S:-/tmp/claude-1000/-home-nick-Documents-git-Ghidra-Rare/738fc310-bd10-40da-87e5-b0a8be585382/scratchpad}
XBU=${1:-${XBU:-$S/work/microblaze/xlnx/build}}
XLD=${2:-${XLD:-$S/work/microblaze/xlnx/build-ld}}
AS=$XBU/gas/as-new LD=$XLD/ld/ld-new
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
"$AS" -mbig-endian "$HERE/mbtest.s" -o "$T/be.o"
"$LD" -m elf32microblaze -e _start -Ttext 0x1000 "$T/be.o" -o "$HERE/mbtest_be.elf"
"$AS" -mlittle-endian "$HERE/mbtest.s" -o "$T/le.o"
"$LD" -m elf32microblazeel -e _start -Ttext 0x1000 "$T/le.o" -o "$HERE/mbtest_le.elf"
# 64-bit: relocatable object only (ld has no elf64 MicroBlaze emulation in this build);
# Xilinx gas -m64 always emits little-endian ELF64.
"$AS" -m64 -mlittle-endian "$HERE/mbtest64.s" -o "$HERE/mbtest64_le.o"
ls -la "$HERE"/mbtest_*.elf "$HERE"/mbtest64_le.o
