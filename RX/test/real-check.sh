#!/usr/bin/env bash
# Real-code check for an RX ELF file: import headless with the ELF loader and full auto-analysis,
# decompile every function, and compare every analysed instruction with GNU objdump at the same
# address.
#   GHIDRA_INSTALL_DIR=... test/real-check.sh <file.elf> <outdir> [expected-lang-id]
# Output: <outdir>/<name>.{summary,dis,c,od,cmp}; prints the summary and the comparison.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
ELF=$(readlink -f "$1"); OUTD=$(readlink -m "$2"); WANT=${3:-}
OBJDUMP=${OBJDUMP:-$HOME/.cache/ghidra-rare-scratch/tools/binutils-all/bin/objdump}
N=$(basename "$ELF"); N=${N%.elf}
mkdir -p "$OUTD"
P="$OUTD/$N"
rm -f "$P".{summary,dis,c,od,cmp,log}
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/rx-real.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$ELF" -scriptPath "$HERE" \
	-postScript RXRealCheck.java "$P" 60 -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
grep -E "^(ERROR|WARN)|Exception" "$PROJ/log.txt" | grep -v JAVA_HOME | head -20 > "$P.log" || true
grep -v "^bookmark" "$P.summary"
rc=0
if [[ -n $WANT ]] && ! grep -q "language: $WANT " "$P.summary"; then
	echo "expected language $WANT"; rc=1
fi
if "$OBJDUMP" -h "$ELF" | grep -q "file format" && [[ $(od -An -tx1 -j16 -N1 "$ELF" | tr -d ' ') == 01 ]]; then
	echo "relocatable object: section addresses differ from objdump's; no listing comparison"
	exit $rc
fi
"$OBJDUMP" -d -z "$ELF" > "$P.od"
python3 "$HERE/real_compare.py" "$P.od" "$P.dis" "$N" > "$P.cmp" || rc=1
cat "$P.cmp"
exit $rc
