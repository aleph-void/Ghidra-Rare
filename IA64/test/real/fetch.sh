#!/usr/bin/env bash
# Fetch the freely licensed IA-64 test binaries (Debian 7 "wheezy" ia64 packages from
# archive.debian.org), check their pinned SHA-256 and unpack them:
#   fetch.sh <workdir>      ->  <workdir>/dl/*.deb, <workdir>/x/<package>/...
# Nothing fetched here is committed to the repository.
set -euo pipefail
W=$(readlink -m "${1:?usage: fetch.sh <workdir>}")
mkdir -p "$W/dl" "$W/x"
B=https://archive.debian.org/debian/pool/main
while read -r sum path; do
	f=$W/dl/$(basename "$path")
	[[ -f $f ]] || curl -sSfL -o "$f" "$B/$path"
	echo "$sum  $f" | sha256sum -c --quiet - || { echo "checksum mismatch: $f" >&2; exit 1; }
	n=$(basename "$path" .deb)
	if [[ ! -d $W/x/$n ]]; then
		mkdir -p "$W/x/$n"
		(cd "$W/x/$n" && ar x "$f" && tar xf data.tar.*)
	fi
done <<'LIST'
be20451e7424ba0e155aaa71fa68748205afd670abfd1d079e74e7c6f5e989f5 z/zlib/zlib1g_1.2.7.dfsg-13_ia64.deb
6d7780f4987ce0d4d91ccba17e202e67e67bf8a7ade3a89fb979b82bdb695a5f z/zlib/zlib1g-dbg_1.2.7.dfsg-13_ia64.deb
10909634c93db756ea6bc8d0b6806b1ae6bc3725ba3475c4f76972e78e2f7b5a b/busybox/busybox_1.20.0-7_ia64.deb
f95050adf85e014f7619ffe1ad85773f1fed64112464cd1ed142139b36d46d15 b/busybox/busybox-static_1.20.0-7_ia64.deb
8d63290cd8f67a1ac024ef0c23da9158227c2a51b38abac9382973685a344c0b g/gzip/gzip_1.5-1.1_ia64.deb
9a920c6667d30d6f2fa1bdf212defdd0d78ca9725c962b5fc35642df46391ee5 b/bc/bc_1.06.95-2_ia64.deb
87217fd727a4e7b0998586009a45420eca83d597516f3b30020799762ce95aab s/sqlite3/libsqlite3-0_3.7.13-1+deb7u2_ia64.deb
22dcc933fa91afe837dd36df33b375408a9d779ab223aa005846ce08292506c3 e/eglibc/libc6.1_2.13-38+deb7u10_ia64.deb
LIST
echo "fetched into $W"
