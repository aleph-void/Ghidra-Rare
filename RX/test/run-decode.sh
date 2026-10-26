#!/usr/bin/env bash
# Decode differential vs GNU objdump -m rx / rx:v2 / rx:v3:  test/run-decode.sh <workdir> [nrandom] [seed] [langs]
# Slot corpora from gen_corpus.py, decoded by Ghidra (one instruction per 16-byte slot) in each
# language and by objdump; compare.py buckets every difference. Exit 0 only if every difference
# is explained (explain.py).
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "$1"); NR=${2:-65536}; SEED=${3:-1}; LANGS=${4:-"v1 v2 v3"}
OBJDUMP=${OBJDUMP:-$HOME/.cache/ghidra-rare-scratch/tools/binutils-all/bin/objdump}
mkdir -p "$W"
# compile up front: parallel Ghidra processes would otherwise race to rebuild a stale .sla
for v in $LANGS; do
	"$GHIDRA_INSTALL_DIR/support/sleigh" "$HERE/../data/languages/rx_$v.slaspec" >/dev/null 2>&1
done
files=$(python3 "$HERE/gen_corpus.py" "$W/corpus" "$NR" "$SEED")
rc=0
for v in $LANGS; do
	m=rx; [[ $v != v1 ]] && m=rx:$v
	for f in $files; do
		"$OBJDUMP" -D -b binary -m "$m" "$f" > "${f%.bin}.$v.od" &
	done
	wait
	for f in $files; do
		"$HERE/ghidra-dis.sh" "RX:LE:32:RX$v" "$f" "${f%.bin}.$v.ghidra" 0 16 &
		while (( $(jobs -r | wc -l) >= ${JOBS:-4} )); do wait -n; done
	done
	wait
	for f in $files; do
		python3 "$HERE/compare.py" --lang "$v" "${f%.bin}.$v.od" "${f%.bin}.$v.ghidra" \
			"$(basename "${f%.bin}") $v" > "${f%.bin}.$v.cmp" || rc=1
		head -40 "${f%.bin}.$v.cmp"
	done
done
exit $rc
