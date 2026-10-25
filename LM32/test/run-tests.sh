#!/usr/bin/env bash
# LM32 module tests that need no third-party downloads:
#   1. compile both .slaspec files
#   2. decode corpora (every binutils opcode-table entry + 50,000 random words) vs objdump
#      -m lm32, BE (-EB) and LE (-EL)
#   3. every-entry decode test
#   4. p-code emulator tests (26 per language)
#   5. relocation handler: test/elf/relocs.o vs GNU ld, relocs_gprel.o vs the bfd formula
#      (the ld step needs lm32-elf binutils; it is skipped without LM32_BINUTILS)
#
#   test/run-tests.sh [workdir]
#
# Environment:
#   GHIDRA_INSTALL_DIR  Ghidra 12.1.x whose Ghidra/Processors/LM32 is (a symlink to) this module
#   OBJDUMP             GNU objdump built with the lm32 target (binutils 2.45 --enable-targets=all)
#   LM32_OPC            binutils opcodes/lm32-opc.c (opcode table the corpus is generated from)
#   LM32_BINUTILS       optional: bin/ directory of binutils configured --target=lm32-elf
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
OBJDUMP=${OBJDUMP:?set OBJDUMP to an objdump with the lm32 target}
LM32_OPC=${LM32_OPC:?set LM32_OPC to binutils opcodes/lm32-opc.c}
W=$(readlink -f "${1:-lm32-test-work}")
mkdir -p "$W"
cd "$W"

echo "== compiling SLEIGH"
(cd "$MOD/data/languages" && for s in *.slaspec; do
	"$GHIDRA_INSTALL_DIR/support/sleigh" "$s" 2>&1 | grep -E "ERROR|^Error" || true
done)
ls -la "$MOD"/data/languages/*.sla | awk '{print "   " $9 ": " $5 " bytes"}'
"$HERE/build-jar.sh"

echo "== decode corpora vs objdump"
python3 "$HERE/gen_corpus.py" "$LM32_OPC" .
for e in be le; do
	L=lm32:${e^^}:32:default
	ef=-EB
	[[ $e == le ]] && ef=-EL
	for c in table fuzz; do
		"$HERE/ghidra-dis.sh" "$L" ${c}_$e.bin g_${c}_$e.txt
		"$OBJDUMP" -D -b binary -m lm32 $ef ${c}_$e.bin >o_${c}_$e.txt
		python3 "$HERE/compare.py" g_${c}_$e.txt o_${c}_$e.txt 3 >cmp_${c}_$e.txt
		echo "-- $c $e ($L vs objdump -m lm32 $ef): $(head -1 cmp_${c}_$e.txt)"
		sed -n '2,$p' cmp_${c}_$e.txt | grep -E "^  (differences|  explained)" || true
	done
done

echo "== every-entry decode test"
for e in be le; do
	python3 "$HERE/entry_check.py" entries.txt g_table_$e.txt o_table_$e.txt >entry_$e.txt || true
	echo "-- $e: $(tail -1 entry_$e.txt)"
	grep FAIL entry_$e.txt || true
done

echo "== p-code emulator tests"
python3 "$HERE/emu_tests.py" .
for e in be le; do
	"$HERE/ghidra-script.sh" raw "lm32:${e^^}:32:default" emu_$e.bin EmuCheck.java \
		"$W/emu_$e.txt" "$W/emu_res_$e.txt"
	echo "-- $e: $(tail -1 emu_res_$e.txt)"
	grep -v "^PASS\|^emulator" emu_res_$e.txt || true
done

echo "== relocation handler (test/elf)"
if [[ -n ${LM32_BINUTILS:-} ]]; then
	"$HERE/reloc-check.sh" "$LM32_BINUTILS/lm32-elf-ld" "$OBJDUMP" "$W/rel" "$HERE/elf/relocs.o"
else
	echo "-- relocs.o vs ld: skipped (set LM32_BINUTILS)"
fi
"$HERE/reloc-check.sh" --no-ld "$OBJDUMP" "$W/rel" "$HERE/elf/relocs_gprel.o"
echo "-- $(python3 "$HERE/gprel_check.py" "$W/rel/relocs_gprel.o.mem" "$W/rel/relocs_gprel.o.sum")"
