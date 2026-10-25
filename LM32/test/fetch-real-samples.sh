#!/usr/bin/env bash
# Download the public real-world LM32 binaries used by test/real-binaries.sh. Nothing is
# committed; the files land in <dest> (default: ./real-samples) and are checked against pinned
# SHA-256 sums.
#
#   test/fetch-real-samples.sh [dest]
#
# Source (pinned): timvideos/HDMI2USB-firmware-prebuilt, commit bf8ee7bf, build
# archive/master/v0.0.4-130-g155c7db: gcc-built LatticeMico32 ELF executables with DWARF for
# LiteX/MiSoC SoCs. The BIOS is LiteX's (BSD-2-Clause); the firmware is HDMI2USB-litex-firmware
# (BSD-2-Clause, with uIP and compiler-rt parts under their BSD/MIT-style licenses). The
# repository's LICENSE is BSD-style.
#   opsis-net-bios.elf               LiteX BIOS, Numato Opsis "net" target
#   opsis-net-firmware.elf           HDMI2USB firmware with Ethernet, Opsis
#   nexys_video-video-firmware.elf   HDMI2USB video firmware, Digilent Nexys Video
set -euo pipefail
DEST=${1:-real-samples}
mkdir -p "$DEST"
cd "$DEST"
C=bf8ee7bf8ec3569980b02ab39c9700bf4b9ce5a9
B=https://raw.githubusercontent.com/timvideos/HDMI2USB-firmware-prebuilt/$C/archive/master/v0.0.4-130-g155c7db
fetch() { # path out
	if [[ ! -s $2 ]]; then
		curl -fsSL --retry 3 -o "$2.part" "$B/$1"
		mv "$2.part" "$2"
	fi
}
fetch opsis/net/lm32/software/bios/bios.elf opsis-net-bios.elf
fetch opsis/net/lm32/software/firmware/firmware.elf opsis-net-firmware.elf
fetch nexys_video/video/lm32/software/firmware/firmware.elf nexys_video-video-firmware.elf

sha256sum -c - <<'EOF2'
335004245d2fa61242a16c766584329f413b12ac0faa1cbcd43307fe69080b17  opsis-net-bios.elf
ee305a4c5e2adcbb35f3a6770598e55564436da1df9ead7559d573553e46c3d6  opsis-net-firmware.elf
60a3a694edd1c4eb8fbf751fd85768787e1057f5d9a8bacf51473bd701699d69  nexys_video-video-firmware.elf
EOF2
