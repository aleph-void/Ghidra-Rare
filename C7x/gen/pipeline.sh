#!/usr/bin/env bash
# Rebuild the encoding database for one silicon version from dis7x and regenerate its SLEIGH.
#   gen/pipeline.sh WORKDIR [SIL] [NSAMPLES]
# Needs TI C7000 CGT (asm7x/dis7x); set C7X_CGT to its install dir if not at the default path.
# Outputs data/languages/c7x_{gen,fields,regs,ops}_SIL.sinc
set -euo pipefail
W=$1; SIL=${2:-7100}; N=${3:-10000000}
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$W"
cd "$HERE"
[[ -s $W/samp$SIL.json ]] || python3 sample.py $SIL $N $W/samp$SIL.json
[[ -f $W/extra$SIL.json ]] && EXTRA=$W/extra$SIL.json || EXTRA=
python3 infer.py $SIL $W/samp$SIL.json $W/inf$SIL.json $EXTRA
python3 refine.py $SIL $W/inf$SIL.json $W/ref$SIL.json 2>$W/refine$SIL.log
rm -f $W/inf$SIL.json
python3 probe_ext.py $SIL $W/ref$SIL.json $W/ext$SIL.json
python3 anaext.py $W/ext$SIL.json $W/ref$SIL.json >/dev/null
rm -f $W/ext$SIL.json
python3 gen.py $W/ref$SIL.json $W/ext_rules$SIL.json ../data/languages $SIL
