#!/usr/bin/env bash
# Decode diff of every Alpha language against GNU objdump (and MAME unidasm for the OS-specific
# CALL_PAL names).   test/run-decode.sh <workdir>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "$1"); mkdir -p "$W"; cd "$W"
: "${OBJDUMP:=$HOME/.cache/ghidra-rare-scratch/tools/binutils-all/bin/objdump}"
: "${BINUTILS_SRC:=$HOME/.cache/ghidra-rare-scratch/tools/bu/binutils-2.45}"
: "${BINUTILS_BUILD:=$HOME/.cache/ghidra-rare-scratch/tools/bu-all-build}"
# GNU binutils' alpha opcode table (alpha-opc.c), dumped from the built libopcodes. It is
# generated here rather than committed (binutils is GPL).
if [[ -z ${ALPHA_OPC:-} ]]; then
	ALPHA_OPC=$W/alpha-opc.txt
	B=$BINUTILS_BUILD
	gcc -I"$BINUTILS_SRC/include" "$HERE/dumpopc.c" "$B/opcodes/.libs/libopcodes.a" \
		"$B/bfd/.libs/libbfd.a" "$B/libiberty/libiberty.a" "$B/libsframe/.libs/libsframe.a" \
		-lz -lzstd -o "$W/dumpopc"
	"$W/dumpopc" alpha >"$ALPHA_OPC"
fi
export ALPHA_OPC
python3 "$HERE/gen_corpus.py" "$ALPHA_OPC" .
for c in "21064 ev4" "21164 ev5" "21264 ev6" "21364 ev6" "21464 ev6"; do
	set -- $c
	for b in table fuzz; do
		"$OBJDUMP" -z -D -b binary -m alpha:$2 $b.bin > o_${b}_$2.txt
		for os in unix nt vms; do
			"$HERE/ghidra-dis.sh" $1:LE:64:$os $b.bin g_${b}_$1_$os.txt &
		done
		wait
	done
done
for c in "21064 ev4" "21164 ev5" "21264 ev6" "21364 ev6" "21464 ev6"; do
	set -- $c
	for b in table fuzz; do for os in unix nt vms; do
		python3 "$HERE/compare.py" g_${b}_$1_$os.txt o_${b}_$2.txt 3 --regs $os > cmp_${b}_$1_$os.txt
		echo "$1 $os $b: $(head -1 cmp_${b}_$1_$os.txt)"
	done; done
done
echo "== CALL_PAL names vs MAME unidasm"
python3 -c "
import struct
open('pal.bin','wb').write(b''.join(struct.pack('<I',w) for w in list(range(0,0x40))+list(range(0x80,0xc0))))"
for os in unix nt vms; do
	"$HERE/ghidra-dis.sh" 21264:LE:64:$os pal.bin g_pal_$os.txt
	unidasm -arch alpha_$os pal.bin > m_pal_$os.txt
	python3 "$HERE/pal_names_check.py" g_pal_$os.txt m_pal_$os.txt $os
done
echo "== every opcode-table entry"
for c in "21064 ev4" "21164 ev5" "21264 ev6"; do
	set -- $c
	python3 "$HERE/compare.py" g_table_$1_unix.txt o_table_$2.txt 0 --entries "$ALPHA_OPC" $2 | sed -n '/^table entries/,$p'
done
