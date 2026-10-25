#!/usr/bin/env bash
# Real-code check: import one Z8 image (Intel HEX from the assembler) headless with full
# auto-analysis, decompile every function, and compare the analysed listing with MAME unidasm
# and with the assembler listing.
#
#   GHIDRA_INSTALL_DIR=... test/real-check.sh [--linear] <image.hex> <image.lst> <outdir> [lang-id]
#
# --linear: no analysis, a linear sweep of the whole image instead (for the assembler's
# instruction-list sources, which are not runnable programs).
#
# Output: <outdir>/<name>.{bin,summary,dis,c}; prints the summary and the comparison.
set -euo pipefail
LINEAR=0
[[ ${1:-} == --linear ]] && { LINEAR=1; shift; }
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
HEX=$(readlink -f "$1"); LST=$(readlink -f "$2"); OUTD=$(readlink -m "$3")
LANG_ID=${4:-Z8:BE:16:default}
N=$(basename "$HEX" .hex)
mkdir -p "$OUTD"
P="$OUTD/$N"
python3 "$HERE/real/ihex2bin.py" "$HEX" "$P.bin"
if ((LINEAR)); then
	"$HERE/ghidra-dis.sh" "$LANG_ID" "$P.bin" "$P.dis" 0
	python3 "$HERE/real/real_compare.py" "$P.bin" "$P.dis" "$LST" "$N"
	exit
fi
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/z8-real.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$P.bin" -loader BinaryLoader \
	-loader-baseAddr 0 -processor "$LANG_ID" -scriptPath "$HERE" \
	-postScript Z8RealCheck.java "$P" 60 -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
grep -E "^(ERROR|WARN)|Exception" "$PROJ/log.txt" | grep -v JAVA_HOME | head -20 > "$P.log" || true
grep -v "^bookmark" "$P.summary"
python3 "$HERE/real/real_compare.py" "$P.bin" "$P.dis" "$LST" "$N"
