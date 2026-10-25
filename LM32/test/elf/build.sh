#!/usr/bin/env bash
# Rebuild the committed test objects with GNU binutils for lm32-elf (binutils 2.45 configured
# with --target=lm32-elf): relocs.o and relocs_gprel.o are relocs.s and relocs_gprel.s
# assembled (relocation-type coverage).
#   test/elf/build.sh <lm32-elf bin dir>
set -euo pipefail
B=${1:?usage: build.sh <lm32-elf binutils bin dir>}
cd "$(dirname "$0")"
"$B/lm32-elf-as" relocs.s -o relocs.o
"$B/lm32-elf-as" relocs_gprel.s -o relocs_gprel.o
