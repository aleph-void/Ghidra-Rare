#!/usr/bin/env bash
# Build the module's own C test program with GCC 14 cross compilers (C only, freestanding) and
# GNU binutils: ia64-linux-gnu objects and a static executable, and ia64-hp-hpux11.23 objects
# (ILP32 and LP64, big-endian). Only the generated files go to <outdir>; nothing is committed.
#   build-own.sh <outdir>      (IA64_TOOLS = prefix holding x-ia64-linux-gnu, x-ia64-hp-hpux11.23)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
O=$(readlink -m "${1:?usage: build-own.sh <outdir>}")
T=${IA64_TOOLS:-$HOME/.cache/ghidra-rare-scratch/tools}
L=$T/x-ia64-linux-gnu/bin/ia64-linux-gnu
H=$T/x-ia64-hp-hpux11.23/bin/ia64-hp-hpux11.23
mkdir -p "$O"
CF="-O2 -g -ffreestanding -fno-builtin -fno-stack-protector -minline-int-divide-max-throughput -minline-float-divide-max-throughput"
"$L-gcc" $CF -c "$HERE/src/prog.c" -o "$O/prog-linux.o"
"$L-gcc" $CF -fPIC -c "$HERE/src/prog.c" -o "$O/prog-linux-pic.o"
"$L-ld" -static -e entry -o "$O/prog-linux.exe" "$O/prog-linux.o"
"$L-ld" -shared -o "$O/prog-linux.so" "$O/prog-linux-pic.o"
if [[ -x "$H-gcc" ]]; then
	"$H-gcc" $CF -c "$HERE/src/prog.c" -o "$O/prog-hpux32.o"
	"$H-gcc" $CF -mlp64 -c "$HERE/src/prog.c" -o "$O/prog-hpux64.o"
fi
ls -la "$O"
