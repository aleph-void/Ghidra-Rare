#!/usr/bin/env bash
# 65816 module test harness.
#
#   GHIDRA_INSTALL_DIR=/path/to/ghidra_12.1.4 [CC65_BIN=/path/to/cc65/bin] \
#   [SINGLESTEP=1] [REAL_SAMPLES=<dir>] test/run-tests.sh [workdir] [nrandom]
#
# 1. compiles the SLEIGH spec and the SNES ROM loader (lib/65816.jar)
# 2. builds MAME's g65816 disassembler with M/X options (test/build-mame-dis.sh)
# 3. decode corpus (every opcode with edge/random operands + random words) under every M/X/E
#    combination: Ghidra vs MAME (test/compare.py), and, with CC65_BIN, re-assembly of Ghidra's
#    output by ca65 (test/asm_roundtrip.py)
# 4. context tracking (test/ctx-test.sh) and p-code emulation (test/emu-test.sh)
# 5. SINGLESTEP=1: SingleStepTests/65816, 50 tests per opcode and mode (downloads ~3 GB once,
#    keeps 13 MB; test/fetch-singlestep.py, test/singlestep-test.sh)
# 6. REAL_SAMPLES=<dir>: fetched homebrew ROMs (test/real-binaries.sh; MAME traces if installed)
# Report: <workdir>/report.txt
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(dirname "$HERE")
WORK=$(mkdir -p "${1:-${TMPDIR:-/tmp}/65816-test}" && cd "${1:-${TMPDIR:-/tmp}/65816-test}" && pwd)
NRAND=${2:-30000}
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR (Ghidra 12.1.4)}"
: > "$WORK/report.txt"

echo "[1] SLEIGH + loader"
"$GHIDRA_INSTALL_DIR/support/sleigh" "$MOD/data/languages/65816.slaspec" 2>&1 | grep -E "^ERROR" && exit 1 || true
[[ -e $GHIDRA_INSTALL_DIR/Ghidra/Processors/65816 ]] || ln -sfn "$MOD" "$GHIDRA_INSTALL_DIR/Ghidra/Processors/65816"
"$HERE/build-jar.sh"

echo "[2] MAME g65816 disassembler"
"$HERE/build-mame-dis.sh" "$WORK/bin" >/dev/null
DIS=$WORK/bin/mame65816dis

echo "[3] decode corpus"
python3 "$HERE/gen_corpus.py" "$WORK/corpus.bin" "$NRAND" 1
for mxe in 000 010 100 110 111; do
	"$HERE/ghidra-dis.sh" "$WORK/corpus.bin" "$WORK/ghidra_$mxe.txt" 4 "${mxe:0:1}" "${mxe:1:1}" "${mxe:2:1}" &
	"$DIS" "$WORK/corpus.bin" -stride 4 -basepc 8000 -m "${mxe:0:1}" -x "${mxe:1:1}" > "$WORK/mame_$mxe.txt"
done
wait
for mxe in 000 010 100 110 111; do
	python3 "$HERE/compare.py" "$WORK/ghidra_$mxe.txt" "$WORK/mame_$mxe.txt" --label "MXE=$mxe" | tee -a "$WORK/report.txt"
	if [[ -n ${CC65_BIN:-} ]]; then
		python3 "$HERE/asm_roundtrip.py" "$WORK/ghidra_$mxe.txt" "${mxe:0:1}" "${mxe:1:1}" \
			"$CC65_BIN/ca65" "$WORK/rt_$mxe" --label "ca65 MXE=$mxe" | tee -a "$WORK/report.txt"
	fi
done
# every opcode must decode in every mode (both-undefined can't hide a missing constructor)
python3 - "$WORK" <<'PY' | tee -a "$WORK/report.txt"
import sys
bad = []
for mxe in ("000", "010", "100", "110", "111"):
    seen = set()
    for l in open(f"{sys.argv[1]}/ghidra_{mxe}.txt"):
        p = l.split(" ", 2)
        if len(p) == 3 and not p[2].startswith("BAD"):
            seen.add(p[1][:2])
    bad += [(mxe, "%02x" % o) for o in range(256) if "%02x" % o not in seen]
print(f"every-opcode decode: {5 * 256 - len(bad)}/{5 * 256} opcode x mode entries decode", bad[:10])
PY

echo "[4] context tracking + emulation"
CA65=${CC65_BIN:+$CC65_BIN/ca65} LD65=${CC65_BIN:+$CC65_BIN/ld65} "$HERE/ctx-test.sh" "$WORK/ctx" | tail -1 | tee -a "$WORK/report.txt"
CA65=${CC65_BIN:+$CC65_BIN/ca65} LD65=${CC65_BIN:+$CC65_BIN/ld65} "$HERE/emu-test.sh" "$WORK/emu.txt" | tail -1 | tee -a "$WORK/report.txt"

if [[ -n ${SINGLESTEP:-} ]]; then
	echo "[5] SingleStepTests"
	[[ -s $WORK/singlestep.json ]] || python3 -I "$HERE/fetch-singlestep.py" "$WORK/singlestep.json" 50
	"$HERE/singlestep-test.sh" "$WORK/singlestep.json" "$WORK/singlestep.txt" | tee -a "$WORK/report.txt"
fi
if [[ -n ${REAL_SAMPLES:-} ]]; then
	echo "[6] real binaries"
	"$HERE/real-binaries.sh" "$REAL_SAMPLES" "$WORK/real" "$DIS" 10 | tee -a "$WORK/report.txt"
fi
echo "report: $WORK/report.txt"
