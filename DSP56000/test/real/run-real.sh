#!/usr/bin/env bash
# All DSP56000 real-code checks: test/real/run-real.sh <workdir> [jobs]
# Runs fetch-and-build.sh, then real-check.sh on every LOD (with its listing when there is
# one) and sums the results (real/summary.py). Exit 1 on any listing or unexplained MAME
# difference.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "$1"); JOBS=${2:-4}
"$HERE/fetch-and-build.sh" "$W"
mkdir -p "$W/out"
i=0
run() {   # n lod [lst]
	local n=$1; shift
	"$HERE/../real-check.sh" "$@" "$W/out/$n" > "$W/out/$n.txt" 2>&1 || true
}
while read -r lod lst; do
	i=$((i + 1)); run "p$i" "$lod" "$lst" &
	(( i % JOBS == 0 )) && wait
done < "$W/pairs.txt"
while read -r lod; do
	i=$((i + 1)); run "l$i" "$lod" &
	(( i % JOBS == 0 )) && wait
done < "$W/lods.txt"
wait
python3 "$HERE/summary.py" "$W/out"/*.txt
