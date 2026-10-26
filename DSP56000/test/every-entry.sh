#!/usr/bin/env bash
# Every-entry test: test/every-entry.sh <lang-id> <stride-words> <out.txt> <ctxlist> <image.bin>...
# Decodes every slot of every image once per context setting in <ctxlist> (comma-free list
# separated by '/', e.g. "-/rep=1/lend=1,laddr=0x10") and lists the SLEIGH constructors that no
# image reached. Exit status 0 only if every constructor was reached.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
LANG_ID=$1; STRIDE=$2; OUT=$(readlink -m "$3"); CTXS=$4; shift 4
W=$(mktemp -d "${TMPDIR:-/tmp}/dsp56k-ee.XXXXXX")
trap 'rm -rf "$W"' EXIT
IFS=/ read -r -a ctx <<< "$CTXS"
run_one() {   # image outfile
	local P
	P=$(mktemp -d "$W/p.XXXXXX")
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$P" p -import "$1" -loader BinaryLoader \
		-loader-baseAddr 0 -processor "$LANG_ID" -noanalysis -scriptPath "$HERE" \
		-postScript EveryEntry.java "$2" "$STRIDE" "${ctx[@]}" -deleteProject >"$P.log" 2>&1 \
		|| { tail -20 "$P.log" >&2; return 1; }
	rm -rf "$P" "$P.log"
}
i=0
for img in "$@"; do
	i=$((i + 1))
	run_one "$(readlink -f "$img")" "$W/out.$i" &
	if (( i % ${JOBS:-6} == 0 )); then wait; fi
done
wait
python3 - "$OUT" "$W"/out.* <<'PY'
import sys
out, files = sys.argv[1], sys.argv[2:]
seen, allk, n = set(), set(), 0
for f in files:
    for line in open(f):
        if line.startswith("SEEN "):
            k = line[5:].strip(); seen.add(k); allk.add(k)
        elif line.startswith("NOT REACHED "):
            allk.add(line[12:].strip())
        elif line.startswith("every-entry:"):
            n += int(line.split()[1])
miss = sorted(allk - seen)
with open(out, "w") as o:
    for k in miss:
        o.write("NOT REACHED %s\n" % k)
    o.write("every-entry: %d decodes in %d images, %d/%d constructors reached, %d not reached\n"
            % (n, len(files), len(allk) - len(miss), len(allk), len(miss)))
PY
cat "$OUT" | tail -15
grep -q " 0 not reached" "$OUT"
