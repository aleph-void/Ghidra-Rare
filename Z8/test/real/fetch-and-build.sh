#!/usr/bin/env bash
# Fetch the freely licensed Z8 sources used as real code (pinned commits, SHA-256 checked) and
# assemble them with the libasm assembler (Apache-2.0, https://github.com/tgtakaoka/libasm,
# build its cli/ with "make cli"). Nothing fetched or built here is committed.
#
#   LIBASM_ASM=/path/to/libasm/cli/asm test/real/fetch-and-build.sh <workdir>
#
# Sources:
#   89Mods/misc-computers UB8840/ (MIT, Copyright (c) 2023 Tholin): programs for the UB8840, an
#     East German Z8 clone: Blinky, DivMul, Mandel, VFD, test_6850
#   tgtakaoka/libasm test/reference/ (Apache-2.0): the assembler's Z8 and Z86C reference
#     sources, every instruction form, assembled at 0100h
# Output: <workdir>/src/*, <workdir>/bin/<name>.{hex,lst}
set -euo pipefail
W=$(readlink -m "${1:?usage: fetch-and-build.sh <workdir>}")
ASM=${LIBASM_ASM:-asm}
MC=88930ac19adbade5e0aacaeca3cdee3e5b83ba49
LA=9cd9a81cc0ee534db1cc6799638f515c7892b927
mkdir -p "$W/src" "$W/bin"
cd "$W/src"
fetch() { # url file sha256
	[[ -f $2 ]] || curl -sSfL -o "$2" "$1"
	echo "$3  $2" | sha256sum -c --quiet - || { echo "checksum mismatch: $2" >&2; exit 1; }
}
U=https://raw.githubusercontent.com/89Mods/misc-computers/$MC
fetch $U/LICENSE misc-computers-LICENSE 0c2940083747be67dc9f7fe34637375a1adeb5c29fc953663ed3ef1ba21edb8f
fetch $U/UB8840/Blinky/blinky.asm blinky.asm f703d94d82a73918ffecbadc0f0cdda08d9c07f7ac50c314e8a56539f4f358c5
fetch $U/UB8840/DivMul/divmul.asm divmul.asm 268049a3012f19b5d381f70dfcf9f61cd24bebe27aa3000ad3a379050426411b
fetch $U/UB8840/Mandel/mandel.asm mandel.asm 4804b5cc564ed65d2de61b52d22301b62aecb6a981be9a0e812276c495cd5659
fetch $U/UB8840/VFD/vfd.asm vfd.asm 1c981cbf84b09b65115065c47e205e1cff16b0fd42201d6f3c74e6991e75b4f8
fetch $U/UB8840/test_6850/test_6580.asm test_6580.asm 4b7f2c54cc90355964503d6b730faeb2c9d33b1fa56a2142fdbe4aa467ddf56c
U=https://raw.githubusercontent.com/tgtakaoka/libasm/$LA
fetch $U/LICENSE.md libasm-LICENSE.md 519fce32ce161910654748207f1a993e4572f5b58bd0cf448f31261101f61240
fetch $U/test/reference/test_z8.asm test_z8.asm 63a8beebf07f9ef1e7e8ff1508e5d06520655a9eddf0b1af0469942a26925f68
fetch $U/test/reference/test_z86c.asm test_z86c.asm af6b7c1592714f5141c4d62216cea9cbe159789224bfdb84695d2c5963afde95
fetch $U/test/reference/test_z8.inc test_z8.inc 6f4b9c7f476b6924225dcbe8825469249a37afd1084af7cf8cffecb56f1b0a58
fetch $U/test/reference/test_z86.inc test_z86.inc 915705fb656af8b037a022b4f7bc96f15017e2b09e1cc8097c3cc44da42b1e72
fetch $U/test/reference/test_z86_rp00.inc test_z86_rp00.inc 9cb76bec7504ee2064ec0e218cff38cb340e7044333314c4f0ebd9086fca38d4
fetch $U/test/reference/test_z86_rp20.inc test_z86_rp20.inc f9a62c88826af03bdd2fe2266d69a212c6b128018c0dde5a444ef9f202f57b5e
fetch $U/test/reference/test_z86c.inc test_z86c.inc 3480edbfc1da97c0f4db41522b674ba45c7c0260ea5716799a03ae8e2fc32856
for f in blinky divmul mandel vfd test_6580 test_z8 test_z86c; do
	"$ASM" -C Z86C -o "$W/bin/$f.hex" -l "$W/bin/$f.lst" "$f.asm" >"$W/bin/$f.log" 2>&1 \
		|| { cat "$W/bin/$f.log" >&2; exit 1; }
	if grep -qi error "$W/bin/$f.log"; then cat "$W/bin/$f.log" >&2; exit 1; fi
done
ls "$W/bin"/*.hex
