#!/usr/bin/env python3
"""Compare Ghidra's ADSP-218x decode with MAME unidasm -arch adsp21xx, word by word.

  compare.py [--show N] [--dump-bucket NAME] <mame.txt[.gz]> <ghidra.txt[.gz]> [label]

mame.txt:   unidasm output for 32-bit little-endian words ("addr: wwwwwwww  text"); only the
            low 24 bits are the instruction.
ghidra.txt: test/ghidra-corpus.sh output ("wwwwww text", "BAD" when undecodable).

Both texts are normalised (numbers to decimal, spacing removed, multifunction clauses and
ENA/DIS/POP/PUSH lists sorted, manual syntax vs MAME syntax: PASS, MR transfer, "+ 0 + C").
Each remaining difference is put in a bucket by explain(); a bucket is either a documented
reason (manual-reserved encoding MAME decodes, confirmed MAME bug, MAME omission) or
UNEXPLAINED.  Exit status 1 if any difference is unexplained.
"""
import collections
import gzip
import re
import sys


def opener(p):
    return gzip.open(p, "rt") if p.endswith(".gz") else open(p)


NUM_MAME = re.compile(r"\$([0-9A-F]+)")
NUM_GH = re.compile(r"(?<![A-Za-z0-9_])(-?)0x([0-9a-fA-F]+)")


def clauses(t):
    out, depth, cur = [], 0, ""
    for ch in t:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [c.strip() for c in out if c.strip()]


def pairs_sorted(c):
    w = c.split()
    if w and w[0] in ("ENA", "DIS", "POP", "PUSH") and len(w) % 2 == 0:
        return " ".join(sorted(" ".join(w[i:i + 2]) for i in range(0, len(w), 2)))
    return c


def finish(cl):
    cl = [pairs_sorted(c) for c in cl]
    cl = [re.sub(r"\s+", "", c) for c in cl]
    return ";".join(sorted(cl))


def norm_mame(t):
    t = t.strip()
    if t.startswith("???") or t == "":
        return None
    t = t.replace("PUSH STAT", "PUSH STS").replace("POP STAT", "POP STS")
    # PASS constant through Y + 1 / Y - 1: "$0001 + 1"
    t = re.sub(r"= \$([0-9A-F]+) ([+-]) 1$",
               lambda m: "= $%04X" % ((int(m.group(1), 16) + (1 if m.group(2) == "+" else -1)) & 0xffff), t)
    t = re.sub(r"= \$([0-9A-F]+) ([+-]) 1,",
               lambda m: "= $%04X," % ((int(m.group(1), 16) + (1 if m.group(2) == "+" else -1)) & 0xffff), t)
    t = re.sub(r"MR \+ \w+ \* 0 \(SS\)", "MR", t)
    t = re.sub(r"MR \+ \w+ \* 0 \(RND\)", "MR (RND)", t)
    t = t.replace(" + 0 + C", " + C")
    t = NUM_MAME.sub(lambda m: str(int(m.group(1), 16)), t)
    return finish(clauses(t))


def norm_ghidra(t):
    t = t.strip()
    if t == "BAD":
        return None
    t = t.upper().replace("0X", "0x")
    t = re.sub(r"\bPASS ", "", t)
    t = NUM_GH.sub(lambda m: str((-1 if m.group(1) else 1) * int(m.group(2), 16)), t)
    return finish(clauses(t))


def explain(w, mt, gt, mn, gn):
    """Return the bucket name for a difference (see the module README for each reason)."""
    top = w >> 16
    if mn is not None and gn is None:
        # MAME decodes, Ghidra rejects: manual-reserved encodings
        if top == 0x00:
            return "reserved: NOP with nonzero low bits"
        if mt.startswith("DIVS AY0") or mt.startswith("DIVS 0"):
            return "reserved: DIVS with AY0 or 0 as yop (manual: AY1 or AF)"
        if top == 0x0c and (w & 3):
            return "reserved: mode control bits 1-0 nonzero"
        if top == 0x02 and (w >> 12) & 0xf == 0 and (w & 0xff0) == 0:
            return "reserved: modify flag out with no flag operation"
        if top == 0x02:
            return "reserved: type 28/31 fixed bits"
        if 0x20 <= top <= 0x27:
            b74 = (w >> 4) & 0xf
            amf = (w >> 13) & 0x1f
            if amf >= 16 and b74 and not (b74 & 1):
                return "reserved: type 9 ALU bits 7-4 with BO=00/10"
            if amf >= 16:
                return "reserved: type 9 constant with NOT/negate/ABS"
            if amf == 0:
                return "reserved: type 9 AMF=00000"
            if b74 == 1:
                return "reserved: type 9 xop*xop outside SS/UU/RND or with yop!=0"
            return "reserved: type 9 MAC bits 7-4 not 0000/0001"
        if top in (0x0e,) and (w >> 4) & 0xf:
            return "reserved: type 16 bits 7-4 nonzero"
        if top == 0x0b:
            return "reserved: type 19 bit 5 or bits 15-8"
        if top in (0x0a, 0x09, 0x05, 0x04, 0x06, 0x07):
            return "reserved: fixed bits of types 20/21/23-26 nonzero"
        if "??" in mt:
            return "reserved: register code MAME prints as ??"
        if re.match(r"^(SSTAT) =|= (IFC|OWRCNTR)\b|^DM\(\$[0-9A-F]+\) = (IFC|OWRCNTR)$|, (IFC|OWRCNTR) =", mt) \
                or re.search(r"\b(SSTAT) = ", mt) or re.search(r"= (IFC|OWRCNTR)$", mt):
            return "reserved: write to read-only / read of write-only register"
        if (w >> 15) == 0x1f or (w >> 15) == 0x1d or (w >> 15) == 0x21:
            return "reserved: unassigned shifter type codes"
        return "UNEXPLAINED (MAME decodes, Ghidra rejects)"
    if mn is None and gn is not None:
        if top == 0x02 and (w >> 15) & 1:
            return "MAME omission: IDLE / IDLE (n) printed as an empty string"
        if w in (0x040020, 0x040060):
            return "MAME omission: ENA/DIS INTS"
        if "TOPPCSTACK" in gt:
            return "MAME omission: TOPPCSTACK"
        if top == 0x0c:
            return "MAME omission: mode control with no mode change prints empty"
        return "UNEXPLAINED (Ghidra decodes, MAME rejects)"
    # both decode, different text
    amf = (w >> 13) & 0x1f
    if 0x20 <= top <= 0x27 and amf >= 16 and (w >> 4) & 1 and (w >> 11) & 3 == 3:
        return "MAME bug: type 9 constants with YY=11 (bits 12-15) decoded as Y = 0"
    if amf == 0x0d and "(SS)" in mt and "(SU)" in gt and re.search(r"M[RF] = MR - ", gt):
        return "MAME bug: AMF 01101 (MR - xop*yop, SU) printed as (SS)"
    if "??" in mt and "TOPPCSTACK" in gt:
        return "MAME omission: TOPPCSTACK (printed as ??)"
    return "UNEXPLAINED (texts differ)"


def main():
    args = sys.argv[1:]
    show = 10
    dump = None
    while args and args[0].startswith("--"):
        if args[0] == "--show":
            show = int(args[1])
            args = args[2:]
        elif args[0] == "--dump-bucket":
            dump = args[1]
            args = args[2:]
    mf, gf = args[0], args[1]
    label = args[2] if len(args) > 2 else gf
    stats = collections.Counter()
    buckets = collections.Counter()
    examples = collections.defaultdict(list)
    with opener(mf) as m, opener(gf) as g:
        for ml, gl in zip(m, g):
            mw, mt = ml.split(":", 1)[1].strip().split("  ", 1) if "  " in ml.split(":", 1)[1].strip() else (ml.split(":", 1)[1].strip(), "")
            w = int(mw, 16) & 0xffffff
            gw, gt = gl.rstrip("\n").split(" ", 1)
            if int(gw, 16) != w:
                sys.exit(f"misaligned: mame {w:06x} ghidra {gw}")
            mn, gn = norm_mame(mt), norm_ghidra(gt)
            if mn is None and gn is None:
                stats["both invalid"] += 1
            elif mn == gn:
                stats["agree"] += 1
            else:
                b = explain(w, mt, gt, mn, gn)
                buckets[b] += 1
                stats["differ"] += 1
                if len(examples[b]) < show:
                    examples[b].append(f"{w:06x}  mame: {mt.strip()!r}  ghidra: {gt.strip()!r}")
                if dump and b.startswith(dump):
                    print(f"{w:06x}\t{mt.strip()}\t{gt.strip()}")
    if dump:
        return 0
    total = sum(stats.values())
    print(f"== {label}: {total} words, {stats['agree']} agree, {stats['both invalid']} both invalid, "
          f"{stats['differ']} differ")
    unexplained = 0
    for b, n in buckets.most_common():
        print(f"  {n:9d}  {b}")
        if b.startswith("UNEXPLAINED"):
            unexplained += n
            for e in examples[b]:
                print("              " + e)
    print(f"  unexplained: {unexplained}")
    return 1 if unexplained else 0


if __name__ == "__main__":
    sys.exit(main())
