#!/usr/bin/env bash
# Compile the module's Java part (ELF relocation handler) into lib/LM32.jar with javac, for
# a development install where the module directory is symlinked into Ghidra/Processors.
# (gradle buildExtension does the same for release zips.)
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
MOD=$(cd "$(dirname "$0")/.." && pwd)
CLS=$(mktemp -d "${TMPDIR:-/tmp}/lm32-cls.XXXXXX")
trap 'rm -rf "$CLS"' EXIT
CP=$(find "$GHIDRA_INSTALL_DIR/Ghidra/Framework" "$GHIDRA_INSTALL_DIR/Ghidra/Features" \
	-path '*/lib/*.jar' | tr '\n' ':')
javac -nowarn --release 21 -cp "$CP" -d "$CLS" $(find "$MOD/src/main/java" -name '*.java')
mkdir -p "$MOD/lib"
jar cf "$MOD/lib/LM32.jar" -C "$CLS" .
