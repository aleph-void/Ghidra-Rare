#!/usr/bin/env bash
# Decode differential vs MAME unidasm -arch z8:  test/run-decode.sh <workdir> [nrandom] [rp...]
# Runs the corpus with RP unknown and once per given RP value (context set over the image).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "$1"); NR=${2:-50000}; shift 2 || true
mkdir -p "$W"
files=$(python3 "$HERE/gen_corpus.py" "$W/corpus" "$NR" 1)
rc=0
for rp in none "$@"; do
	for f in $files; do
		b=$(basename "$f" .bin)
		[[ -s $W/$b.mame ]] || unidasm "$f" -arch z8 -basepc 0x1000 > "$W/$b.mame"
		arg=; [[ $rp == none ]] || arg=$rp
		"$HERE/ghidra-dis.sh" Z8:BE:16:default "$f" "$W/$b.rp$rp.ghidra" 0x1000 $arg &
	done
	wait
	for f in $files; do
		b=$(basename "$f" .bin)
		python3 "$HERE/compare.py" "$W/$b.mame" "$W/$b.rp$rp.ghidra" "$b rp=$rp" || rc=1
	done
done
exit $rc
