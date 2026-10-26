#!/usr/bin/env bash
# Every-entry test: test/every-entry.sh <out.txt> [workdir]
# Decodes all 16,777,216 instruction words with the default context, then 2^20 words with
# each loop-end context (DO UNTIL last instruction, CE and other termination codes), and lists
# SLEIGH constructors that were never used.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$(readlink -m "$1")
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/adsp-ee.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
python3 -c "
import sys
w = sys.stdout.buffer.write
for k in range(256):
    w(b''.join(x.to_bytes(3, 'big') for x in range(k << 16, (k + 1) << 16)))
" > "$PROJ/all.be"
head -c $((65536 * 3)) /dev/zero > "$PROJ/pm.bin"
ctxs=(- lpend=1,lpterm=0:0x400000 lpend=1,lpterm=14:0x400000)
for t in $(seq 1 13) 15; do ctxs+=("lpend=1,lpterm=$t:1"); done
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$PROJ/pm.bin" -loader BinaryLoader \
	-processor ADSP218x:BE:16:default -noanalysis -scriptPath "$HERE" \
	-postScript EveryEntry.java "$OUT" "$PROJ/all.be" "${ctxs[@]}" -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
cat "$OUT"
