#!/usr/bin/env python3
"""Fetch a subset of SingleStepTests/65816 (MIT, github.com/SingleStepTests/65816) at a pinned
commit: the first N tests of every opcode in emulation (.e) and native (.n) mode.

  fetch-singlestep.py <out.json> [N]

Each upstream file (~6 MB, 10,000 tests) is downloaded, reduced and discarded. The output is
one JSON list of {"name", "initial", "final"} records (cycle lists dropped).
"""
import json
import sys
import urllib.request

COMMIT = "307c63f5673c8c6b861c52f71ddb89212a227480"
URL = "https://raw.githubusercontent.com/SingleStepTests/65816/%s/v1/%02x.%s.json"
out, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 50
tests = []
for op in range(256):
    for mode in ("e", "n"):
        with urllib.request.urlopen(URL % (COMMIT, op, mode)) as r:
            data = json.load(r)
        for t in data[:n]:
            tests.append({"name": t["name"], "initial": t["initial"], "final": t["final"]})
    print("%02x" % op, len(tests), file=sys.stderr, flush=True)
json.dump(tests, open(out, "w"))
