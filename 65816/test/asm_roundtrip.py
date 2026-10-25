#!/usr/bin/env python3
"""Assembler round trip: re-assemble Ghidra's 65816 disassembly with ca65 (cc65) and check
that it reproduces the original bytes.

  asm_roundtrip.py <ghidra.txt> <MF> <XF> <ca65> <workdir> [--label L]

Each record of the Ghidra dump ("<addr> <bytes> <text>") is rewritten in ca65 syntax with
explicit address sizes (z: a: f:) and assembled at its own address with .a8/.a16 and
.i8/.i16 set from MF/XF. A record passes when ca65 emits exactly Ghidra's instruction bytes.
"""
import argparse
import collections
import os
import re
import subprocess

ap = argparse.ArgumentParser()
ap.add_argument("ghidra")
ap.add_argument("mf", type=int)
ap.add_argument("xf", type=int)
ap.add_argument("ca65")
ap.add_argument("work")
ap.add_argument("--label", default="")
a = ap.parse_args()


def h(m):
    return "$%x" % int(m.group(1), 16)


def to_ca65(addr, text):
    t = text.strip()
    mn, _, ops = t.partition(" ")
    mn = mn.lower()
    ops = ops.strip()
    if mn in ("brk", "cop", "wdm"):
        return "%s %s" % (mn, re.sub(r"\$0x([0-9a-f]+)", h, ops)) if mn != "brk" else \
            "brk #%s" % re.sub(r"\$0x([0-9a-f]+)", h, ops)
    if mn in ("mvn", "mvp"):
        s, d = [int(x, 16) for x in ops.split(",")]
        return "%s #$%x,#$%x" % (mn, s, d)
    if mn in ("jmp", "jsr") and ops.startswith("!$0x"):       # absolute: same bank
        return "%s a:$%x" % (mn, int(ops[4:], 16) & 0xffff)
    if mn in ("bpl", "bmi", "bvc", "bvs", "bcc", "bcs", "bne", "beq", "bra", "brl", "per"):
        # targets wrap within the bank; give ca65 the unwrapped value it range-checks
        tgt = int(ops.lstrip("$"), 16)
        nxt = addr + (2 if mn not in ("brl", "per") else 3)
        lim = 0x80 if mn not in ("brl", "per") else 0x8000
        for adj in (0, 0x10000, -0x10000):
            if -lim <= tgt + adj - nxt < lim:
                tgt += adj
                break
        return "%s $%x" % (mn, tgt)
    ops = ops.replace("!>$0x", "f:$0x").replace("!$0x", "a:$0x").replace("<$0x", "z:$0x")
    ops = re.sub(r"\$0x([0-9a-f]+)", h, ops)
    ops = re.sub(r"#\$?0x([0-9a-f]+)", lambda m: "#$%x" % int(m.group(1), 16), ops)
    # ca65 takes no size prefix inside indirect brackets/parentheses
    ops = re.sub(r"([\(\[])[zaf]:", r"\1", ops)
    if mn == "pei":
        ops = ops.replace("z:", "")
    ops = ops.replace(",X", ",x").replace(",Y", ",y").replace(",S", ",s")
    if ops == "A":
        ops = "a"
    return (mn + " " + ops).strip()


recs = []
for line in open(a.ghidra):
    p = line.rstrip("\n").split(" ", 2)
    if len(p) == 3 and re.fullmatch(r"[0-9a-f]{6}", p[0]) and not p[2].startswith("BAD"):
        recs.append((int(p[0], 16), p[1], p[2]))

os.makedirs(a.work, exist_ok=True)
src = os.path.join(a.work, "rt.s")
with open(src, "w") as f:
    f.write(".p816\n.smart -\n%s\n%s\n" % (".a8" if a.mf else ".a16", ".i8" if a.xf else ".i16"))
    for addr, b, t in recs:
        f.write(".org $%x\n%s\n" % (addr, to_ca65(addr, t)))
lst = os.path.join(a.work, "rt.lst")
r = subprocess.run([a.ca65, "-l", lst, "-o", os.path.join(a.work, "rt.o"), src],
                   capture_output=True, text=True)
errs = collections.Counter()
for l in r.stderr.splitlines():
    m = re.match(r".*rt\.s:(\d+): Error: (.*)", l)
    if m:
        errs[m.group(2)] += 1
got = {}
for l in open(lst, errors="replace") if os.path.exists(lst) else []:
    m = re.match(r"([0-9A-F]{6})  \d+  ((?:[0-9A-Fr]{2} )+)\s+(\S.*)$", l)
    if m and not m.group(3).startswith("."):
        got[int(m.group(1), 16)] = m.group(2).replace(" ", "").lower()
ok = 0
bad = collections.defaultdict(list)
for addr, b, t in recs:
    g = got.get(addr)
    if g == b:
        ok += 1
    else:
        bad[b[:2]].append((addr, b, t, to_ca65(addr, t), g))
print(f"{a.label}: {len(recs)} records, ca65 reproduces {ok} ({100*ok/max(len(recs),1):.2f}%)")
for e, c in errs.most_common(5):
    print(f"  ca65 error x{c}: {e}")
for op, v in sorted(bad.items(), key=lambda kv: -len(kv[1]))[:20]:
    addr, b, t, s, g = v[0]
    print(f"  op={op} {len(v)}: {addr:06x} {b} {t!r} -> {s!r} -> {g}")
