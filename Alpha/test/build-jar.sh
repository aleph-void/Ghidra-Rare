#!/usr/bin/env bash
# Compile the module's Java (the ELF relocation handler and gp analyzer) into lib/Alpha.jar so a Ghidra
# install that has this directory linked/copied under Ghidra/Processors/Alpha
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
OUT=$(mktemp -d "${TMPDIR:-/tmp}/alpha-jar.XXXXXX")
trap 'rm -rf "$OUT"' EXIT
"$JAVAC" -nowarn --release 21 -cp "$CP" -d "$OUT" $(find "$MOD/src/main/java" -name '*.java')
mkdir -p "$MOD/lib"
JAR=jar
[[ -n ${JAVA_HOME:-} ]] && JAR=$JAVA_HOME/bin/jar
"$JAR" cf "$MOD/lib/Alpha.jar" -C "$OUT" .
echo "built $MOD/lib/Alpha.jar"
