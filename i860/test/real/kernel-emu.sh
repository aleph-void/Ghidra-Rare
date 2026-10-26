#!/usr/bin/env bash
# Assemble test/real/kernels.s with GNU as (binutils 2.30, black box), import the ELF into
# Ghidra with auto-analysis and run the kernels in the p-code emulator against the
# mathematical results (kernel_cases.txt): test/real/kernel-emu.sh <binutils-bin-dir> <outdir>
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
BU=$1; OUT=$(readlink -m "$2"); mkdir -p "$OUT"
"$BU/i860-stardent-sysv4-as" -mxp "$HERE/kernels.s" -o "$OUT/kernels.o"
"$BU/i860-stardent-sysv4-ld" -e dot_pipe -Ttext 0x10000 "$OUT/kernels.o" -o "$OUT/kernels.elf"
python3 "$HERE/kernel_cases.py" > "$OUT/kernel_cases.txt"
cmp -s "$OUT/kernel_cases.txt" "$HERE/kernel_cases.txt" || { echo "kernel_cases.txt is stale"; exit 1; }
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/i860-kern.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$OUT/kernels.elf" \
	-scriptPath "$(cd "$HERE/.." && pwd)" -postScript I860EmuTest.java "$OUT/kernel_cases.txt" "$OUT/kernel-emu.txt" \
	-postScript I860RealCheck.java "$OUT/kernels" 60 -deleteProject > "$OUT/kernel-emu.log" 2>&1 \
	|| { tail -30 "$OUT/kernel-emu.log" >&2; exit 1; }
grep -v ^PASS "$OUT/kernel-emu.txt"
grep -E "^(functions|instructions|bookmarks|decompile):" "$OUT/kernels.summary"
"$BU/i860-stardent-sysv4-objdump" -d "$OUT/kernels.elf" > "$OUT/kernels.objdump"
"$BU/i860-stardent-sysv4-objcopy" -O binary -j .text "$OUT/kernels.elf" "$OUT/kernels.text"
unidasm "$OUT/kernels.text" -arch i860 -basepc 10000 > "$OUT/kernels.mame"
python3 "$HERE/real_compare.py" "$OUT/kernels.dis" "$OUT/kernels.objdump" "$OUT/kernels.mame"
grep -q " 0 failed" "$OUT/kernel-emu.txt"
