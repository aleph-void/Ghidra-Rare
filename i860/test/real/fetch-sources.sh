#!/usr/bin/env bash
# Fetch the public sources of the real-code test programs (pinned URL + SHA-256) into
# <workdir>/real/src: test/real/fetch-sources.sh <workdir>
#  - zlib 1.3.1 (zlib license)
#  - Embench-IoT 1.0 (GPL-3.0-or-later; built and analysed locally, nothing is committed)
set -euo pipefail
W=$(readlink -m "$1"); D=$W/real/dl; S=$W/real/src
mkdir -p "$D" "$S"
get() {
	local url=$1 file=$2 sha=$3
	[[ -f $D/$file ]] || curl -sSL -o "$D/$file" "$url"
	echo "$sha  $D/$file" | sha256sum -c --quiet || { echo "checksum mismatch: $file" >&2; exit 1; }
	tar xzf "$D/$file" -C "$S"
}
get https://zlib.net/fossils/zlib-1.3.1.tar.gz zlib-1.3.1.tar.gz \
	9a93b2b7dfdac77ceba5a558a580e74667dd6fede4585b91eefb60f03b72df23
get https://github.com/embench/embench-iot/archive/refs/tags/embench-1.0.tar.gz embench-iot-1.0.tar.gz \
	ec188bfc2fc470bc096157e033a377d7f20ac34823c4473381c0f902d47a656b
ls "$S"
