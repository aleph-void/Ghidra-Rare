#!/usr/bin/env bash
# Compile the module's Java (SASS_ElfExtension) into lib/SASS.jar so a Ghidra
# install that has this directory linked under Ghidra/Processors/SASS picks it
# up.  The release route is `gradle buildExtension`.
#   GHIDRA_INSTALL_DIR=... test/build-jar.sh
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
MOD=$(cd "$(dirname "$0")/.." && pwd)
G=$GHIDRA_INSTALL_DIR/Ghidra
CP=$(find "$G/Framework" "$G/Features/Base" -name '*.jar' ! -name '*-src*' | tr '\n' ':')
JAVAC=javac; JAR=jar
if [[ -n ${JAVA_HOME:-} ]]; then JAVAC=$JAVA_HOME/bin/javac; JAR=$JAVA_HOME/bin/jar; fi
OUT=$(mktemp -d "${TMPDIR:-/tmp}/sass-jar.XXXXXX")
trap 'rm -rf "$OUT"' EXIT
"$JAVAC" -nowarn --release 21 -cp "$CP" -d "$OUT" $(find "$MOD/src/main/java" -name '*.java')
mkdir -p "$MOD/lib"
"$JAR" cf "$MOD/lib/SASS.jar" -C "$OUT" .
echo "built $MOD/lib/SASS.jar"
