#!/usr/bin/env bash
# Import + auto-analyze a PRU ELF headless and dump functions/decompilation.
#   test/elf-check.sh <file.elf> <out.txt> [-processor PRU:LE:32:vN]
set -euo pipefail
ELF=$(readlink -f "$1"); OUT=$(readlink -m "$2"); shift 2
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/pru-elf.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$ELF" "$@" \
	-scriptPath "$HERE/../ghidra_scripts;$HERE" -preScript PRUFixupTiLabels.java -preScript PRUSetConstantTable.java am335x \
	-postScript PRUFixupTiLabels.java -postScript PruElfCheck.java "$OUT" -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
grep -E "WARN|ERROR" "$PROJ/log.txt" | grep -v "JAVA_HOME_OVERRIDE" | head -20 >&2 || true
