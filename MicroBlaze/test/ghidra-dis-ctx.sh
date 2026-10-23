#!/usr/bin/env bash
# Like tools/ghidra-dis.sh but runs DumpDisasmCtx.java (real Disassembler, so imm/imml
# prefix context reaches the next instruction).
#   test/ghidra-dis-ctx.sh <language-id> <raw.bin> [step] [out.txt]
set -euo pipefail
LANG_ID=$1
BIN=$(readlink -f "$2")
STEP=${3:-4}
OUT=${4:-/dev/stdout}
[[ $OUT != /dev/stdout ]] && OUT=$(readlink -f "$OUT")
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/mb-dis.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
# (retried: the OSGi script bundle occasionally fails to resolve when several headless
# Ghidras share the user's script cache)
for try in 1 2 3; do
	rm -f "$PROJ/out.txt"
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p \
		-import "$BIN" -loader BinaryLoader -processor "$LANG_ID" \
		-noanalysis -scriptPath "$HERE" -postScript DumpDisasmCtx.java "$STEP" "$PROJ/out.txt" \
		-deleteProject >"$PROJ/log.txt" 2>&1 || { tail -40 "$PROJ/log.txt" >&2; exit 1; }
	[[ -s $PROJ/out.txt ]] && break
	sleep 2
done
if [[ ! -s $PROJ/out.txt ]]; then
	grep -E "ERROR|Exception|error" "$PROJ/log.txt" | head -40 >&2
	exit 1
fi
cat "$PROJ/out.txt" >"$OUT"
