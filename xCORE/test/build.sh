#!/usr/bin/env bash
# Regenerate and compile the SLEIGH specs.
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
python3 "$HERE/scripts/gen_sleigh.py"
for v in xs1 xs2 xs3; do
	"$GHIDRA_INSTALL_DIR/support/sleigh" "$HERE/data/languages/xcore_$v.slaspec" 2>&1 | grep -v "JAVA_HOME_OVERRIDE" | grep -E "^ERROR|^Error" && exit 1 || true
done
