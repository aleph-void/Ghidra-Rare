#!/usr/bin/env bash
# Real-code check for one i860 ELF: test/real-check.sh <elf> <outdir> [binutils-bin-dir]
# Imports the ELF with auto-analysis (the language comes from the ELF opinion), records
# functions, bookmarks and decompiler results (I860RealCheck.java), and compares the analysed
# disassembly with GNU objdump and MAME at the same addresses (real/real_compare.py).
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
ELF=$(readlink -f "$1"); OUT=$(readlink -m "$2"); BU=${3:-}
mkdir -p "$OUT"
N=$(basename "$ELF" .elf)
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/i860-real.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$ELF" -scriptPath "$HERE" \
	-postScript I860RealCheck.java "$OUT/$N" 60 -deleteProject >"$OUT/$N.log" 2>&1 \
	|| { tail -40 "$OUT/$N.log" >&2; exit 1; }
grep -E "^(language|functions|instructions|bookmarks|decompile):" "$OUT/$N.summary"
if [[ -n $BU ]]; then
	"$BU/i860-stardent-sysv4-objdump" -d "$ELF" > "$OUT/$N.objdump"
	"$BU/i860-stardent-sysv4-objcopy" -O binary -j .text "$ELF" "$OUT/$N.text"
	base=$("$BU/i860-stardent-sysv4-readelf" -S "$ELF" | awk '{for (i = 1; i < NF; i++) if ($i == ".text") print $(i + 2)}')
	unidasm "$OUT/$N.text" -arch i860 -basepc "$(printf %x $((16#$base)))" > "$OUT/$N.mame"
	python3 "$HERE/real/real_compare.py" "$OUT/$N.dis" "$OUT/$N.objdump" "$OUT/$N.mame"
fi
