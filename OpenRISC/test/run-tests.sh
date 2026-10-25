#!/usr/bin/env bash
# OpenRISC module tests that need no third-party downloads:
#   1. compile both .slaspec files
#   2. decode corpora (every binutils opcode-table entry + 50,000 random words) vs objdump,
#      BE (-m or1k -EB) and LE (-m or1knd -EL)
#   3. every-entry decode test
#   4. p-code emulator tests (33 per language)
#   5. committed test ELFs: import + analysis + decompile, and the relocation handler vs ld
#      (the ld step needs the Bootlin toolchain; it is skipped without OR1K_TOOLCHAIN)
#
#   test/run-tests.sh [workdir]
#
# Environment:
#   GHIDRA_INSTALL_DIR  Ghidra 12.1.x whose Ghidra/Processors/OpenRISC is (a symlink to) this
#                       module
#   OBJDUMP             GNU objdump built with the or1k target (binutils 2.45 --enable-targets=all)
#   OR1K_OPC            binutils opcodes/or1k-opc.c (opcode table the corpus is generated from)
#   OR1K_TOOLCHAIN      optional: Bootlin openrisc--glibc--stable-2025.08-1 bin/ directory
#                       (test/fetch-real-samples.sh <dir> --keep-toolchain)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
OBJDUMP=${OBJDUMP:?set OBJDUMP to an objdump with the or1k target}
OR1K_OPC=${OR1K_OPC:?set OR1K_OPC to binutils opcodes/or1k-opc.c}
W=$(readlink -f "${1:-or1k-test-work}")
mkdir -p "$W"
cd "$W"

echo "== compiling SLEIGH"
(cd "$MOD/data/languages" && for s in *.slaspec; do
	"$GHIDRA_INSTALL_DIR/support/sleigh" "$s" 2>&1 | grep -E "ERROR|^Error" || true
done)
ls -la "$MOD"/data/languages/*.sla | awk '{print "   " $9 ": " $5 " bytes"}'
"$HERE/build-jar.sh"

echo "== decode corpora vs objdump"
python3 "$HERE/gen_corpus.py" "$OR1K_OPC" .
for e in be le; do
	L=OpenRISC:${e^^}:32:default
	m=or1k ef=-EB
	[[ $e == le ]] && m=or1knd ef=-EL
	for c in table fuzz; do
		"$HERE/ghidra-dis.sh" "$L" ${c}_$e.bin g_${c}_$e.txt
		"$OBJDUMP" -D -b binary -m $m $ef ${c}_$e.bin >o_${c}_$e.txt
		python3 "$HERE/compare.py" g_${c}_$e.txt o_${c}_$e.txt 3 >cmp_${c}_$e.txt
		echo "-- $c $e ($L vs objdump -m $m): $(head -1 cmp_${c}_$e.txt)"
		sed -n '2,$p' cmp_${c}_$e.txt | grep -E "^\[" | sed 's/^/     /'
	done
done

echo "== every-entry decode test"
for e in be le; do
	python3 "$HERE/entry_check.py" entries.txt g_table_$e.txt >entry_$e.txt || true
	echo "-- $e: $(tail -1 entry_$e.txt)"
	grep FAIL entry_$e.txt || true
done

echo "== p-code emulator tests"
python3 "$HERE/emu_tests.py" .
for e in be le; do
	"$HERE/ghidra-script.sh" raw "OpenRISC:${e^^}:32:default" emu_$e.bin EmuCheck.java \
		"$W/emu_$e.txt" "$W/emu_res_$e.txt"
	echo "-- $e: $(tail -1 emu_res_$e.txt)"
	grep -v "^PASS\|^emulator" emu_res_$e.txt || true
done

echo "== committed test ELFs (test/elf)"
for f in or1ktest.elf; do
	p=$(mktemp -d "${TMPDIR:-/tmp}/or1k-elf.XXXXXX")
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$p" p -import "$HERE/elf/$f" -scriptPath "$HERE" \
		-postScript RealCheck.java "$W/$f.sum" "$W/$f.lst" "$W/$f.c" 60 -deleteProject >"$W/$f.log" 2>&1
	rm -rf "$p"
	"$OBJDUMP" -d "$HERE/elf/$f" >"$W/$f.od"
	echo "-- $f: $(grep -E '^(language|functions|bad-instruction|decompile)' "$W/$f.sum" | tr '\n' ';')"
	echo "   vs objdump: $(python3 "$HERE/compare.py" --listing "$W/$f.lst" "$W/$f.od" | head -1)"
done
if [[ -n ${OR1K_TOOLCHAIN:-} ]]; then
	"$HERE/reloc-check.sh" "$OR1K_TOOLCHAIN/or1k-buildroot-linux-gnu-ld" "$OBJDUMP" "$W/rel" \
		"$HERE/elf/relocs.o" "$HERE/elf/or1ktest.o"
else
	echo "-- relocation handler vs ld: skipped (set OR1K_TOOLCHAIN)"
fi
