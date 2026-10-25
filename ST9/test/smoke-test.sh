#!/usr/bin/env bash
# Import an original small program, run automatic analysis, and decompile every function.
#   GHIDRA_INSTALL_DIR=... test/smoke-test.sh [outdir]
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
OUTD=$(readlink -m "${1:-${TMPDIR:-/tmp}/st9-smoke}")
mkdir -p "$OUTD"
python3 "$HERE/gen_sample.py" "$OUTD/sample.bin"
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/st9-smoke.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
for lang in ST9:BE:16:default ST9:BE:24:ST9+; do
	prefix="$OUTD/${lang##*:}"
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$OUTD/sample.bin" \
		-loader BinaryLoader -processor "$lang" -scriptPath "$HERE" \
		-postScript ST9RealCheck.java "$prefix" 30 -deleteProject >"$prefix.log" 2>&1 \
		|| { tail -40 "$prefix.log" >&2; exit 1; }
	cat "$prefix.summary"
	grep -qx 'functions: 3' "$prefix.summary"
	grep -qx 'instructions: 11' "$prefix.summary"
	grep -qx 'bookmarks: {}' "$prefix.summary"
	grep -q 'decompile: 3 ok, 0 failed, 0 timeouts' "$prefix.summary"
done
