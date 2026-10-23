#!/usr/bin/env bash
# Real-world binary check: fetch public PRU firmware (test/fetch-real-samples.sh),
# import each ELF headless without -processor, auto-analyse, decompile every
# function, and diff the analysed listing against GNU objdump and TI dispru.
#
#   GHIDRA_INSTALL_DIR=/path/to/ghidra_12.1.4 \
#   OBJDUMP=/path/to/objdump-with-pru  [TI_CGT=/path/to/ti-cgt-pru_2.3.3] \
#   test/real-binaries.sh [workdir]
#
# Per-sample results (summary, analysed listing, decompiler output, diff) land
# in <workdir>/out/; the combined report is <workdir>/real-report.txt.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=$(readlink -m "${1:-${TMPDIR:-/tmp}/pru-real}")
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR (Ghidra 12.1.4)}"
: "${OBJDUMP:?set OBJDUMP to a binutils objdump built with pru support}"
MOD=$(dirname "$HERE")
[[ -e $GHIDRA_INSTALL_DIR/Ghidra/Processors/PRU ]] || ln -sfn "$MOD" "$GHIDRA_INSTALL_DIR/Ghidra/Processors/PRU"
"$HERE/build-jar.sh"
"$HERE/fetch-real-samples.sh" "$WORK/samples"
mkdir -p "$WORK/out"
: > "$WORK/real-report.txt"
for f in "$WORK"/samples/beaglelogic/beaglelogic-pru0 "$WORK"/samples/beaglelogic/beaglelogic-pru1; do
	"$HERE/real-check.sh" "$f" "$WORK/out" 3 | tee -a "$WORK/real-report.txt"
done
echo "report: $WORK/real-report.txt"
