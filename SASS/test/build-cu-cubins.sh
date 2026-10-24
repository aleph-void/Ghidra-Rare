#!/usr/bin/env bash
# Build test cubins from test/cuda/kernels.cu for every SM generation:
# clang (CUDA device-only, no NVIDIA headers/libdevice) -> PTX -> ptxas -> cubin.
#
#   test/build-cu-cubins.sh <outdir> [sm ...]       (default: all SMs below)
#
# ptxas: CUDA 11.8 for sm_35, 12.9 for sm_50..72, 13.x for sm_75+ (paths from
# test/nvd.py, or PTXAS11 / PTXAS12 / PTXAS13).  Each SM gets four cubins:
# clang -O1/-O3 x ptxas -O1/-O3, named k<SM>_c<O>p<O>.cubin.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${1:?outdir}; shift
SMS=("$@")
[[ ${#SMS[@]} -eq 0 ]] && SMS=(35 50 52 60 61 70 75 80 86 89 90 100 120)
mkdir -p "$OUT"
NV=$(python3 -c "import sys; sys.path.insert(0,'$HERE'); import nvd; print(nvd.NV)")
P13=$(python3 -c "import sys, os; sys.path.insert(0,'$HERE'); import nvd; print(os.path.join(os.path.dirname(nvd.TOOLS['13']), 'ptxas'))")
PTXAS11=${PTXAS11:-$NV/11.8/nvidia/cuda_nvcc/bin/ptxas}
PTXAS12=${PTXAS12:-$NV/12.9/nvidia/cuda_nvcc/bin/ptxas}
PTXAS13=${PTXAS13:-$P13}
CLANG=${CLANG:-clang}
for sm in "${SMS[@]}"; do
	if [[ $sm -lt 50 ]]; then P=$PTXAS11; feat=+ptx78
	elif [[ $sm -lt 75 ]]; then P=$PTXAS12; feat=+ptx78
	elif [[ $sm -lt 100 ]]; then P=$PTXAS13; feat=+ptx78
	else P=$PTXAS13; feat=+ptx87; fi
	[[ -x $P ]] || { echo "no ptxas for sm_$sm ($P)"; continue; }
	for co in 1 3; do
		ptx=$OUT/k${sm}_c$co.ptx
		"$CLANG" -x cuda --cuda-device-only -nocudainc -nocudalib --cuda-gpu-arch=sm_$sm \
			-Xclang -target-feature -Xclang $feat -O$co -S -o "$ptx" "$HERE/cuda/kernels.cu" 2>/dev/null \
			|| { echo "clang failed for sm_$sm"; continue; }
		for po in 1 3; do
			"$P" -arch=sm_$sm -O$po "$ptx" -o "$OUT/k${sm}_c${co}p$po.cubin" 2>/dev/null \
				|| echo "ptxas failed for sm_$sm -O$po"
		done
		rm -f "$ptx"
	done
done
ls "$OUT"/*.cubin 2>/dev/null | wc -l
