#!/usr/bin/env python3
"""Compare Ghidra and GNU objdump disassembly of an RX slot image.

    compare.py [--stride 16] [--lang v1|v2|v3] <objdump.txt> <ghidra.txt> [label]

objdump.txt: `objdump -D -b binary -m rx<:v2|:v3>` output; ghidra.txt: test/RXDumpDisasm.java
output. One test instruction starts every <stride> bytes. Texts are compared after
normalisation (case, spacing, numbers compared as 32-bit values). Every difference is put in a
bucket; buckets in explain.py are differences traced to the manual (oracle bugs, encodings the
manual reserves, instructions outside the language's ISA version). The exit status is 0 only if
every difference is explained.
"""
import argparse
import collections
import re
import sys

import explain

NUM = re.compile(r"(?<![a-z0-9_.])-?(0x[0-9a-f]+|[0-9]+)(?![0-9a-z_])")


def norm(s):
    s = s.lower().strip()
    if s in ("bad", "*unknown*") or "<invalid>" in s or s.startswith(".byte"):
        return "bad"
    if "<invalid" in s:
        return "bad"
    s = re.sub(r"^nop\s*;\s*", "", s)
    s = re.sub(r"\s+", " ", s)
    s = s.replace(", ", ",")
    s = re.sub(r"^(\S+) ", r"\1 ", s)

    def num(m):
        v = int(m.group(0), 0) & 0xffffffff
        return str(v)
    return NUM.sub(num, s)


def read_objdump(path):
    out = {}
    for line in open(path, errors="replace"):
        m = re.match(r"^\s*([0-9a-f]+):\t((?:[0-9a-f]{2} )+)\s*\t?(.*)$", line)
        if not m:
            continue
        a = int(m.group(1), 16)
        nbytes = len(m.group(2).split())
        out[a] = (m.group(3).strip(), nbytes, m.group(2).replace(" ", ""))
    return out


def read_ghidra(path):
    out = {}
    for line in open(path):
        p = line.rstrip("\n").split(" ", 2)
        if len(p) < 3:
            continue
        a = int(p[0], 16)
        out[a] = (p[2], len(p[1]) // 2, p[1])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stride", type=int, default=16)
    ap.add_argument("--lang", default="v3")
    ap.add_argument("--show", type=int, default=3)
    ap.add_argument("od")
    ap.add_argument("gh")
    ap.add_argument("label", nargs="?", default="")
    a = ap.parse_args()
    od, gh = read_objdump(a.od), read_ghidra(a.gh)
    stats = collections.Counter()
    buckets = collections.defaultdict(list)
    for addr in sorted(gh):
        if addr % a.stride:
            continue
        g_txt, g_len, g_hex = gh[addr]
        if addr not in od:
            stats["objdump missing"] += 1
            buckets["UNEXPLAINED objdump missing slot"].append((addr, g_hex, "", g_txt))
            continue
        o_txt, o_len, o_hex = od[addr]
        go, oo = norm(g_txt), norm(o_txt)
        if go == "bad" and oo == "bad":
            stats["both invalid"] += 1
            continue
        if go == oo and (go == "bad" or g_len == o_len):
            stats["agree"] += 1
            continue
        raw = bytes.fromhex(o_hex if o_len >= g_len else g_hex)
        # the slot's first 8 bytes are the test instruction
        why = explain.explain(raw, oo, go, o_len, g_len, a.lang)
        key = why if why else f"UNEXPLAINED {oo.split(' ')[0]} / {go.split(' ')[0]}"
        stats["explained" if why else "unexplained"] += 1
        buckets[key].append((addr, o_hex if o_len >= g_len else g_hex, o_txt, g_txt))
    total = sum(stats.values())
    print(f"== {a.label}: {total} slots: " + ", ".join(f"{k} {v}" for k, v in sorted(stats.items())))
    for k in sorted(buckets, key=lambda k: (not k.startswith("UNEXPLAINED"), -len(buckets[k]))):
        v = buckets[k]
        print(f"  {len(v):7d}  {k}")
        if k.startswith("UNEXPLAINED") or a.show > 3:
            for addr, hx, o, g in v[:a.show]:
                print(f"           {addr:08x} {hx:<18} objdump: {o:<36} ghidra: {g}")
    sys.exit(1 if stats["unexplained"] else 0)


if __name__ == "__main__":
    main()
