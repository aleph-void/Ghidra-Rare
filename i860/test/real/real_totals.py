#!/usr/bin/env python3
"""Totals over the real-code check outputs (*.check from real-check.sh)."""
import re
import sys

tot = dict(files=0, functions=0, instructions=0, ok=0, failed=0, timeouts=0, bad=0, objdump=0,
           mame=0, unexpl=0, bookmarks_other=0, dwarf_bm=0)
rows = []
for path in sys.argv[1:]:
    t = open(path).read()
    name = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    tot["files"] += 1
    f = int(re.search(r"^functions: (\d+)", t, re.M).group(1))
    i = int(re.search(r"^instructions: (\d+)$", t, re.M).group(1))
    d = re.search(r"decompile: (\d+) ok, (\d+) failed, (\d+) timeouts", t)
    bm = re.search(r"^bookmarks: \{(.*)\}", t, re.M).group(1)
    bad = sum(int(n) for k, n in re.findall(r"([\w/ -]+)=(\d+)", bm) if "Bad Instruction" in k)
    dwarf = sum(int(n) for k, n in re.findall(r"([\w/ -]+)=(\d+)", bm) if k.strip() == "Error/DWARF")
    other = sum(int(n) for k, n in re.findall(r"([\w/ -]+)=(\d+)", bm)) - bad - dwarf
    c = re.search(r"identical to objdump: (\d+); identical to MAME: (\d+) \(\+(\d+) explained.*unexplained: objdump (\d+), MAME (\d+)", t)
    tot["functions"] += f
    tot["instructions"] += i
    tot["ok"] += int(d.group(1)); tot["failed"] += int(d.group(2)); tot["timeouts"] += int(d.group(3))
    tot["bad"] += bad; tot["dwarf_bm"] += dwarf; tot["bookmarks_other"] += other
    if c:
        tot["objdump"] += int(c.group(1)); tot["mame"] += int(c.group(2)) + int(c.group(3))
        tot["unexpl"] += int(c.group(4)) + int(c.group(5))
    rows.append(f"  {name:22s} functions {f:4d}  instructions {i:6d}  decompile {d.group(1)}/{f}"
                f"  bad {bad}  other bookmarks {other}  objdump {c.group(1) if c else '-'}")
print("\n".join(rows))
print(f"total: {tot['files']} files, {tot['functions']} functions, {tot['instructions']} "
      f"instructions; {tot['objdump']} identical to objdump, {tot['mame']} agree with MAME "
      f"(incl. explained), {tot['unexpl']} unexplained; decompile {tot['ok']} ok, "
      f"{tot['failed']} failed, {tot['timeouts']} timeouts; bad-instruction bookmarks {tot['bad']}, "
      f"DWARF line bookmarks {tot['dwarf_bm']}, other error/warning bookmarks {tot['bookmarks_other']}")
sys.exit(1 if tot["failed"] or tot["timeouts"] or tot["bad"] or tot["unexpl"] else 0)
