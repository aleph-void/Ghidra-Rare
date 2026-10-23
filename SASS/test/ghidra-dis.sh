#!/usr/bin/env bash
# Disassemble a raw binary with a SASS language (linear sweep, no analysis).
# Copy of the repository-level tools/ghidra-dis.sh that uses test/SassDumpDisasm.java
# (marks the control words of the 64-bit encodings).
#
#   tools/ghidra-dis.sh <language-id> <raw.bin> [step] [out.txt]
#
# Example: tools/ghidra-dis.sh PRU:LE:32:v3 test.bin 4 out.txt
#
# GHIDRA_INSTALL_DIR must point at a Ghidra 12.1.4 install whose Ghidra/Processors
# contains (or symlinks) the processor modules from this repo; see tools/link-modules.sh.
set -euo pipefail

LANG_ID=$1
BIN=$(readlink -f "$2")
STEP=${3:-4}
OUT=${4:-/dev/stdout}
[[ $OUT != /dev/stdout ]] && OUT=$(readlink -f "$OUT")

: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/ghidra-dis.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT

TMPOUT="$PROJ/out.txt"
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p \
	-import "$BIN" -loader BinaryLoader -processor "$LANG_ID" \
	-noanalysis -scriptPath "$HERE" -postScript SassDumpDisasm.java "$STEP" "$TMPOUT" \
	-deleteProject >"$PROJ/log.txt" 2>&1 || { tail -40 "$PROJ/log.txt" >&2; exit 1; }
if [[ ! -s $TMPOUT ]]; then
	grep -E "ERROR|Exception|error" "$PROJ/log.txt" | head -40 >&2
	exit 1
fi
cat "$TMPOUT" >"$OUT"
