#!/usr/bin/env bash
# Every-entry test:  test/every-entry.sh <lang-id> <chunk dir> <out.txt> <ctx>...
# Decodes every record of every chunk under each context setting; reports constructors never used.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
LANG_ID=$1; DIR=$(readlink -f "$2"); OUT=$(readlink -m "$3"); shift 3
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/tms-ee.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$DIR" -loader BinaryLoader \
	-processor "$LANG_ID" -noanalysis -scriptPath "$HERE" \
	-postScript EveryEntry.java "$OUT" "$@" -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
tail -1 "$OUT"
