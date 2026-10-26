#!/usr/bin/env bash
# DSP56000 real code: Motorola's freely distributed DSP56000 software (the Motorola DSP
# bulletin-board archive mirrored on bitsavers: "available to user without any license fee or
# royalty"), fetched by pinned URL + SHA-256 and never committed.
#   test/real/fetch-and-build.sh <workdir>
# Produces <workdir>/pairs.txt: "<prog.lod> <prog.lst>" lines for
#   - the LOD files Motorola built and shipped with listings in 56000.zip (third-party
#     binaries), and
#   - every source of the archives that Motorola's DSP56000 Assembler 3.1 (ASM56000.EXE from
#     DSPBIN_3.1, run under headless dosbox as a black box) assembles without errors into P
#     code (absolute LOD + listing).
# and <workdir>/lods.txt: the shipped LOD files without a listing.
# Needs curl, unzip, dosbox (the assembler step is skipped without it).
set -euo pipefail
W=$(readlink -m "$1"); mkdir -p "$W/dl" "$W/src" "$W/asm"
B=https://bitsavers.mirrorservice.org/components/motorola/56000
fetch() {  # url sha256 file
	[[ -s $3 ]] || curl -sfL --max-time 600 -o "$3" "$1"
	echo "$2  $3" | sha256sum -c --quiet
}
fetch "$B/DSPBIN_3.1/dspbin.zip" 96c39092b81371b5f4ef072bb2b45f2729469f29194d85fdac04332082a29e4b "$W/dl/dspbin.zip"
while read -r name sha; do
	fetch "$B/56K_BBS/$name.zip" "$sha" "$W/dl/$name.zip"
done <<'EOF'
56000 8a03cc22a2d53213a447335032be54e2e9c3238be285046207748bac69c30974
fft 9e4e788ada485e1a3be37a7ce61519d567152ab3ced449e2a7e877c233fb4bea
flts 228be4abcaaa133d87761c51b78eeec4880a3693dfc7a2fc32eff0c0b169854f
float fd2049f9db87f0cb0de292f297c93739a654fc8d3b1f7749e0dbc1a91fc49595
fntns 8bb95a274dbcb8af78ef879a018df20bd9bde07d452a922a19fe5ce0432b7d98
bench 55d7d933a703a41a032a8b6cdc87834567ca9b90c245d7cedd2f508ebe789af3
speech 03d6888523fb3784ecfaa7e6df20e156710f46c3a9ca60a1b8d8e935c0c47f18
lattice ab80b0e7fefcfa658a8c63cea3a1643be980cf0831e7b2c472566e184528a9a8
matrix e3845045bb8e590ae449de94e21da135bb96ba12a29a7645f376cb162bbf30ac
srt-srch b21dd383699c78e3a221038ea69e4aeeb67d113a9ffdc39f6aba26e0979261f1
codec 6dd8f6f8b8d965ca79a237b70c70ff52662de84381e62cdb0394faa8e1161581
dtmf b9144b27d3ad5f38693c7bf98d431bba2c5e465d3968483844786953936be3a9
viterbi 92ddcfe02427825135bef3047395d1affe2558c1843e8c4be6023feba22a4fff
reed-sol e28e92f982547d534a894dab7eb5bfb9ca09b1fe884869d3a351459def929a01
sqrt 63a61a675afda8588b6b524a80afa5cfcec2d93d13ad6d819e6728d39ce3886f
sioeq f6081fad8c7d21c9fd42e4b93a60fbe7771bfc02176ab47c20c1058a9db2027c
EOF
# shipped binaries
[[ -d $W/src/56000 ]] || { unzip -qo "$W/dl/56000.zip" -d "$W/src"; chmod -R u+rwX "$W/src/56000"; }
: > "$W/pairs.txt"; : > "$W/lods.txt"
while read -r lod; do
	# skip files that hold no data (an empty 48COMPEQ.LOD) or are not LOD files (DATA.LOD)
	[[ $(head -c 6 "$lod") == _START ]] && grep -q "^_DATA" "$lod" || continue
	lst=${lod%.*}.LST
	if [[ -f $lst ]]; then echo "$lod $lst" >> "$W/pairs.txt"; else echo "$lod" >> "$W/lods.txt"; fi
done < <(find "$W/src/56000" -name '*.LOD' | sort)
# sources assembled with ASM56000
command -v dosbox >/dev/null || { echo "dosbox not found: assembler step skipped" >&2; exit 0; }
[[ -s $W/asm/ASM56000.EXE ]] || { unzip -qo -j "$W/dl/dspbin.zip" 'BIN/ASM56000.EXE' -d "$W/asm"; }
for z in fft flts float fntns bench speech lattice matrix srt-srch codec dtmf viterbi reed-sol sqrt sioeq; do
	d=$W/src/$z
	if [[ ! -d $d ]]; then mkdir -p "$d"; unzip -qo -LL "$W/dl/$z.zip" -d "$d"; chmod -R u+rwX "$d"; fi
done
[[ -d $W/src/m56k ]] || cp -r "$W/src/56000" "$W/src/m56k"
python3 - "$W" <<'PY'
import os, re, shutil, sys
w = sys.argv[1]
# The sources include library routines as 'dsplib:name' (a VAX logical name) or
# '\dsp56000.asm\name': every source directory gets a copy of each library .asm file, and
# the copies' include statements name the plain file (only the working copies change).
lib = {}
for root, dirs, files in os.walk(os.path.join(w, "src")):
    if os.path.relpath(root, w + "/src").split(os.sep)[0] == "56000":
        continue
    for f in files:
        if f.lower().endswith(".asm"):
            lib.setdefault(f.lower(), os.path.join(root, f))
for root, dirs, files in os.walk(os.path.join(w, "src")):
    if os.path.relpath(root, w + "/src").split(os.sep)[0] == "56000" or root == w + "/src":
        continue
    if not any(f.lower().endswith(".asm") for f in files):
        continue
    orig = os.path.join(root, ".originals")
    if not os.path.exists(orig):
        open(orig, "w").write("\n".join(sorted(f for f in files if f.lower().endswith(".asm"))) + "\n")
    have = {f.lower() for f in files}
    for name, path in lib.items():
        if name not in have:
            shutil.copy(path, os.path.join(root, name))
    for f in os.listdir(root):
        if f.lower().endswith(".asm"):
            p = os.path.join(root, f)
            t = open(p, errors="replace").read()
            t2 = re.sub(r"(?i)(include\s+')(?:dsplib:|\\dsp56000\.asm\\)", r"\1", t)
            if t2 != t:
                open(p, "w").write(t2)
lines = ["@echo off"]
for top in sorted(os.listdir(w + "/src")):
    if top == "56000":
        continue
    for root, dirs, files in os.walk(os.path.join(w, "src", top)):
        rel = os.path.relpath(root, w + "/src").replace("/", "\\")
        orig = os.path.join(root, ".originals")
        if not os.path.exists(orig):
            continue
        for f in open(orig).read().split():
                b = f[:-4]
                lines.append("cd \\%s" % rel)
                lines.append("c:\\asm56000 -a -b%s.lod -l%s.lst %s > %s.err" % (b, b, f, b))
lines += ["cd \\", "exit"]
open(w + "/src/RUN.BAT", "w").write("\r\n".join(lines) + "\r\n")
PY
cp "$W/asm/ASM56000.EXE" "$W/src/"
if [[ ! -f $W/src/.assembled ]]; then
	printf '[cpu]\ncycles=max\n[autoexec]\nmount c %s\nc:\nRUN.BAT\n' "$W/src" > "$W/asm/db.conf"
	SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy timeout 3600 dosbox -conf "$W/asm/db.conf" -noconsole >/dev/null 2>&1 || true
	touch "$W/src/.assembled"
fi
find "$W/src" -path "$W/src/56000" -prune -o -iname '*.err' -print | sort | while read -r e; do
	b=${e%.*}
	lod=$(ls "$b".[lL][oO][dD] 2>/dev/null | head -1 || true); lst=$(ls "$b".[lL][sS][tT] 2>/dev/null | head -1 || true)
	[[ -n $lod && -n $lst ]] || continue
	grep -q "ERROR" "$e" && continue
	grep -q "^_DATA P" "$lod" || continue
	echo "$lod $lst" >> "$W/pairs.txt"
done
# the per-topic archives repeat sources of 56000.zip: keep one of each identical LOD file
python3 - "$W/pairs.txt" <<'PY'
import hashlib, sys
seen, out = set(), []
for line in open(sys.argv[1]):
    h = hashlib.sha256(open(line.split()[0], "rb").read()).hexdigest()
    if h not in seen:
        seen.add(h)
        out.append(line)
open(sys.argv[1], "w").writelines(out)
PY
echo "$(wc -l < "$W/pairs.txt") LOD/listing pairs, $(wc -l < "$W/lods.txt") LOD files without listing"
