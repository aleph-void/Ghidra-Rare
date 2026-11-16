#!/usr/bin/env bash
# Real-code check for a Casio fx-CG add-in (.g3a): the code (file offset 0x7000 up to the 4-byte
# checksum at the end) is imported raw with SH4ALDSP:BE:32:default at 0x00300000, its first
# instruction marked as the entry, analysed, decompiled, and every analysed instruction compared
# with GNU objdump -b binary -m sh4al-dsp at the same address.
#   test/real-g3a.sh <file.g3a> <outdir> [decompile-timeout-s]
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
G3A=$(readlink -f "$1"); OUTD=$(readlink -m "$2"); TMO=${3:-20}
OBJDUMP=${OBJDUMP:-$HOME/.cache/ghidra-rare-scratch/tools/x-sh-elf/bin/sh-elf-objdump}
N=$(basename "$G3A" .g3a)
mkdir -p "$OUTD"
P="$OUTD/$N"
python3 -I - "$G3A" "$P.bin" <<'PY'
import sys
d = open(sys.argv[1], "rb").read()
open(sys.argv[2], "wb").write(d[0x7000:len(d) - 4])
PY
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/sh4al-g3a.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$P.bin" -loader BinaryLoader \
	-loader-baseAddr 0x300000 -processor SH4ALDSP:BE:32:default -scriptPath "$HERE" \
	-preScript G3AEntry.java -postScript RealCheck.java "$P.summary" "$P.dis" "$P.c" "$TMO" \
	-deleteProject >"$PROJ/log.txt" 2>&1 || { tail -40 "$PROJ/log.txt" >&2; exit 1; }
grep -v "^  Warning\|^  Error" "$P.summary"
"$OBJDUMP" -D -b binary -m sh4al-dsp -EB --adjust-vma=0x300000 "$P.bin" > "$P.od"
RC_OBJDUMP="$OBJDUMP -D -b binary -m sh4al-dsp -EB --adjust-vma=0x300000" RC_OBJDUMP_FILE="$P.bin" \
	python3 -I "$HERE/real_compare.py" "$P.od" "$P.dis" "$N" 0 > "$P.cmp" || rc=1
tail -1 "$P.cmp"
exit ${rc:-0}
