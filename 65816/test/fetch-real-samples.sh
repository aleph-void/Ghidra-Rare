#!/usr/bin/env bash
# Fetch freely licensed SNES homebrew ROMs for the real-binary test (never committed).
#   test/fetch-real-samples.sh <dir>
# Sources (pinned by SHA-256):
#   PVSnesLib 4.6.0 Linux release (github.com/alekmaul/pvsneslib, MIT; library zlib): example
#     ROMs built with 816-tcc (C) + WLA-DX, LoROM and HiROM.
#   snes-test-roms 20210217 (github.com/undisbeliever/snes-test-roms, MIT): hand-written ca65.
set -euo pipefail
DIR=$(mkdir -p "${1:?usage: fetch-real-samples.sh <dir>}" && cd "$1" && pwd)
cd "$DIR"
get() { # url sha256 file
	[[ -f $3 ]] || curl -sfL -o "$3" "$1"
	echo "$2  $3" | sha256sum -c --quiet -
}
get https://github.com/alekmaul/pvsneslib/releases/download/4.6.0/pvsneslib_460_64b_linux_release.zip \
	db08f2f95400125f8ae0cc62e87c3c350fa46a3eadb3174dd3161606ee49c84c pvsneslib-4.6.0.zip
get https://github.com/undisbeliever/snes-test-roms/releases/download/v20210217/snes-test-roms-20210217.zip \
	00945927bee494317663accaeb21d854b6cdfef674813e6c119877a8eeacb1c4 snes-test-roms-20210217.zip
mkdir -p roms
while read -r sha zip path; do
	out=roms/$(basename "$path")
	[[ -f $out ]] || unzip -p "$zip" "$path" > "$out"
	echo "$sha  $out" | sha256sum -c --quiet -
done <<'LIST'
6ddad5301fafdc861ed98774a085113c0031884a7838745d444fd7c583586ff8 pvsneslib-4.6.0.zip pvsneslib/snes-examples/systems/games/breakout/breakout.sfc
cad5126ac19cc7729a274ae1f1342a51d6086b172b55d5a76f2e2fe7e23cdadf pvsneslib-4.6.0.zip pvsneslib/snes-examples/systems/games/likemario/likemario.sfc
2f9cbc701fbad4c802a0b09afe93a1123d755dcdf2c011ef695ba0b98be97c18 pvsneslib-4.6.0.zip pvsneslib/snes-examples/systems/objects/mapandobjects/mapandobjects.sfc
e43e97456eea9c3bc322a93bbe901e5c7e5616b97d4ed7ee5918f26f00d3375e pvsneslib-4.6.0.zip pvsneslib/snes-examples/systems/sram/sramsimple/sram.sfc
0584e0e64357f60ed4cbb1407ba09ce3c9e2f8ebc67048ff24fe26c480598dfb pvsneslib-4.6.0.zip pvsneslib/snes-examples/systems/timer/timer.sfc
abee5f2588b2c33c55babe2e7e4ee9eb7583918ec4579ca13f0d0e82ec89a526 pvsneslib-4.6.0.zip pvsneslib/snes-examples/systems/memory_mapping/memory_mapping.sfc
6ecf32a4537ac46587df5896135683d533c6c743c46288a3b634bc9a717e6f36 pvsneslib-4.6.0.zip pvsneslib/snes-examples/audio/musicHiROM/musicHiROM.sfc
86f8773c4db36340fb4cdb2a6edf24cb1b6af135e5f18fa9c395df43ca93675d pvsneslib-4.6.0.zip pvsneslib/snes-examples/audio/music/music.sfc
1370a97a62cd320c9ebaf01e4e87720e5841ece47e6bb69beb841a4d034efeda pvsneslib-4.6.0.zip pvsneslib/snes-examples/graphics/Backgrounds/Mode7Perspective/Mode7Perspective.sfc
e6c891baf64edae4bec9907233e39dc031a4e98dc4ca550b2b008417b8c81cd9 pvsneslib-4.6.0.zip pvsneslib/snes-examples/graphics/maps/slopemario/slopemario.sfc
196a9ba7885073c9ce7210bc3de35fc82c824554c94742ff6c66816e5ff9ee2b snes-test-roms-20210217.zip snes-test-roms/hdmaen_latch_test.sfc
e9ca995e598625fdb3183969e260b048663b080d9fc3eeafeae83da244e507ba snes-test-roms-20210217.zip snes-test-roms/scpu-a-dma-bug-1.sfc
bfa2eab7ac8d7bb9792028f6a4b4520f668944ec35dd9f7940df6fc37fb77766 snes-test-roms-20210217.zip snes-test-roms/inidisp_d7_glitch_test.sfc
LIST
ls "$DIR"/roms
