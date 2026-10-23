#!/usr/bin/env bash
# Fetch XS3 ground truth into <dir>: vendor (xcc)-built objects from the xmos-ai-tools wheel
# (runtime/lib/libxtflitemicro.a) and the matching assembly sources (lib_nn, lib_tflite_micro).
#   test/fetch_xmos.sh <dir>      -> <dir>/objs/*.obj, <dir>/srcs/{lib_nn,lib_tflite_micro}
set -euo pipefail
D=$(mkdir -p "$1" && cd "$1" && pwd)
mkdir -p "$D/objs" "$D/srcs" "$D/whl"
if [[ -z $(ls "$D/objs") ]]; then
	(cd "$D/whl" && pip download -q --no-deps xmos-ai-tools==1.4.2 &&
		unzip -q -o ./*.whl 'xmos_ai_tools/runtime/lib/libxtflitemicro.a')
	(cd "$D/objs" && ar x "$D/whl/xmos_ai_tools/runtime/lib/libxtflitemicro.a")
	rm -rf "$D/whl"
fi
for r in lib_nn lib_tflite_micro; do
	[[ -d $D/srcs/$r ]] || git clone -q --depth 1 "https://github.com/xmos/$r.git" "$D/srcs/$r"
done
echo "objects: $(ls "$D/objs" | wc -l) in $D/objs"
