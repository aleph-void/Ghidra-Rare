#!/usr/bin/env bash
# Linear-sweep a raw Z8 image with Ghidra:  ghidra-dis.sh <lang-id> <raw.bin> <out.txt> [base] [rp]
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
LANG_ID=$1; BIN=$(readlink -f "$2"); OUT=$(readlink -m "$3"); BASE=${4:-0x1000}; RP=${5:-}
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/z8-dis.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$BIN" -loader BinaryLoader \
	-loader-baseAddr "$BASE" -processor "$LANG_ID" -noanalysis -scriptPath "$HERE" \
	-postScript Z8DumpDisasm.java "$OUT" $RP -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
[[ -s $OUT ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -20 >&2; exit 1; }
