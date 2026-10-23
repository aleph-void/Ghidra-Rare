#!/usr/bin/env bash
# C7x module test-suite.
#   test/run-tests.sh [WORKDIR] [FUZZ_WORDS]
# Needs: GHIDRA_INSTALL_DIR (Ghidra 12.1.x) and TI C7000 CGT 5.0.2 (asm7x/dis7x/cl7x; set C7X_CGT if it
# is not at the default path baked into gen/oracle.py).  The module must be linked/installed into
# $GHIDRA_INSTALL_DIR/Ghidra/Processors/C7x (or installed as an extension).
#
# 1. compiles all four .slaspec files
# 2. for every silicon (7100 7120 7504 7524): FUZZ_WORDS random 32-bit words (p-bit clear) are
#    disassembled by dis7x and by Ghidra; reports % of dis7x-decodable words Ghidra renders
#    identically (after whitespace/number normalisation) and how many dis7x-invalid words Ghidra decodes
# 3. real compiler output: demo.c compiled with cl7x; the .text words (with execute packets,
#    constant- and condition-extension slots) are compared the same way
# 4. headless import + auto-analysis + decompilation of the linked demo ELF for each silicon
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
W=${1:-${TMPDIR:-/tmp}/c7x-tests}
N=${2:-50000}
SILS=${SILS:-"7100 7120 7504 7524"}
mkdir -p "$W"

echo "== compiling SLEIGH"
for s in 7100 7120 7504 7524; do     # one at a time: each compile needs ~1-2 GB of heap
  "$GHIDRA_INSTALL_DIR/support/sleigh" "$MOD/data/languages/c$s.slaspec" > "$W/sleigh$s.log" 2>&1 || true
  [[ -s $MOD/data/languages/c$s.sla ]] && ! grep -q "^ERROR [^:]*sinc\|No output produced" "$W/sleigh$s.log" ||
    { grep ERROR "$W/sleigh$s.log" | head; exit 1; }
done

declare -A FUZZ REAL DEC
for s in $SILS; do
  echo "== C$s: fuzz ($N words)"
  python3 "$HERE/compare.py" fuzz $s "$N" 7 "$W/fuzz$s" | tee "$W/fuzz$s.txt"
  FUZZ[$s]=$(head -1 "$W/fuzz$s.txt" | sed 's/.*(\(.*\)).*/\1/')

  echo "== C$s: compiler output"
  "$HERE/elf/build.sh" $s "$W/elf" > /dev/null
  awk '/^TEXT Section \.text/{t=1;next} /Section/{t=0} t && /^0x[0-9a-f]+ +[0-9a-f]{8} /{print $2}' \
      "$W/elf/demo$s.dis" > "$W/elf/text$s.txt"
  python3 "$HERE/compare.py" words $s "$W/elf/text$s.txt" "$W/real$s" | tee "$W/real$s.txt"
  REAL[$s]=$(head -1 "$W/real$s.txt" | sed 's/.*(\(.*\)).*/\1/')

  echo "== C$s: headless import/analysis/decompile of demo$s.out"
  P=$(mktemp -d "$W/proj.XXXXXX")
  "$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$P" p -import "$W/elf/demo$s.out" \
      -processor C7x:LE:64:C$s -scriptPath "$HERE" \
      -postScript DecompC7x.java "$W/decomp$s.txt" all sum_array classify caller vec_add vec_dot crc32 run_machine state_name main \
      -deleteProject > "$W/headless$s.log" 2>&1 || { tail -20 "$W/headless$s.log"; exit 1; }
  rm -rf "$P"
  grep -E "^(LANGUAGE|INSTRUCTIONS|ERROR_BOOKMARKS|DECOMPILED|FAILED)" "$W/decomp$s.txt"
  DEC[$s]=$(grep "^DECOMPILED" "$W/decomp$s.txt")
done

# ELF auto-detection (opinion): import without -processor
echo "== ELF opinion"
P=$(mktemp -d "$W/proj.XXXXXX")
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$P" p -import "$W/elf/demo7100.out" -noanalysis \
    -deleteProject > "$W/opinion.log" 2>&1 || true
rm -rf "$P"
grep -o "Using Language/Compiler: [^ ]*" "$W/opinion.log" | head -1 || echo "opinion: language not reported"

echo
echo "== SUMMARY"
for s in $SILS; do
  printf "C%s  fuzz %-8s  compiler-output %-8s  %s\n" "$s" "${FUZZ[$s]}" "${REAL[$s]}" "${DEC[$s]}"
done
echo "details (mismatches.txt, decomp*.txt) in $W"
