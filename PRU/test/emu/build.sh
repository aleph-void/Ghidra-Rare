#!/usr/bin/env bash
# Rebuild emu_test.bin (raw .text image) with TI PRU CGT.
#   TI_CGT=/path/to/ti-cgt-pru_2.3.3 OBJCOPY=/path/to/objcopy ./build.sh
set -euo pipefail
cd "$(dirname "$0")"
: "${TI_CGT:?set TI_CGT}"
W=$(mktemp -d)
"$TI_CGT/bin/clpru" -v3 emu_test.asm --output_file="$W/emu_test.obj" -z emu_test.cmd -o "$W/emu_test.elf" >/dev/null
"${OBJCOPY:-objcopy}" -O binary -j .text "$W/emu_test.elf" emu_test.bin
rm -rf "$W"
