#!/usr/bin/env bash
# Build Ghidra-Rare's processor modules from this checkout and install them into a Ghidra install:
#   tools/install.sh [options] <ghidra install dir>        (or set GHIDRA_INSTALL_DIR)
#
# By default this installs the modules written here (the "Modules" table in README.md). Add
# --community to also install the community modules (git submodules under community/; check them
# out first with `git submodule update --init`).
#
# Each module is built as an extension zip with tools/build-module.sh (so the SLEIGH specs are
# compiled by that Ghidra's own compiler) and unpacked into <ghidra>/Ghidra/Extensions, where every
# user of that install picks it up. Restart Ghidra afterwards. Building needs a full JDK (javac):
# JDK 21+ for Ghidra 12.1, JDK 25 for Ghidra 12.2; point JAVA_HOME at it.
#
# Options:
#   --community        also install the community modules
#   --only A,B,...     install only the named modules (names as in README.md, e.g. PRU,Z8,SM83)
#   --zips DIR         install prebuilt zips from DIR (e.g. downloaded from the Releases page)
#                      instead of building; they must be built for this Ghidra version
#   --dest DIR         extension directory to install into (default: <ghidra>/Ghidra/Extensions;
#                      use ~/.config/ghidra/ghidra_<version>_PUBLIC/Extensions for one user only)
#   --list             print the module names and exit
#   -h, --help         show this help
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)

usage() { sed -n '2,/^set -euo/{/^set -euo/d;s/^# \{0,1\}//;p}' "$0"; }

COMMUNITY=0
ONLY=
ZIPS=
DEST=
LIST=0
while (($#)); do
	case $1 in
	--community) COMMUNITY=1 ;;
	--only) ONLY=${2:?--only needs a list}; shift ;;
	--zips) ZIPS=${2:?--zips needs a directory}; shift ;;
	--dest) DEST=${2:?--dest needs a directory}; shift ;;
	--list) LIST=1 ;;
	-h | --help) usage; exit 0 ;;
	--*) echo "unknown option $1" >&2; usage >&2; exit 2 ;;
	*) break ;;
	esac
	shift
done

# Module lists: "name<TAB>source dir<TAB>build-module.sh options".
own=()
for manifest in "$ROOT"/*/Module.manifest; do
	dir=$(dirname "$manifest")
	own+=("$(basename "$dir")	$dir	")
done
community=()
while IFS=$'\t' read -r name path sub opts; do
	extra="--standard --name $name"
	[[ ,${opts:-}, == *,keep-build,* ]] && extra+=" --keep-build"
	community+=("$name	$ROOT/$path/$sub	$extra")
done < <(grep -v '^#' "$ROOT/community/modules.tsv")

if ((LIST)); then
	echo "Modules:";           printf '  %s\n' "${own[@]%%	*}"
	echo "Community modules:"; printf '  %s\n' "${community[@]%%	*}"
	exit 0
fi

GHIDRA=${1:-${GHIDRA_INSTALL_DIR:-}}
if [[ -z $GHIDRA ]]; then
	echo "error: pass the Ghidra install dir or set GHIDRA_INSTALL_DIR" >&2
	usage >&2
	exit 2
fi
GHIDRA=$(cd "$GHIDRA" && pwd)
PROPS=$GHIDRA/Ghidra/application.properties
[[ -f $PROPS ]] || { echo "error: $GHIDRA is not a Ghidra install (no Ghidra/application.properties)" >&2; exit 1; }
VERSION=$(sed -n 's/^application.version=//p' "$PROPS")
RELEASE=$(sed -n 's/^application.release.name=//p' "$PROPS")
DEST=${DEST:-$GHIDRA/Ghidra/Extensions}
mkdir -p "$DEST"
DEST=$(cd "$DEST" && pwd)
[[ -w $DEST ]] || { echo "error: $DEST is not writable (try sudo, or --dest)" >&2; exit 1; }

selected=("${own[@]}")
((COMMUNITY)) && selected+=("${community[@]}")
if [[ -n $ONLY ]]; then
	selected=()
	IFS=, read -ra want <<<"$ONLY"
	for w in "${want[@]}"; do
		found=
		for m in "${own[@]}" "${community[@]}"; do
			[[ ${m%%	*} == "$w" ]] && { selected+=("$m"); found=1; break; }
		done
		[[ -n $found ]] || { echo "error: no module named '$w' (see --list)" >&2; exit 2; }
	done
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
ZIPDIR=$TMP/zips
mkdir -p "$ZIPDIR"

echo "Installing ${#selected[@]} module(s) for Ghidra $VERSION into $DEST"
failed=()
installed=()
for m in "${selected[@]}"; do
	IFS=$'\t' read -r name src opts <<<"$m"
	if [[ -n $ZIPS ]]; then
		zip=$(ls -t "$ZIPS"/ghidra_"${VERSION}"_"${RELEASE}"_*_"$name".zip 2>/dev/null | head -1 || true)
		if [[ -z $zip ]]; then
			echo "!! $name: no ghidra_${VERSION}_${RELEASE}_*_$name.zip in $ZIPS" >&2
			failed+=("$name"); continue
		fi
	else
		if [[ ! -f $src/Module.manifest && ! -d $src/data/languages ]]; then
			echo "!! $name: $src is empty; run 'git submodule update --init' first" >&2
			failed+=("$name"); continue
		fi
		if [[ -z $opts ]]; then
			# Build the repository's own modules from a copy: build-module.sh compiles .sla files in
			# place, and the working tree's must stay in the format of the Ghidra used for development.
			# The directories left out are ones the modules' build.gradle excludes from the zip anyway.
			copy=$TMP/src/$name
			mkdir -p "$copy"
			tar -C "$src" --exclude=./build --exclude=./dist --exclude=./lib --exclude=./.gradle \
				--exclude=./test --exclude=./tests --exclude=./tools --exclude=./gen \
				--exclude=./scripts --exclude=./spec -cf - . | tar -C "$copy" -xf -
			src=$copy
		fi
		# shellcheck disable=SC2086  # opts is a list of options
		if ! "$ROOT/tools/build-module.sh" $opts "$GHIDRA" "$src" "$ZIPDIR"; then
			echo "!! $name: build failed" >&2
			failed+=("$name"); continue
		fi
		zip=$(ls -t "$ZIPDIR"/ghidra_"${VERSION}"_*_"$name".zip | head -1)
	fi
	# Extension zips hold one top-level directory named after the extension.
	top=$(unzip -Z1 "$zip" | head -1 | cut -d/ -f1)
	if [[ -z $top || $top != "$name" ]]; then
		echo "!! $name: unexpected layout in $(basename "$zip") (top-level '$top')" >&2
		failed+=("$name"); continue
	fi
	rm -rf "${DEST:?}/$top"
	unzip -q "$zip" -d "$DEST"
	echo "installed $name"
	installed+=("$name")
done

# The same module loaded twice (from here and from a symlink in Ghidra/Processors, or from the
# other extension directory) stops Ghidra from starting; warn about each one found.
USER_EXT=${XDG_CONFIG_HOME:-$HOME/.config}/ghidra/ghidra_${VERSION}_${RELEASE}/Extensions
[[ $(uname) == Darwin ]] && USER_EXT=$HOME/Library/ghidra/ghidra_${VERSION}_${RELEASE}/Extensions
clashes=()
for name in ${installed[@]+"${installed[@]}"}; do
	[[ -e $GHIDRA/Ghidra/Processors/$name ]] && clashes+=("$GHIDRA/Ghidra/Processors/$name")
	for other in "$GHIDRA/Ghidra/Extensions" "$USER_EXT"; do
		[[ $other != "$DEST" && -e $other/$name ]] && clashes+=("$other/$name")
	done
done

echo
echo "Installed ${#installed[@]} module(s) into $DEST."
if ((${#failed[@]})); then
	echo "Failed: ${failed[*]}" >&2
fi
if ((${#clashes[@]})); then
	echo
	echo "warning: these copies of the same modules would also be loaded; remove them or Ghidra" >&2
	echo "         will refuse to start (duplicate module names):" >&2
	printf '           %s\n' "${clashes[@]}" >&2
fi
echo "Restart Ghidra to load them."
((${#failed[@]} == 0))
