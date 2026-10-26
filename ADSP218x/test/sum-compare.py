#!/usr/bin/env python3
"""Sum the per-slice compare.py reports: sum-compare.py <report>..."""
import collections
import re
import sys

tot = collections.Counter()
buckets = collections.Counter()
for f in sys.argv[1:]:
    for line in open(f):
        m = re.match(r"== \S+: (\d+) words, (\d+) agree, (\d+) both invalid, (\d+) differ", line)
        if m:
            for k, v in zip(("words", "agree", "both invalid", "differ"), m.groups()):
                tot[k] += int(v)
            continue
        m = re.match(r"\s+(\d+)  (\S.*)$", line)
        if m:
            buckets[m.group(2)] += int(m.group(1))
print(f"== total: {tot['words']} words, {tot['agree']} agree, {tot['both invalid']} both invalid, "
      f"{tot['differ']} differ")
unexpl = 0
for b, n in buckets.most_common():
    print(f"  {n:9d}  {b}")
    if b.startswith("UNEXPLAINED"):
        unexpl += n
print(f"  unexplained: {unexpl}")
