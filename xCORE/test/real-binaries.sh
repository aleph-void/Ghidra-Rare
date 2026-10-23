#!/usr/bin/env bash
# Real-world check on public XMOS release binaries (fetched by fetch-real-samples.sh).
#   GHIDRA_INSTALL_DIR=... test/real-binaries.sh <sample-dir> [workdir]
# Env: JOBS=n (parallel headless runs, default 3); RESULTS_ONLY=1 re-prints the report of a previous run; NOSETUP=1 skips ghidra_scripts/XcoreElfSetup.java
# (issue mode from $s/$d mapping symbols + cp/dp) to show the plain-import baseline.
#
# For every tile image of every .xe (test/xe_extract.py):
#  1. headless import with NO -processor (ELF opinion) + auto-analysis
#  2. functions, instructions, error bookmarks, instructions in non-executable memory
#  3. decompile every function (failures, timeouts, halt_baddata)
#  4. compare every decoded instruction with LLVM's XCore (XS1) disassembler, check pc-relative
#     call/branch targets land on instructions / FUNC symbols, check the issue mode against the
#     $s/$d mapping symbols (test/real_compare.py)
#  5. images whose .xmosnote says XS2: re-import as xCORE:LE:32:XS2 and diff with the XS3 listing
#  6. images containing lib_xud: compare with the lib_xud assembly sources (linked_srccheck.py)
#  7. issue-mode handling on the xk_316 tile-0 image (lib_xud, dual issue): plain import (no
#     XcoreElfSetup) and a copy with the $s/$d mapping symbols renamed (stripped-image fallback:
#     XcoreElfSetup as post-script)
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(dirname "$HERE")
SAMPLES=$(readlink -f "${1:?usage: real-binaries.sh <sample-dir> [workdir]}")
W=${2:-${TMPDIR:-/tmp}/xcore-real}
mkdir -p "$W/elf" "$W/out"
W=$(readlink -f "$W")
[[ -e $GHIDRA_INSTALL_DIR/Ghidra/Processors/xCORE ]] || ln -sfn "$MOD" "$GHIDRA_INSTALL_DIR/Ghidra/Processors/xCORE"
[[ -f $MOD/data/languages/xcore_xs3.sla ]] || "$HERE/build.sh" | tail -1

if [[ -z ${RESULTS_ONLY:-} ]]; then
echo "== extract"
for xe in "$SAMPLES"/*.xe; do python3 -I "$HERE/xe_extract.py" "$xe" "$W/elf"; done | sed 's/^/  /'

RUN_PRE="-preScript XcoreElfSetup.java"
[[ -n ${NOSETUP:-} ]] && RUN_PRE=""
run() {   # elf [processor] [tag] [extra args...]
	local e=$1 b p=() tag=""
	b=$(basename "$e" .elf)
	[[ -n ${2:-} ]] && { p=(-processor "$2"); tag=".${2##*:}"; }
	[[ -n ${3:-} ]] && tag=".$3"
	shift $(($# < 3 ? $# : 3))
	local post=("$@")
	local proj
	proj=$(mktemp -d "$W/proj.XXXXXX")
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$proj" p -import "$e" "${p[@]}" \
		-scriptPath "$HERE;$MOD/ghidra_scripts" $RUN_PRE "${post[@]}" \
		-postScript RealCheck.java "$W/out/$b$tag.sum" "$W/out/$b$tag.lst" "$W/out/$b$tag.dec" 60 \
		-deleteProject >"$W/out/$b$tag.log" 2>&1 || echo "headless failed: $b (see $W/out/$b$tag.log)"
	rm -rf "$proj"
}
export -f run
export W HERE MOD GHIDRA_INSTALL_DIR RUN_PRE
echo "== headless import + analysis + decompile (${JOBS:-3} parallel)"
ls "$W"/elf/*.elf | xargs -P "${JOBS:-3}" -I{} bash -c 'run "$1"' _ {}
# XS2 images (per .xmosnote): also decode with the XS2 language
xs2=()
for e in "$W"/elf/*.elf; do
	[[ $(readelf -nW "$e" 2>/dev/null | grep -c 'description data: 58 53 32') -gt 0 ]] && xs2+=("$e")
done
if ((${#xs2[@]})); then
	printf '%s\n' "${xs2[@]}" | xargs -P "${JOBS:-3}" -I{} bash -c 'run "$1" xCORE:LE:32:XS2' _ {}
fi

# issue-mode experiments on the lib_xud image
X=$W/elf/app_usb_aud_xk_316_mc_1AMi2o2xxxxxx_n0_t0_1.elf
if [[ -f $X ]]; then
	python3 - "$X" "$W/elf/xk316_t0_nomap.elf.in" <<'PY'
import sys
d = open(sys.argv[1], 'rb').read()
open(sys.argv[2], 'wb').write(d.replace(b'\0$s.', b'\0_s.').replace(b'\0$d.', b'\0_d.'))
PY
	mkdir -p "$W/exp" && mv "$W/elf/xk316_t0_nomap.elf.in" "$W/exp/xk316_t0_nomap.elf"
	cp "$X" "$W/exp/xk316_t0_plain.elf"
	RUN_PRE="" run "$W/exp/xk316_t0_plain.elf" &
	RUN_PRE="" run "$W/exp/xk316_t0_nomap.elf" "" "" -postScript XcoreElfSetup.java nocpdp &
	wait
fi

fi
X=$W/elf/app_usb_aud_xk_316_mc_1AMi2o2xxxxxx_n0_t0_1.elf

echo "== results"
set +e   # report everything; a grep without matches must not end the script
for e in "$W"/elf/*.elf; do
	b=$(basename "$e" .elf)
	s=$W/out/$b.sum
	echo "-- $b ($(readelf -nW "$e" 2>/dev/null | grep -o 'description data: 58 53 3[123]' | sed 's/.* 58 53 3/XS/' | head -1))"
	[[ -s $s ]] || { echo "   no summary"; continue; }
	grep -hE '^(language|functions|instructions|bookmarks|decompiled)' "$s" | sed 's/^/   /'
	grep -h 'decompile failed' "$s" | head -5 | sed 's/^/   /'
	grep -h 'XcoreElfSetup.java>' "$W/out/$b.log" | sed 's/.*java> /   setup: /; s/ (GhidraScript).*//'
	python3 "$HERE/real_compare.py" "$e" "$W/out/$b.lst" 12 | sed 's/^/   /'
	if [[ -s $W/out/$b.XS2.lst ]]; then
		d=$(diff <(cut -f1 "$W/out/$b.lst") <(cut -f1 "$W/out/$b.XS2.lst") | grep -c '^[<>]' || true)
		echo "   XS2 language vs XS3 language: $d differing listing lines;" \
			"$(grep -h '^decompiled' "$W/out/$b.XS2.sum")"
	fi
	# lib_xud sources are from the sw_usb_audio 8.1.0 release (sln_voice ships another version)
	if [[ -d $SAMPLES/lib_xud && $b == app_usb_aud_* && $(readelf -sW "$e" 2>/dev/null | grep -c ' Pid_In$') -gt 0 ]]; then
		a=XS3
		[[ $(readelf -nW "$e" 2>/dev/null | grep -c 'description data: 58 53 32') -gt 0 ]] && a=XS2
		python3 "$HERE/linked_srccheck.py" "$e" "$W/out/$b.lst" "$SAMPLES/lib_xud" $a | head -12 | sed 's/^/   lib_xud source: /'
	fi
done
if [[ -f $X ]]; then
	echo "-- issue mode on $(basename "$X" .elf)"
	for t in plain nomap; do
		echo "   $t: $(grep -hE '^bookmarks Error/Bad|^instructions decoded' "$W/out/xk316_t0_$t.sum" | tr '\n' ' ')"
		grep -h 'XcoreElfSetup.java>' "$W/out/xk316_t0_$t.log" | sed 's/.*java> /      setup: /; s/ (GhidraScript).*//'
		python3 "$HERE/real_compare.py" "$X" "$W/out/xk316_t0_$t.lst" 0 | grep -A4 '^pc-relative' | sed 's/^/      /'
	done
fi
