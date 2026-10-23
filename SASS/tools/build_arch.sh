#!/usr/bin/env bash
# Learn + generate one 128-bit variant.
#   tools/build_arch.sh <ARCH> <corpus.txt> [init-spec.json] [rounds]
# Needs nvdisasm (see test/nvd.py).  Writes spec/<ARCH>.json and
# data/languages/sass_<ARCH>.sinc.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ARCH=$1; CORPUS=$2; INIT=${3:-}; ROUNDS=${4:-10}
cd "$HERE"
args=(--corpus "$CORPUS" --rounds "$ROUNDS" --max-new 500 --jobs ${JOBS:-8})
[[ -n $INIT ]] && args+=(--init "$INIT")
[[ -f ../spec/$ARCH.json ]] && args+=(--resume)
python3 build_spec.py "$ARCH" "${args[@]}"
python3 evidence.py "$ARCH" "../spec/$ARCH.json" "$CORPUS"
python3 gen_sleigh.py "../spec/$ARCH.json" "../data/languages/sass_$ARCH.sinc"
