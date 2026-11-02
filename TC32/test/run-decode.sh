#!/usr/bin/env bash
# Decode differential vs tc32-elf-objdump: test/run-decode.sh <workdir> [random-count] [seed]
# Corpora from gen_corpus.py: every halfword (4-byte slots), tjl pairs (8-byte slots), random
# 32-bit words (4-byte slots). Ghidra decodes each image by linear sweep (tools/DumpDisasm.java);
# compare.py buckets the differences and fails on any unexplained one.
# TC32_OBJDUMP must point at tc32-elf-objdump (Telink toolchain, run as a black box).
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
: "${TC32_OBJDUMP:?set TC32_OBJDUMP to tc32-elf-objdump}"
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
W=$(readlink -m "$1"); N=${2:-50000}; SEED=${3:-1}
mkdir -p "$W"
python3 "$HERE/gen_corpus.py" "$W" "$N" "$SEED"
rc=0
for c in all16:4 pairs:8 random:4; do
	name=${c%:*}; stride=${c#*:}
	"$TC32_OBJDUMP" -D -b binary -m tc32 "$W/$name.bin" > "$W/$name.od"
	"$ROOT/tools/ghidra-dis.sh" TC32:LE:32:default "$W/$name.bin" 2 "$W/$name.gh"
	python3 "$HERE/compare.py" "$W/$name.od" "$W/$name.gh" "$stride" --show 5 > "$W/$name.cmp" || rc=1
	echo "$name: $(head -1 "$W/$name.cmp")"
done
exit $rc
