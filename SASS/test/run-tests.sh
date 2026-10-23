#!/usr/bin/env bash
# SASS module test driver.
#
#   GHIDRA_INSTALL_DIR=<ghidra 12.1.4> test/run-tests.sh [variant ...]
#
# Steps
#   1. compile lib/SASS.jar (ELF extension) and all .slaspec files
#   2. per variant: disassemble the committed test vectors (test/vectors/<V>.txt:
#      words of MIT-licensed bitsandbytes cubins and of test/ptx kernels, plus
#      random words accepted by nvdisasm) with Ghidra and nvdisasm, report agreement;
#      if test/corpus exists (test/fetch-libcurand-corpus.py, local only) also the
#      libcurand corpus the module was learned from
#   3. per variant: a fresh random fuzz set (seed fixed per run date unless
#      FUZZ_SEED is set), only words nvdisasm accepts are scored
#   4. ELF: build cubins from test/ptx/kernels.ptx with ptxas (if available) and
#      the bitsandbytes cubins (test/fetch-real-samples.sh) - import + analyze +
#      decompile headless, and diff every .text section against nvdisasm
#
# Needs: python3, java 21, nvdisasm 13.x (SASS_NV or default scratch path, see
# test/nvd.py); ptxas optional.
set -uo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
REPO=$(cd "$MOD/.." && pwd)
VARIANTS=("$@")
if [[ ${#VARIANTS[@]} -eq 0 ]]; then
	VARIANTS=($(cd "$MOD/data/languages" && ls sass_*.slaspec | sed 's/sass_\(.*\)\.slaspec/\1/'))
fi
WORK=${SASS_TEST_WORK:-$(mktemp -d "${TMPDIR:-/tmp}/sass-test.XXXXXX")}
mkdir -p "$WORK"
echo "work dir: $WORK"

# make sure the module is visible to Ghidra
if [[ ! -e $GHIDRA_INSTALL_DIR/Ghidra/Processors/SASS ]]; then
	ln -s "$MOD" "$GHIDRA_INSTALL_DIR/Ghidra/Processors/SASS"
fi

echo "== build"
"$HERE/build-jar.sh" || exit 1
for v in "${VARIANTS[@]}"; do
	"$GHIDRA_INSTALL_DIR/support/sleigh" "$MOD/data/languages/sass_$v.slaspec" >"$WORK/sleigh_$v.log" 2>&1 \
		|| { echo "SLEIGH compile failed for $v"; tail -20 "$WORK/sleigh_$v.log"; exit 1; }
done

echo "== test vectors (Ghidra vs nvdisasm)"
for v in "${VARIANTS[@]}"; do
	[[ -f $HERE/vectors/$v.txt ]] || continue
	python3 "$HERE/vectors.py" tobin "$HERE/vectors/$v.txt" "$WORK/vec_$v.bin"
	python3 "$HERE/compare.py" "$v" "$WORK/vec_$v.bin" --show 5 --json "$WORK/vec_$v.json"
done

CORPUS=${SASS_CORPUS:-$HERE/corpus}
if [[ -d $CORPUS ]]; then
	echo "== LOCAL check: libcurand corpus (test/fetch-libcurand-corpus.py; never committed)"
	for v in "${VARIANTS[@]}"; do
		sm=$(echo "$v" | sed 's/SM/sm/')
		[[ -f $CORPUS/$sm.txt ]] || continue
		python3 "$HERE/vectors.py" tobin "$CORPUS/$sm.txt" "$WORK/corpus_$v.bin"
		python3 "$HERE/compare.py" "$v" "$WORK/corpus_$v.bin" --show 3
	done
fi

echo "== random fuzz (Ghidra vs nvdisasm)"
for v in "${VARIANTS[@]}"; do
	python3 "$HERE/vectors.py" fuzz "$v" "$WORK/fuzz_$v.bin" "${FUZZ_SEED:-$(date +%Y%m%d)}" 20000
	python3 "$HERE/compare.py" "$v" "$WORK/fuzz_$v.bin" --show 3 --json "$WORK/fuzz_$v.json"
done

echo "== ELF import / analysis / decompile"
PTXAS=${PTXAS:-$(python3 -c "import sys; sys.path.insert(0,'$HERE'); import nvd, os; print(os.path.join(os.path.dirname(nvd.TOOLS['13']), 'ptxas'))")}
if [[ -x $PTXAS ]]; then
	for a in 75 80 86 89 90 100 120; do
		[[ -f $MOD/data/languages/sass_SM$a.slaspec ]] || continue
		sed "s/sm_80/sm_$a/" "$HERE/ptx/kernels.ptx" >"$WORK/k$a.ptx"
		"$PTXAS" -arch=sm_$a "$WORK/k$a.ptx" -o "$WORK/k$a.cubin" || continue
		echo "-- k$a.cubin"
		"$HERE/ghidra-import.sh" "$WORK/k$a.cubin" "$WORK/k$a.c" 20 | grep SASS-CHECK
		python3 "$HERE/cubin_compare.py" "$WORK/k$a.cubin"
	done
fi
SAMPLES=${SASS_SAMPLES:-$MOD/test/samples}
for f in "$SAMPLES"/*.cubin; do
	[[ -f $f ]] || continue
	v=$(python3 "$HERE/cubin_compare.py" "$f" --variant)
	[[ -f $MOD/data/languages/sass_$v.slaspec ]] || { echo "-- $(basename "$f"): $v not built, skipped"; continue; }
	echo "-- $(basename "$f")"
	"$HERE/ghidra-import.sh" "$f" "$WORK/$(basename "$f").c" 30 | grep SASS-CHECK
	python3 "$HERE/cubin_compare.py" "$f"
done
