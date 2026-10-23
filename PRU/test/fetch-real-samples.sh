#!/usr/bin/env bash
# Download the public real-world PRU firmware used by test/real-binaries.sh.
# The binaries are not committed; they are fetched from pinned release URLs and
# checked against their SHA-256.
#
#   test/fetch-real-samples.sh <dir>
#
# BeagleLogic release-v1.1 (GPL-3.0, Kumar Abhishek), built with TI clpru for
# AM335x PRU-ICSS (core V3); source: github.com/abhishek-kakkar/BeagleLogic,
# tag release-v1.1 (commit aa771f4c), directory beaglelogic-firmware/.
set -euo pipefail
DIR=${1:?usage: fetch-real-samples.sh <dir>}
mkdir -p "$DIR/beaglelogic"
BL=https://github.com/abhishek-kakkar/BeagleLogic/releases/download/release-v1.1
while read -r sha name; do
	f=$DIR/beaglelogic/$name
	if [[ ! -s $f ]] || ! echo "$sha  $f" | sha256sum -c --status; then
		curl -fsSL -o "$f" "$BL/$name"
	fi
	echo "$sha  $f" | sha256sum -c --quiet
done <<'LIST'
55e1d4d7ac6b32e6cf7100289d430945911348a09019c5b2c55b352562f97d16 beaglelogic-pru0
cdebad5d01f7547497fa87f4cc4d7e06009bf4526741be40630280cc0723eba9 beaglelogic-pru1
LIST
echo "samples in $DIR"
