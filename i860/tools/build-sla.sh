#!/usr/bin/env bash
# Regenerate i860_gen.sinc and compile both languages: tools/build-sla.sh [ghidra-install]
set -euo pipefail
G=${1:-${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}}
L=$(cd "$(dirname "$0")/../data/languages" && pwd)
python3 "$L/../../tools/gen_i860.py" > "$L/i860_gen.sinc"
for v in xr xp; do
	"$G/support/sleigh" "$L/i860$v.slaspec" > "$L/../../build-sla-$v.log" 2>&1 || { grep -E "ERROR|Error" "$L/../../build-sla-$v.log"; exit 1; }
	rm -f "$L/../../build-sla-$v.log"
	echo "i860$v.sla $(stat -c %s "$L/i860$v.sla") bytes"
done
