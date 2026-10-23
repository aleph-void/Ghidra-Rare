#!/usr/bin/env bash
# Import one real PRU ELF headless (no -processor: the ELF opinion must pick
# the language), auto-analyse, decompile every function and diff the analysed
# listing against GNU objdump and (optionally) TI dispru.
#
#   GHIDRA_INSTALL_DIR=... OBJDUMP=... [TI_CGT=...] \
#   test/real-check.sh <file.elf> <outdir> [ti-silicon-version, default 3]
#
# Output: <outdir>/<name>.{summary,dis,c,cmp} ; prints summary + comparison.
set -euo pipefail
ELF=$(readlink -f "$1"); OUTD=$(readlink -m "$2"); TIV=${3:-3}
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
: "${OBJDUMP:?set OBJDUMP to a binutils objdump built with pru support}"
HERE=$(cd "$(dirname "$0")" && pwd)
N=$(basename "$ELF")
mkdir -p "$OUTD"
P="$OUTD/$N"
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/pru-real.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$ELF" \
	-scriptPath "$HERE" -postScript PruRealCheck.java "$P" 60 \
	-deleteProject >"$PROJ/log.txt" 2>&1 || { tail -40 "$PROJ/log.txt" >&2; exit 1; }
grep -E "^(ERROR|WARN)|Exception" "$PROJ/log.txt" | grep -v JAVA_HOME | head -20 > "$P.log" || true

python3 "$HERE/elf_code.py" "$ELF" "$P.bin" "$P.ranges"
"$OBJDUMP" -D -z -b binary -m pru "$P.bin" > "$P.gnu"   # -z: do not elide zero words
args=(--ghidra "$P.dis" --ranges "$P.ranges" --gnu "$P.gnu" --label "$N")
if [[ -n ${TI_CGT:-} ]]; then
	python3 "$HERE/ti_dis.py" "$TI_CGT" "$TIV" "$P.bin" "$P.ti" "$PROJ/ti"
	args+=(--ti "$P.ti")
fi
python3 "$HERE/real_compare.py" "${args[@]}" > "$P.cmp"
rm -f "$P.bin"
echo "#### $N"
grep -v "^bookmark \|^baddata \|^decompile failed" "$P.summary"
cat "$P.cmp"
