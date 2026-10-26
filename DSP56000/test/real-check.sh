#!/usr/bin/env bash
# Real-code check of one Motorola LOD file:  test/real-check.sh <prog.lod> [<prog.lst>] <outdir>
#  1. import with the LOD loader and run Ghidra's auto-analysis; count functions, instructions,
#     bad-instruction and error bookmarks, decompile every function (DspRealCheck.java)
#  2. with a listing: decode every listed P statement (listing-guided) and compare it with the
#     assembler's source text (real/lst_compare.py) and with MAME at the same addresses
#     (real/real_mame.py; DSP56000 only)
# Exit status 1 if a listed statement differs from the source or MAME differs unexplained.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
LOD=$(readlink -f "$1")
if [[ $# -ge 3 ]]; then LST=$(readlink -f "$2"); OUT=$(readlink -m "$3"); else LST=; OUT=$(readlink -m "$2"); fi
mkdir -p "$OUT"
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/dsp56k-real.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
ADDRS=()
if [[ -n $LST ]]; then
	python3 "$HERE/real/lst_compare.py" addrs "$LST" > "$OUT/addrs.txt"
	ADDRS=("$OUT/addrs.txt")
fi
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$LOD" -loader DspLodLoader \
	-scriptPath "$HERE" -postScript DspRealCheck.java "$OUT" "${ADDRS[@]}" -deleteProject \
	>"$OUT/log.txt" 2>&1 || { tail -40 "$OUT/log.txt" >&2; exit 1; }
[[ -s $OUT/summary.txt ]] || { grep -E "ERROR|Exception" "$OUT/log.txt" | head -20 >&2; exit 1; }
echo "$(basename "$LOD"): $(head -2 "$OUT/summary.txt" | tr '\n' ' ')"
rc=0
if [[ -n $LST ]]; then
	python3 "$HERE/real/lst_compare.py" compare "$LST" "$OUT/guided.txt" --auto "$OUT/auto.txt" || rc=1
	if grep -q "^_DATA P" "$LOD" && head -c 400 "$LOD" | grep -qE "^[0-9A-Fa-f]{6}( |$)"; then
		python3 "$HERE/real/real_mame.py" "$LOD" "$OUT/addrs.txt" "$OUT/guided.txt" "$OUT" || rc=1
	fi
fi
exit $rc
