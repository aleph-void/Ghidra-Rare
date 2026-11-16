#!/usr/bin/env bash
# Every-entry test: test/every-entry.sh <workdir>
# Decodes every 16-bit word and every B field (with the A field cycling through all 1024 values),
# in the normal context and in each repeat-loop context, and lists the SLEIGH constructors no
# word used.  Exits non-zero when any constructor is never reached.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "$1"); mkdir -p "$W"
python3 -I - "$W/every.bin" <<'PY'
import struct, sys
w = []
for x in range(65536):
    w += [x, 9]
for b in range(65536):
    w += [0xf800 | ((b * 37) & 0x3ff), b]
open(sys.argv[1], "wb").write(b"".join(struct.pack(">H", x) for x in w))
PY
rc=0
P=$(mktemp -d "${TMPDIR:-/tmp}/sh4al-ee.XXXXXX")
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$P" p -import "$W/every.bin" -loader BinaryLoader \
	-loader-baseAddr 0 -processor SH4ALDSP:BE:32:default -noanalysis -scriptPath "$HERE" \
	-postScript EveryEntry.java "$W/every.txt" 4 default "rpt_ext=1,ctop=0x80" "conv_k=1,re_ctx=0x80" \
	"conv_k=2,ctop=0x80,rs_ctx=0x40" "conv_k=3,ctop=0x80,rs_ctx=0x40" "conv_k=4,ctop=0x80,rs_ctx=0x40" \
	-deleteProject >"$P/log.txt" 2>&1 || { tail -40 "$P/log.txt" >&2; rm -rf "$P"; exit 1; }
rm -rf "$P"
grep -E "NOT REACHED|^every-entry" "$W/every.txt"
grep -q " 0 not reached" "$W/every.txt" || rc=1
exit $rc
