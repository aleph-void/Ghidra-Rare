#!/usr/bin/env bash
# Download the real-world validation cubins (bitsandbytes 0.50.2, MIT) into
# test/samples (git-ignored).  See fetch-real-samples.py for details.
set -euo pipefail
exec python3 "$(dirname "$0")/fetch-real-samples.py" "$@"
