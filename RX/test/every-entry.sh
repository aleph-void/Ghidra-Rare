#!/usr/bin/env bash
# Every-entry test: test/every-entry.sh <lang-id> <out.txt> [ctx...]
# Builds the 16-byte-slot image (the decode corpora of gen_corpus.py), decodes
# every slot once per context setting and lists SLEIGH constructors that were never used.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
LANG_ID=$1; OUT=$(readlink -m "$2"); shift 2
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/rx-ee.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
python3 "$HERE/gen_corpus.py" --every "$PROJ/every.bin" >/dev/null
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$PROJ/every.bin" -loader BinaryLoader \
	-loader-baseAddr 0 -processor "$LANG_ID" -noanalysis -scriptPath "$HERE" \
	-postScript EveryEntry.java "$OUT" 16 "${@:--}" -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
cat "$OUT"
