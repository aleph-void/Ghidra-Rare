#!/usr/bin/env python3
"""Compare Ghidra slot disassembly with MAME unidasm output.

    compare.py [--stride N] [--arch dsp56000|dsp56156] [--explain rules.py] <mame.txt> <ghidra.txt> [label]

Both outputs are reduced to one record per slot (word address multiple of the stride). Texts
are normalized: lower case, whitespace collapsed, MAME's '$' and Ghidra's '0x' hex and decimal
numbers parsed to integers, the assembler force operators '<' '>' dropped (absolute short,
long and I/O short forms are distinguished by the encoding, not the text), and MAME's operand
spellings x1x0/y1y0 (X/Y) and x0_0 etc. (24-bit sources) mapped to Motorola syntax.

Records are bucketed: agree, both invalid, Ghidra-only, MAME-only, and differ. Differences
that tools/../test/explain_<arch>.py explains (confirmed MAME bugs, encodings the manual
reserves) are counted per reason; anything else is "unexplained" and makes the exit status 1.
"""
import collections
import importlib.util
import os
import re
import sys

NUM = re.compile(r"(?<![a-z0-9_.])(\$[0-9a-f]+|0x[0-9a-f]+|\d+)(?![a-z0-9_])")


def num(m):
    t = m.group(1)
    if t.startswith("$"):
        return str(int(t[1:], 16))
    if t.startswith("0x"):
        return str(int(t[2:], 16))
    return str(int(t))


def norm(t):
    t = t.lower().strip()
    if t.startswith("_"):
        t = t[1:]                       # Ghidra marks a delay-slot (REP) instruction with '_'

    t = t.replace("<", "").replace(">", "")
    t = re.sub(r"\bx1x0\b", "x", t)
    t = re.sub(r"\by1y0\b", "y", t)
    t = re.sub(r"\b(x0|x1|y0|y1)_0\b", r"\1", t)
    t = NUM.sub(num, t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s*,\s*", ",", t)
    return t


def load_mame(path, stride, wordchars):
    recs = {}
    for line in open(path, errors="replace"):
        m = re.match(r"\s*([0-9a-f]+):\s+((?:[0-9a-f]{%d}\s)+)\s*(.*)$" % wordchars, line.rstrip("\n") + " ")
        if not m:
            continue
        a = int(m.group(1), 16)
        if a % stride:
            continue
        words = m.group(2).split()
        recs[a] = (len(words), m.group(3).strip(), [int(w, 16) for w in words])
    return recs


def load_ghidra(path, stride):
    recs = {}
    for line in open(path, errors="replace"):
        parts = line.rstrip("\n").split(" ")
        a = int(parts[0], 16)
        if a % stride:
            continue
        words = []
        i = 1
        while i < len(parts) and re.fullmatch(r"[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8}", parts[i] or "x"):
            words.append(int(parts[i], 16))
            i += 1
        recs[a] = (len(words), " ".join(parts[i:]).strip(), words)
    return recs


def mame_invalid(t):
    if t == "" or t.startswith("dc ") or "reserved" in t or "?" in t or t.startswith("*") or " * " in t:
        return True
    first = t.split()[0]
    return any(c in first for c in ":,(#")      # no mnemonic: MAME's reserved data ALU op


def main():
    args = sys.argv[1:]
    stride, arch, explain = 2, "dsp56000", None
    while args and args[0].startswith("--"):
        if args[0] == "--stride":
            stride = int(args[1])
        elif args[0] == "--arch":
            arch = args[1]
        elif args[0] == "--explain":
            explain = args[1]
        args = args[2:]
    mpath, gpath = args[0], args[1]
    label = args[2] if len(args) > 2 else os.path.basename(gpath)
    if explain is None:
        explain = os.path.join(os.path.dirname(os.path.abspath(__file__)), "explain_%s.py" % arch)
    rules = None
    if os.path.exists(explain):
        spec = importlib.util.spec_from_file_location("explain", explain)
        rules = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rules)
    wordchars = 8 if arch == "dsp56000" else 4
    mame = load_mame(mpath, stride, wordchars)
    gh = load_ghidra(gpath, stride)
    counts = collections.Counter()
    reasons = collections.Counter()
    unexplained = collections.defaultdict(list)
    for a in sorted(gh):
        if a not in mame:
            continue
        mn, mt, mw = mame[a]
        gn, gt, gw = gh[a]
        word = gw[0] if gw else mw[0] & 0xffffff
        ext = gw[1] if len(gw) > 1 else (mw[1] if len(mw) > 1 else None)
        if rules is not None and hasattr(rules, "mame_raw"):
            mt = rules.mame_raw(mt, a, mw)     # arch-specific raw-text fixes (DSP56156: *+$n)
        mi = mame_invalid(mt)
        gi = gt == "BAD"
        nm, ng = norm(mt), norm(gt)
        if rules is not None and hasattr(rules, "mame_fix"):
            nm = rules.mame_fix(nm, word)
        if mi and gi:
            counts["both invalid"] += 1
            continue
        if not mi and not gi and nm == ng and mn == gn:
            counts["agree"] += 1
            continue
        why = rules.explain(word, nm, ng, mi, gi, mn, gn, ext) if rules is not None else None
        if why:
            counts["explained"] += 1
            reasons[why] += 1
            continue
        if gi:
            key = "ghidra invalid: " + (nm.split(" ")[0] if nm else "?")
        elif mi:
            key = "mame invalid: " + ng.split(" ")[0]
        else:
            key = "differ: %s / %s" % (nm.split(" ")[0], ng.split(" ")[0])
        counts["unexplained"] += 1
        unexplained[key].append("%06x | %s | %s | words %d/%d" % (word, mt, gt, mn, gn))
    total = sum(counts.values())
    print("%s: %d records: %s" % (label, total, ", ".join("%s %d" % kv for kv in sorted(counts.items()))))
    for r, c in sorted(reasons.items(), key=lambda x: -x[1]):
        print("    explained %6d  %s" % (c, r))
    for k, v in sorted(unexplained.items(), key=lambda x: -len(x[1])):
        print("  UNEXPLAINED %6d  %s" % (len(v), k))
        for s in v[:4]:
            print("        " + s)
    sys.exit(1 if counts["unexplained"] else 0)


if __name__ == "__main__":
    main()
