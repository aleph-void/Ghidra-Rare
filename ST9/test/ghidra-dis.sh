#!/usr/bin/env bash
# Decode raw ST9 images with Ghidra:  test/ghidra-dis.sh <lang-id> <raw.bin|dir> <out.txt|outdir/> <stride> [ctx]
# stride 0 = linear sweep; ctx = "name=value,..." context assignments over the whole image.
# With a directory of images, every file is imported and <outdir>/<file>.txt written for each.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
LANG_ID=$1; BIN=$(readlink -f "$2"); OUT=$(readlink -m "$3"); STRIDE=$4; CTX=${5:--}
[[ $3 == */ ]] && { mkdir -p "$OUT"; OUT=$OUT/; }
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/st9-dis.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$BIN" -loader BinaryLoader \
	-processor "$LANG_ID" -noanalysis -scriptPath "$HERE" \
	-postScript St9Dump.java "$OUT" "$STRIDE" "$CTX" -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
[[ $OUT == */ || -s $OUT ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -20 >&2; exit 1; }
