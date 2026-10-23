#!/usr/bin/env bash
# Build demo.c into a C7x ELF executable with TI C7000 CGT.  build.sh SIL OUTDIR
set -euo pipefail
SIL=${1:-7100}; OUT=${2:?outdir}
CGT=${C7X_CGT:-/tmp/claude-1000/-home-nick-Documents-git-Ghidra-Rare/738fc310-bd10-40da-87e5-b0a8be585382/scratchpad/tools/ti/inst/ti-cgt-c7000_5.0.2.LTS}
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"; cd "$OUT"
"$CGT/bin/cl7x" -mv$SIL -O2 -I"$CGT/include" "$HERE/demo.c" -z -o demo$SIL.out -m demo$SIL.map \
    -i"$CGT/lib" -lrts${SIL}_le.lib >/dev/null
"$CGT/bin/cl7x" -mv$SIL -O2 -I"$CGT/include" -c "$HERE/demo.c" -fe demo$SIL.obj >/dev/null
"$CGT/bin/dis7x" -i demo$SIL.obj > demo$SIL.dis 2>/dev/null || true
echo "$OUT/demo$SIL.out"
