#!/usr/bin/env python3
"""Sum the real-check.sh reports: summary.py <report.txt>..."""
import collections
import re
import sys

t = collections.Counter()
mame = collections.Counter()
diffs = []
for p in sys.argv[1:]:
    for line in open(p, errors="replace"):
        m = re.match(r"(\S+): functions (\d+), instructions (\d+), bad-instruction bookmarks (\d+), "
                     r"error bookmarks (\d+) decompile: (\d+) ok, (\d+) failed, (\d+) timed out", line)
        if m:
            t["programs"] += 1
            for k, g in zip(("functions", "instructions", "bad", "errors", "dec ok", "dec failed", "dec timeout"),
                            m.groups()[1:]):
                t[k] += int(g)
            continue
        m = re.match(r"\S+: (\d+) code statements: (\d+) identical, (\d+) different, (\d+) skipped", line)
        if m:
            t["listings"] += 1
            for k, g in zip(("statements", "identical", "different", "skipped"), m.groups()):
                t[k] += int(g)
            continue
        m = re.match(r"\s+auto-analysis reached (\d+)/(\d+) statements", line)
        if m:
            t["reached"] += int(m.group(1))
            continue
        m = re.match(r"\s+MAME at \d+ listed addresses: (.*)$", line)
        if m:
            for k, v in re.findall(r"(agree|both invalid \(data words\)|unexplained|MAME out of step|explained: .*?) (\d+)(?=, (?:agree|both|unexplained|MAME|explained)|$)", m.group(1)):
                mame[k] += int(v)
            continue
        if "DIFF" in line or "ERROR" in line or "Exception" in line:
            diffs.append("%s: %s" % (p.split("/")[-1], line.rstrip()))
print("programs %(programs)d: %(functions)d functions, %(instructions)d instructions, %(bad)d bad-instruction "
      "bookmarks, %(errors)d error bookmarks; decompile %(dec ok)d ok, %(dec failed)d failed, "
      "%(dec timeout)d timed out" % t)
print("listings %(listings)d: %(statements)d code statements, %(identical)d identical, %(different)d different, "
      "%(skipped)d skipped; auto-analysis reached %(reached)d" % t)
print("MAME at the listed addresses: " + ", ".join("%s %d" % kv for kv in sorted(mame.items())))
for d in diffs[:60]:
    print("  " + d)
sys.exit(1 if t["different"] or mame["unexplained"] or any("Exception" in d for d in diffs) else 0)
