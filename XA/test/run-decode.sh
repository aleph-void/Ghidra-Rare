#!/usr/bin/env bash
# Decode differential vs MAME unidasm -arch xa:  test/run-decode.sh <workdir> [nrandom] [seed]
# Slot corpora (every first/second byte pair with three operand tails, plus random
# instructions), decoded by Ghidra in the native language with DS tracked (default context) and
# with DS dynamic (dsk=0), and in the page 0 language. Exit status 0 only if every difference
# is explained (see compare.py).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "$1"); NR=${2:-65536}; SEED=${3:-1}
mkdir -p "$W"
files=$(python3 "$HERE/gen_corpus.py" "$W/corpus" "$NR" "$SEED")
for f in $files; do
	unidasm "$f" -arch xa > "${f%.bin}.mame" &
done
wait
rc=0
for cfg in "XA:LE:24:default -" "XA:LE:24:default dsk=0" "XA:LE:24:page0 -"; do
	set -- $cfg
	tag=${1##*:}${2/-/}
	for f in $files; do
		"$HERE/ghidra-dis.sh" "$1" "$f" "${f%.bin}.$tag.ghidra" 0 16 "$2" &
	done
	wait
	for f in $files; do
		python3 "$HERE/compare.py" --stride 16 "${f%.bin}.mame" "${f%.bin}.$tag.ghidra" \
			"$(basename "${f%.bin}") $tag" | head -30 || rc=1
	done
done
exit $rc
