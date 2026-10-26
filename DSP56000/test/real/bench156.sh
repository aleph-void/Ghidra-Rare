#!/usr/bin/env bash
# DSP56156 real-code check: Motorola's DSP56100 family benchmark programs (DSP56100 Family
# Manual, Appendix B), assembled with Motorola's ASM56100 (DOS build, run under headless
# dosbox as a black box), compared statement by statement with Ghidra and with MAME.
#   test/real/bench156.sh <workdir>
# Needs curl, pdftotext, unzip, dosbox, unidasm and GHIDRA_INSTALL_DIR. Downloads are pinned
# by SHA-256; nothing downloaded or built is committed.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(cd "$HERE/.." && pwd)
W=$(readlink -m "$1"); mkdir -p "$W/dl" "$W/src" "$W/asm"
fetch() {  # url sha256 file
	[[ -s $3 ]] || curl -sfL --max-time 600 -o "$3" "$1"
	echo "$2  $3" | sha256sum -c --quiet
}
B=https://bitsavers.mirrorservice.org/components/motorola/56000
fetch "$B/56100/1994_DSP56100_Family_Manual.pdf" \
	d801b6c0f8dd5ed3ba0f4a99486a4ae5a4595a4fee6ab99d26f16a456038ba1a "$W/dl/fm100.pdf"
fetch "$B/dsp56100Simulator.zip" \
	edd0c3536f1bc232360fcc4f137ac3be06e9746b5ff0baa434fd56ed04f06052 "$W/dl/sim.zip"
[[ -s $W/dl/fm100.txt ]] || pdftotext -layout "$W/dl/fm100.pdf" "$W/dl/fm100.txt"
[[ -s $W/asm/ASM56100.EXE ]] || {
	unzip -qo "$W/dl/sim.zip" 'dsp56100Simulator/dos/BIN/ASM56100.EXE' 'dsp56100Simulator/dos/BIN/DOS4GW.EXE' -d "$W/dl"
	cp "$W/dl/dsp56100Simulator/dos/BIN/ASM56100.EXE" "$W/dl/dsp56100Simulator/dos/BIN/DOS4GW.EXE" "$W/asm/"
}
python3 "$HERE/extract156.py" "$W/dl/fm100.txt" "$W/src" > "$W/src/list.txt"
asm() {  # file.asm -> file.lst (ASM56100 under dosbox)
	local d; d=$(mktemp -d "$W/asm/run.XXXXXX")
	cp "$W/asm/ASM56100.EXE" "$W/asm/DOS4GW.EXE" "$d/"; cp "$1" "$d/T.ASM"
	printf '[cpu]\ncycles=max\n[autoexec]\nmount c %s\nc:\nASM56100.EXE -lT.LST T.ASM > OUT.TXT\nexit\n' "$d" > "$d/db.conf"
	SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy timeout 300 dosbox -conf "$d/db.conf" -noconsole >/dev/null 2>&1 || true
	cp "$d/T.LST" "${1%.asm}.lst"; rm -rf "$d"
}
rc=0
: > "$W/cmp.txt"
while read -r f; do
	b=${f%.asm}
	[[ -s $b.lst ]] || asm "$f"
	python3 "$HERE/listing156.py" image "$b.lst" "$b.img"
	"$T/ghidra-dis.sh" DSP56000:BE:16:DSP56156 "$b.img" "$b.gh" 0 0
	python3 "$HERE/listing156.py" compare "$b.lst" "$b.gh" >> "$W/cmp.txt"
	python3 -c "import sys;d=open(sys.argv[1],'rb').read();open(sys.argv[2],'wb').write(b''.join(d[i+1:i+2]+d[i:i+1] for i in range(0,len(d),2)))" "$b.img" "$b.m.img"
	unidasm "$b.m.img" -arch dsp56156 > "$b.mame"
	python3 "$T/compare.py" --arch dsp56156 --stride 1 "$b.mame" "$b.gh" "$(basename "$b")" > "$b.mcmp" || rc=1
done < "$W/src/list.txt"
grep -v "statements" "$W/cmp.txt" || true
grep "statements" "$W/cmp.txt" | awk '{s+=$2; i+=$4; d+=$6; b+=$9; sh+=$13}
	END {printf "benchmarks vs ASM56100 listings: %d statements, %d identical, %d different, %d boundary, %d shadowed\n", s, i, d, b, sh; exit (d+b) > 0}' || rc=1
python3 "$T/summarize.py" "$W"/src/*.mcmp
# auto-analysis and decompilation of every benchmark image (zero-filled around the code, so
# the pspec's vector entries in the fill also become functions)
i=0
while read -r f; do
	b=${f%.asm}; i=$((i + 1))
	(
		P=$(mktemp -d "${TMPDIR:-/tmp}/dsp56156-ana.XXXXXX")
		"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$P" p -import "$b.img" -loader BinaryLoader \
			-loader-baseAddr 0 -processor DSP56000:BE:16:DSP56156 -scriptPath "$T" \
			-postScript DspRealCheck.java "$b.ana" -deleteProject > "$P.log" 2>&1 || true
		echo "$(basename "$b"): $(head -2 "$b.ana/summary.txt" 2>/dev/null | tr '\n' ' ')" > "$b.anatxt"
		rm -rf "$P" "$P.log"
	) &
	(( i % ${JOBS:-4} == 0 )) && wait
done < "$W/src/list.txt"
wait
python3 "$HERE/summary.py" "$W"/src/*.anatxt | head -1 || true
exit $rc
