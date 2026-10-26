#!/usr/bin/env bash
# Decode differential vs MAME unidasm -arch adsp21xx:
#   test/run-decode.sh <workdir> [--exhaustive | <nrandom> <seed>]
# --exhaustive (default) decodes all 16,777,216 instruction words in 16 slices; otherwise
# <nrandom> random words.  Exit status 0 only if every difference is explained (compare.py).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "$1"); shift
mkdir -p "$W"
JOBS=${JOBS:-4}
slices=()
if [[ ${1:---exhaustive} == --exhaustive ]]; then
	for k in $(seq 0 15); do
		python3 "$HERE/gen_corpus.py" "$W/s$k" $((k << 20)) $((1 << 20))
		slices+=("s$k")
	done
else
	python3 "$HERE/gen_corpus.py" --random "$W/r" "$1" "${2:-1}"
	slices+=(r)
fi
run_slice() {
	local s=$1
	unidasm "$W/$s.le" -arch adsp21xx | gzip -1 > "$W/$s.mame.gz"
	"$HERE/ghidra-corpus.sh" "$W/$s.be" "$W/$s.ghidra"
	gzip -1f "$W/$s.ghidra"
	rm -f "$W/$s.le" "$W/$s.be"
}
export -f run_slice; export W HERE
printf '%s\n' "${slices[@]}" | xargs -P "$JOBS" -I{} bash -c 'run_slice {}'
rc=0
for s in "${slices[@]}"; do
	python3 "$HERE/compare.py" "$W/$s.mame.gz" "$W/$s.ghidra.gz" "$s" > "$W/$s.cmp" || rc=1
done
python3 "$HERE/sum-compare.py" "$W"/*.cmp
exit $rc
