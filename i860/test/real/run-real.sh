#!/usr/bin/env bash
# Real-code checks over every built test program: test/real/run-real.sh <workdir> [jobs]
# (<workdir>/real/bin from build-programs.sh, binutils in <workdir>/tc/inst/bin). Writes
# <workdir>/real/out/<name>.* and prints the totals; exit status 0 only if no program has bad
# instructions, decompile failures or unexplained objdump/MAME differences.
set -uo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -f "$1"); J=${2:-4}
OUT=$W/real/out; mkdir -p "$OUT"
ls "$W"/real/bin/*.elf | xargs -P "$J" -I{} sh -c \
	'"$0/../real-check.sh" "$1" "$2" "$3" > "$2/$(basename "$1" .elf).check" 2>&1' \
	"$HERE" {} "$OUT" "$W/tc/inst/bin"
python3 "$HERE/real_totals.py" "$OUT"/*.check
