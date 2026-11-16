#!/usr/bin/env bash
# P-code emulation test: test/emu-test.sh [--broken] [outdir]
# Runs every case of test/emu/cases.txt (hand-computed expectations) in both byte orders.  With
# --broken it runs a copy with one deliberately wrong expectation (the first case) and succeeds
# only if exactly that case fails in each language.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
BROKEN=0
[[ ${1:-} == --broken ]] && { BROKEN=1; shift; }
OUTD=$(readlink -m "${1:-${TMPDIR:-/tmp}/sh4al-emu}")
mkdir -p "$OUTD"
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/sh4al-emu.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
head -c 65536 /dev/zero > "$PROJ/zero.bin"
CASES=$HERE/emu/cases.txt
if (( BROKEN )); then
	# the same cases with the first expectation of the first case changed (value xor 1)
	python3 -I - "$HERE/emu/cases.txt" >"$PROJ/broken.txt" <<'PY'
import sys
done = False
for line in open(sys.argv[1]):
    f = line.split()
    if not done and f and f[0] == "expect":
        line = "expect %s 0x%x\n" % (f[1], int(f[2], 16) ^ 1)
        done = True
    sys.stdout.write(line)
PY
	CASES=$PROJ/broken.txt
fi
rc=0
for lang in SH4ALDSP:BE SH4ALDSP:LE; do
	out=$OUTD/emu-${lang/:/_}.txt
	(( BROKEN )) && out=$OUTD/emu-broken-${lang/:/_}.txt
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$PROJ/zero.bin" \
		-loader BinaryLoader -processor "${lang%%:*}:${lang##*:}:32:default" -noanalysis \
		-scriptPath "$HERE" -postScript SH4ALEmuTest.java "$CASES" "$out" -deleteProject \
		>"$PROJ/log.txt" 2>&1 || { tail -40 "$PROJ/log.txt" >&2; exit 1; }
	[[ -s $out ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -20 >&2; exit 1; }
	echo "== $lang"
	grep -v ^PASS "$out" || true
	if (( BROKEN )); then
		first=$(awk '/^case /{print $2; exit}' "$CASES")
		if [[ $(grep -c ^FAIL "$out") == 1 ]] && grep -q "^FAIL $first:" "$out"; then
			echo "broken expectation detected ($first)"
		else
			echo "BROKEN EXPECTATION NOT DETECTED"; rc=1
		fi
	else
		grep -q " 0 failed" "$out" || rc=1
	fi
done
exit $rc
