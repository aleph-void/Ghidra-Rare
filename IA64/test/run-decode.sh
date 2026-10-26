#!/usr/bin/env bash
# Decode differential vs GNU objdump:  test/run-decode.sh <workdir> [random bundles] [seed]
# Corpora: random bundles over every template, the opcode space (every value of slot bits 27-40
# per unit and slot position, plus the MLX X slot), pseudo-op encodings and branch forms.
# Each corpus is decoded by all three languages (bundles are little-endian in every language);
# exit status 1 if any language shows an unexplained difference.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "${1:?usage: run-decode.sh <workdir> [random] [seed]}"); N=${2:-100000}; SEED=${3:-1}
mkdir -p "$W"
python3 "$HERE/gen_corpus.py" random "$W/random.bin" "$N" "$SEED" >/dev/null
python3 "$HERE/gen_corpus.py" opcodes "$W/opcodes.bin" "$SEED" >/dev/null
python3 "$HERE/gen_corpus.py" pseudo "$W/pseudo.bin" "$SEED" >/dev/null
python3 "$HERE/gen_corpus.py" branches "$W/branches.bin" >/dev/null
rc=0
for lang in IA64:LE:64:default IA64:BE:64:default IA64:BE:32:default; do
	for c in random opcodes pseudo branches; do
		tag=${lang//:/_}-$c
		"$HERE/ghidra-dis.sh" "$lang" "$W/$c.bin" "$W/$tag.txt"
		echo "-- $lang $c"
		a32=; [[ $lang == *:32:* ]] && a32=--addr32
		python3 "$HERE/compare.py" "$W/$c.bin" "$W/$tag.txt" "$W/$tag" $a32 | grep -E "slots|exact|both|different|explained|unexplained" || rc=1
		grep -q "^unexplained: 0" "$W/$tag/summary.txt" || rc=1
	done
done
exit $rc
