#!/usr/bin/env bash
# Real-code check: import one XA image (Intel HEX from the assembler) headless with full
# auto-analysis, decompile every function, and compare the analysed listing with MAME unidasm
# and with the assembler listing.
#
#   GHIDRA_INSTALL_DIR=... test/real-check.sh [--linear] [--seed] [--entry <hex>] [--equ <file>]...
#       <image.hex> <image.lst> <outdir> [lang-id]
#
# --linear: no analysis, a linear sweep of the image instead (the assembler's test bench, which
#           is not a runnable program)
# --entry:  disassemble and make a function at this address (RAM programs without a vector table)
# --equ:    symbol file for the source-text comparison (real/src_compare.py), repeatable
# --seed:   also disassemble at every instruction address in the assembler listing before
#           analysis (code reached only through computed jumps); output names get a .seed suffix
#
# Output: <outdir>/<name>.{bin,summary,dis,c}; prints the summary and the comparison.
set -euo pipefail
LINEAR=0; ENTRY=; SEED=0; EQU=()
while [[ ${1:-} == --* ]]; do
	case $1 in
	--linear) LINEAR=1; shift ;;
	--entry) ENTRY=$2; shift 2 ;;
	--seed) SEED=1; shift ;;
	--equ) EQU+=("$(readlink -f "$2")"); shift 2 ;;
	*) echo "unknown option $1" >&2; exit 2 ;;
	esac
done
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
HEX=$(readlink -f "$1"); LST=$(readlink -f "$2"); OUTD=$(readlink -m "$3")
LANG_ID=${4:-XA:LE:24:default}
N=$(basename "$HEX" .hex)
((SEED)) && N=$N.seed
mkdir -p "$OUTD"
P="$OUTD/$N"
if ((LINEAR)); then
	BASE=$(python3 "$HERE/real/ihex2bin.py" --crop "$HEX" "$P.bin")
	"$HERE/ghidra-dis.sh" "$LANG_ID" "$P.bin" "$P.dis" "$BASE"
	rc=0
	python3 "$HERE/real/real_compare.py" "$P.bin" "$P.dis" "$LST" "$N" "$BASE" || rc=1
	python3 "$HERE/real/src_compare.py" "$P.dis" "$LST" "$N" "${EQU[@]}" || rc=1
	exit $rc
fi
python3 "$HERE/real/ihex2bin.py" "$HEX" "$P.bin"
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/xa-real.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
PRE=(); POST=()
[[ -n $ENTRY ]] && PRE=(-preScript XAEntry.java "$ENTRY")
if ((SEED)); then
	python3 "$HERE/real/real_compare.py" --addresses "$LST" > "$P.seeds"
	POST=(-postScript XASeed.java "$P.seeds")
fi
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$P.bin" -loader BinaryLoader \
	-loader-baseAddr 0 -processor "$LANG_ID" -scriptPath "$HERE" "${PRE[@]}" "${POST[@]}" \
	-postScript XARealCheck.java "$P" 60 -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
grep -E "^(ERROR|WARN)|Exception" "$PROJ/log.txt" | grep -v JAVA_HOME | head -20 > "$P.log" || true
grep -v "^bookmark" "$P.summary"
rc=0
python3 "$HERE/real/real_compare.py" "$P.bin" "$P.dis" "$LST" "$N" || rc=1
python3 "$HERE/real/src_compare.py" "$P.dis" "$LST" "$N" "${EQU[@]}" || rc=1
grep -q "0 failed, 0 timeouts" "$P.summary" || rc=1
exit $rc
