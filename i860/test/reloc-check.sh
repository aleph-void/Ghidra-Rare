#!/usr/bin/env bash
# ELF relocation check: test/reloc-check.sh <binutils-bin-dir> <outdir>
# Assembles reloc.s, imports the relocatable object into Ghidra (I860_ElfRelocationHandler
# applies the relocations), links the same object with GNU ld 2.30 (black box) at the
# addresses Ghidra chose, and compares every relocated word.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
BU=$1; OUT=$(readlink -m "$2"); mkdir -p "$OUT"
T=i860-stardent-sysv4
"$BU/$T-as" "$HERE/reloc.s" -o "$OUT/reloc.o"
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/i860-rel.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$OUT/reloc.o" -noanalysis \
	-scriptPath "$HERE" -postScript I860RelocDump.java "$OUT/reloc.ghidra" -deleteProject \
	> "$OUT/reloc.log" 2>&1 || { tail -30 "$OUT/reloc.log" >&2; exit 1; }
args=()
while read -r _ name addr _; do
	case $name in .text|.data|.text2|.far) args+=("--section-start=$name=0x$addr");; esac
done < <(grep ^section "$OUT/reloc.ghidra")
"$BU/$T-ld" -e start "${args[@]}" "$OUT/reloc.o" -o "$OUT/reloc.elf"
"$BU/$T-readelf" -r "$OUT/reloc.o" > "$OUT/reloc.relocs"
python3 "$HERE/reloc_compare.py" "$OUT/reloc.ghidra" "$OUT/reloc.elf" "$OUT/reloc.relocs"
