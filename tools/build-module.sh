#!/usr/bin/env bash
# Build one processor module as an extension zip for one Ghidra install:
#   tools/build-module.sh [--standard --name <Name>] <ghidra install dir> <module dir> [outdir]
# SLEIGH specs are compiled with that install's compiler first, so the zip ships .sla files in the
# format its Ghidra version reads.
#
# --keep-build (with --standard) keeps the module's own Gradle build files instead of writing this
# repository's build.gradle: for modules whose code needs more than the plain extension build (for
# example a Kotlin module with library dependencies). The module's build must produce
# dist/ghidra_<version>_PUBLIC_*_<Name>.zip like buildExtension.gradle does.
#
# --standard builds a copy of the module with this repository's build.gradle and
# version=@extversion@. Upstream forks use it: their own build files are missing, pinned to another
# Ghidra version or include development folders. --name sets the extension name (default: the
# module directory's name).
set -euo pipefail
STANDARD=0
KEEP_BUILD=0
NAME=
while [[ ${1:-} == --* ]]; do
	case $1 in
	--standard) STANDARD=1; shift ;;
	--keep-build) KEEP_BUILD=1; shift ;;
	--name) NAME=$2; shift 2 ;;
	*) echo "unknown option $1" >&2; exit 2 ;;
	esac
done
GHIDRA=$(cd "${1:?usage: build-module.sh [--standard --name N] <ghidra dir> <module dir> [outdir]}" && pwd)
SRC=$(cd "${2:?module dir}" && pwd)
mkdir -p "${3:-dist}"
OUT=$(cd "${3:-dist}" && pwd)
NAME=${NAME:-$(basename "$SRC")}
VERSION=$(sed -n 's/^application.version=//p' "$GHIDRA/Ghidra/application.properties")

# Ghidra 12 bundles a Gradle wrapper pinned to a compatible Gradle; fall back to gradle on PATH.
GRADLE=gradle
[[ -x "$GHIDRA/support/gradle/gradlew" ]] && GRADLE="$GHIDRA/support/gradle/gradlew"

DIR=$SRC
if ((STANDARD)); then
	WORK=$(mktemp -d)
	trap 'rm -rf "$WORK"' EXIT
	DIR=$WORK/$NAME
	mkdir -p "$DIR"
	tar -C "$SRC" --exclude=.git --exclude=.github --exclude=build --exclude=dist -cf - . | tar -C "$DIR" -xf -
	if ((!KEEP_BUILD)); then
	cat > "$DIR/build.gradle" <<'EOF'
// Written by Ghidra-Rare's tools/build-module.sh --standard.
def ghidraInstallDir = System.env.GHIDRA_INSTALL_DIR
if (!ghidraInstallDir) {
	throw new GradleException("GHIDRA_INSTALL_DIR is not defined!")
}
apply from: new File(ghidraInstallDir).getCanonicalPath() + "/support/buildExtension.gradle"
copyDependencies.enabled = false
buildExtension {
	exclude 'test/**', 'tests/**', 'tools/**', 'docs/**', 'scripts/**'
}
EOF
	fi
	if [[ -f "$DIR/extension.properties" ]]; then
		sed -i 's/^version=.*/version=@extversion@/' "$DIR/extension.properties"
	else
		printf 'name=%s\ndescription=%s processor module\nauthor=see README and LICENSE\ncreatedOn=\nversion=@extversion@\n' \
			"$NAME" "$NAME" > "$DIR/extension.properties"
	fi
	touch "$DIR/Module.manifest"
fi

echo "== $NAME (Ghidra $VERSION)"
# One spec per JVM: compiling several large specs in one run has exhausted memory.
for spec in "$DIR"/data/languages/*.slaspec; do
	"$GHIDRA/support/sleigh" "$spec"
done
(cd "$DIR" && GHIDRA_INSTALL_DIR="$GHIDRA" "$GRADLE" --no-daemon -q buildExtension)
zip=$(ls -t "$DIR"/dist/ghidra_"${VERSION}"_PUBLIC_*_"$NAME".zip | head -1)
cp "$zip" "$OUT/"
echo "built $(basename "$zip")"
