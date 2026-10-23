#!/usr/bin/env bash
# PRU module test harness.
#
#   GHIDRA_INSTALL_DIR=/path/to/ghidra_12.1.4 \
#   OBJDUMP=/path/to/objdump-with-pru  [TI_CGT=/path/to/ti-cgt-pru_2.3.3] \
#   test/run-tests.sh [workdir] [nrandom]
#
# 1. recompiles the SLEIGH specs
# 2. builds the corpus (structured vectors + random words)  -> test/gen_corpus.py
# 3. disassembles it with GNU objdump (-b binary -m pru), TI dispru for each
#    core revision (if TI_CGT is set) and Ghidra for each PRU:LE:32:vN language
# 4. normalizes and compares (test/compare.py); report in <workdir>/report.txt
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(dirname "$HERE")
WORK=${1:-${TMPDIR:-/tmp}/pru-test}
NRAND=${2:-20000}
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR (Ghidra 12.1.4)}"
: "${OBJDUMP:?set OBJDUMP to a binutils objdump built with pru support}"
mkdir -p "$WORK"

echo "[1] compiling SLEIGH"
python3 "$MOD/tools/gen_pru_sinc.py" > "$MOD/data/languages/pru.sinc"
"$GHIDRA_INSTALL_DIR/support/sleigh" -a "$MOD/data/languages" 2>&1 | grep -E "^ERROR .*(sinc|slaspec)|No output" && exit 1 || true
[[ -e $GHIDRA_INSTALL_DIR/Ghidra/Processors/PRU ]] || ln -sfn "$MOD" "$GHIDRA_INSTALL_DIR/Ghidra/Processors/PRU"

echo "[2] corpus"
python3 "$HERE/gen_corpus.py" "$WORK/corpus.bin" "$NRAND" 1

echo "[3] reference disassemblers"
"$OBJDUMP" -D -b binary -m pru "$WORK/corpus.bin" > "$WORK/gnu.txt"
if [[ -n ${TI_CGT:-} ]]; then
	for v in 0 1 2 3 4; do
		python3 "$HERE/ti_dis.py" "$TI_CGT" $v "$WORK/corpus.bin" "$WORK/ti_v$v.txt" "$WORK/ti" &
	done
	wait
fi

echo "[3b] Ghidra"
for v in 0 1 2 3 4; do
	"$HERE/ghidra-dis.sh" PRU:LE:32:v$v "$WORK/corpus.bin" "$WORK/ghidra_v$v.txt" &
done
wait

echo "[4] compare"
: > "$WORK/report.txt"
for v in 0 1 2 3 4; do
	args=(--ghidra "$WORK/ghidra_v$v.txt" --version $v --label corpus)
	# GNU objdump has no notion of core revision: compare it with V3/V4 only
	[[ $v -ge 3 ]] && args+=(--gnu "$WORK/gnu.txt")
	[[ -n ${TI_CGT:-} ]] && args+=(--ti "$WORK/ti_v$v.txt")
	python3 "$HERE/compare.py" "${args[@]}" | tee -a "$WORK/report.txt"
done

echo "[5] p-code emulation semantics test"
"$HERE/emu-test.sh" "$WORK/emu.txt" | tail -1 | tee -a "$WORK/report.txt"

echo "[6] ELF import + analysis + decompile (TI clpru and GNU ld ELFs)"
for e in demo_v3 gnu_demo; do
	"$HERE/elf-check.sh" "$HERE/elf/$e.elf" "$WORK/elf_$e.txt" 2>/dev/null
	nf=$(grep -c "^==== " "$WORK/elf_$e.txt")
	bad=$(grep -c "DECOMPILE FAILED\|halt_baddata\|Bad instruction" "$WORK/elf_$e.txt" || true)
	echo "ELF $e: $(head -1 "$WORK/elf_$e.txt"), $nf functions, $bad decompile problems" | tee -a "$WORK/report.txt"
done
echo "report: $WORK/report.txt"
