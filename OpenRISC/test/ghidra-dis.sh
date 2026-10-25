#!/usr/bin/env bash
# Linear-sweep disassembly of a raw image with one OpenRISC language (DumpWords.java).
#   test/ghidra-dis.sh <language-id> <raw.bin> <out.txt>
set -euo pipefail
LANG_ID=$1
BIN=$(readlink -f "$2")
OUT=$(readlink -f "$3")
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)

PROJ=$(mktemp -d "${TMPDIR:-/tmp}/or1k-dis.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
for try in 1 2 3; do
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p \
		-import "$BIN" -loader BinaryLoader -processor "$LANG_ID" \
		-noanalysis -scriptPath "$HERE" -postScript DumpWords.java "$PROJ/out.txt" \
		-deleteProject >"$PROJ/log.txt" 2>&1 || { tail -40 "$PROJ/log.txt" >&2; exit 1; }
	[[ -s $PROJ/out.txt ]] && break
	sleep 2
done
[[ -s $PROJ/out.txt ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -40 >&2; exit 1; }
cp "$PROJ/out.txt" "$OUT"
