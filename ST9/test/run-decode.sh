#!/usr/bin/env bash
# Decode differential vs MAME unidasm:  test/run-decode.sh <workdir> [nrandom] [seed]
# Builds the corpus (test/gen_corpus.py), disassembles every 64K chunk with unidasm -arch st9/st9p
# and Ghidra (ST9:BE:16:default / ST9:BE:24:ST9+), and compares record by record (test/compare.py).
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "$1"); NR=${2:-20000}; SEED=${3:-1}
rm -rf "$W/chunks" "$W"/g.* "$W"/m.*; mkdir -p "$W/chunks"
python3 "$HERE/gen_corpus.py" "$W/c.bin" "$NR" "$SEED"
mv "$W"/c.[0-9][0-9][0-9].bin "$W/chunks/"
rc=0
for arch in st9 st9p; do
	lang=ST9:BE:16:default; [[ $arch == st9p ]] && lang=ST9:BE:24:ST9+
	mkdir -p "$W/m.$arch"
	for f in "$W"/chunks/*.bin; do
		unidasm "$f" -arch $arch -norawbytes > "$W/m.$arch/$(basename "$f").mame"
	done
	"$HERE/ghidra-dis.sh" "$lang" "$W/chunks" "$W/g.$arch/" 12
	python3 "$HERE/compare.py" "$W/c.bin" "$W/m.$arch" "$W/g.$arch" "$arch" > "$W/report.$arch.txt" || rc=1
	head -20 "$W/report.$arch.txt"
done
exit $rc
