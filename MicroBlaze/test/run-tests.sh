#!/usr/bin/env bash
# MicroBlaze processor module test: rebuild corpora, disassemble with Ghidra and with the
# reference objdumps, normalize and report agreement.
#
#   test/run-tests.sh [workdir]
#
# Environment (defaults point at the Ghidra-Rare scratch tool builds):
#   MB_GHIDRA           Ghidra 12.1.4 to test with (default: the scratch copy). An inherited
#                       GHIDRA_INSTALL_DIR is deliberately ignored so a user's real install is
#                       never modified; the module is symlinked into MB_GHIDRA/Ghidra/Processors.
#   OBJDUMP             GNU binutils 2.45 objdump (reference for the 32-bit variants)
#   XBU                 build dir of AMD/Xilinx-patched binutils 2.42 (see build-xlnx-binutils.sh);
#                       its objdump is the reference for the 64-bit variants (upstream binutils has
#                       no 64-bit MicroBlaze) and a second opinion for 32-bit; its gas assembles
#                       the assembler-generated vectors.
#   BU245SRC, XBUSRC    binutils source trees (only their opcode tables are read, to direct fuzzing)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
S=${S:-/tmp/claude-1000/-home-nick-Documents-git-Ghidra-Rare/738fc310-bd10-40da-87e5-b0a8be585382/scratchpad}
export GHIDRA_INSTALL_DIR=${MB_GHIDRA:-$S/tools/ghidra}
OBJDUMP=${OBJDUMP:-$S/tools/bu/build/binutils/objdump}
BU245SRC=${BU245SRC:-$S/tools/bu/binutils-2.45}
XBU=${XBU:-$S/work/microblaze/xlnx/build}
XBUSRC=${XBUSRC:-$S/work/microblaze/xlnx/binutils-2.42}
W=${1:-$S/work/microblaze/run}
mkdir -p "$W"
cd "$W"

echo "== compiling SLEIGH"
"$GHIDRA_INSTALL_DIR/support/sleigh" -a "$MOD/data/languages" 2>&1 | grep -E "ERROR|successfully" || true
P="$GHIDRA_INSTALL_DIR/Ghidra/Processors/MicroBlaze"
if [[ ! -e $P ]]; then ln -s "$MOD" "$P"; elif [[ $(readlink -f "$P") != "$MOD" ]]; then
	echo "warning: $P exists and is not this module" >&2; fi

echo "== generating corpora"
python3 "$HERE/gen_corpus.py" "$BU245SRC/opcodes/microblaze-opc.h" 32 . 1
python3 "$HERE/gen_corpus.py" "$XBUSRC/opcodes/microblaze-opc.h" 64 . 2
# assembler vectors
"$XBU/gas/as-new" -mbig-endian asm32.s -o asm32_be.o
"$XBU/gas/as-new" -mlittle-endian asm32.s -o asm32_le.o
"$XBU/gas/as-new" -m64 -mbig-endian asm64.s -o asm64_be.o 2>/dev/null
"$XBU/gas/as-new" -m64 -mlittle-endian asm64.s -o asm64_le.o 2>/dev/null
for f in asm32_be asm32_le asm64_be asm64_le; do
	"$XBU/binutils/objcopy" -O binary -j .text $f.o $f.bin
done
# the committed hand-written vectors (imm/imml prefixes, flow) -- see vectors.py
python3 "$HERE/vectors.py" .

run_one() { # lang bits endian bin refobjdump tag
	local lang=$1 bits=$2 e=$3 bin=$4 od=$5 tag=$6 eflag
	[[ $e == be ]] && eflag=-EB || eflag=-EL
	"$od" -D -b binary -m microblaze $eflag "$bin" > "o_$tag.txt"
	[[ -s g_${bin%.bin}.txt ]] || "$HERE/ghidra-dis-ctx.sh" "$lang" "$bin" 4 "g_${bin%.bin}.txt"
	echo "-- $tag: $lang vs $(basename "$(dirname "$(dirname "$od")")")/$(basename "$od")"
	python3 "$HERE/compare.py" "$bits" "$e" "g_${bin%.bin}.txt" "o_$tag.txt" 25 | tee "cmp_$tag.txt" | head -60
}
rm -f g_*.txt

echo "== 32-bit (reference: binutils 2.45 objdump; second opinion: Xilinx binutils objdump)"
for e in be le; do
	L=MicroBlaze:${e^^}:32:default
	run_one $L 32 $e fuzz32_$e.bin "$OBJDUMP" fuzz32_${e}_bu245
	run_one $L 32 $e asm32_$e.bin "$OBJDUMP" asm32_${e}_bu245
	run_one $L 32 $e vec32_$e.bin "$OBJDUMP" vec32_${e}_bu245
	run_one $L 32 $e fuzz32_$e.bin "$XBU/binutils/objdump" fuzz32_${e}_xlnx
done
echo "== 64-bit (reference: Xilinx binutils objdump)"
for e in be le; do
	L=MicroBlaze:${e^^}:64:default
	run_one $L 64 $e fuzz64_$e.bin "$XBU/binutils/objdump" fuzz64_${e}_xlnx
	run_one $L 64 $e asm64_$e.bin "$XBU/binutils/objdump" asm64_${e}_xlnx
	run_one $L 64 $e vec64_$e.bin "$XBU/binutils/objdump" vec64_${e}_xlnx
done
echo "== p-code emulator tests (emu_tests.py / EmuCheck.java)"
python3 "$HERE/emu_tests.py" .
for v in BE:32 LE:32 BE:64 LE:64; do
	b=${v#*:} e=${v%:*}; e=${e,,}
	"$HERE/ghidra-script.sh" raw "MicroBlaze:$v:default" "emu${b}_$e.bin" EmuCheck.java "$W/emu$b.txt" "$W/emu_$e$b.txt"
	grep -v "^PASS" "emu_$e$b.txt" | sed "s/^/$e$b: /"
done
echo "== ELF import + auto-analysis + decompile (test/elf, DecompileCheck.java)"
for f in mbtest_be.elf mbtest_le.elf mbtest64_le.o; do
	"$HERE/ghidra-script.sh" elf - "$HERE/elf/$f" DecompileCheck.java "$W/dec_$f.txt"
	echo "-- $f: $(head -2 "dec_$f.txt" | tr '\n' ' ')"
	echo "   decompiled: $(grep -c '^==== ' "dec_$f.txt") functions, failed: $(grep -c 'DECOMPILE FAILED' "dec_$f.txt")"
done
echo "== summary"
grep -H "^compared" cmp_*.txt | sed 's/^cmp_//; s/\.txt:/: /'
grep -H "^emulator tests" emu_*.txt | sed 's/\.txt:/: /'
