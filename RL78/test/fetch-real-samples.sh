#!/usr/bin/env bash
# Fetch the public RL78 sample sources (pinned commits, SHA-256 checked) and build them with
# rl78-elf-gcc (see build-toolchain.sh) into <outdir>/*.elf. Nothing fetched or built here is
# committed.
#   test/fetch-real-samples.sh <outdir>
# Sources and licences:
#   msalau/rl78-samples-R5F100SLAFB, -R5F104FEAFP   Unlicense (public domain)   RL78/G13, G14 demos
#   FreeRTOS/FreeRTOS-Kernel V11.1.0                 MIT                         kernel + GCC RL78 port
# plus two small programs in test/real-src (FreeRTOS tasks/queue; newlib/libm/libgcc calls), which
# pull in newlib (BSD-style) and libgcc (GPL with the runtime exception) from the toolchain.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
O=$(mkdir -p "$1" && cd "$1" && pwd)
S=$O/src
mkdir -p "$S"
fetch() { # url sha256 dir
	local f=$S/$3.tar.gz
	[[ -f $f ]] || curl -fsSL -o "$f" "$1"
	echo "$2  $f" | sha256sum -c --quiet
	rm -rf "${S:?}/$3" && mkdir -p "$S/$3" && tar xzf "$f" -C "$S/$3" --strip-components=1
}
fetch https://github.com/msalau/rl78-samples-R5F100SLAFB/archive/5b98601d0df528362deb76342ac5828d69a75758.tar.gz \
	1eedabd472b05bbd75463e49a8edac4bfa78111ebb53c0c479cb7abaf336806b R5F100SLAFB
fetch https://github.com/msalau/rl78-samples-R5F104FEAFP/archive/a667778a20c2cbffed9082cfd5ef0343fa3f4ff0.tar.gz \
	a82aa93b7afd98b08aa75421b5d4efb621c4d10ab2922cbe1d212b1a12608549 R5F104FEAFP
fetch https://github.com/FreeRTOS/FreeRTOS-Kernel/archive/refs/tags/V11.1.0.tar.gz \
	0e21928b3bcc4f9bcaf7333fb1c8c0299d97e2ec9e13e3faa2c5a7ac8a3bc573 frk
cp -r "$HERE/real-src/90-freertos" "$S/R5F104FEAFP/"
cp -r "$HERE/real-src/91-newlib" "$S/R5F100SLAFB/"
rl78-elf-gcc --version | head -1
for d in R5F100SLAFB/00-led R5F100SLAFB/01-it R5F100SLAFB/02-uart R5F100SLAFB/91-newlib \
	R5F104FEAFP/00-led R5F104FEAFP/01-uart R5F104FEAFP/02-spi R5F104FEAFP/03-uart-dtc \
	R5F104FEAFP/04-sleep R5F104FEAFP/05-adc R5F104FEAFP/90-freertos; do
	(cd "$S/$d" && make -s FRK="$S/frk" >build.log 2>&1) || { tail -20 "$S/$d/build.log"; exit 1; }
	cp "$S/$d"/*.elf "$O/${d%%/*}_${d##*/}.elf"
done
ls -l "$O"/*.elf
