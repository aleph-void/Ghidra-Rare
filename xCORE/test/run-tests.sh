#!/usr/bin/env bash
# xCORE module test suite.
#   GHIDRA_INSTALL_DIR=/path/to/ghidra_12.1.4 test/run-tests.sh [workdir]
# Optional: XMOS_EXT=<dir prepared by test/fetch_xmos.sh> enables the XS3 source check and the
# ELF import/decompile sanity check (otherwise those steps are skipped).
#
# 1. regenerate + compile the SLEIGH specs
# 2. XS1 vs LLVM (libLLVM XCore disassembler, via ctypes): every 16-bit word, ~1M 32-bit items
# 3. XS2 / XS3 on the same corpus (differences are the documented re-encodings / new opcodes)
# 4. XS3: decode xcc-assembled lib_nn / lib_tflite_micro objects and compare with the .S sources
# 5. link the vendor objects into an ELF (xobj2elf.py), import headless (ELF opinion),
#    auto-analyse and decompile every function
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(dirname "$HERE")
REPO=$(dirname "$MOD")
W=${1:-${TMPDIR:-/tmp}/xcore-tests}
mkdir -p "$W"
DIS="$REPO/tools/ghidra-dis.sh"

[[ -e $GHIDRA_INSTALL_DIR/Ghidra/Processors/xCORE ]] || ln -sfn "$MOD" "$GHIDRA_INSTALL_DIR/Ghidra/Processors/xCORE"
echo "== build"
"$HERE/build.sh" | tail -3

echo "== corpus"
python3 "$HERE/mkcorpus.py" "$W"
for v in XS1 XS2 XS3; do
	echo "== $v vs LLVM (XS1 ISA), 16-bit words"
	"$DIS" "xCORE:LE:32:$v" "$W/w16.bin" 2 "$W/g16.txt"
	python3 "$HERE/compare.py" "$W/w16.bin" "$W/g16.txt" 2 25 | grep -v '^           ' || true
	echo "== $v vs LLVM (XS1 ISA), 32-bit items"
	"$DIS" "xCORE:LE:32:$v" "$W/w32.bin" 4 "$W/g32.txt"
	python3 "$HERE/compare.py" "$W/w32.bin" "$W/g32.txt" 4 25 | grep -v '^           ' || true
	rm -f "$W/g16.txt" "$W/g32.txt"
done

if [[ -n ${XMOS_EXT:-} ]]; then
	echo "== XS3 decoding vs XMOS assembly sources"
	python3 "$HERE/xs3_srccheck.py" extract "$XMOS_EXT/objs" "$XMOS_EXT/srcs" "$W/xs3chk"
	"$DIS" xCORE:LE:32:XS3 "$W/xs3chk/funcs.bin" 2 "$W/xs3chk/g.txt"
	python3 "$HERE/xs3_srccheck.py" check "$W/xs3chk" "$W/xs3chk/g.txt"

	echo "== ELF import + auto-analysis + decompile"
	python3 "$HERE/xobj2elf.py" "$W/xcore.elf" "$XMOS_EXT"/objs/*.c.obj "$XMOS_EXT"/objs/*.S.obj
	rm -rf "$W/proj" && mkdir -p "$W/proj"
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$W/proj" p -import "$W/xcore.elf" \
		-scriptPath "$HERE" -preScript SetCpDp.java -postScript DecompileDump.java "$W/decomp.txt" 100000 \
		-deleteProject >"$W/headless.log" 2>&1
	rm -rf "$W/proj"
	head -3 "$W/decomp.txt"
	echo "functions decompiled: $(grep -c '^====' "$W/decomp.txt"), failed: $(grep -c 'DECOMPILE FAILED' "$W/decomp.txt" || true)," \
		"bad-instruction warnings: $(grep -c 'halt_baddata' "$W/decomp.txt" || true)  (full output: $W/decomp.txt)"
else
	echo "(XMOS_EXT not set: skipping XS3 source check and ELF decompile check; see test/fetch_xmos.sh)"
fi
