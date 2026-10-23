#!/usr/bin/env bash
# Symlink every processor module in this repo into $GHIDRA_INSTALL_DIR/Ghidra/Processors
# and compile its .slaspec files. Use this for development and testing.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
ROOT=$(cd "$(dirname "$0")/.." && pwd)
for mod in "$ROOT"/*/Module.manifest; do
	dir=$(dirname "$mod")
	name=$(basename "$dir")
	ln -sfn "$dir" "$GHIDRA_INSTALL_DIR/Ghidra/Processors/$name"
	echo "linked $name"
done
