#!/usr/bin/env bash
# Every-entry test: test/every-entry.sh <lang-id> <out.txt> <image.bin>...
# Decodes every 8-byte slot of the images (the word corpora and the assembler corpus) in each
# disassembly context that selects different constructors (single mode; low and high word of a
# dual pair; a high word whose partner is a floating-point compare) and lists the SLEIGH
# constructors that were never used.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
LANG_ID=$1; OUT=$(readlink -m "$2"); shift 2
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/i860-ee.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
# Extra slots: dual-mode branches whose delay pair is two nops (the corpora put another test word
# there), and scyc.s / scyc.l, which GNU as cannot assemble.
python3 - "$PROJ/extra.bin" <<'PY'
import struct, sys
nop = 0xa0000000
words = []
for w in (0x68000000, 0x40000800, 0x4c002002, 0x4c80020b, 0x4c80040b):
    words += [w, nop, nop, nop]
open(sys.argv[1], "wb").write(b"".join(struct.pack("<I", w) for w in words))
PY
cat "$@" "$PROJ/extra.bin" > "$PROJ/every.bin"
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$PROJ/every.bin" -loader BinaryLoader \
	-loader-baseAddr 0 -processor "$LANG_ID" -noanalysis -scriptPath "$HERE" \
	-postScript EveryEntry.java "$OUT" 8 - "dual=1,dnext=1,slot=0" "dual=1,dnext=1,slot=1" \
	"dual=1,dnext=1,slot=1,cmpslot=1" "dual=1,dnext=0,dnn=0,slot=1" -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
tail -1 "$OUT"
