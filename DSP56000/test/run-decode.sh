#!/usr/bin/env bash
# Decode differential vs MAME unidasm:  test/run-decode.sh <workdir> [nrandom] [seed] [jobs]
# DSP56000: slot corpora (every non-parallel word, every parallel-move field with two data ALU
# opcodes, every data ALU opcode with 32 move fields, random words) vs -arch dsp56000.
# DSP56156: every 16-bit word with three extension-word tails vs -arch dsp56156.
# Exit status 0 only if every difference is explained (see compare.py, explain_*.py).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "$1"); NR=${2:-65536}; SEED=${3:-1}; JOBS=${4:-6}
mkdir -p "$W/56000" "$W/56156"
rc=0
# --- DSP56000
python3 "$HERE/gen_corpus.py" "$W/56000" "$NR" "$SEED" > "$W/56000/list.txt"
while read -r f; do
	b=${f%.bin}
	[[ -s $b.mame ]] || unidasm "$b.m.bin" -arch dsp56000 > "$b.mame"
done < "$W/56000/list.txt"
xargs -P "$JOBS" -I{} sh -c 'b=${1%.bin}; "$2/ghidra-dis.sh" DSP56000:BE:16:default "$1" "$b.ghidra" 0 2' _ {} "$HERE" \
	< "$W/56000/list.txt"
while read -r f; do
	b=${f%.bin}
	python3 "$HERE/compare.py" --arch dsp56000 "$b.mame" "$b.ghidra" "$(basename "$b")" > "$b.cmp" || rc=1
done < "$W/56000/list.txt"
python3 "$HERE/summarize.py" "$W/56000"/*.cmp
# --- DSP56156
if [[ -f $HERE/gen_corpus156.py ]]; then
	python3 "$HERE/gen_corpus156.py" "$W/56156" "$NR" "$SEED" > "$W/56156/list.txt"
	while read -r f; do
		b=${f%.bin}
		[[ -s $b.mame ]] || unidasm "$b.m.bin" -arch dsp56156 > "$b.mame"
	done < "$W/56156/list.txt"
	xargs -P "$JOBS" -I{} sh -c 'b=${1%.bin}; "$2/ghidra-dis.sh" DSP56000:BE:16:DSP56156 "$1" "$b.ghidra" 0 2' _ {} "$HERE" \
		< "$W/56156/list.txt"
	while read -r f; do
		b=${f%.bin}
		python3 "$HERE/compare.py" --arch dsp56156 --stride 2 "$b.mame" "$b.ghidra" "$(basename "$b")" > "$b.cmp" || rc=1
	done < "$W/56156/list.txt"
	python3 "$HERE/summarize.py" "$W/56156"/*.cmp
fi
exit $rc
