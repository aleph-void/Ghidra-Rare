#!/usr/bin/env bash
# Real programs: import, auto-analyse, decompile and compare with MAME unidasm.
#   GHIDRA_INSTALL_DIR=... test/real-test.sh <inputs dir from fetch-inputs.sh> [outdir]
# Inputs (all MIT, fetched by pinned URL + SHA-256, never committed):
#   TMS320C25: c25dbg-BINARY.BIN, c25dbg-DUMP.BIN (big-endian words, loaded at 0)
#   TMS320C5x: the nine c5xtools example images assembled by TI's tools (little-endian, at 0800h)
#   TI COFF:   c5xtools' fir.asm assembled + linked by c5xasm/c5xlnk (.out), and test/coff/rel.asm
#              as a relocatable object (.obj) for the relocation handler
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
IN=$(readlink -f "$1"); OUTD=$(readlink -m "${2:-${TMPDIR:-/tmp}/tms-real}")
mkdir -p "$OUTD"
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/tms-real.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
rc=0
analyse() { # image lang prefix [base entry]
	local extra=()
	[[ -n ${4:-} ]] && extra=(-loader-baseAddr "0x$4" -preScript TmsEntry.java "$5")
	local ldr=(-loader BinaryLoader -processor "$2")
	[[ $2 == coff ]] && ldr=()
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$1" "${ldr[@]}" \
		"${extra[@]}" -scriptPath "$HERE" -postScript TmsRealCheck.java "$3" 30 -deleteProject \
		>"$3.log" 2>&1 || { tail -30 "$3.log" >&2; return 1; }
}
check() { # prefix  -> require no bookmarks and every function decompiled
	local s="$1.summary"
	printf '%-28s %s\n' "$(basename "$1")" "$(grep -E '^(functions|instructions|bookmarks|decompile):' "$s" | tr '\n' ' ')"
	grep -qx 'bookmarks: {}' "$s" || { echo "  FAIL: bookmarks" >&2; rc=1; }
	grep -q ' 0 failed, 0 timeouts; ' "$s" || { echo "  FAIL: decompile" >&2; rc=1; }
	! grep -q '^functions: 0$' "$s" || { echo "  FAIL: no functions" >&2; rc=1; }
}
for b in BINARY DUMP; do
	analyse "$IN/c25dbg-$b.BIN" TMS320C2x:BE:16:default "$OUTD/c25dbg-$b"
	check "$OUTD/c25dbg-$b"
	python3 "$HERE/real-compare.py" c2x "$IN/c25dbg-$b.BIN" "$OUTD/c25dbg-$b.dis" be | tail -1 || rc=1
done
for f in "$IN"/c5xtools/test/examples/golden/*.img; do
	b=$(basename "$f" .img)
	analyse "$f" TMS320C5x:LE:16:default "$OUTD/$b" 800 800
	check "$OUTD/$b"
	python3 "$HERE/real-compare.py" c5x "$f" "$OUTD/$b.dis" le 800 | tail -1 || rc=1
done
# TI COFF: linked executable and relocatable object
T=$IN/c5xtools/tools
if [[ -x $T/c5xasm/c5xasm ]]; then
	make -s -C "$T/c5xlnk" >/dev/null 2>&1 || true
	(cd "$OUTD" && "$T/c5xasm/c5xasm" "$IN/c5xtools/examples/src/fir.asm" -coff -o fir.obj -v50 -q &&
		"$T/c5xlnk/c5xlnk" fir.obj -o fir.out -q && "$T/c5xasm/c5xasm" "$HERE/coff/rel.asm" -coff -o rel.obj -v50 -q)
	analyse "$OUTD/fir.out" coff "$OUTD/coff-fir" "" ""
	grep -q 'TMS320C5x:LE:16:default' "$OUTD/coff-fir.summary" || { echo "  FAIL: COFF language" >&2; rc=1; }
	grep -qx 'bookmarks: {}' "$OUTD/coff-fir.summary" || { echo "  FAIL: COFF bookmarks" >&2; rc=1; }
	echo "coff fir.out: $(grep -E '^language|^bookmarks' "$OUTD/coff-fir.summary" | tr '\n' ' ')"
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$OUTD/rel.obj" -scriptPath "$HERE" \
		-preScript TmsEntry.java 2200 -postScript TmsRealCheck.java "$OUTD/coff-rel" 30 -deleteProject \
		>"$OUTD/coff-rel.log" 2>&1
	grep -qx 'bookmarks: {}' "$OUTD/coff-rel.summary" || { echo "  FAIL: relocation bookmarks" >&2; rc=1; }
	for want in '2200 bc40 LDP #0x40' '2201 1000 LACC 0x2000,0x0' '2202 9001 SACL 0x2001,0x0' \
		'2203 79802206 B 0x2206' '2208 bf902100 ADD #0x2100,0x0' '220a be802100 MPY #0x2100' \
		'220c bf092000 LAR AR1,#0x2000'; do
		grep -qxF "$want" "$OUTD/coff-rel.dis" || { echo "  FAIL: relocation result missing: $want" >&2; rc=1; }
	done
	echo "coff rel.obj: $(grep -c . "$OUTD/coff-rel.dis") instructions, $(grep -E '^bookmarks' "$OUTD/coff-rel.summary")"
fi
exit $rc
