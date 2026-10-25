#!/usr/bin/env bash
# Real-binary test: import each fetched ROM with the SNES ROM loader, analyse, count problems,
# re-decode Ghidra's listing with MAME's g65816 disassembler, and (when MAME is installed)
# compare against an execution trace of the ROM in MAME's snes driver.
#   test/real-binaries.sh <samples-dir> <workdir> <mame65816dis> [seconds-to-trace]
# MAME's snes machine needs an SPC700 boot ROM; trace/make_ipl.py writes an independent one.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SAMPLES=$(mkdir -p "$1" && cd "$1" && pwd); WORK=$(mkdir -p "$2" && cd "$2" && pwd); DIS=$3; SECS=${4:-10}
"$HERE/fetch-real-samples.sh" "$SAMPLES" >/dev/null
python3 "$HERE/trace/make_ipl.py" "$WORK/mame-roms" >/dev/null
for rom in "$SAMPLES"/roms/*.sfc; do
	name=$(basename "$rom" .sfc)
	"$HERE/real-check.sh" "$rom" "$WORK/$name"
	targs=()
	if command -v mame >/dev/null; then
		cat > "$WORK/$name.lua" <<LUA
local d = manager.machine.debugger
d:command("trace $WORK/$name.trace,:maincpu,noloop")
d:command("go")
LUA
		timeout 600 mame snes -rompath "$WORK/mame-roms" -cart "$rom" -debug -debugger none \
			-autoboot_script "$WORK/$name.lua" -autoboot_delay 0 -video none -sound none \
			-nothrottle -seconds_to_run "$SECS" -skip_gameinfo >/dev/null 2>&1 || true
		if [[ -s $WORK/$name.trace ]]; then
			sort -u -o "$WORK/$name.trace" "$WORK/$name.trace"
			targs=(--trace "$WORK/$name.trace")
		fi
	fi
	echo "== $name: $(sed -n 2p "$WORK/$name.summary")"
	python3 "$HERE/real_compare.py" "$WORK/$name.lst" "$DIS" "${targs[@]}" --label "$name"
	rm -f "$WORK/$name.lua"
done
