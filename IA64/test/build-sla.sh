#!/usr/bin/env bash
# Regenerate the SLEIGH tables and compile both languages; fails on any SLEIGH error.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
MOD=$(cd "$(dirname "$0")/.." && pwd)
python3 "$MOD/tools/gen_ia64.py" "$MOD/data/languages"
for s in "$MOD"/data/languages/*.slaspec; do
	log=$("$GHIDRA_INSTALL_DIR/support/sleigh" "$s" 2>&1) || { echo "$log" | grep -E "rror" | head -20; exit 1; }
	if echo "$log" | grep -qE "^ERROR|^Error"; then echo "$log" | grep -E "rror" | head -20; exit 1; fi
	echo "$(basename "${s%.slaspec}").sla $(stat -c %s "${s%.slaspec}.sla") bytes"
done
