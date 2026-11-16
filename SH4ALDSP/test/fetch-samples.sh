#!/usr/bin/env bash
# Fetch third-party Casio fx-CG add-ins (.g3a) from their GitHub releases, pinned by URL and
# SHA-256; nothing is committed.  All are freely licensed:
#   duarteapcoelho/prizm_racing v1.4 (MIT)       racing.zip -> racing.g3a
#   tswilliamson/nesizm v1.00 (MIT)              nesizm_v1.0.zip -> nesizm.g3a
#   oxixes/bad-apple-cg50 1.1.0 (Unlicense)      BadApple.g3a
#   Adamskye/BadAppleCG50 v1 (MIT)               BACG50.g3a
#   test/fetch-samples.sh <workdir>     output: <workdir>/g3a/*.g3a
set -euo pipefail
W=$(readlink -m "$1"); mkdir -p "$W/dl" "$W/g3a"
fetch() {   # <url> <sha256> <file>
	if [[ ! -f $W/dl/$3 ]] || ! echo "$2  $W/dl/$3" | sha256sum -c --status; then
		curl -fsSL -o "$W/dl/$3.part" "$1"
		echo "$2  $W/dl/$3.part" | sha256sum -c --status || { echo "SHA-256 mismatch: $3" >&2; exit 1; }
		mv "$W/dl/$3.part" "$W/dl/$3"
	fi
}
GH=https://github.com
fetch $GH/duarteapcoelho/prizm_racing/releases/download/v1.4/racing.zip \
	a2cd1da8e423d9737133d6f6c4ec4aedd97a7a4db5a7914b6eb62cf9fd48df74 racing.zip
fetch $GH/tswilliamson/nesizm/releases/download/v1.00/nesizm_v1.0.zip \
	9dc94ba57665e049e08fea3045ce8c813eedd2b0ef0848ffe72f6a7871cadb56 nesizm_v1.0.zip
fetch $GH/oxixes/bad-apple-cg50/releases/download/1.1.0/BadApple.g3a \
	fb52195810523205cec4b82637ae0f00f475c68a7e05f0b3bfb9f234fa775bd7 BadApple.g3a
fetch $GH/Adamskye/BadAppleCG50/releases/download/v1/BACG50.g3a \
	bbe3c6e8d69f29c9e0198b08378a6eaf96eacd1cc92fba91fe4ea639e3059183 BACG50.g3a
unzip -o -q -j "$W/dl/racing.zip" racing.g3a -d "$W/g3a"
unzip -o -q -j "$W/dl/nesizm_v1.0.zip" nesizm.g3a -d "$W/g3a"
cp "$W/dl/BadApple.g3a" "$W/dl/BACG50.g3a" "$W/g3a/"
ls -l "$W"/g3a
