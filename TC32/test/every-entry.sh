#!/usr/bin/env bash
# Every-entry test: test/every-entry.sh <out.txt>
# Decodes every halfword plus tjl pairs (gen_corpus.py every.bin, 4-byte slots) and lists the
# SLEIGH constructors that were never used.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$(readlink -m "$1")
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/tc32-ee.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
python3 "$HERE/gen_corpus.py" "$PROJ" 0 >/dev/null
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$PROJ/every.bin" -loader BinaryLoader \
	-loader-baseAddr 0 -processor TC32:LE:32:default -noanalysis -scriptPath "$HERE" \
	-postScript EveryEntry.java "$OUT" 4 - -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
cat "$OUT"
