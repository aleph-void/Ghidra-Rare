#!/usr/bin/env bash
# Real-binary checks: fetch the pinned Debian ia64 packages, import and analyse each ELF headless,
# decompile every function, and compare the disassembly with GNU objdump.
#   run-real.sh <workdir> [name ...]     (default: all)
# Ghidra projects go to $IA64_PROJ (default ${TMPDIR:-/tmp}/ia64-proj); Ghidra rejects project
# paths containing a dot-directory such as ~/.cache.
# Results: <workdir>/out/<name>.{summary,dis,bookmarks,decomp-failures,decomp-warnings,compare}
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "${1:?usage: run-real.sh <workdir> [name ...]}"); shift
"$HERE/fetch.sh" "$W" >/dev/null
declare -A BIN=(
	[libz]=x/zlib1g_1.2.7.dfsg-13_ia64/lib/ia64-linux-gnu/libz.so.1.2.7
	[busybox]=x/busybox_1.20.0-7_ia64/bin/busybox
	[busybox-static]=x/busybox-static_1.20.0-7_ia64/bin/busybox
	[gzip]=x/gzip_1.5-1.1_ia64/bin/gzip
	[bc]=x/bc_1.06.95-2_ia64/usr/bin/bc
	[libsqlite3]=x/libsqlite3-0_3.7.13-1+deb7u2_ia64/usr/lib/ia64-linux-gnu/libsqlite3.so.0.8.6
	[libm]=x/libc6.1_2.13-38+deb7u10_ia64/lib/ia64-linux-gnu/libm-2.13.so
	[libc]=x/libc6.1_2.13-38+deb7u10_ia64/lib/ia64-linux-gnu/libc-2.13.so
)
names=("$@")
[[ ${#names[@]} -gt 0 ]] || names=(libz busybox busybox-static gzip bc libsqlite3 libm libc)
PJ=${IA64_PROJ:-${TMPDIR:-/tmp}/ia64-proj}
mkdir -p "$W/out" "$PJ"
rc=0
for n in "${names[@]}"; do
	elf=$W/${BIN[$n]}
	echo "== $n"
	"$HERE/../real-check.sh" "$elf" "$W/out/$n" "$PJ/$n" || { rc=1; continue; }
	# shared objects are loaded at Ghidra's image base 0x100000, executables at their link address
	adj=0
	file -L "$elf" | grep -q "shared object" && adj=100000
	python3 "$HERE/real_compare.py" "$elf" "$W/out/$n.dis" $adj > "$W/out/$n.compare"
	head -1 "$W/out/$n.compare"
done
exit $rc
