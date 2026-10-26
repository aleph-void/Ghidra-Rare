#!/usr/bin/env bash
# Fetch asxa 1.12 (Marcos A. Stemmer and Fabio D'Agostini, GPL-2.0, https://asxa.sourceforge.net),
# build the assembler and assemble its example programs, which are the real XA code used by
# test/real-check.sh. The assembler is only run, as a black box; nothing fetched or built here is
# committed.
#
#   test/real/fetch-and-build.sh <workdir>
#
# Programs (examples/ in the asxa tarball, GPL):
#   monxa        monitor with disassembler and debugger, ROM build (vector table at 0), native mode
#   monxa_p0     the same with pagezero = 1 (SCR.PZ set, 16-bit addresses): page 0 language
#   monitor_rom  small serial monitor, ROM build (eprom = 1)
#   timer_int_rom, uart_int_rom   interrupt-driven clock and UART queue examples, ROM builds
#   keybrd       PC keyboard reader, loaded in RAM at B000h (no vector table)
#   test         the assembler's test bench: every instruction form (not runnable)
# Output: <workdir>/bin/<name>.{hex,lst}
set -euo pipefail
W=$(readlink -m "${1:?usage: fetch-and-build.sh <workdir>}")
URL="https://sourceforge.net/projects/asxa/files/Linux_Unix%20Source/asxa-1.12.tar.gz/asxa-1.12.tar.gz/download"
SHA=ab98d28ddca6391fa93f4f64b9049ed37f40a551f2c82e7f2dc753e5771ed2b6
mkdir -p "$W/src" "$W/bin"
cd "$W/src"
[[ -f asxa-1.12.tar.gz ]] || curl -sSfL -o asxa-1.12.tar.gz "$URL"
echo "$SHA  asxa-1.12.tar.gz" | sha256sum -c --quiet - || { echo "checksum mismatch" >&2; exit 1; }
rm -rf asxa-1.12
tar xzf asxa-1.12.tar.gz
# the 2007 sources overflow a fixed buffer under _FORTIFY_SOURCE; build without it
make -C asxa-1.12 asxa OPTIONS="-O0 -w -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 -fno-stack-protector" >/dev/null
ASXA=$W/src/asxa-1.12/asxa
E=$W/src/asxa-1.12/examples
cd "$E"
variant() { # source name sed-expression
	sed -e "$3" "$1.xa" > "$2.xa"
}
variant monitor monitor_rom 's/^eprom:\(\s*\)equ\(\s*\)0/eprom:\1equ\21/'
variant timer_int timer_int_rom 's/^eprom\(\s*\)equ\(\s*\)0/eprom\1equ\21/'
variant uart_int uart_int_rom 's/^eprom\(\s*\)equ\(\s*\)0/eprom\1equ\21/'
variant monxa monxa_p0 's/^pagezero = 0/pagezero = 1/'
for f in monxa monxa_p0 monitor_rom timer_int_rom uart_int_rom keybrd test; do
	"$ASXA" -l -i -h "$f.xa" >"$W/bin/$f.log" 2>&1 || { cat "$W/bin/$f.log" >&2; exit 1; }
	if grep -qi error "$W/bin/$f.log"; then cat "$W/bin/$f.log" >&2; exit 1; fi
	cp "$f.hex" "$f.lst" "$W/bin/"
done
ls "$W/bin"/*.hex
