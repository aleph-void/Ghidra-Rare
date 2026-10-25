#!/usr/bin/env bash
# Compile the module's Java (SnesRomLoader) into lib/65816.jar so a Ghidra
# install that has this directory linked/copied under Ghidra/Processors/65816
# picks it up (Ghidra loads <module>/lib/*.jar).  The release route is
# `gradle buildExtension`; this is the quick path for the test harness.
#   GHIDRA_INSTALL_DIR=... test/build-jar.sh
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
MOD=$(cd "$(dirname "$0")/.." && pwd)
G=$GHIDRA_INSTALL_DIR/Ghidra
CP=$(find "$G/Framework" "$G/Features/Base" -name '*.jar' ! -name '*-src*' | tr '\n' ':')
JAVAC=javac
[[ -n ${JAVA_HOME:-} ]] && JAVAC=$JAVA_HOME/bin/javac
OUT=$(mktemp -d "${TMPDIR:-/tmp}/65816-jar.XXXXXX")
trap 'rm -rf "$OUT"' EXIT
"$JAVAC" -nowarn --release 21 -cp "$CP" -d "$OUT" $(find "$MOD/src/main/java" -name '*.java')
mkdir -p "$MOD/lib"
JAR=jar
[[ -n ${JAVA_HOME:-} ]] && JAR=$JAVA_HOME/bin/jar
"$JAR" cf "$MOD/lib/65816.jar" -C "$OUT" .
echo "built $MOD/lib/65816.jar"
