#!/usr/bin/env bash
# Every-entry test: test/every-entry.sh <lang-id> <workdir>
# Decodes the opcode-space corpus with the default frame context and a branch image under every
# frame context the generated tables distinguish (cfm_sol, cfm_out, cfm_sor), then lists the SLEIGH
# constructors that were never used.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
LANG_ID=$1; W=$(readlink -m "$2"); mkdir -p "$W"
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/ia64-ee.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
python3 "$HERE/gen_corpus.py" opcodes "$W/ee-op.bin" 7 >/dev/null
python3 "$HERE/gen_corpus.py" random "$W/ee-rand.bin" 20000 7 >/dev/null
python3 "$HERE/gen_corpus.py" branches "$W/ee-br.bin" >/dev/null
python3 "$HERE/gen_corpus.py" pseudo "$W/ee-ps.bin" 7 >/dev/null
triples=()
for s in $(seq 0 127); do triples+=("$s,8,0"); done
for o in $(seq 0 127); do triples+=("0,$o,0"); done
for r in $(seq 0 15); do triples+=("0,0,$r"); done
run() {  # image outfile triples...
	local img=$1 out=$2; shift 2
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$img" -loader BinaryLoader \
		-loader-baseAddr 0 -processor "$LANG_ID" -noanalysis -scriptPath "$HERE" \
		-postScript IA64EveryEntry.java "$out" "$@" -deleteProject >"$PROJ/log.txt" 2>&1 \
		|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
}
run "$W/ee-op.bin" "$W/ee-op.txt"
run "$W/ee-rand.bin" "$W/ee-rand.txt"
run "$W/ee-br.bin" "$W/ee-br.txt" "${triples[@]}"
run "$W/ee-ps.bin" "$W/ee-ps.txt"
python3 - "$W/ee-op.txt" "$W/ee-rand.txt" "$W/ee-br.txt" "$W/ee-ps.txt" <<'PY'
import sys
seen, allc = set(), set()
for f in sys.argv[1:]:
    for l in open(f):
        kind, key = l.rstrip('\n').split(' ', 1)
        (seen if kind == 'SEEN' else allc).add(key)
miss = sorted(allc - seen)
for m in miss:
    print('NOT REACHED', m)
print('every-entry: %d/%d constructors reached, %d not reached' % (len(allc) - len(miss), len(allc), len(miss)))
PY
