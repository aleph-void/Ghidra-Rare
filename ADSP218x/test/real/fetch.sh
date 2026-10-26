#!/usr/bin/env bash
# Fetch the freely licensed real ADSP-2181 programs used by the real-code check:
#   test/real/fetch.sh <dir>
# Source: github.com/AlexLefte/Electricity-Consumption-Meter (MIT license), pinned to commit
# 81db8b40f8c601b239dbd5c59a26aa0febc3d46a: two VisualDSP++ 3.x executables built for the
# ADSP-2181 EZ-KIT Lite, their assembler sources and the include file they use.  Nothing is
# committed to this repository; each file is checked against its SHA-256.
set -euo pipefail
D=$(readlink -m "$1"); mkdir -p "$D"
BASE=https://raw.githubusercontent.com/AlexLefte/Electricity-Consumption-Meter/81db8b40f8c601b239dbd5c59a26aa0febc3d46a
while read -r name sha path; do
	f="$D/$name"
	if [[ ! -f $f ]] || ! echo "$sha  $f" | sha256sum -c --quiet 2>/dev/null; then
		curl -fsSL -o "$f" "$BASE/$path"
	fi
	echo "$sha  $f" | sha256sum -c --quiet
done <<'LIST'
meter.dxe 395a39a5af9bb66ea10c169a6f8fe1e6a0b08f301e2f20a3eac7fdf3050d483d ADSP/test_ext/Debug/test_ext.dxe
meter.asm 3693a1c738c815013b231a0ce55f7c5fab5a8dee1f8da8e67731587aa91d4ce8 ADSP/test_ext/test_ext.asm
pftest.dxe 2be8741644c6732dd7504b1cf7c5f2a6f43d132e0166a000819687e010d03598 ADSP/Useful/_Tema_2019_T4x4_PF/test_ext_PF/Debug/test_ext.dxe
pftest.asm b426b3959928d7076b79640d395bab629f4a4849ec40c0694332c14a27a1ccab ADSP/Useful/_Tema_2019_T4x4_PF/test_ext_PF/test_ext.asm
def2181.h 50ca8d34cf84fdb44e84ad32d50eb5b55dc42b1b257c007f3b52f053b5c0831d ADSP/Useful/_Tema_2019_T4x4_PF/test_ext_PF/def2181.h
LIST
echo "fetched into $D"
