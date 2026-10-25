#!/usr/bin/env bash
# DEC Alpha module test suite: everything that needs no downloaded inputs.
#
#   test/run-tests.sh [workdir]
#
# Environment:
#   GHIDRA_INSTALL_DIR  Ghidra 12.1.x to test with. The module is symlinked into its
#                       Ghidra/Processors/Alpha (a different existing entry is left alone) and
#                       lib/Alpha.jar is rebuilt; use a scratch copy, not your real install.
#   OBJDUMP             GNU binutils objdump with the alpha target (default: the Ghidra-Rare
#                       all-targets 2.45 build)
#   JAVA_HOME           a JDK with javac (for lib/Alpha.jar)
#   QEMU_ALPHA          qemu-alpha user-mode emulator (default: qemu-alpha on PATH; skipped
#                       when missing)
# Real binaries (Debian alpha packages) are separate: test/fetch-real-samples.sh and
# test/real-binaries.sh.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR to a scratch Ghidra 12.1.x}"
: "${OBJDUMP:=$HOME/.cache/ghidra-rare-scratch/tools/binutils-all/bin/objdump}"
QEMU_ALPHA=${QEMU_ALPHA:-qemu-alpha}
W=$(readlink -m "${1:-${TMPDIR:-/tmp}/alpha-tests}")
mkdir -p "$W"
export OBJDUMP
if [[ -z ${JAVA_HOME:-} && -x /usr/lib/jvm/java-25-openjdk-amd64/bin/javac ]]; then
	export JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64
fi

echo "== compiling SLEIGH (one spec per JVM)"
for s in "$MOD"/data/languages/*.slaspec; do
	"$GHIDRA_INSTALL_DIR/support/sleigh" "$s" 2>&1 | grep -E "ERROR" && exit 1 || true
done
ls -l "$MOD"/data/languages/*.sla | awk '{s+=$5} END {printf "   %d .sla files, %d bytes in total\n", NR, s}'
P="$GHIDRA_INSTALL_DIR/Ghidra/Processors/Alpha"
if [[ ! -e $P ]]; then ln -s "$MOD" "$P"; elif [[ $(readlink -f "$P") != "$MOD" ]]; then
	echo "warning: $P exists and is not this module" >&2; fi
"$HERE/build-jar.sh"

echo "== decode: every language vs GNU objdump, CALL_PAL names vs MAME"
"$HERE/run-decode.sh" "$W/decode"

echo "== p-code: hand-computed emulator tests (emu_tests.py / EmuCheck.java)"
python3 "$HERE/emu_tests.py" "$W"
"$HERE/ghidra-script.sh" raw 21264:LE:64:unix "$W/emu.bin" EmuCheck.java "$W/emu.txt" "$W/emu_out.txt"
grep -v "^PASS" "$W/emu_out.txt"

echo "== p-code: random operate instructions, Ghidra emulator vs qemu-alpha"
if command -v "$QEMU_ALPHA" >/dev/null; then
	for seed in 1 2; do
		mkdir -p "$W/qd$seed"
		python3 "$HERE/qemu_diff.py" gen "$W/decode/alpha-opc.txt" "$W/qd$seed" 20000 $seed
		"$QEMU_ALPHA" -cpu ev67 "$W/qd$seed/qd.elf" >"$W/qd$seed/q.bin"
		"$HERE/ghidra-script.sh" elf-noanalysis - "$W/qd$seed/qd.elf" QemuDiff.java "$W/qd$seed/qd.txt" "$W/qd$seed/g.bin"
		python3 "$HERE/qemu_diff.py" cmp "$W/qd$seed" "$W/qd$seed/q.bin" "$W/qd$seed/g.bin" 3
	done
else
	echo "   (skipped: $QEMU_ALPHA not found)"
fi
