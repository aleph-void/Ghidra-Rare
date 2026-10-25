#!/usr/bin/env bash
# RL78 processor module tests.
#
#   test/run-tests.sh [workdir]
#
# 1. compile both SLEIGH specs and link the module into $GHIDRA_INSTALL_DIR/Ghidra/Processors
# 2. decode corpora (gen_corpus.py): every 2-byte opcode prefix (and 3 bytes after ES:) with
#    three operand tails, plus 60,000 random slots; Ghidra (DumpSlots.java) vs GNU objdump's
#    RL78 disassembler (slotdis, built against binutils 2.45 libopcodes) for the G14 and G13
#    ISAs; compare.py scores exact/semantic agreement and buckets every difference
# 3. every-entry decode test (CoverageCheck.java): every constructor of both languages is reached
# 4. p-code emulator tests (emu_tests.py, EmuCheck.java); needs rl78-elf-as/ld (build-toolchain.sh)
# 5. if REAL_SAMPLES is set (fetch-real-samples.sh output): real-binaries.sh
#
# Environment:
#   GHIDRA_INSTALL_DIR  Ghidra 12.1.x/12.2 to test with (the module is symlinked into it)
#   SLOTDIS             slotdis binary; if unset it is built from slotdis.c with BU_SRC/BU_BUILD
#   BU_SRC, BU_BUILD    binutils 2.45 source tree and a build tree configured --enable-targets=all
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
W=$(mkdir -p "${1:-$PWD/rl78-test-work}" && cd "${1:-$PWD/rl78-test-work}" && pwd)
cd "$W"

echo "== compiling SLEIGH"
for s in "$MOD"/data/languages/*.slaspec; do
	"$GHIDRA_INSTALL_DIR/support/sleigh" "$s" 2>&1 | grep -E "^ERROR|^Error" || true
done
ls -l "$MOD"/data/languages/*.sla | awk '{print "   " $5, $9}'
P="$GHIDRA_INSTALL_DIR/Ghidra/Processors/RL78"
if [[ ! -e $P ]]; then ln -s "$MOD" "$P"; elif [[ $(readlink -f "$P") != "$MOD" ]]; then
	echo "warning: $P exists and is not this module" >&2; fi

if [[ -z ${SLOTDIS:-} ]]; then
	: "${BU_SRC:?set SLOTDIS, or BU_SRC and BU_BUILD to build it}" "${BU_BUILD:?}"
	SLOTDIS=$W/slotdis
	gcc -O2 -DPACKAGE=1 -DPACKAGE_VERSION=1 -include "$BU_BUILD/bfd/config.h" -o "$SLOTDIS" \
		"$HERE/slotdis.c" -I"$BU_BUILD/bfd" -I"$BU_SRC/include" -I"$BU_SRC/bfd" \
		"$BU_BUILD/opcodes/.libs/libopcodes.a" "$BU_BUILD/bfd/.libs/libbfd.a" \
		"$BU_BUILD/libiberty/libiberty.a" "$BU_BUILD/libsframe/.libs/libsframe.a" \
		"$BU_BUILD/zlib/libz.a" -lzstd 2>/dev/null
fi

echo "== decode corpora vs GNU objdump"
python3 "$HERE/gen_corpus.py" .
for c in enum fuzz; do
	"$SLOTDIS" rl78 8 $c.bin -f rl78_g14 >o_${c}_g14.txt
	"$SLOTDIS" rl78 8 $c.bin -f rl78_g13 >o_${c}_g13.txt
	"$HERE/ghidra-slots.sh" RL78:LE:16:default $c.bin 8 g_${c}_S3.txt
	"$HERE/ghidra-slots.sh" RL78:LE:16:S2 $c.bin 8 g_${c}_S2.txt
	for v in "S3 g14" "S2 g13"; do
		set -- $v
		echo "-- $c: RL78:LE:16:$( [[ $1 == S3 ]] && echo default || echo S2 ) vs objdump $2"
		python3 "$HERE/compare.py" g_${c}_$1.txt o_${c}_$2.txt 3 | tee cmp_${c}_$1.txt | grep -v '^      ' | head -30
	done
done

echo "== every-entry decode test"
head -c 64 /dev/zero >zero.bin
for l in default S2; do
	"$HERE/ghidra-script.sh" raw RL78:LE:16:$l zero.bin CoverageCheck.java "$W/cov_$l.txt" 256
	echo "-- RL78:LE:16:$l: $(tail -1 cov_$l.txt)"
	grep '^unreached' cov_$l.txt | head -20 || true
done

echo "== p-code emulator tests"
python3 "$HERE/emu_tests.py" .
"$HERE/ghidra-script.sh" raw RL78:LE:16:default emu.bin EmuCheck.java "$W/emu.txt" "$W/emu_out.txt"
grep -v '^PASS' emu_out.txt

if [[ -n ${REAL_SAMPLES:-} ]]; then
	echo "== real binaries"
	"$HERE/real-binaries.sh" "$REAL_SAMPLES" "$W/real"
fi

echo "== summary"
grep -H "^compared" cmp_*.txt | sed 's/^cmp_//; s/\.txt:/: /'
grep -H "^coverage" cov_*.txt | sed 's/\.txt:/: /'
tail -1 emu_out.txt
