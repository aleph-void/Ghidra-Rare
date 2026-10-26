#!/usr/bin/env python3
"""Sum compare.py reports: summarize.py <file.cmp>..."""
import collections
import re
import sys

tot = collections.Counter()
reasons = collections.Counter()
unexp = collections.Counter()
for p in sys.argv[1:]:
    for line in open(p):
        m = re.match(r"\S+: (\d+) records: (.*)$", line)
        if m:
            tot["records"] += int(m.group(1))
            for part in m.group(2).split(", "):
                k, v = part.rsplit(" ", 1)
                tot[k] += int(v)
            continue
        m = re.match(r"\s+explained\s+(\d+)\s+(.*)$", line)
        if m:
            reasons[m.group(2)] += int(m.group(1))
            continue
        m = re.match(r"\s+UNEXPLAINED\s+(\d+)\s+(.*)$", line)
        if m:
            unexp[m.group(2)] += int(m.group(1))
print("TOTAL: " + ", ".join("%s %d" % kv for kv in sorted(tot.items())))
for k, v in sorted(reasons.items(), key=lambda x: -x[1]):
    print("  explained %8d  %s" % (v, k))
for k, v in sorted(unexp.items(), key=lambda x: -x[1]):
    print("  UNEXPLAINED %6d  %s" % (v, k))
