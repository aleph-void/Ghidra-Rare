#!/usr/bin/env bash
# Decode differential vs MAME unidasm:  test/run-decode.sh <workdir> [nrandom] [seed]
# For each family builds the corpus (gen_corpus.py), disassembles every 64K-word chunk with
# unidasm (-arch tms320c2x big-endian words / tms320c5x little-endian words) and with Ghidra
# (TMS320C2x:BE:16:default / TMS320C5x:LE:16:default), then compares record by record
# (compare.py). Also checks that the other-endian language decodes the byte-swapped corpus
# identically.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "$1"); NR=${2:-32768}; SEED=${3:-1}
rc=0
for fam in c2x c5x; do
	d=$W/$fam; rm -rf "$d"; mkdir -p "$d/m"
	if [[ $fam == c2x ]]; then end=be; arch=tms320c2x; lang=TMS320C2x:BE:16:default; other=TMS320C2x:LE:16:default
	else end=le; arch=tms320c5x; lang=TMS320C5x:LE:16:default; other=TMS320C5x:BE:16:default; fi
	python3 "$HERE/gen_corpus.py" $fam $end "$d" "$NR" "$SEED"
	for f in "$d"/chunks/*.bin; do unidasm "$f" -arch $arch > "$d/m/$(basename "$f" .bin).txt"; done
	"$HERE/ghidra-dis.sh" $lang "$d/chunks" "$d/g/" 4
	python3 "$HERE/compare.py" $fam "$d" > "$d/report.txt" || rc=1
	head -20 "$d/report.txt"
	# other byte order: swap bytes and expect the same listing
	mkdir -p "$d/swapped"
	for f in "$d"/chunks/*.bin; do python3 -c "import sys;b=open(sys.argv[1],'rb').read();open(sys.argv[2],'wb').write(bytes(x for i in range(0,len(b),2) for x in (b[i+1],b[i])))" "$f" "$d/swapped/$(basename "$f")"; done
	"$HERE/ghidra-dis.sh" $other "$d/swapped" "$d/gs/" 4
	if diff -rq "$d/g" "$d/gs" >/dev/null; then echo "$fam: $other decodes the byte-swapped corpus identically"
	else echo "$fam: $other DIFFERS on the byte-swapped corpus"; rc=1; fi
done
exit $rc
