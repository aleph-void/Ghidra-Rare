#!/usr/bin/env bash
# Real-code check for an SH4AL-DSP ELF file (from aleph-void/ghidra-sh, MIT): auto-detecting headless import (no forced language) with
# full analysis, decompile every function, and compare every analysed instruction with GNU
# objdump -d at the same address.
#   test/real-check.sh <file> <outdir> <expected language id> <objdump -m arch> [decompile-timeout-s (0: skip)]
# Output: <outdir>/<name>.{summary,dis,c,od,cmp}; prints the summary and the comparison total.
# Exit 1 on a wrong language or an unexplained objdump difference; bookmarks and decompile
# failures are reported.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
ELF=$(readlink -f "$1"); OUTD=$(readlink -m "$2"); LANGID=$3; ARCH=$4; TMO=${5:-60}
OBJDUMP=${OBJDUMP:-$HOME/.cache/ghidra-rare-scratch/tools/x-sh-elf/bin/sh-elf-objdump}
N=$(basename "$ELF")
mkdir -p "$OUTD"
P="$OUTD/$N"
rm -f "$P".{summary,dis,c,od,cmp}
"$HERE/ghidra-elf.sh" "$ELF" RealCheck.java "$P.summary" "$P.dis" "$P.c" "$TMO" 2>/dev/null
grep -v "^  Warning\|^  Error" "$P.summary"
rc=0
grep -q "^language: $LANGID " "$P.summary" || { echo "wrong language (expected $LANGID)"; rc=1; }
"$OBJDUMP" -d -z -m "$ARCH" "$ELF" > "$P.od"
# a shared object (ET_DYN) linked at 0 is loaded at Ghidra's image base
DELTA=0
if [[ $(od -An -tx1 -j16 -N1 "$ELF" | tr -d ' ') == 03 || $(od -An -tx1 -j17 -N1 "$ELF" | tr -d ' ') == 03 ]]; then
	base=$(sed -n 's/^image base: 0x//p' "$P.summary")
	low=$(python3 -I - "$ELF" <<'PY'
import struct, sys
d = open(sys.argv[1], "rb").read()
e = "<" if d[5] == 1 else ">"
phoff, = struct.unpack_from(e + "I", d, 28)
phentsize, phnum = struct.unpack_from(e + "HH", d, 42)
print(min(struct.unpack_from(e + "II", d, phoff + i * phentsize + 4)[1]
          for i in range(phnum) if struct.unpack_from(e + "I", d, phoff + i * phentsize)[0] == 1))
PY
)
	DELTA=$(( 0x$base - low ))
fi
RC_OBJDUMP="$OBJDUMP -d -z -m $ARCH" RC_OBJDUMP_FILE="$ELF" python3 -I "$HERE/real_compare.py" "$P.od" "$P.dis" "$N" "$DELTA" > "$P.cmp" || rc=1
tail -1 "$P.cmp"
exit $rc
