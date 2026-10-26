#!/usr/bin/env python3
"""MAME decode at the listing addresses of a DSP56000 LOD file:
    real_mame.py <prog.lod> <addrs.txt> <ghidra-guided.txt> <outdir>
Builds the P memory image in MAME's format (4 bytes per word), runs unidasm -arch dsp56000
and compares each listed address with Ghidra's decode, through compare.py's normalization
and the explain_dsp56000.py rules (confirmed MAME bugs). Exit 1 on unexplained differences."""
import collections
import importlib.util
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, "..", name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


cmp = load("compare")
ex = load("explain_dsp56000")
lod, addrs, guided, out = sys.argv[1:5]
mem = {}
space, addr = None, 0
for line in open(lod, errors="replace"):
    f = line.split()
    if not f:
        continue
    if f[0].startswith("_"):
        space = f[1].upper() if f[0] == "_DATA" else None
        if f[0] == "_DATA":
            addr = int(f[2], 16)
        continue
    if space == "P":
        for w in f:
            mem[addr] = int(w, 16)
            addr += 1
top = max(mem) + 2 if mem else 0
img = os.path.join(out, "p.m.bin")
with open(img, "wb") as g:
    for a in range(top):
        g.write(struct.pack(">I", mem.get(a, 0)))
txt = subprocess.run(["unidasm", img, "-arch", "dsp56000"], capture_output=True, text=True).stdout
open(os.path.join(out, "p.mame"), "w").write(txt)
mame = cmp.load_mame(os.path.join(out, "p.mame"), 1, 8)
gh = cmp.load_ghidra(guided, 1)
c = collections.Counter()
unexp = []
for a in sorted(gh):
    if a not in mame:
        c["MAME out of step"] += 1
        if os.environ.get("LST_DEBUG"):
            print("    STEP %04x %s" % (a, gh[a]))
        continue
    mn, mt, mw = mame[a]
    gn, gt, gw = gh[a]
    w = gw[0] if gw else mem.get(a, 0)
    ext = gw[1] if len(gw) > 1 else None
    nm, ng = ex.mame_fix(cmp.norm(mt), w), cmp.norm(gt)
    mi, gi = cmp.mame_invalid(mt), gt == "BAD"
    if not mi and not gi and nm == ng and mn == gn:
        c["agree"] += 1
        continue
    if mi and gi:
        c["both invalid (data words)"] += 1
        continue
    why = ex.explain(w, nm, ng, mi, gi, mn, gn, ext)
    if why:
        c["explained: " + why] += 1
    else:
        c["unexplained"] += 1
        unexp.append("%04x %06x | %s | %s" % (a, w, mt, gt))
print("    MAME at %d listed addresses: %s" % (sum(c.values()), ", ".join("%s %d" % kv for kv in sorted(c.items()))))
for u in unexp[:20]:
    print("    MAME DIFF " + u)
sys.exit(1 if unexp else 0)
