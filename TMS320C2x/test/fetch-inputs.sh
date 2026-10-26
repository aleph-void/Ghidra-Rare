#!/usr/bin/env bash
# Fetch the freely licensed test inputs (pinned URLs and SHA-256; nothing is committed):
#   test/fetch-inputs.sh <dir>
# - c0demaster8051/tms320c25_debugger (MIT): BINARY.BIN (TMS320C25 example program) and DUMP.c
#   (the register-dump routine as a C array; extracted to DUMP.BIN)
# - wgrzegorz/c5xtools (MIT): TI-assembled example images and ISA conformance corpus, plus the
#   c5xasm assembler used by the round-trip test (built here with cc/make)
set -euo pipefail
D=$(readlink -m "$1"); mkdir -p "$D"
fetch() { # url sha256 out
	if [[ ! -f $3 ]] || ! echo "$2  $3" | sha256sum -c --quiet - 2>/dev/null; then
		curl -sSL -o "$3.part" "$1"; mv "$3.part" "$3"
	fi
	echo "$2  $3" | sha256sum -c --quiet - || { echo "checksum mismatch: $3" >&2; exit 1; }
}
C25=https://raw.githubusercontent.com/c0demaster8051/tms320c25_debugger/b8f664019be97f6cdc378b0babdf76b17e9d9949
fetch $C25/BINARY.BIN 9c00b8f79c7ace9df21ebe7f082ae887071bfdc2125dbc8170fdbf9a3d5d2743 "$D/c25dbg-BINARY.BIN"
fetch $C25/software/DUMP.c c2a5421cbe5cbc6a7dced4c7b37207a86f81c84ecc730bdda7d38a1d9e7e6525 "$D/c25dbg-DUMP.c"
python3 - "$D/c25dbg-DUMP.c" "$D/c25dbg-DUMP.BIN" <<'PY'
import re, sys
s = open(sys.argv[1], encoding="latin-1").read()
open(sys.argv[2], "wb").write(bytes(int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{2})", s.split("{", 1)[1])))
PY
fetch https://codeload.github.com/wgrzegorz/c5xtools/tar.gz/90ee7c91b4aba11d7089365a62eaf658970226c0 \
	b679f38f84798d1c64b38dd4c26b59c97f6b645f898318cf7631a439023d2092 "$D/c5xtools.tar.gz"
if [[ ! -x $D/c5xtools/tools/c5xasm/c5xasm ]]; then
	rm -rf "$D/c5xtools"; mkdir -p "$D/c5xtools"
	tar -xzf "$D/c5xtools.tar.gz" -C "$D/c5xtools" --strip-components=1
	make -s -C "$D/c5xtools/tools/c5xasm" >/dev/null 2>&1 || (cd "$D/c5xtools" && sh build.sh >/dev/null 2>&1)
fi
ls "$D"/c25dbg-BINARY.BIN "$D"/c25dbg-DUMP.BIN "$D"/c5xtools/test/examples/golden/*.img "$D"/c5xtools/test/conformance/corpus.img >/dev/null
echo "inputs ready in $D"
