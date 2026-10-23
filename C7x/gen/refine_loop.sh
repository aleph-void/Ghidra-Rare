#!/usr/bin/env bash
# Iteratively add Ghidra-vs-dis7x fuzz mismatches as extra samples and rebuild.
#   gen/refine_loop.sh WORKDIR SIL ROUNDS
set -euo pipefail
W=$1; SIL=$2; R=${3:-3}
HERE=$(cd "$(dirname "$0")" && pwd)
SL=$GHIDRA_INSTALL_DIR/support/sleigh
for i in $(seq 1 $R); do
  python3 $HERE/../test/compare.py fuzz $SIL 200000 $((1000+i)) $W/loop$i | head -2
  python3 - "$W/loop$i/mismatches.txt" "$W/extra$SIL.json" <<'PY'
import sys, json, os
f, ex = sys.argv[1], sys.argv[2]
words = set(json.load(open(ex))) if os.path.exists(ex) else set()
for l in open(f):
    p = l.split()
    if len(p) > 2 and p[2] == 'dis7x:': words.add(int(p[1], 16))
json.dump(sorted(words), open(ex, 'w')); print('extra samples', len(words))
PY
  rm -rf $W/loop$i
  $HERE/pipeline.sh $W $SIL 2>&1 | tail -1
  (cd $HERE/../data/languages && $SL c$SIL.slaspec 2>&1 | grep -E "ERROR|rror" | head -5 || true)
done
