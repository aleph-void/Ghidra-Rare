#!/usr/bin/env bash
# Reach every SLEIGH constructor in both ST9 languages.
#   GHIDRA_INSTALL_DIR=... test/coverage.sh <workdir>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "${1:?usage: coverage.sh <workdir>}")
mkdir -p "$W/chunks"
if ! compgen -G "$W/chunks/*.bin" >/dev/null; then
	python3 "$HERE/gen_corpus.py" "$W/c.bin" 20000 1
	mv "$W"/c.[0-9][0-9][0-9].bin "$W/chunks/"
fi
common=(
	-
	dp=0
	'rmode=1,rpk0=1,rpk1=1,ppk=1,rp0=0,rp1=0,page=0,dp=0'
	'rmode=1,rpk0=1,rpk1=1,ppk=1,rp0=28,rp1=28,page=63,dp=0'
	'rmode=2,rpk0=1,rpk1=1,ppk=1,rp0=30,rp1=31,page=0,sstk=1,ustk=1,dp=0'
)
"$HERE/every-entry.sh" ST9:BE:16:default "$W/chunks" "$W/coverage.st9.txt" "${common[@]}"
grep -q '0 not reached$' "$W/coverage.st9.txt"
"$HERE/every-entry.sh" ST9:BE:24:ST9+ "$W/chunks" "$W/coverage.st9p.txt" \
	- dp=0 sstk=1,encsr=0 "${common[@]:2}" \
	'sstk=1,encsr=1' 'sstk=0,encsr=1' 'sstk=1,encsr=1'
grep -q '0 not reached$' "$W/coverage.st9p.txt"
