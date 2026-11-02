#!/usr/bin/env bash
# Build the real-code test binaries: Telink tc_platform_sdk (Apache-2.0) B85 driver demos, pinned commit,
# compiled with the Telink tc32 toolchain, then run real-check.sh on every ELF.
#   TC32_TOOLCHAIN=<dir with bin/tc32-elf-gcc> GHIDRA_INSTALL_DIR=... test/real-build.sh <workdir>
# The SDK links Telink's prebuilt chip/B85/drivers/lib/libdriver.a, which is part of the Apache-2.0 repository.
# Nothing built here is committed.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "${1:?workdir}"); mkdir -p "$W"
TC=${TC32_TOOLCHAIN:-$HOME/.Telink_Tools/tc32}
export TC32_OBJDUMP=${TC32_OBJDUMP:-$TC/bin/tc32-elf-objdump}
URL=https://github.com/telink-semi/tc_platform_sdk.git
SHA=19fbf0cd289e558a4c299734380746e91ebdcd3f
if [[ ! -d $W/sdk/.git ]]; then git clone -q "$URL" "$W/sdk"; fi
git -C "$W/sdk" checkout -q "$SHA"
[[ $(git -C "$W/sdk" rev-parse HEAD) == "$SHA" ]] || { echo "SDK commit mismatch"; exit 1; }
cmake -S "$W/sdk" -B "$W/build" -G Ninja -DPROJECT_NAME=B85_Driver_Demo "-DTOOLCHAIN_NAME=TC32-GCC Toolchain" \
	-DTOOLCHAIN_PATH="$TC" -DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY >"$W/cmake.log" 2>&1
ninja -C "$W/build" -k 0 >"$W/ninja.log" 2>&1 || true   # one demo (USB host) does not build at this SDK commit
mkdir -p "$W/real"
n=0 bad=0
for e in "$W"/build/*.elf; do
	n=$((n + 1))
	"$HERE/real-check.sh" "$e" "$W/real" TC32:LE:32:default > "$W/real/$(basename "$e" .elf).out" 2>&1 || bad=1
	tail -1 "$W/real/$(basename "$e" .elf).out"
done
echo "real code: $n ELF files"
grep -h "^decompile:" "$W"/real/*.summary | awk '{ok+=$2; f+=$4; t+=$6; b+=$(NF-3)} END {print "decompile totals: " ok " ok, " f " failed, " t " timeouts, " b " with bad data"}'
grep -h "^== " "$W"/real/*.out | awk '{n+=$3; s+=$6; d+=$10} END {print "instructions: " n ", identical to objdump: " s ", different: " d}'
exit $bad
