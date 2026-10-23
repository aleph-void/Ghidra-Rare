#!/usr/bin/env bash
# Download the public XMOS release binaries used by real-binaries.sh, plus the lib_xud sources
# from the same release (XMOS Public Licence v1; not committed to this repo). Only the needed zip members are fetched, via HTTP range reads.
#   test/fetch-real-samples.sh <dir>
set -euo pipefail
D=${1:?usage: fetch-real-samples.sh <dir>}
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$D"
get() {   # url member outfile
	[[ -s $D/$3 ]] && return
	echo "fetch $3"
	python3 -I "$HERE/rzip.py" "$1" "$2" "$D/$3"
}
U=https://github.com/xmos/sw_usb_audio/releases/download/v8.1.0/sw_usb_audio_8.1.0.zip
for b in 216 316; do   # xCORE-200 (XS2) and xcore.ai (XS3) multichannel USB audio reference designs
	get $U sw_usb_audio/app_usb_aud_xk_${b}_mc/bin/1AMi2o2xxxxxx/app_usb_aud_xk_${b}_mc_1AMi2o2xxxxxx.xe \
		app_usb_aud_xk_${b}_mc_1AMi2o2xxxxxx.xe
done
get $U sw_usb_audio/LICENSE.rst LICENSE-sw_usb_audio.rst
# lib_xud assembly sources (+ headers) from the same release, for linked_srccheck.py
[[ -d $D/lib_xud ]] || { echo "fetch lib_xud sources"; python3 -I "$HERE/rzip.py" $U -x "$D" '^lib_xud/lib_xud/(src|api)/.*[.](S|h|inc)$'; }
U=https://github.com/xmos/sln_voice/releases/download/v0.20.0/sln_voice_example_apps.zip
get $U example_ffd.xe example_ffd.xe
get $U example_audio_mux.xe example_audio_mux.xe
U=https://github.com/xmos/sln_voice/releases/download/v0.10.0/application_ffd.zip
get $U application_ffd/application_ffd.xe application_ffd.xe
(cd "$D" && sha256sum -c - <<'SUMS')
fd38dab2dcc37314bea59cbc95f736e3ceee47dd46330160ad210997b59ac5ed  app_usb_aud_xk_216_mc_1AMi2o2xxxxxx.xe
78f90778176c5bca34043f0c7401cab5d6502f5238dbddd1e818f7f9f0b19b4d  app_usb_aud_xk_316_mc_1AMi2o2xxxxxx.xe
b38cd992dc8c47d89ae8953c092421c4a6b71509bb255d89c16886865621fff8  example_ffd.xe
908100a68c3eea0794a69902256957ada8ffbfa089ae2c9db16f393985a2fc6f  example_audio_mux.xe
1ddefdc0cb37f25cbe69820849b9e291a6b349b75009e0cf039585bfe8637e43  application_ffd.xe
SUMS
